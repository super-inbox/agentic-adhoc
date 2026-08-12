#!/usr/bin/env python3
"""Run the documented men's-grooming request through the real runtime offline.

Only the model gateway and storage adapters are deterministic demo fixtures.
Routing, planning, tool invocation, vote aggregation, rendering, verification,
artifact presentation, and tracing are the production v0 implementations.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
backend_root_value = os.getenv("CURIFY_BACKEND_ROOT")
if not backend_root_value:
    raise SystemExit(
        "Set CURIFY_BACKEND_ROOT to a Curify curify_background directory "
        "containing the Design Agent integration."
    )
BACKEND_ROOT = Path(backend_root_value).expanduser().resolve()
if not (BACKEND_ROOT / "app" / "config.py").is_file():
    raise SystemExit(f"Invalid CURIFY_BACKEND_ROOT: {BACKEND_ROOT}")
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# The offline adapters do not connect to these services, but application
# settings validate the common backend environment at import time.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("CALLBACK_API_BASE_URL", "http://localhost:8000")
os.environ.setdefault("SECRET_KEY", "offline_demo")
os.environ.setdefault(
    "AZURE_STORAGE_CONNECTION_STRING",
    "DefaultEndpointsProtocol=https;AccountName=demo;AccountKey=demo;EndpointSuffix=core.windows.net",
)
os.environ.setdefault("OPENAI_API_KEY", "offline_demo")
os.environ.setdefault("ELEVENLABS_API_KEY", "offline_demo")
os.environ.setdefault("SYNC_LAB_API_KEY", "offline_demo")
os.environ.setdefault("AZURE_TRANSLATOR_KEY", "offline_demo")
os.environ.setdefault("IS_PRODUCTION", "False")
os.environ.setdefault("SKIP_DB_CREATE", "true")

from app.agent_runtime.runtime import DesignAgentRuntime
from app.agent_runtime.schemas import (
    AgentArtifact,
    AgentRunRequest,
    AgentArtifactKind,
    VerificationVerdict,
    VoteDraft,
    VoteSegmentDraft,
    VoteVariant,
)
from app.agent_runtime.services import DesignAgentServices


BOARD_HANDLE = "images/uploads/42/board.jpg"
BOARD_PATH = HERE / "mens-grooming-board.png"
OUTPUT_DIR = HERE / "output"


class DemoImageLoader:
    async def load(self, source: str) -> bytes:
        if source != BOARD_HANDLE:
            raise ValueError(f"Unknown offline image handle: {source}")
        return BOARD_PATH.read_bytes()


class DemoArtifactStore:
    async def put(
        self,
        run_id: str,
        filename: str,
        data: bytes,
        media_type: str,
        kind: AgentArtifactKind,
        label: str,
        metadata=None,
    ) -> AgentArtifact:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / filename
        path.write_bytes(data)
        return AgentArtifact(
            artifact_id=uuid.uuid4().hex[:12],
            kind=kind,
            label=label,
            object_path=str(path),
            media_type=media_type,
            metadata=metadata or {},
        )

    async def sign(self, object_path: str, expiry_minutes: int = 60) -> str:
        return Path(object_path).resolve().as_uri()


class DemoVisionGateway:
    """A reproducible stand-in for Gemini, grounded in the generated 2x2 board."""

    model_name = "demo-vision-fixture-v1"
    generation_model_name = "not-used-for-design-vote"

    async def analyze_vote(self, prompt, candidate_images, repair_instruction=None):
        return VoteDraft(
            product="男士洁面泡沫包装",
            category="男士理容",
            axis="质感、品牌识别与货架高级感",
            variants=[
                VoteVariant(
                    id="A",
                    design_language="深海军蓝、居中秩序、细铜线点缀",
                    strengths=["稳重克制，传统高端感明确"],
                    weaknesses=["视觉语言偏保守"],
                ),
                VoteVariant(
                    id="B",
                    design_language="黑白瑞士网格、大比例几何构成",
                    strengths=["货架识别强，年轻且理性"],
                    weaknesses=["冷峻感可能削弱亲和力"],
                ),
                VoteVariant(
                    id="C",
                    design_language="鼠尾草绿、非对称编辑式版面",
                    strengths=["自然、设计感鲜明"],
                    weaknesses=["男性理容识别略弱"],
                ),
                VoteVariant(
                    id="D",
                    design_language="暖炭黑、铜色徽记、克制层级",
                    strengths=["高级、成熟且品牌记忆点完整"],
                    weaknesses=["对年轻潮流人群吸引力稍弱"],
                ),
            ],
            segments=[
                VoteSegmentDraft(
                    name="都市专业男性",
                    share=0.35,
                    votes={"A": 20, "B": 15, "C": 20, "D": 45},
                    rationale="D 的徽记和暖黑材质最像成熟高端理容品牌。",
                ),
                VoteSegmentDraft(
                    name="年轻潮流消费者",
                    share=0.25,
                    votes={"A": 10, "B": 35, "C": 30, "D": 25},
                    rationale="B 的高反差网格更有即时货架冲击力。",
                ),
                VoteSegmentDraft(
                    name="设计敏感人群",
                    share=0.15,
                    votes={"A": 10, "B": 30, "C": 40, "D": 20},
                    rationale="C 的非对称编辑语言最具设计辨识度。",
                ),
                VoteSegmentDraft(
                    name="高端礼赠购买者",
                    share=0.25,
                    votes={"A": 20, "B": 10, "C": 15, "D": 55},
                    rationale="D 的铜色徽记和克制构图最符合礼赠质感。",
                ),
            ],
            recommendation="以 D 款作为主推；B 款可用于更年轻、强调货架冲击力的渠道测试。",
            confidence=0.84,
        )

    async def review_vote(self, prompt, candidate_images, analysis):
        return VerificationVerdict(
            passed=True,
            scores={
                "grounding": 4.6,
                "segment_plausibility": 4.3,
                "ranking_sanity": 4.4,
                "actionability": 4.5,
            },
        )


async def main() -> None:
    request = AgentRunRequest.model_validate_json((HERE / "request.json").read_text())
    runtime = DesignAgentRuntime(
        DesignAgentServices(
            gateway=DemoVisionGateway(),
            image_loader=DemoImageLoader(),
            artifact_store=DemoArtifactStore(),
        )
    )
    result = await runtime.run("design_agent_demo_mens_grooming", request)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT_DIR / "run-result.json"
    result_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result.status.value,
                "task_type": result.task_type.value if result.task_type else None,
                "summary": result.summary,
                "iterations": result.iterations,
                "verdict": result.verdict.model_dump() if result.verdict else None,
                "artifacts": [artifact.object_path for artifact in result.artifacts],
                "trace_steps": len(result.trace),
                "result_json": str(result_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
