from __future__ import annotations

import asyncio
import io
import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from PIL import Image, ImageChops, ImageStat


SCORE_MIN = 0.0
SCORE_MAX = 5.0


@dataclass(frozen=True)
class JudgeImage:
    label: str
    data: bytes
    content_type: str


@dataclass(frozen=True)
class JudgeRequest:
    task_id: str
    brief: str
    category: str
    capability_id: str
    success_criteria: list[str]
    negative_constraints: list[str]
    deliverable_contract: dict[str, Any]
    dimension_criteria: dict[str, str]
    input_images: list[JudgeImage]
    output_images: list[JudgeImage]
    output_text_evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DimensionJudgment:
    score: float
    rationale: str
    evidence: list[str]
    confidence: float


@dataclass(frozen=True)
class JudgeResult:
    dimensions: dict[str, DimensionJudgment]
    fatal_issues: list[str]
    model: str
    judge_version: str = "judge-v2"
    independent: bool = True
    mock: bool = False


class IndependentJudgeProtocol(Protocol):
    model_name: str

    async def evaluate(self, request: JudgeRequest) -> JudgeResult: ...


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Independent judge did not return a JSON object")
    return json.loads(cleaned[start : end + 1])


def _extract_text(response: Any) -> str:
    direct = getattr(response, "text", None)
    if direct:
        return str(direct)
    texts: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            value = getattr(part, "text", None)
            if value:
                texts.append(str(value))
    return "\n".join(texts).strip()


def _validate_payload(
    payload: dict[str, Any],
    required_dimensions: set[str],
    *,
    model: str,
) -> JudgeResult:
    dimensions: dict[str, DimensionJudgment] = {}
    for item in payload.get("dimensions") or []:
        name = str(item.get("name") or "")
        if name not in required_dimensions or name in dimensions:
            continue
        dimensions[name] = DimensionJudgment(
            score=_clamp(float(item.get("score", 0.0)), SCORE_MIN, SCORE_MAX),
            rationale=str(item.get("rationale") or "")[:2_000],
            evidence=[str(value)[:500] for value in (item.get("evidence") or [])[:8]],
            confidence=_clamp(float(item.get("confidence", 0.5)), 0.0, 1.0),
        )
    missing = required_dimensions - set(dimensions)
    if missing:
        raise ValueError(f"Independent judge omitted dimensions: {', '.join(sorted(missing))}")
    return JudgeResult(
        dimensions=dimensions,
        fatal_issues=[str(value)[:1_000] for value in (payload.get("fatal_issues") or [])[:12]],
        model=model,
    )


class GeminiIndependentJudgeV2:
    """A benchmark judge that is separate from the runtime's own verifier.

    The judge receives only the agent-neutral task contract plus source/output
    artifacts. It never receives Curify routes, traces, support tiers, or the
    runtime's self-reported verdict.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model_name = model or os.getenv(
            "DESIGN_AGENT_BENCH_JUDGE_MODEL",
            os.getenv("CURIFY_EVAL_JUDGE_MODEL", "gemini-2.5-pro"),
        )
        self.api_key = (
            api_key
            or os.getenv("DESIGN_AGENT_BENCH_JUDGE_API_KEY")
            or os.getenv("CURIFY_EVAL_JUDGE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        if not self.api_key:
            raise RuntimeError(
                "Independent judge-v2 requires DESIGN_AGENT_BENCH_JUDGE_API_KEY or GEMINI_API_KEY"
            )

    @staticmethod
    def _image_part(types: Any, image: JudgeImage) -> Any:
        return types.Part(
            inline_data=types.Blob(data=image.data, mime_type=image.content_type)
        )

    def _evaluate_sync(self, request: JudgeRequest) -> JudgeResult:
        from google import genai
        from google.genai import types

        required = set(request.dimension_criteria)
        task_contract = {
            "task_id": request.task_id,
            "brief": request.brief,
            "category": request.category,
            "capability_id": request.capability_id,
            "success_criteria": request.success_criteria,
            "negative_constraints": request.negative_constraints,
            "deliverable_contract": request.deliverable_contract,
            "dimensions": request.dimension_criteria,
        }
        prompt = f"""
