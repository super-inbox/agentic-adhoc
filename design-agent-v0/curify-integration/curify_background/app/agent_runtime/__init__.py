"""Bounded, tool-mediated Design Agent runtime.

The runtime is intentionally small and deterministic around the model calls:
skills choose typed tools, tools are permission-gated, verifiers return a
structured repair contract, and the runtime owns the retry budget.

Imports stay lazy so the offline evaluator can use its scoring helpers without
loading model clients or application settings.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.agent_runtime.runtime import DesignAgentRuntime
    from app.agent_runtime.schemas import (
        AgentRunRequest,
        AgentRunResult,
        AgentRunStatus,
        AgentTaskType,
    )

__all__ = [
    "AgentRunRequest",
    "AgentRunResult",
    "AgentRunStatus",
    "AgentTaskType",
    "DesignAgentRuntime",
    "build_default_runtime",
]


def __getattr__(name: str) -> Any:
    if name in {"DesignAgentRuntime", "build_default_runtime"}:
        from app.agent_runtime import runtime

        return getattr(runtime, name)
    if name in {"AgentRunRequest", "AgentRunResult", "AgentRunStatus", "AgentTaskType"}:
        from app.agent_runtime import schemas

        return getattr(schemas, name)
    raise AttributeError(name)
