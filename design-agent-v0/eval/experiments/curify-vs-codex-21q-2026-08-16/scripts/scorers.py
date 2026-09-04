from __future__ import annotations

import io
import mimetypes
from pathlib import Path
from typing import Any

from braintrust import Score
from PIL import Image

from judge_v2 import (
    IndependentJudgeProtocol,
    JudgeImage,
    JudgeRequest,
)


FULL_STAGES = {"UNDERSTAND", "PLAN", "GENERATE", "VERIFY", "PRESENT"}
GEMINI_INLINE_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}


def _score(name: str, value: float | bool | None, **metadata: Any) -> Score:
    numeric = None if value is None else float(value)
    return Score(name=name, score=numeric, metadata=metadata)


def _attachment_bytes(value: Any) -> bytes:
    data = getattr(value, "data", None)
    if callable(data):
        data = data()
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, bytes):
        return data
    raise TypeError(f"Unsupported attachment type: {type(value).__name__}")


def _image_artifacts(
    output: dict[str, Any], *, include_evidence_only: bool = True
) -> list[dict[str, Any]]:
    return [
        item
        for item in output.get("artifacts", [])
        if str(item.get("content_type", "")).startswith("image/")
        and (include_evidence_only or not item.get("evidence_only"))
    ]


def _actual_stage_names(output: dict[str, Any]) -> set[str]:
    return {
        str(step.get("stage"))
        for step in output.get("trace", [])
        if step.get("status") in {"RUNNING", "COMPLETED", "FAILED"}
    }


def provider_failure(output: dict[str, Any]) -> bool:
    errors = " ".join(
        str(step.get("error") or "") for step in output.get("trace", [])
    ).lower()
    return any(
        marker in errors
        for marker in ("resource_exhausted", "monthly spending cap", "429")
    )


def _capability_matches(
    output: dict[str, Any], expected: dict[str, Any]
) -> bool | None:
    actual = output.get("capability_id") or output.get("task_type")
    if actual is None:
        return None
    return actual == expected["capability_id"]


def _reference_utilization(output: dict[str, Any], expected: dict[str, Any]) -> float:
    required = int(expected["input_contract"]["asset_count"])
    if required <= 0:
        return 1.0
    unique_loaded = len(set(output.get("loaded_asset_ids") or []))
    return min(1.0, unique_loaded / required)


def _artifact_contract(
    output: dict[str, Any], expected: dict[str, Any]
) -> tuple[float, dict[str, Any]]:
    contract = expected["deliverable_contract"]
    artifacts = [
        item for item in (output.get("artifacts") or []) if not item.get("evidence_only")
    ]
    image_count = len(_image_artifacts(output, include_evidence_only=False))
    minimum_artifacts = int(contract["minimum_artifacts"])
    minimum_images = int(contract["minimum_image_artifacts"])
    total_ok = len(artifacts) >= minimum_artifacts
    images_ok = image_count >= minimum_images
    return float(total_ok and images_ok), {
        "actual_artifacts": len(artifacts),
        "minimum_artifacts": minimum_artifacts,
        "actual_image_artifacts": image_count,
        "minimum_image_artifacts": minimum_images,
        "distinct_direction_requirement": contract.get("minimum_distinct_directions"),
        "note": "Semantic direction count is checked by judge-v2, not by file count.",
    }


