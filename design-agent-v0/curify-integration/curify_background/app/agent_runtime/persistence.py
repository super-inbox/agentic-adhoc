from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.runtime import build_default_runtime
from app.agent_runtime.schemas import AgentRunRequest, AgentRunStatus
from app.agent_runtime.tracing import safe_error
from app.crud.project import create_project, update_project_fields
from app.database import async_session_maker
from app.models.project import JobSettings, JobType, ProjectStatus

logger = logging.getLogger(__name__)


def new_agent_run_id() -> str:
    return f"design_agent_{uuid.uuid4().hex[:16]}"


def _source_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def initial_runtime_config(request: AgentRunRequest) -> Dict[str, Any]:
    return {
        "kind": "design_agent",
        "agent_status": AgentRunStatus.QUEUED.value,
        "request": {
            "task_type": request.task_type.value,
            "prompt": request.prompt,
            "locale": request.locale,
            "image_count": len(request.image_urls),
            # Never persist signed URLs or private object paths in trace JSON.
            "image_ref_hashes": [_source_hash(value) for value in request.image_urls],
            "output_count": request.output_count,
            "max_iterations": request.max_iterations,
            "allow_paid_generation": request.allow_paid_generation,
            "constraints": request.constraints,
        },
        "trace": [],
    }


async def prepare_agent_project(
    db: AsyncSession,
    run_id: str,
    user_id: int,
    request: AgentRunRequest,
) -> None:
    await create_project(
        db=db,
        project_id=run_id,
        user_id=user_id,
        video_id=None,
        project_name=f"Design Agent · {request.task_type.value}",
        job_settings=JobSettings(job_type=JobType.DESIGN_AGENT),
        description=f"single-turn multimodal design agent; images={len(request.image_urls)}",
        is_production=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await update_project_fields(
        db,
        run_id,
        status=ProjectStatus.STARTED,
        runtime_config=initial_runtime_config(request),
    )


async def run_agent_project(
    run_id: str,
    user_id: int,
    request_payload: Dict[str, Any],
) -> None:
    request = AgentRunRequest.model_validate(request_payload)
    base_config = initial_runtime_config(request)
    async with async_session_maker() as db:
        async def trace_sink(steps) -> None:
            current_stage = steps[-1].stage.value if steps else None
            await update_project_fields(
                db,
                run_id,
                runtime_config={
                    **base_config,
                    "agent_status": AgentRunStatus.RUNNING.value,
                    "current_stage": current_stage,
                    "trace": [step.model_dump(mode="json") for step in steps],
                },
            )

        try:
            result = await build_default_runtime().run(run_id, request, trace_sink)
            project_status = (
                ProjectStatus.COMPLETED
                if result.status in (AgentRunStatus.COMPLETED, AgentRunStatus.ABSTAINED)
                else ProjectStatus.FAILED
            )
            result_json = result.model_dump(mode="json")
            runtime_config = {
                **base_config,
                "agent_status": result.status.value,
                "current_stage": result.trace[-1].stage.value if result.trace else None,
                "trace": result_json.pop("trace"),
                "result": result_json,
            }
            updates: Dict[str, Any] = {
                "status": project_status,
                "runtime_config": runtime_config,
                "cost_credits": sum(
                    step.metrics.get("estimated_credits", 0.0) for step in result.trace
                ),
            }
            if result.artifacts:
                updates["final_video_blob_path"] = result.artifacts[0].object_path
            await update_project_fields(db, run_id, **updates)
        except Exception as exc:
            logger.exception("Design Agent background task crashed run_id=%s user_id=%s", run_id, user_id)
            await update_project_fields(
                db,
                run_id,
                status=ProjectStatus.FAILED,
                runtime_config={
                    **base_config,
                    "agent_status": AgentRunStatus.FAILED.value,
                    "failure_code": "AGENT_BACKGROUND_CRASH",
                    "failure_reason": safe_error(exc),
                },
            )
