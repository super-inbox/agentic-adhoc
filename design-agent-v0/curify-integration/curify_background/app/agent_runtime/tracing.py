from __future__ import annotations

import inspect
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional

from pydantic import BaseModel

from app.agent_runtime.schemas import (
    AgentStage,
    AgentStepStatus,
    AgentTraceStep,
)

logger = logging.getLogger(__name__)

TraceSink = Callable[[list[AgentTraceStep]], Awaitable[None]]


def safe_error(value: Exception) -> str:
    message = str(value)
    message = re.sub(r"https?://\S+", "[url-redacted]", message)
    message = re.sub(r"images/uploads/\S+", "[image-ref-redacted]", message)
    return message[:500]


def safe_summary(value: Any, *, depth: int = 0) -> Any:
    """Return a trace-safe summary without raw images, prompts, or signed URLs."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 240:
            return value[:237] + "..."
        return value
    if depth > 3:
        return type(value).__name__
    if isinstance(value, bytes):
        return {"type": "bytes", "size": len(value)}
    if isinstance(value, BaseModel):
        return safe_summary(value.model_dump(mode="json"), depth=depth + 1)
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in list(value.items())[:24]:
            key_lower = str(key).lower()
            if any(token in key_lower for token in ("url", "prompt", "image_bytes")):
                if isinstance(item, list):
                    out[str(key)] = {"count": len(item)}
                elif isinstance(item, bytes):
                    out[str(key)] = {"type": "bytes", "size": len(item)}
                else:
                    out[str(key)] = "[redacted]"
            else:
                out[str(key)] = safe_summary(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], bytes):
            return {"count": len(value), "sizes": [len(v) for v in value[:8]]}
        return [safe_summary(v, depth=depth + 1) for v in list(value)[:12]]
    return type(value).__name__


class TraceRecorder:
    def __init__(self, sink: Optional[TraceSink] = None):
        self.steps: list[AgentTraceStep] = []
        self._sink = sink

    async def _emit(self) -> None:
        # Always write a compact structured log; Project-backed persistence is
        # supplied by the API layer through ``sink``.
        if self.steps:
            logger.info(
                "design_agent_trace %s",
                json.dumps(self.steps[-1].model_dump(mode="json"), ensure_ascii=False),
            )
        if self._sink:
            await self._sink(list(self.steps))

    async def record(
        self,
        stage: AgentStage,
        name: str,
        operation: Callable[[], Any],
        *,
        tool_name: Optional[str] = None,
        model: Optional[str] = None,
        input_summary: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> Any:
        step = AgentTraceStep(
            step_id=uuid.uuid4().hex[:12],
            stage=stage,
            name=name,
            status=AgentStepStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            tool_name=tool_name,
            model=model,
            input_summary=safe_summary(input_summary or {}),
            metrics=metrics or {},
        )
        self.steps.append(step)
        await self._emit()
        started = time.perf_counter()
        try:
            result = operation()
            if inspect.isawaitable(result):
                result = await result
            step.status = AgentStepStatus.COMPLETED
            step.output_summary = safe_summary(result)
            return result
        except Exception as exc:
            step.status = AgentStepStatus.FAILED
            step.error = safe_error(exc)
            raise
        finally:
            step.ended_at = datetime.now(timezone.utc)
            step.latency_ms = int((time.perf_counter() - started) * 1_000)
            await self._emit()
