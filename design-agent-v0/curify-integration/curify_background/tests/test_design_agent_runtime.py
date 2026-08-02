import io
import os
import unittest
import uuid
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("CALLBACK_API_BASE_URL", "http://localhost:8000")
os.environ.setdefault("SECRET_KEY", "test_secret_key")
os.environ.setdefault(
    "AZURE_STORAGE_CONNECTION_STRING",
    "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key;EndpointSuffix=core.windows.net",
)
os.environ.setdefault("ELEVENLABS_API_KEY", "test_eleven_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")
os.environ.setdefault("SYNC_LAB_API_KEY", "test_sync_key")
os.environ.setdefault("AZURE_TRANSLATOR_KEY", "test_azure_key")
os.environ.setdefault("IS_PRODUCTION", "False")
os.environ.setdefault("SKIP_DB_CREATE", "true")

from fastapi import BackgroundTasks
from fastapi import HTTPException
from PIL import Image

from app.agent_runtime.runtime import DesignAgentRuntime
from app.agent_runtime.evaluation import aggregate_results, score_case
from app.agent_runtime.schemas import (
    AgentArtifact,
    AgentRunRequest,
    AgentRunStatus,
    AgentTaskType,
    TryOnPosterScore,
    TryOnReview,
    VerificationVerdict,
    VoteDraft,
    VoteSegmentDraft,
    VoteVariant,
)
from app.agent_runtime.services import DesignAgentServices, SafeImageLoader
from app.routers.design_agent import create_design_agent_run, get_design_agent_run


def sample_jpeg(color=(190, 180, 170), size=(1200, 900)) -> bytes:
    image = Image.new("RGB", size, color)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()


class MemoryImageLoader:
    def __init__(self):
        self.calls = []

    async def load(self, source: str) -> bytes:
        self.calls.append(source)
        return sample_jpeg()


class MemoryArtifactStore:
    def __init__(self):
        self.objects = {}

    async def put(
        self,
        run_id,
        filename,
        data,
        media_type,
        kind,
        label,
        metadata=None,
    ):
        path = f"memory/{run_id}/{filename}"
        self.objects[path] = data
        return AgentArtifact(
            artifact_id=uuid.uuid4().hex[:12],
            kind=kind,
            label=label,
            object_path=path,
            media_type=media_type,
            metadata=metadata or {},
        )

    async def sign(self, object_path: str, expiry_minutes: int = 60) -> str:
        return f"https://example.com/{object_path}"


class FakeGateway:
    model_name = "fake-multimodal-model"
    generation_model_name = "fake-image-model"

    def __init__(self, fail_vote_reviews=0, fail_tryon_reviews=0, invalid_vote=False):
        self.fail_vote_reviews = fail_vote_reviews
        self.fail_tryon_reviews = fail_tryon_reviews
        self.invalid_vote = invalid_vote
        self.vote_analysis_calls = 0
        self.vote_review_calls = 0
        self.tryon_generation_calls = 0
        self.tryon_review_calls = 0

    async def analyze_vote(self, prompt, candidate_images, repair_instruction=None):
        self.vote_analysis_calls += 1
        if self.invalid_vote:
            return VoteDraft(valid_variants=False, issues=["Only three coherent designs are visible."])
        return VoteDraft(
            valid_variants=True,
            product="Men's grooming cleanser",
            category="men's grooming",
            axis="premium feel",
            variants=[
                VoteVariant(
                    id=label,
                    design_language=f"Visible hierarchy {label}",
                    strengths=[f"strength {label}"],
                    weaknesses=[f"weakness {label}"],
                )
                for label in "ABCD"
            ],
            segments=[
                VoteSegmentDraft(
                    name="Urban professionals",
                    share=0.6,
                    votes={"A": 10, "B": 20, "C": 25, "D": 45},
                    rationale="D has the clearest hierarchy.",
                ),
                VoteSegmentDraft(
                    name="Design-aware shoppers",
                    share=0.4,
                    votes={"A": 10, "B": 10, "C": 50, "D": 30},
                    rationale="C has a more editorial composition.",
                ),
            ],
            recommendation="Lead with D and retain C as an editorial alternative.",
            confidence=0.82,
        )

    async def review_vote(self, prompt, candidate_images, analysis):
        self.vote_review_calls += 1
        if self.vote_review_calls <= self.fail_vote_reviews:
            return VerificationVerdict(
                passed=False,
                scores={"grounding": 2.0},
                repairable_failures=["Ground the ranking in visible hierarchy."],
                repair_instruction="Use concrete visible hierarchy evidence.",
            )
        return VerificationVerdict(
            passed=True,
            scores={
                "grounding": 4.4,
                "segment_plausibility": 4.2,
                "ranking_sanity": 4.1,
                "actionability": 4.0,
            },
        )

    async def generate_tryon(
        self,
        selfie,
        product,
        prompt,
        direction,
        repair_instruction=None,
    ):
        self.tryon_generation_calls += 1
        color = (80 + self.tryon_generation_calls * 20, 110, 150)
        return sample_jpeg(color=color, size=(1080, 1350))

    async def review_tryon(self, selfie, product, prompt, posters):
        self.tryon_review_calls += 1
        scores = []
        for index in range(len(posters)):
            failed = self.tryon_review_calls <= self.fail_tryon_reviews and index == 1
            scores.append(
                TryOnPosterScore(
                    index=index,
                    identity=2.5 if failed else 4.5,
                    product_fidelity=2.5 if failed else 4.2,
                    anatomy=4.2,
                    instruction_following=4.3,
                    layout=4.4,
                    failures=["face identity drift"] if failed else [],
                )
            )
        return TryOnReview(posters=scores)


