from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from app.agent_runtime.registry import AgentAbstention, ToolContext, ToolRegistry, ToolSpec
from app.agent_runtime.rendering import (
    render_tryon_poster,
    render_vote_report,
    split_vote_candidates,
    validate_image_bytes,
)
from app.agent_runtime.schemas import (
    AgentArtifactKind,
    AgentStage,
    VerificationVerdict,
    VoteAnalysis,
)
from app.agent_runtime.services import DesignAgentServices, aggregate_vote_draft


TRYON_DIRECTIONS = (
    "Studio product hero · premium catalog lighting",
    "Editorial lifestyle · confident social campaign",
    "Marketplace detail · clean conversion-focused composition",
    "Seasonal campaign · bold color-block environment",
)


def _combine_verdicts(
    deterministic_hard: List[str],
    deterministic_repairable: List[str],
    model_verdict: VerificationVerdict,
) -> VerificationVerdict:
    hard = list(dict.fromkeys([*deterministic_hard, *model_verdict.hard_failures]))
    repairable = list(
        dict.fromkeys([*deterministic_repairable, *model_verdict.repairable_failures])
    )
    passed = model_verdict.passed and not hard and not repairable
    repair_instruction = model_verdict.repair_instruction
    if not repair_instruction and repairable:
        repair_instruction = "; ".join(repairable)
    return VerificationVerdict(
        passed=passed,
        scores=model_verdict.scores,
        hard_failures=hard,
        repairable_failures=repairable,
        repair_instruction=repair_instruction,
        retry_scope=model_verdict.retry_scope,
    )


