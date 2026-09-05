#!/usr/bin/env python3
"""Build the two-layer external-brief planning dataset.

Layer 1 recovers a documented workflow from 11 case-study-derived briefs.
Layer 2 tests grounded planning over seven ZCOOL portfolio briefs and their
low-resolution published-outcome thumbnails. The second layer has no workflow
gold and must never be reported as trajectory accuracy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parents[1]
WORKFLOW_SOURCE = EVAL / "briefs.jsonl"
ZCOOL_SOURCE = EVAL / "zcool_briefs" / "zcool_briefs.jsonl"
OUTPUT = EXP / "dataset" / "external-briefs.jsonl"

STEP_VOCAB = [
    "intake_brief",
    "research",
    "principles",
    "process_model",
    "structure_spec",
    "prototype_test",
    "explore_concepts",
    "select_direction",
    "refine",
    "identity_system",
    "expand_assets",
    "learning_activities",
    "dieline",
    "production_file",
    "deliver",
]

VISIBLE_CONTEXT = {
    "BRF-BRAND-01": "Evolve an 85-year-old higher-education design institution for modern relevance. The identity must explain design as a method for creating responsible change, not merely visual styling, and work coherently from digital interfaces to signage, print and merchandise.",
    "BRF-BRAND-02": "Create the brand platform and visual identity for a global initiative working to make fashion circular and sustainable. It must unite brands, producers, retailers, nonprofits, innovators and funders while remaining bold, practical and accessible across campaigns and partner applications.",
    "BRF-BRAND-03": "Rebrand an established managed-portfolios program into its parent financial-services brand and launch it to several advisor and client audiences. The system must support English and French plus selected Chinese-language print materials, update persona-led communications and increase advisor awareness and adoption.",
    "BRF-ECOM-01": "Turn a set of raw product photographs into a high-conversion Tmall detail page. The job requires understanding the product and audience, choosing a defensible visual direction, and defining a page structure that communicates benefits and purchase information clearly.",
    "BRF-ECOM-03": "Plan one cohesive content-production system for a lean zero-sugar beverage brand with eight flavours. It must cover both ecommerce/retail product imagery and lifestyle/social content without losing the brand look, and deliver reusable assets for listings, ads, web, email and SMS.",
    "BRF-EDU-01": "Define a scalable visual and interaction system for a children's AI-learning product. The work must connect lesson structure and learning principles to repeatable content modules, character/graphic assets and final learning screens rather than treating each screen as an isolated illustration.",
    "BRF-EDU-02": "Design a beginner language-learning experience that teaches reusable sentence patterns. The plan must turn a learning objective into sound instructional principles and a coherent set of lesson activities and visual assets.",
    "BRF-MERCH-01": "Take an independent illustrator's original artwork from an early product idea to a small sellable merchandise line. Plan the product choices, repeatable making/fulfilment process and final sales-ready assets without assuming factory details that have not been supplied.",
    "BRF-MERCH-02": "Develop a culturally grounded cat-themed merchandise family inspired by a major museum property. Research the source culture, establish a repeatable product-development model, explore a coherent character/product direction and extend it into deliverable merchandise.",
    "BRF-PACK-01": "Take a selected fruit-wine packaging direction through the remaining work needed for production. Validate the market and product context, resolve the packaging system, prepare production-ready files and define the final handoff rather than stopping at a mockup.",
    "BRF-PACK-02": "Create shelf-ready packaging for a new pet-care tool that consumers may not immediately understand. The package must fit and protect the physical product, explain the benefit at retail, support client concept selection and end in an accurate printable structure for major retailers.",
}

WORKFLOW_CLASS = {
    "brand": "brand_visual_exploration",
    "product": "ecommerce_content",
    "education": "education_content",
    "merch": "merchandise_family",
    "packaging": "concept_to_production",
}

WORKFLOW_DELIVERABLES = {
    "BRF-BRAND-01": ["brand_strategy", "visual_identity", "brand_applications"],
    "BRF-BRAND-02": ["brand_strategy", "logo_system", "visual_identity", "campaign_key_visual"],
    "BRF-BRAND-03": ["visual_identity", "campaign_key_visual", "brand_applications"],
    "BRF-ECOM-01": ["ecommerce_content", "brand_applications"],
    "BRF-ECOM-03": ["product_photography", "ecommerce_content", "brand_applications"],
    "BRF-EDU-01": ["education_content_system", "brand_applications"],
    "BRF-EDU-02": ["education_content_system"],
    "BRF-MERCH-01": ["merchandise_family", "production_spec", "brand_applications"],
    "BRF-MERCH-02": ["merchandise_family", "visual_identity", "brand_applications"],
    "BRF-PACK-01": ["packaging_family", "production_spec", "dieline"],
    "BRF-PACK-02": ["structural_packaging", "prototype", "dieline", "production_spec"],
}

ZCOOL_GOLD = {
    "BRF-BRAND-04": ("brand_visual_exploration", ["logo_system", "visual_identity", "brand_applications"]),
    "BRF-BRAND-05": ("brand_visual_exploration", ["logo_system", "visual_identity", "brand_applications"]),
    "BRF-BRAND-06": ("brand_campaign", ["campaign_key_visual", "environmental_graphics", "brand_applications"]),
    "BRF-PACK-03": ("packaging_sku_series", ["logo_system", "packaging_family", "sku_differentiation", "brand_applications"]),
    "BRF-PACK-04": ("packaging_sku_series", ["logo_system", "packaging_family", "brand_applications"]),
    "BRF-PACK-05": ("packaging_sku_series", ["visual_identity", "packaging_family", "sku_differentiation"]),
    "BRF-PACK-06": ("concept_to_production", ["structural_packaging", "mockups", "production_spec"]),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workflow_rows() -> list[dict]:
    source = read_jsonl(WORKFLOW_SOURCE)
    if len(source) != 11:
        raise ValueError(f"expected 11 workflow rows, got {len(source)}")
    rows = []
    for item in source:
        if item.get("primary_intent") != "generate":
            raise ValueError(f"{item['id']}: missing upgraded primary_intent")
        expected_steps = item.get("expected_steps") or []
        if not expected_steps or any(step not in STEP_VOCAB for step in expected_steps):
            raise ValueError(f"{item['id']}: invalid workflow gold")
        rows.append({
            "schema_version": "external-brief-plan-v1",
            "id": item["id"],
            "layer": "case_study_workflow",
            "input": {
                "brief": VISIBLE_CONTEXT[item["id"]],
                "domain": item["domain"],
                "input_assets": [],
                "reference_policy": "none",
            },
            "expected": {
                "primary_intent": item["primary_intent"],
                "brief_class": WORKFLOW_CLASS[item["domain"]],
                "workflow_steps": expected_steps,
                "step_count": item["expected_step_count"],
                "deliverable_concepts": WORKFLOW_DELIVERABLES[item["id"]],
            },
            "protocol": {
                "mode": "plan_only",
                "max_user_turns": 1,
                "tools_allowed": False,
                "score_dimensions": ["intent", "step_f1", "step_order", "step_count", "boundary_awareness"],
                "hard_gates": ["schema_valid", "tool_call_free", "not_executed"],
            },
            "metadata": {
                "source_dataset": "eval/briefs.jsonl",
                "source_id": item["id"],
                "evidence": item["evidence"],
                "gold_semantics": "one documented public case-study workflow; not the only valid design process",
                "candidate_visible_provenance": False,
            },
        })
    return rows


def zcool_rows() -> list[dict]:
    source = read_jsonl(ZCOOL_SOURCE)
    if len(source) != 7:
        raise ValueError(f"expected 7 ZCOOL rows, got {len(source)}")
    rows = []
    for item in source:
        expected_class, expected_deliverables = ZCOOL_GOLD[item["id"]]
        assets = []
        for index, thumb in enumerate(item["assets"]["thumbnails"], start=1):
            path = EVAL / "zcool_briefs" / thumb["path"]
            if not path.is_file():
                raise FileNotFoundError(path)
            assets.append({
                "asset_id": f"{item['id']}-reference-{index}",
                "path": str(path.relative_to(EVAL)),
                "sha256": digest(path),
                "bytes": path.stat().st_size,
                "role": "published_outcome_reference",
            })
        rows.append({
            "schema_version": "external-brief-plan-v1",
            "id": item["id"],
            "layer": "portfolio_reference",
            "input": {
                "brief": item["brief"],
                "domain": item["domain"],
                "input_assets": assets,
                "reference_policy": "analyse as published outcome evidence; do not treat as a style input or copy it",
            },
            "expected": {
                "primary_intent": item["deliverable_intent"],
                "brief_class": expected_class,
                "workflow_steps": [],
                "step_count": None,
                "deliverable_concepts": expected_deliverables,
            },
            "protocol": {
                "mode": "reference_grounded_plan_only",
                "max_user_turns": 1,
                "tools_allowed": False,
                "score_dimensions": ["intent", "brief_class", "reference_coverage", "deliverable_recall", "boundary_awareness"],
                "hard_gates": ["schema_valid", "tool_call_free", "not_executed", "all_references_observed"],
            },
            "metadata": {
                "source_dataset": "eval/zcool_briefs/zcool_briefs.jsonl",
                "source_id": item["id"],
                "evidence": item["evidence"],
                "gold_semantics": "published outcome reference only; no workflow or rejected-direction ground truth",
                "candidate_visible_provenance": False,
                "rights": "internal evaluation only; low-resolution identification thumbnails",
            },
        })
    return rows


def main() -> int:
    rows = workflow_rows() + zcool_rows()
    if len(rows) != 18 or len({row["id"] for row in rows}) != 18:
        raise ValueError("external brief dataset must contain 18 unique rows")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(f"wrote {len(rows)} rows -> {OUTPUT}")
    print(f"sha256={digest(OUTPUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
