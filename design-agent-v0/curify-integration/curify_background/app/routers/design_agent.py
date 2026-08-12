from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import (
    new_agent_run_id,
    prepare_agent_project,
    run_agent_project,
)
from app.agent_runtime.schemas import (
    AgentArtifact,
    AgentRunRequest,
    AgentRunStatus,
    AgentRunStatusResponse,
    AgentStage,
    AgentTaskType,
    AgentTraceStep,
    CreateAgentRunResponse,
    VerificationVerdict,
)
from app.crud.project import get_project_by_id
from app.database import get_db
from app.models.user import User
from app.utils import gcs_storage
from app.utils.auth_utils import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/design-agent", tags=["design-agent"])


def _validate_image_sources(body: AgentRunRequest, user_id: int) -> None:
    """Prevent one user from asking the service account to read another upload."""
    owned_prefix = f"images/uploads/{user_id}/"
    for source in body.image_urls:
        if "://" not in source:
            if not source.startswith(owned_prefix) or ".." in source.split("/"):
                raise HTTPException(
                    status_code=400,
                    detail="Private image handles must come from this user's /images/upload endpoint.",
                )
            continue
        parsed = urlparse(source)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise HTTPException(
                status_code=400,
                detail="External image inputs must be public HTTPS URLs without embedded credentials.",
            )


@router.post(
    "/runs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CreateAgentRunResponse,
)
async def create_design_agent_run(
    body: AgentRunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateAgentRunResponse:
    _validate_image_sources(body, current_user.user_id)
    run_id = new_agent_run_id()
    await prepare_agent_project(db, run_id, current_user.user_id, body)
    background_tasks.add_task(
        run_agent_project,
        run_id,
        current_user.user_id,
        body.model_dump(mode="json"),
    )
    return CreateAgentRunResponse(run_id=run_id)


def _status(value: Any) -> AgentRunStatus:
    try:
        return AgentRunStatus(str(value))
    except ValueError:
        return AgentRunStatus.RUNNING


@router.get("/runs/{run_id}", response_model=AgentRunStatusResponse)
async def get_design_agent_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentRunStatusResponse:
    project = await get_project_by_id(db, run_id)
    if (
        not project
        or project.user_id != current_user.user_id
        or not run_id.startswith("design_agent_")
    ):
        raise HTTPException(status_code=404, detail="Design Agent run not found.")
    runtime_config: Dict[str, Any] = project.runtime_config or {}
    result: Dict[str, Any] = runtime_config.get("result") or {}
    artifact_payloads = result.get("artifacts") or []
    artifacts = []
    for payload in artifact_payloads:
        artifact = AgentArtifact.model_validate(payload)
        try:
            artifact.url = await asyncio.to_thread(
                gcs_storage.generate_signed_url,
                artifact.object_path,
                60,
            )
        except Exception:
            logger.warning("Could not sign Design Agent artifact %s", artifact.object_path, exc_info=True)
        artifacts.append(artifact)
    trace_payload = runtime_config.get("trace") or []
    trace = [AgentTraceStep.model_validate(step) for step in trace_payload]
    current_stage = runtime_config.get("current_stage")
    return AgentRunStatusResponse(
        run_id=run_id,
        status=_status(runtime_config.get("agent_status", AgentRunStatus.RUNNING.value)),
        task_type=(AgentTaskType(result["task_type"]) if result.get("task_type") else None),
        skill_id=result.get("skill_id"),
        summary=result.get("summary"),
        code=result.get("code") or runtime_config.get("failure_code"),
        current_stage=AgentStage(current_stage) if current_stage else None,
        artifacts=artifacts,
        verdict=(VerificationVerdict.model_validate(result["verdict"]) if result.get("verdict") else None),
        iterations=int(result.get("iterations") or 0),
        trace=trace,
    )