def runtime_with_gateway(gateway: FakeGateway):
    loader = MemoryImageLoader()
    store = MemoryArtifactStore()
    runtime = DesignAgentRuntime(
        DesignAgentServices(gateway=gateway, image_loader=loader, artifact_store=store)
    )
    return runtime, loader, store


class TestDesignAgentRuntime(unittest.IsolatedAsyncioTestCase):
    async def test_design_vote_runs_end_to_end(self):
        gateway = FakeGateway()
        runtime, loader, store = runtime_with_gateway(gateway)
        result = await runtime.run(
            "run_vote",
            AgentRunRequest(
                prompt="站在消费者角度，哪款男士理容包装更有质感？",
                image_urls=["private/comparison-board.jpg"],
            ),
        )

        self.assertEqual(result.status, AgentRunStatus.COMPLETED)
        self.assertEqual(result.task_type, AgentTaskType.DESIGN_VOTE)
        self.assertEqual(result.skill_id, "design-vote")
        self.assertEqual(len(result.artifacts), 2)
        self.assertEqual(result.iterations, 1)
        self.assertIn("D", result.summary)
        self.assertTrue(result.verdict and result.verdict.passed)
        self.assertEqual(gateway.vote_analysis_calls, 1)
        self.assertEqual(gateway.vote_review_calls, 1)
        self.assertTrue(any(step.stage.value == "VERIFY" for step in result.trace))
        stage_order = [step.stage.value for step in result.trace]
        self.assertLess(stage_order.index("UNDERSTAND"), stage_order.index("PLAN"))
        self.assertLess(stage_order.index("PLAN"), stage_order.index("GENERATE"))
        self.assertLess(stage_order.index("GENERATE"), stage_order.index("VERIFY"))
        self.assertLess(stage_order.index("VERIFY"), stage_order.index("PRESENT"))
        self.assertEqual(len(store.objects), 2)

    async def test_design_vote_repairs_after_visual_feedback(self):
        gateway = FakeGateway(fail_vote_reviews=1)
        runtime, loader, _ = runtime_with_gateway(gateway)
        result = await runtime.run(
            "run_vote_retry",
            AgentRunRequest(
                task_type=AgentTaskType.DESIGN_VOTE,
                prompt="Compare these four package designs",
                image_urls=["a", "b", "c", "d"],
                max_iterations=1,
            ),
        )

        self.assertEqual(result.status, AgentRunStatus.COMPLETED)
        self.assertEqual(result.iterations, 2)
        self.assertEqual(gateway.vote_analysis_calls, 2)
        self.assertEqual(gateway.vote_review_calls, 2)
        self.assertEqual(len(loader.calls), 4)  # references are reused during repair

    async def test_design_vote_abstains_when_vision_rejects_the_board(self):
        gateway = FakeGateway(invalid_vote=True)
        runtime, _, _ = runtime_with_gateway(gateway)
        result = await runtime.run(
            "run_invalid_board",
            AgentRunRequest(
                task_type=AgentTaskType.DESIGN_VOTE,
                prompt="Vote on these designs",
                image_urls=["board"],
            ),
        )
        self.assertEqual(result.status, AgentRunStatus.ABSTAINED)
        self.assertEqual(result.code, "INSUFFICIENT_CANDIDATES")

    async def test_design_vote_abstains_on_invalid_candidate_count(self):
        gateway = FakeGateway()
        runtime, _, _ = runtime_with_gateway(gateway)
        result = await runtime.run(
            "run_bad_vote",
            AgentRunRequest(
                task_type=AgentTaskType.DESIGN_VOTE,
                prompt="Vote on these designs",
                image_urls=["a", "b"],
            ),
        )
        self.assertEqual(result.status, AgentRunStatus.ABSTAINED)
        self.assertEqual(result.code, "INVALID_CANDIDATE_COUNT")
        self.assertEqual(gateway.vote_analysis_calls, 0)

    async def test_exact_product_tryon_requires_product_reference(self):
        gateway = FakeGateway()
        runtime, _, _ = runtime_with_gateway(gateway)
        result = await runtime.run(
            "run_missing_product",
            AgentRunRequest(
                task_type=AgentTaskType.TRYON_POSTER,
                prompt="用自拍生成这个真实商品的试穿电商海报",
                image_urls=["selfie"],
                allow_paid_generation=True,
            ),
        )
        self.assertEqual(result.status, AgentRunStatus.ABSTAINED)
        self.assertEqual(result.code, "MISSING_PRODUCT_IMAGE")

    async def test_tryon_requires_paid_generation_permission(self):
        gateway = FakeGateway()
        runtime, _, _ = runtime_with_gateway(gateway)
        result = await runtime.run(
            "run_no_permission",
            AgentRunRequest(
                task_type=AgentTaskType.TRYON_POSTER,
                prompt="Generate outfit posters",
                image_urls=["selfie"],
            ),
        )
        self.assertEqual(result.status, AgentRunStatus.ABSTAINED)
        self.assertEqual(result.code, "PAID_GENERATION_NOT_APPROVED")

    async def test_tryon_retries_only_failed_poster(self):
        gateway = FakeGateway(fail_tryon_reviews=1)
        runtime, _, store = runtime_with_gateway(gateway)
        result = await runtime.run(
            "run_tryon",
            AgentRunRequest(
                task_type=AgentTaskType.TRYON_POSTER,
                prompt="Use my selfie and product image to create ecommerce posters",
                image_urls=["selfie", "product"],
                output_count=3,
                max_iterations=1,
                allow_paid_generation=True,
            ),
        )
        self.assertEqual(result.status, AgentRunStatus.COMPLETED)
        self.assertEqual(result.iterations, 2)
        self.assertEqual(gateway.tryon_generation_calls, 4)  # 3 first pass + failed index 1
        self.assertEqual(gateway.tryon_review_calls, 2)
        self.assertEqual(len(result.artifacts), 4)
        self.assertEqual(len(store.objects), 4)
        generation_steps = [
            step for step in result.trace if step.tool_name == "generate_tryon_posters"
        ]
        self.assertTrue(generation_steps)
        self.assertTrue(all(step.model == "fake-image-model" for step in generation_steps))
        self.assertEqual(
            sum(step.metrics.get("estimated_credits", 0.0) for step in result.trace),
            40.0,
        )