def runtime_scores(
    input: dict[str, Any],
    output: dict[str, Any],
    expected: dict[str, Any],
    **_: Any,
) -> list[Score]:
    diagnostics = output.get("adapter_diagnostics") or {}
    support_tier = diagnostics.get("support_tier")
    expected_current_status = diagnostics.get("expected_current_status")
    status = output.get("status")
    current_contract = (
        status == expected_current_status if expected_current_status else None
    )
    capability_ok = _capability_matches(output, expected)
    artifact_contract, artifact_meta = _artifact_contract(output, expected)
    # Capability labels are an optional internal diagnostic. Cross-agent task
    # completion is determined by observable output contracts and judge-v2, so
    # agents that do not expose a normalized route are not penalized here.
    completed_target = status == "COMPLETED" and artifact_contract == 1.0
    required_stages = set(
        expected["evaluation_protocol"]["required_normalized_stages"]
    )
    stages = _actual_stage_names(output)
    stage_coverage = len(stages & required_stages) / len(required_stages)
    reference_utilization = _reference_utilization(output, expected)
    verdict_pass = bool((output.get("verdict") or {}).get("passed"))
    reference_gate = completed_target and reference_utilization == 1.0
    safe_abstention = (
        status == "ABSTAINED" and output.get("code") == "UNSUPPORTED_TASK"
        if support_tier == "unsupported_runtime"
        else None
    )
    provider_ok = not provider_failure(output)
    quality_evaluable = (
        status == "COMPLETED" and bool(_image_artifacts(output)) and provider_ok
    )
    return [
        _score(
            "current_behavior_contract",
            current_contract,
            source="agent adapter diagnostic; not a shared benchmark label",
            expected_status=expected_current_status,
            actual_status=status,
        ),
        _score(
            "target_capability_coverage",
            completed_target,
            target_capability=expected["capability_id"],
            actual_capability=output.get("capability_id") or output.get("task_type"),
        ),
        _score(
            "route_accuracy",
            capability_ok,
            diagnostic_only=True,
            comparable=capability_ok is not None,
            note=(
                "Internal routing is not used for cross-agent ranking; N/A when "
                "the product surface exposes no normalized route."
            ),
        ),
        _score(
            "safe_abstention",
            safe_abstention,
            applicable=support_tier == "unsupported_runtime",
            code=output.get("code"),
        ),
        _score(
            "target_stage_coverage",
            stage_coverage,
            seen=sorted(stages),
            required=sorted(required_stages),
        ),
        _score(
            "target_reference_utilization",
            reference_utilization,
            loaded=output.get("loaded_asset_ids") or [],
            expected_count=expected["input_contract"]["asset_count"],
        ),
        _score("artifact_contract", artifact_contract, **artifact_meta),
        _score(
            "runtime_verification_pass",
            verdict_pass,
            diagnostic_only=True,
            note="The runtime self-verifier is not used by independent judge-v2.",
        ),
        _score(
            "reference_fidelity_gate",
            reference_gate,
            reference_utilization=reference_utilization,
            artifact_contract=artifact_contract,
        ),
        _score("provider_availability", provider_ok),
        _score(
            "quality_evaluable",
            quality_evaluable,
            provider_failure=not provider_ok,
            output_images=len(_image_artifacts(output)),
        ),
    ]


def _production_readiness(
    output: dict[str, Any], expected: dict[str, Any]
) -> tuple[float | None, bool, dict[str, Any]]:
    artifacts = [
        item for item in (output.get("artifacts") or []) if not item.get("evidence_only")
    ]
    contract = expected["deliverable_contract"]
    minimum_images = int(contract["minimum_image_artifacts"])
    image_artifacts = _image_artifacts(output, include_evidence_only=False)
    readable = 0
    large_enough = 0
    dimensions: list[str] = []
    errors: list[str] = []
    for artifact in image_artifacts:
        try:
            data = _attachment_bytes(artifact["attachment"])
            image = Image.open(io.BytesIO(data))
            image.verify()
            image = Image.open(io.BytesIO(data))
            dimensions.append(f"{image.width}x{image.height}")
            readable += 1
            large_enough += int(min(image.size) >= 900)
        except Exception as exc:
            errors.append(type(exc).__name__)

    capability_id = expected["capability_id"]
    if capability_id == "factory_export":
        media_types = {str(item.get("content_type") or "").lower() for item in artifacts}
        production_file = bool(
            media_types
            & {
                "application/pdf",
                "application/zip",
                "image/svg+xml",
                "application/postscript",
            }
        )
        spec_file = bool(
            media_types
            & {
                "application/pdf",
                "application/json",
                "text/plain",
            }
        )
        value = 0.5 * float(production_file) + 0.5 * float(spec_file)
        hard_gate = bool(production_file and spec_file)
        return value, hard_gate, {
            "validator": "factory-package-v1",
            "media_types": sorted(media_types),
            "production_file": production_file,
            "production_spec": spec_file,
            "required_checks": contract.get("production_checks") or [],
            "note": "Physical dimensions, bleed, cutline, and color-space validators remain TODO.",
        }

    if minimum_images == 0:
        return None, True, {"validator": "not-applicable"}
    readable_ratio = min(1.0, readable / minimum_images)
    resolution_ratio = min(1.0, large_enough / minimum_images)
    value = 0.5 * readable_ratio + 0.5 * resolution_ratio
    hard_gate = readable >= minimum_images
    return value, hard_gate, {
        "validator": "rendered-asset-v2",
        "readable_images": readable,
        "minimum_images": minimum_images,
        "images_at_least_900px": large_enough,
        "dimensions": dimensions,
        "errors": errors,
        "note": "This is rendered-asset readiness, not factory-package readiness.",
    }