You are judge-v2 for an agent-neutral Design Agent Benchmark. You are independent
from the system that produced the artifacts. The system identity is intentionally
hidden. Evaluate only visible source/output evidence and the task contract below.

Never use or infer an internal route, model confidence, trace, self-reported
verdict, or implementation support tier. Do not reward abstention as design
quality. Do not compare against a single imagined gold image: open-ended designs
may have multiple valid solutions.

Score only the requested dimensions on a strict 0-5 scale:
0 = missing, unusable, or contradicts the task
1 = major failures dominate
2 = substantial correction required
3 = usable first draft with visible weaknesses
4 = strong professional result with minor issues
5 = exceptional and fully supported by visible evidence

TASK CONTRACT:
{json.dumps(task_contract, ensure_ascii=False, sort_keys=True)}

Text artifacts or manifest evidence, when present:
{json.dumps(request.output_text_evidence, ensure_ascii=False)}

Return only JSON with exactly one entry for every requested dimension:
{{
  "dimensions": [
    {{
      "name": "brief_adherence",
      "score": 0.0,
      "rationale": "concise reason tied to the criterion",
      "evidence": ["specific visible observation"],
      "confidence": 0.0
    }}
  ],
  "fatal_issues": []
}}
"""
        parts: list[Any] = [prompt]
        for image in request.input_images:
            parts.extend([f"SOURCE INPUT — {image.label}", self._image_part(types, image)])
        for image in request.output_images:
            parts.extend([f"AGENT OUTPUT — {image.label}", self._image_part(types, image)])

        client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=120_000),
        )
        response = client.models.generate_content(
            model=self.model_name,
            contents=parts,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
                temperature=0,
            ),
        )
        return _validate_payload(
            _parse_json_object(_extract_text(response)),
            required,
            model=self.model_name,
        )

    async def evaluate(self, request: JudgeRequest) -> JudgeResult:
        return await asyncio.to_thread(self._evaluate_sync, request)


def _decoded_images(images: list[JudgeImage]) -> list[Image.Image]:
    decoded: list[Image.Image] = []
    for item in images:
        try:
            decoded.append(Image.open(io.BytesIO(item.data)).convert("RGB"))
        except Exception:
            continue
    return decoded


def _normalized_difference(first: Image.Image, second: Image.Image) -> float:
    first = first.resize((64, 64))
    second = second.resize((64, 64))
    difference = ImageChops.difference(first, second)
    return _clamp(sum(ImageStat.Stat(difference).mean) / (3.0 * 255.0), 0.0, 1.0)


class DeterministicIndependentJudgeV2:
    """Offline judge used only to test benchmark plumbing, never visual quality."""

    model_name = "deterministic-independent-judge-v2"

    async def evaluate(self, request: JudgeRequest) -> JudgeResult:
        decoded = _decoded_images(request.output_images)
        readable = len(decoded) == len(request.output_images) and bool(decoded)
        large_enough = bool(decoded) and all(min(image.size) >= 900 for image in decoded)
        diversity = 0.0
        if len(decoded) >= 2:
            pairs = [
                _normalized_difference(decoded[index], decoded[other])
                for index in range(len(decoded))
                for other in range(index + 1, len(decoded))
            ]
            diversity = sum(pairs) / len(pairs)

        values = {
            "brief_adherence": 4.0 if readable else 0.0,
            "visual_quality": 4.0 if large_enough else (2.0 if readable else 0.0),
            "creative_diversity": min(5.0, 2.5 + diversity * 12.0),
            "brand_consistency": 3.5 if readable else 0.0,
            "refinement_ability": 3.5 if readable else 0.0,
            "cross_asset_consistency": 3.5 if readable else 0.0,
        }
        dimensions = {
            name: DimensionJudgment(
                score=values[name],
                rationale="Deterministic mock proxy; validates judge-v2 plumbing only.",
                evidence=[
                    f"decoded_outputs={len(decoded)}",
                    f"mean_pair_difference={diversity:.4f}",
                ],
                confidence=0.1,
            )
            for name in request.dimension_criteria
        }
        return JudgeResult(
            dimensions=dimensions,
            fatal_issues=[] if readable else ["No readable output image"],
            model=self.model_name,
            mock=True,
        )
