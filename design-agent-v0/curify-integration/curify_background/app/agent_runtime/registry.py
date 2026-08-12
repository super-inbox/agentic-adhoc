from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from app.agent_runtime.schemas import AgentRunRequest, AgentStage
from app.agent_runtime.tracing import TraceRecorder, safe_summary


class AgentAbstention(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ToolNotFoundError(RuntimeError):
    pass


@dataclass
class ToolContext:
    run_id: str
    request: AgentRunRequest
    recorder: TraceRecorder


ToolHandler = Callable[[Dict[str, Any], ToolContext], Awaitable[Any]]


@dataclass
class ToolSpec:
    name: str
    description: str
    stage: AgentStage
    handler: ToolHandler
    requires_paid_generation: bool = False
    model: Optional[str] = None
    estimated_credits: float = 0.0
    credit_estimator: Optional[Callable[[Dict[str, Any]], float]] = None


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def describe(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    async def invoke(
        self,
        name: str,
        args: Dict[str, Any],
        context: ToolContext,
    ) -> Any:
        spec = self.describe(name)
        if spec.requires_paid_generation and not context.request.allow_paid_generation:
            raise AgentAbstention(
                "PAID_GENERATION_NOT_APPROVED",
                "This skill creates paid model outputs. Resubmit with allow_paid_generation=true.",
            )
        estimated_credits = (
            spec.credit_estimator(args)
            if spec.credit_estimator is not None
            else spec.estimated_credits
        )
        return await context.recorder.record(
            spec.stage,
            f"tool:{name}",
            lambda: spec.handler(args, context),
            tool_name=name,
            model=spec.model,
            input_summary=safe_summary(args),
            metrics={"estimated_credits": max(0.0, float(estimated_credits))},
        )
