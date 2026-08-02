from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from app.agent_runtime.registry import ToolContext, ToolRegistry
from app.agent_runtime.schemas import (
    AgentCapabilityDecision,
    AgentPlan,
    AgentRunRequest,
    AgentTaskType,
    AgentToolCall,
    VerificationVerdict,
)


@dataclass
class SkillContext:
    run_id: str
    request: AgentRunRequest
    tools: ToolRegistry
    tool_context: ToolContext


class DesignSkill(Protocol):
    skill_id: str
    task_type: AgentTaskType

    def capability(self, request: AgentRunRequest) -> AgentCapabilityDecision: ...

    def plan(
        self,
        request: AgentRunRequest,
        iteration: int,
        feedback: Optional[VerificationVerdict],
    ) -> AgentPlan: ...

    async def execute(
        self,
        context: SkillContext,
        iteration: int,
        previous: Optional[Dict[str, Any]],
        feedback: Optional[VerificationVerdict],
    ) -> Dict[str, Any]: ...

    async def verify(
        self,
        context: SkillContext,
        execution: Dict[str, Any],
    ) -> VerificationVerdict: ...

    async def present(
        self,
        context: SkillContext,
        execution: Dict[str, Any],
    ) -> List[Any]: ...

    def summary(self, execution: Dict[str, Any]) -> str: ...


class DesignVoteSkill:
    skill_id = "design-vote"
    task_type = AgentTaskType.DESIGN_VOTE

    def capability(self, request: AgentRunRequest) -> AgentCapabilityDecision:
        if len(request.image_urls) not in (1, 4):
            return AgentCapabilityDecision(
                supported=False,
                code="INVALID_CANDIDATE_COUNT",
                message="Design vote requires one four-panel board or four separate images.",
            )
        return AgentCapabilityDecision(supported=True)

    def plan(
        self,
        request: AgentRunRequest,
        iteration: int,
        feedback: Optional[VerificationVerdict],
    ) -> AgentPlan:
        return AgentPlan(
            skill_id=self.skill_id,
            iteration=iteration,
            repair_instruction=feedback.repair_instruction if feedback else None,
            calls=[
                AgentToolCall(tool="analyze_design_vote", purpose="ground preferences in visible design cues"),
                AgentToolCall(tool="render_design_vote_report", purpose="render deterministic decision graphic"),
                AgentToolCall(tool="verify_design_vote", purpose="verify math and visual grounding"),
            ],
        )

    async def execute(
        self,
        context: SkillContext,
        iteration: int,
        previous: Optional[Dict[str, Any]],
        feedback: Optional[VerificationVerdict],
    ) -> Dict[str, Any]:
        analyzed = await context.tools.invoke(
            "analyze_design_vote",
            {
                "prompt": context.request.prompt,
                "image_urls": context.request.image_urls,
                "candidate_images": previous.get("candidate_images") if previous else None,
                "repair_instruction": feedback.repair_instruction if feedback else None,
            },
            context.tool_context,
        )
        rendered = await context.tools.invoke(
            "render_design_vote_report",
            {
                "analysis": analyzed["analysis"],
                "candidate_images": analyzed["candidate_images"],
            },
            context.tool_context,
        )
        return {**analyzed, **rendered}

    async def verify(
        self,
        context: SkillContext,
        execution: Dict[str, Any],
    ) -> VerificationVerdict:
        return await context.tools.invoke(
            "verify_design_vote",
            {
                "prompt": context.request.prompt,
                "analysis": execution["analysis"],
                "candidate_images": execution["candidate_images"],
                "report_bytes": execution["report_bytes"],
            },
            context.tool_context,
        )

    async def present(
        self,
        context: SkillContext,
        execution: Dict[str, Any],
    ) -> List[Any]:
        return await context.tools.invoke(
            "store_design_vote_artifacts",
            {
                "analysis": execution["analysis"],
                "report_bytes": execution["report_bytes"],
            },
            context.tool_context,
        )

    def summary(self, execution: Dict[str, Any]) -> str:
        analysis = execution["analysis"]
        return (
            f"AI 模拟投票完成：{analysis.winner} 方案以 "
            f"{analysis.overall[analysis.winner]}% 位列第一。{analysis.recommendation}"
        )


