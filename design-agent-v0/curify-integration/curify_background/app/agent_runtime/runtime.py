from __future__ import annotations

import logging
from typing import Optional

from app.agent_runtime.registry import AgentAbstention, ToolContext
from app.agent_runtime.schemas import (
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentStage,
    VerificationVerdict,
)
from app.agent_runtime.services import DesignAgentServices, default_services
from app.agent_runtime.skills import SkillContext, SkillRegistry, infer_task_type
from app.agent_runtime.tools import build_tool_registry
from app.agent_runtime.tracing import TraceRecorder, TraceSink

logger = logging.getLogger(__name__)


class DesignAgentRuntime:
    """A bounded single-turn loop: understand -> plan -> tools -> verify -> repair."""

    def __init__(
        self,
        services: DesignAgentServices,
        skills: Optional[SkillRegistry] = None,
    ):
        self.services = services
        self.skills = skills or SkillRegistry()
        self.tools = build_tool_registry(services)

    async def run(
        self,
        run_id: str,
        request: AgentRunRequest,
        trace_sink: Optional[TraceSink] = None,
    ) -> AgentRunResult:
        recorder = TraceRecorder(trace_sink)
        selected_task = None
        skill = None
        verdict: Optional[VerificationVerdict] = None
        execution = None
        iterations = 0
        try:
            selected_task = await recorder.record(
                AgentStage.UNDERSTAND,
                "route_task",
                lambda: infer_task_type(request),
                input_summary={
                    "requested_task": request.task_type.value,
                    "image_count": len(request.image_urls),
                    "prompt_chars": len(request.prompt),
                },
            )
            if selected_task is None:
                return AgentRunResult(
                    run_id=run_id,
                    status=AgentRunStatus.ABSTAINED,
                    summary="The request does not match a supported Design Agent skill.",
                    code="UNSUPPORTED_TASK",
                    trace=recorder.steps,
                )
            skill = self.skills.get(selected_task)
            capability = await recorder.record(
                AgentStage.UNDERSTAND,
                "capability_gate",
                lambda: skill.capability(request),
                input_summary={
                    "skill_id": skill.skill_id,
                    "image_count": len(request.image_urls),
                    "allow_paid_generation": request.allow_paid_generation,
                },
            )
            if not capability.supported:
                return AgentRunResult(
                    run_id=run_id,
                    status=AgentRunStatus.ABSTAINED,
                    task_type=selected_task,
                    skill_id=skill.skill_id,
                    summary=capability.message,
                    code=capability.code,
                    trace=recorder.steps,
                )

            tool_context = ToolContext(run_id=run_id, request=request, recorder=recorder)
            skill_context = SkillContext(
                run_id=run_id,
                request=request,
                tools=self.tools,
                tool_context=tool_context,
            )
            feedback: Optional[VerificationVerdict] = None
            previous = None
            for iteration in range(request.max_iterations + 1):
                iterations = iteration + 1
                await recorder.record(
                    AgentStage.PLAN,
                    f"plan_iteration_{iteration}",
                    lambda iteration=iteration, feedback=feedback: skill.plan(
                        request, iteration, feedback
                    ),
                    input_summary={
                        "iteration": iteration,
                        "repair_instruction": feedback.repair_instruction if feedback else None,
                    },
                )
                execution = await skill.execute(
                    skill_context,
                    iteration,
                    previous,
                    feedback,
                )
                verdict = await recorder.record(
                    AgentStage.VERIFY,
                    f"verify_iteration_{iteration}",
                    lambda: skill.verify(skill_context, execution),
                    input_summary={"iteration": iteration, "skill_id": skill.skill_id},
                )
                if verdict.passed:
                    artifacts = await recorder.record(
                        AgentStage.PRESENT,
                        "finalize_artifacts",
                        lambda: skill.present(skill_context, execution),
                        input_summary={"skill_id": skill.skill_id},
                    )
                    return AgentRunResult(
                        run_id=run_id,
                        status=AgentRunStatus.COMPLETED,
                        task_type=selected_task,
                        skill_id=skill.skill_id,
                        summary=skill.summary(execution),
                        artifacts=artifacts,
                        verdict=verdict,
                        iterations=iterations,
                        trace=recorder.steps,
                    )
                if verdict.hard_failures:
                    return AgentRunResult(
                        run_id=run_id,
                        status=AgentRunStatus.ABSTAINED,
                        task_type=selected_task,
                        skill_id=skill.skill_id,
                        summary="Visual verification found an input/output problem that cannot be repaired safely.",
                        code="VISUAL_VERIFICATION_HARD_FAIL",
                        verdict=verdict,
                        iterations=iterations,
                        trace=recorder.steps,
                    )
                if iteration < request.max_iterations and verdict.repairable_failures:
                    previous = execution
                    feedback = verdict
                    continue
                return AgentRunResult(
                    run_id=run_id,
                    status=AgentRunStatus.FAILED,
                    task_type=selected_task,
                    skill_id=skill.skill_id,
                    summary="The artifact did not pass visual verification within the retry budget.",
                    code="VERIFICATION_FAILED",
                    verdict=verdict,
                    iterations=iterations,
                    trace=recorder.steps,
                )
        except AgentAbstention as exc:
            return AgentRunResult(
                run_id=run_id,
                status=AgentRunStatus.ABSTAINED,
                task_type=selected_task,
                skill_id=skill.skill_id if skill else None,
                summary=exc.message,
                code=exc.code,
                verdict=verdict,
                iterations=iterations,
                trace=recorder.steps,
            )
        except Exception:
            logger.exception("Design Agent run failed run_id=%s", run_id)
            return AgentRunResult(
                run_id=run_id,
                status=AgentRunStatus.FAILED,
                task_type=selected_task,
                skill_id=skill.skill_id if skill else None,
                summary="Design Agent execution failed.",
                code="AGENT_RUNTIME_ERROR",
                verdict=verdict,
                iterations=iterations,
                trace=recorder.steps,
            )


def build_default_runtime(
    services: Optional[DesignAgentServices] = None,
) -> DesignAgentRuntime:
    return DesignAgentRuntime(services or default_services())