def build_tool_registry(services: DesignAgentServices) -> ToolRegistry:
    registry = ToolRegistry()

    async def analyze_vote(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
        candidates = args.get("candidate_images")
        if candidates is None:
            source_images = await asyncio.gather(
                *(services.image_loader.load(source) for source in args["image_urls"])
            )
            candidates = split_vote_candidates(list(source_images))
        draft = await services.gateway.analyze_vote(
            args["prompt"],
            candidates,
            args.get("repair_instruction"),
        )
        if not draft.valid_variants:
            raise AgentAbstention(
                "INSUFFICIENT_CANDIDATES",
                "; ".join(draft.issues) or "The input does not contain four usable designs.",
            )
        analysis = aggregate_vote_draft(draft)
        return {"candidate_images": candidates, "analysis": analysis}

    async def make_vote_report(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
        analysis = VoteAnalysis.model_validate(args["analysis"])
        report = await asyncio.to_thread(
            render_vote_report,
            analysis,
            args["candidate_images"],
        )
        return {"report_bytes": report}

    async def verify_vote(args: Dict[str, Any], _context: ToolContext) -> VerificationVerdict:
        analysis = VoteAnalysis.model_validate(args["analysis"])
        hard: List[str] = []
        repairable: List[str] = []
        if len(analysis.variants) != 4:
            hard.append("analysis does not contain four variants")
        if sum(analysis.overall.values()) != 100:
            repairable.append("overall vote distribution does not sum to 100")
        if any(sum(segment.votes.values()) != 100 for segment in analysis.segments):
            repairable.append("one or more segment vote distributions do not sum to 100")
        if abs(sum(segment.share for segment in analysis.segments) - 1.0) > 0.02:
            repairable.append("segment shares do not sum to 1")
        expected_winner = max(analysis.overall, key=analysis.overall.get)
        if expected_winner != analysis.winner:
            repairable.append("winner does not match the aggregated vote")
        report_failures = validate_image_bytes(args["report_bytes"], min_side=900)
        repairable.extend(report_failures)
        model_verdict = await services.gateway.review_vote(
            args["prompt"],
            args["candidate_images"],
            analysis,
        )
        for name, score in model_verdict.scores.items():
            if score < 3.0:
                repairable.append(f"{name} score below 3.0")
        return _combine_verdicts(hard, repairable, model_verdict)

    async def store_vote(args: Dict[str, Any], context: ToolContext) -> List[Any]:
        analysis = VoteAnalysis.model_validate(args["analysis"])
        report_artifact = await services.artifact_store.put(
            context.run_id,
            "design-vote-report.png",
            args["report_bytes"],
            "image/png",
            AgentArtifactKind.REPORT,
            "AI simulated vote report",
            {"winner": analysis.winner, "simulated": True},
        )
        manifest = analysis.model_dump_json(indent=2).encode("utf-8")
        manifest_artifact = await services.artifact_store.put(
            context.run_id,
            "design-vote-analysis.json",
            manifest,
            "application/json",
            AgentArtifactKind.MANIFEST,
            "Structured vote analysis",
            {"simulated": True},
        )
        return [report_artifact, manifest_artifact]

    async def generate_tryon(args: Dict[str, Any], _context: ToolContext) -> Dict[str, Any]:
        source_assets = args.get("source_assets")
        if source_assets:
            selfie = source_assets["selfie"]
            product = source_assets.get("product")
        else:
            selfie = await services.image_loader.load(args["image_urls"][0])
            product = (
                await services.image_loader.load(args["image_urls"][1])
                if len(args["image_urls"]) > 1
                else None
            )
        count = args["output_count"]
        existing: List[Optional[bytes]] = list(args.get("existing_posters") or [None] * count)
        if len(existing) < count:
            existing.extend([None] * (count - len(existing)))
        raw_retry_scope = args.get("retry_scope")
        retry_scope = (
            {int(value) for value in raw_retry_scope}
            if raw_retry_scope
            else set(range(count))
        )
        for index in range(count):
            if existing[index] is not None and index not in retry_scope:
                continue
            raw = await services.gateway.generate_tryon(
                selfie,
                product,
                args["prompt"],
                TRYON_DIRECTIONS[index],
                args.get("repair_instruction"),
            )
            existing[index] = await asyncio.to_thread(
                render_tryon_poster,
                raw,
                TRYON_DIRECTIONS[index],
                args["prompt"],
            )
        posters = [poster for poster in existing if poster is not None]
        if len(posters) != count:
            raise RuntimeError("Try-on generator did not produce every requested poster.")
        return {
            "source_assets": {"selfie": selfie, "product": product},
            "posters": posters,
            "directions": list(TRYON_DIRECTIONS[:count]),
            "concept_only": product is None,
        }

    async def verify_tryon(args: Dict[str, Any], _context: ToolContext) -> VerificationVerdict:
        hard: List[str] = []
        repairable: List[str] = []
        posters: List[bytes] = args["posters"]
        deterministic_retry_scope: List[str] = []
        for index, poster in enumerate(posters):
            image_failures = validate_image_bytes(poster, min_side=900)
            if image_failures:
                deterministic_retry_scope.append(str(index))
            for failure in image_failures:
                repairable.append(f"poster {index}: {failure}")
        review = await services.gateway.review_tryon(
            args["source_assets"]["selfie"],
            args["source_assets"].get("product"),
            args["prompt"],
            posters,
        )
        scores: Dict[str, float] = {}
        retry_scope: List[str] = list(deterministic_retry_scope)
        expected_indices = set(range(len(posters)))
        returned_indices = {score.index for score in review.posters}
        if len(review.posters) != len(posters) or returned_indices != expected_indices:
            hard.append("visual verifier returned invalid poster score indices")
        for score in review.posters:
            if score.index not in expected_indices:
                continue
            values = [
                score.identity,
                score.anatomy,
                score.instruction_following,
                score.layout,
            ]
            has_product = args["source_assets"].get("product") is not None
            if has_product and score.product_fidelity is None:
                retry_scope.append(str(score.index))
                repairable.append(f"poster {score.index}: product fidelity was not scored")
            if score.product_fidelity is not None:
                values.append(score.product_fidelity)
            minimum = min(values)
            scores[f"poster_{score.index}"] = minimum
            if minimum < 3.5 or score.failures:
                retry_scope.append(str(score.index))
                reason = ", ".join(score.failures) or f"minimum visual score {minimum:.1f}"
                repairable.append(f"poster {score.index}: {reason}")
        return VerificationVerdict(
            passed=not hard and not repairable,
            scores=scores,
            hard_failures=hard,
            repairable_failures=list(dict.fromkeys(repairable)),
            repair_instruction="; ".join(dict.fromkeys(repairable)) if repairable else None,
            retry_scope=list(dict.fromkeys(retry_scope)),
        )

    async def store_tryon(args: Dict[str, Any], context: ToolContext) -> List[Any]:
        artifacts = []
        for index, (poster, direction) in enumerate(zip(args["posters"], args["directions"])):
            artifacts.append(
                await services.artifact_store.put(
                    context.run_id,
                    f"tryon-poster-{index + 1}.jpg",
                    poster,
                    "image/jpeg",
                    AgentArtifactKind.IMAGE,
                    direction,
                    {
                        "index": index,
                        "concept_only": args["concept_only"],
                        "contains_personal_image": True,
                    },
                )
            )
        manifest_payload = {
            "kind": "tryon_poster",
            "concept_only": args["concept_only"],
            "directions": args["directions"],
            "disclaimer": (
                "AI outfit concept; no exact merchandise fidelity is claimed."
                if args["concept_only"]
                else "AI virtual try-on using a supplied merchandise reference."
            ),
        }
        artifacts.append(
            await services.artifact_store.put(
                context.run_id,
                "tryon-manifest.json",
                json.dumps(manifest_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json",
                AgentArtifactKind.MANIFEST,
                "Try-on run manifest",
                {"contains_personal_image": False},
            )
        )
        return artifacts

    analysis_model = services.gateway.model_name
    generation_model = services.gateway.generation_model_name

    def tryon_credit_estimate(args: Dict[str, Any]) -> float:
        retry_scope = args.get("retry_scope")
        generated_count = len(retry_scope) if retry_scope else int(args["output_count"])
        return 10.0 * generated_count

    registry.register(
        ToolSpec(
            name="analyze_design_vote",
            description="Visually analyze four candidate designs and simulate category-specific preferences.",
            stage=AgentStage.GENERATE,
            handler=analyze_vote,
            model=analysis_model,
        )
    )
    registry.register(
        ToolSpec(
            name="render_design_vote_report",
            description="Render an honest, deterministic vote decision graphic.",
            stage=AgentStage.GENERATE,
            handler=make_vote_report,
        )
    )
    registry.register(
        ToolSpec(
            name="verify_design_vote",
            description="Check vote math, report integrity, and visual grounding.",
            stage=AgentStage.VERIFY,
            handler=verify_vote,
            model=analysis_model,
        )
    )
    registry.register(
        ToolSpec(
            name="store_design_vote_artifacts",
            description="Persist the vote report and structured analysis.",
            stage=AgentStage.PRESENT,
            handler=store_vote,
        )
    )
    registry.register(
        ToolSpec(
            name="generate_tryon_posters",
            description="Generate and deterministically typeset ecommerce try-on posters.",
            stage=AgentStage.GENERATE,
            handler=generate_tryon,
            requires_paid_generation=True,
            model=generation_model,
            credit_estimator=tryon_credit_estimate,
        )
    )
    registry.register(
        ToolSpec(
            name="verify_tryon_posters",
            description="Verify identity, product fidelity, anatomy, instruction following, and layout.",
            stage=AgentStage.VERIFY,
            handler=verify_tryon,
            model=analysis_model,
        )
    )
    registry.register(
        ToolSpec(
            name="store_tryon_artifacts",
            description="Persist final try-on posters and their manifest.",
            stage=AgentStage.PRESENT,
            handler=store_tryon,
        )
    )
    return registry