class TryOnPosterSkill:
    skill_id = "tryon-poster"
    task_type = AgentTaskType.TRYON_POSTER
    _requires_product = re.compile(
        r"商品|SKU|同款|真实试穿|product\s+try|exact\s+(?:product|garment)|garment\s+reference",
        re.IGNORECASE,
    )

    def capability(self, request: AgentRunRequest) -> AgentCapabilityDecision:
        if not request.image_urls:
            return AgentCapabilityDecision(
                supported=False,
                code="MISSING_SELFIE",
                message="Try-on poster generation requires a selfie as the first image.",
            )
        if self._requires_product.search(request.prompt) and len(request.image_urls) < 2:
            return AgentCapabilityDecision(
                supported=False,
                code="MISSING_PRODUCT_IMAGE",
                message="Exact merchandise try-on requires a product image as the second input.",
            )
        if not request.allow_paid_generation:
            return AgentCapabilityDecision(
                supported=False,
                code="PAID_GENERATION_NOT_APPROVED",
                message="Try-on poster generation requires allow_paid_generation=true.",
            )
        return AgentCapabilityDecision(supported=True)

    def plan(
        self,
        request: AgentRunRequest,
        iteration: int,
        feedback: Optional[VerificationVerdict],
    ) -> AgentPlan:
        return AgentPlan(
            skill_id=self.skill_id,
            iteration=iteration,
            repair_instruction=feedback.repair_instruction if feedback else None,
            calls=[
                AgentToolCall(tool="generate_tryon_posters", purpose="generate ecommerce poster directions"),
                AgentToolCall(tool="verify_tryon_posters", purpose="verify identity, product, anatomy, and layout"),
            ],
        )

    async def execute(
        self,
        context: SkillContext,
        iteration: int,
        previous: Optional[Dict[str, Any]],
        feedback: Optional[VerificationVerdict],
    ) -> Dict[str, Any]:
        args: Dict[str, Any] = {
            "prompt": context.request.prompt,
            "image_urls": context.request.image_urls,
            "output_count": context.request.output_count,
            "repair_instruction": feedback.repair_instruction if feedback else None,
        }
        if previous:
            args.update(
                {
                    "source_assets": previous.get("source_assets"),
                    "existing_posters": previous.get("posters"),
                    "retry_scope": feedback.retry_scope if feedback else [],
                }
            )
        return await context.tools.invoke(
            "generate_tryon_posters",
            args,
            context.tool_context,
        )

    async def verify(
        self,
        context: SkillContext,
        execution: Dict[str, Any],
    ) -> VerificationVerdict:
        return await context.tools.invoke(
            "verify_tryon_posters",
            {
                "prompt": context.request.prompt,
                "source_assets": execution["source_assets"],
                "posters": execution["posters"],
            },
            context.tool_context,
        )

    async def present(
        self,
        context: SkillContext,
        execution: Dict[str, Any],
    ) -> List[Any]:
        return await context.tools.invoke(
            "store_tryon_artifacts",
            execution,
            context.tool_context,
        )

    def summary(self, execution: Dict[str, Any]) -> str:
        qualifier = "穿搭概念" if execution["concept_only"] else "商品参考试穿"
        return f"已生成 {len(execution['posters'])} 张{qualifier}电商海报，并通过视觉校验。"


class SkillRegistry:
    def __init__(self, skills: Optional[List[DesignSkill]] = None):
        self._skills: Dict[AgentTaskType, DesignSkill] = {}
        for skill in skills or [DesignVoteSkill(), TryOnPosterSkill()]:
            self._skills[skill.task_type] = skill

    def get(self, task_type: AgentTaskType) -> DesignSkill:
        if task_type not in self._skills:
            raise KeyError(task_type)
        return self._skills[task_type]


def infer_task_type(request: AgentRunRequest) -> Optional[AgentTaskType]:
    if request.task_type != AgentTaskType.AUTO:
        return request.task_type
    prompt = request.prompt.lower()
    if re.search(r"投票|哪款|哪个设计|包装.*(?:好|质感)|vote|which\s+(?:design|packaging)|compare", prompt):
        return AgentTaskType.DESIGN_VOTE
    if re.search(r"自拍|穿搭|试穿|电商海报|outfit|try[- ]?on|ecommerce\s+poster", prompt):
        return AgentTaskType.TRYON_POSTER
    return None