def _efficiency(output: dict[str, Any], expected: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    metrics = output.get("metrics") or {}
    latency = max(0.0, float(metrics.get("latency_ms", 0.0)))
    latency_budget = max(1.0, float(expected["budgets"]["wall_time_ms"]))
    latency_score = min(1.0, latency_budget / max(latency, 1.0))
    max_iterations = max(0, int(expected["budgets"]["max_iterations"]))
    iterations = max(0, int(output.get("iterations") or 0))
    iteration_score = float(iterations <= max_iterations)
    cost_usd = metrics.get("cost_usd")
    value = 0.8 * latency_score + 0.2 * iteration_score
    return value, {
        "latency_ms": latency,
        "latency_budget_ms": latency_budget,
        "iterations": iterations,
        "max_iterations": max_iterations,
        "cost_usd": cost_usd,
        "estimated_credits_diagnostic": metrics.get("estimated_credits"),
        "model_calls": metrics.get("model_calls"),
        "tool_calls": metrics.get("tool_calls"),
        "note": "Cost is recorded but not scored until adapters report normalized USD cost.",
    }


# Repo root, for assets published as repo-relative paths.
_REPO_ROOT = Path(__file__).resolve().parents[5]


def _asset_image(asset: dict[str, Any]) -> tuple[bytes, str]:
    """Bytes + mime for one dataset asset.

    Two shapes exist. In-run, assets carry a Braintrust Attachment under
    "image". After publication they carry a repo-relative "path" instead — the
    export rewrites them, as the experiment README notes. Reading only the first
    shape is why every case failed with KeyError: 'image' on a fresh clone.
    """
    if asset.get("image") is not None:
        img = asset["image"]
        return _attachment_bytes(img), getattr(img, "content_type", None) or "image/png"

    rel = asset.get("path")
    if not rel:
        raise KeyError(
            f"asset {asset.get('asset_id')!r} has neither 'image' nor 'path'"
        )
    candidate = Path(rel)
    if not candidate.is_absolute():
        candidate = _REPO_ROOT / rel
    data = candidate.read_bytes()
    mime = mimetypes.guess_type(candidate.name)[0] or "image/png"
    return data, mime


def _judge_images_from_input(input: dict[str, Any]) -> list[JudgeImage]:
    images: list[JudgeImage] = []
    for asset in input.get("assets") or []:
        data, mime = _asset_image(asset)
        images.append(
            JudgeImage(
                label=f"{asset['role']} ({asset['asset_id']})",
                data=data,
                content_type=mime,
            )
        )
    return images


def _judge_evidence_from_output(
    output: dict[str, Any]
) -> tuple[list[JudgeImage], list[str]]:
    images: list[JudgeImage] = []
    texts: list[str] = []
    for artifact in output.get("artifacts") or []:
        attachment = artifact.get("attachment")
        if attachment is None:
            continue
        content_type = str(artifact.get("content_type") or "application/octet-stream")
        # Gemini's inline-image API does not accept SVG. Keep vector files in
        # the artifact/production contract, but do not send them as raster
        # visual evidence. These cases also contain rendered PNG/PDF evidence.
        if content_type.lower() in GEMINI_INLINE_IMAGE_TYPES:
            images.append(
                JudgeImage(
                    label=str(artifact.get("label") or artifact.get("filename") or "output"),
                    data=_attachment_bytes(attachment),
                    content_type=content_type,
                )
            )
        elif content_type in {"application/json", "text/plain", "text/markdown"}:
            try:
                value = _attachment_bytes(attachment).decode("utf-8")[:20_000]
                texts.append(
                    f"{artifact.get('label') or artifact.get('filename')}: {value}"
                )
            except Exception:
                continue
    return images, texts


async def benchmark_judge_v2_scores(
    input: dict[str, Any],
    output: dict[str, Any],
    expected: dict[str, Any],
    *,
    judge: IndependentJudgeProtocol,
    **_: Any,
) -> list[Score]:
    rubric = expected["rubric"]
    required_dimensions = list(rubric["required_dimensions"])
    judge_dimensions = list(rubric["judge_dimensions"])
    weights = rubric["weights"]
    artifact_contract, artifact_meta = _artifact_contract(output, expected)
    reference_utilization = _reference_utilization(output, expected)
    completed = output.get("status") == "COMPLETED"
    production, production_gate, production_meta = _production_readiness(output, expected)
    efficiency, efficiency_meta = _efficiency(output, expected)

    values: dict[str, float | None] = {
        "production_readiness": production,
        "efficiency": efficiency,
    }
    dimension_meta: dict[str, dict[str, Any]] = {
        "production_readiness": production_meta,
        "efficiency": efficiency_meta,
    }
    judge_result = None
    judge_error: str | None = None
    output_images, output_texts = _judge_evidence_from_output(output)
    evidence_available = bool(output_images or output_texts)
    if judge_dimensions:
        if evidence_available:
            request = JudgeRequest(
                task_id=str(input["task_id"]),
                brief=str(input["brief"]),
                category=str(expected["category"]),
                capability_id=str(expected["capability_id"]),
                success_criteria=list(expected["success_criteria"]),
                negative_constraints=list(expected["negative_constraints"]),
                deliverable_contract=dict(expected["deliverable_contract"]),
                dimension_criteria={
                    name: rubric["criteria"][name] for name in judge_dimensions
                },
                input_images=_judge_images_from_input(input),
                output_images=output_images,
                output_text_evidence=output_texts,
            )
            try:
                judge_result = await judge.evaluate(request)
            except Exception as exc:
                judge_error = f"{type(exc).__name__}: {str(exc)[:500]}"
        else:
            judge_error = "No image or text output was available to independent judge-v2"

    if judge_result is not None:
        for name, judgment in judge_result.dimensions.items():
            values[name] = judgment.score / 5.0
            dimension_meta[name] = {
                "source": "independent judge-v2",
                "model": judge_result.model,
                "judge_version": judge_result.judge_version,
                "independent": judge_result.independent,
                "mock": judge_result.mock,
                "rationale": judgment.rationale,
                "evidence": judgment.evidence,
                "confidence": judgment.confidence,
            }
    else:
        for name in judge_dimensions:
            values[name] = None
            dimension_meta[name] = {
                "source": "independent judge-v2",
                "error": judge_error or "Task did not produce a completed output",
            }

    available = {
        name: values.get(name)
        for name in required_dimensions
        if values.get(name) is not None
    }
    coverage = len(available) / len(required_dimensions) if required_dimensions else 1.0
    required_weight = sum(float(weights[name]) for name in required_dimensions)
    # Missing required dimensions contribute zero. We normalize only by the full
    # task-applicable weight, never by the subset the system happened to expose.
    weighted = (
        sum(float(weights[name]) * float(value) for name, value in available.items())
        / required_weight
        if required_weight
        else 0.0
    )
    hard_gates = {
        "completed": completed,
        "artifact_contract": artifact_contract == 1.0,
        "all_inputs_consumed": reference_utilization == 1.0,
        "production_gate": production_gate,
        "judge_coverage": coverage == 1.0,
        "judge_no_fatal_issues": bool(
            judge_result is not None and not judge_result.fatal_issues
        ),
    }
    gates_pass = all(hard_gates.values())
    benchmark_total = weighted if gates_pass else 0.0
    case_pass = gates_pass and benchmark_total >= 0.70

    scores = [
        _score(name, values.get(name), **dimension_meta.get(name, {}))
        for name in required_dimensions
    ]
    scores.extend(
        [
            _score(
                "independent_judge_available",
                judge_result is not None if evidence_available else None,
                model=getattr(judge, "model_name", "unknown"),
                error=judge_error,
            ),
            _score(
                "rubric_coverage",
                coverage if evidence_available or completed else 0.0,
                required=required_dimensions,
                scored=sorted(available),
                missing=sorted(set(required_dimensions) - set(available)),
            ),
            _score(
                "weighted_design_score",
                weighted if evidence_available or completed else None,
                denominator="all task-required dimensions",
                provisional=bool(judge_result and judge_result.mock),
            ),
            _score(
                "benchmark_total_score",
                benchmark_total,
                hard_gates=hard_gates,
                threshold=0.70,
            ),
            _score(
                "benchmark_case_pass",
                case_pass,
                hard_gates=hard_gates,
                weighted_design_score=weighted,
                threshold=0.70,
                artifact_contract=artifact_meta,
            ),
        ]
    )
    return scores