class TestSafeImageLoader(unittest.TestCase):
    def test_rejects_http_and_private_network_sources(self):
        with self.assertRaises(ValueError):
            SafeImageLoader._validate_public_https("http://example.com/image.jpg")
        with self.assertRaises(ValueError):
            SafeImageLoader._validate_public_https("https://127.0.0.1/image.jpg")


class TestDesignAgentRouter(unittest.IsolatedAsyncioTestCase):
    async def test_create_run_persists_and_enqueues(self):
        body = AgentRunRequest(
            task_type=AgentTaskType.DESIGN_VOTE,
            prompt="Which design wins?",
            image_urls=["images/uploads/42/board.jpg"],
        )
        background = BackgroundTasks()
        user = type("UserStub", (), {"user_id": 42})()
        with patch(
            "app.routers.design_agent.prepare_agent_project",
            new=AsyncMock(),
        ) as prepare:
            response = await create_design_agent_run(
                body=body,
                background_tasks=background,
                current_user=user,
                db=AsyncMock(),
            )
        self.assertTrue(response.run_id.startswith("design_agent_"))
        prepare.assert_awaited_once()
        self.assertEqual(len(background.tasks), 1)

    async def test_create_run_rejects_another_users_private_image(self):
        body = AgentRunRequest(
            task_type=AgentTaskType.DESIGN_VOTE,
            prompt="Which design wins?",
            image_urls=["images/uploads/99/board.jpg"],
        )
        with self.assertRaises(HTTPException) as raised:
            await create_design_agent_run(
                body=body,
                background_tasks=BackgroundTasks(),
                current_user=type("UserStub", (), {"user_id": 42})(),
                db=AsyncMock(),
            )
        self.assertEqual(raised.exception.status_code, 400)

    async def test_get_run_rehydrates_trace_and_signs_artifacts(self):
        project = type(
            "ProjectStub",
            (),
            {
                "user_id": 42,
                "runtime_config": {
                    "agent_status": "COMPLETED",
                    "current_stage": "PRESENT",
                    "trace": [],
                    "result": {
                        "task_type": "design_vote",
                        "skill_id": "design-vote",
                        "summary": "D wins",
                        "iterations": 1,
                        "verdict": {"passed": True},
                        "artifacts": [
                            {
                                "artifact_id": "artifact-1",
                                "kind": "report",
                                "label": "vote report",
                                "object_path": "design_agent/run/report.png",
                                "media_type": "image/png",
                            }
                        ],
                    },
                },
            },
        )()
        with (
            patch(
                "app.routers.design_agent.get_project_by_id",
                new=AsyncMock(return_value=project),
            ),
            patch(
                "app.routers.design_agent.gcs_storage.generate_signed_url",
                return_value="https://example.com/signed",
            ),
        ):
            response = await get_design_agent_run(
                run_id="design_agent_123",
                current_user=type("UserStub", (), {"user_id": 42})(),
                db=AsyncMock(),
            )
        self.assertEqual(response.status, AgentRunStatus.COMPLETED)
        self.assertEqual(response.current_stage.value, "PRESENT")
        self.assertEqual(response.artifacts[0].url, "https://example.com/signed")


class TestDesignAgentEvaluation(unittest.TestCase):
    def test_score_case_checks_route_trace_verdict_and_artifacts(self):
        case = {
            "id": "vote-1",
            "coverage": "supported",
            "expected": {
                "status": "COMPLETED",
                "task_type": "design_vote",
                "skill_id": "design-vote",
                "required_stages": [
                    "UNDERSTAND",
                    "PLAN",
                    "GENERATE",
                    "VERIFY",
                    "PRESENT",
                ],
                "min_artifacts": 2,
                "artifact_kinds": ["report", "manifest"],
                "artifacts_reachable": True,
                "verdict_passed": True,
                "max_iterations": 2,
            },
        }
        response = {
            "status": "COMPLETED",
            "task_type": "design_vote",
            "skill_id": "design-vote",
            "iterations": 1,
            "verdict": {"passed": True},
            "artifacts": [{"kind": "report"}, {"kind": "manifest"}],
            "_artifact_probe": [{"reachable": True}, {"reachable": True}],
            "trace": [
                {"stage": stage, "status": "COMPLETED"}
                for stage in ("UNDERSTAND", "PLAN", "GENERATE", "VERIFY", "PRESENT")
            ],
        }
        result = score_case(case, response)
        self.assertTrue(result["passed"])
        self.assertEqual(result["stage_coverage"], 1.0)

    def test_aggregate_exposes_coverage_failures(self):
        summary = aggregate_results(
            [
                {
                    "id": "ok",
                    "coverage": "supported",
                    "passed": True,
                    "checks": {"route": True},
                    "stage_coverage": 1.0,
                    "actual_status": "COMPLETED",
                },
                {
                    "id": "gap",
                    "coverage": "gap",
                    "passed": False,
                    "checks": {"route": False},
                    "stage_coverage": 0.5,
                    "actual_status": "ABSTAINED",
                },
            ]
        )
        self.assertEqual(summary["case_pass_rate"], 0.5)
        self.assertEqual(summary["routing_accuracy"], 0.5)
        self.assertEqual(summary["by_coverage"]["gap"]["failed_ids"], ["gap"])


if __name__ == "__main__":
    unittest.main()
