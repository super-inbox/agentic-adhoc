#!/usr/bin/env python3
"""Semantic, fixture, and lineage validation for Brief Bank v0.3."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from PIL import Image


HERE = Path(__file__).resolve().parent
DATASET = HERE / "briefs.v0.3.jsonl"
BASE = HERE / "briefs.v0.2.jsonl"
SEEDS = HERE.parent / "reddit_briefs" / "reddit_brief_seeds_2026-08-30.jsonl"
ASSET_PACKS = (
    (HERE.parent / "assets" / "reference-pack-v0.2", "manifest.jsonl"),
    (HERE.parent / "assets" / "brief-bank-v0.3", "manifest.jsonl"),
)

ID_RE = re.compile(r"^DAB-(L3|L4)-[A-Z]{2,4}-[0-9]{3}$")
CATEGORIES = {
    "brand_identity_directions", "existing_brand_campaign", "packaging_sku_family",
    "ecommerce_launch_suite", "multi_format_adaptation", "client_feedback_revision",
    "reference_to_original", "concept_to_factory_ready",
}
INTENTS = {"generate", "edit", "evaluate_rank", "export", "adapt"}
REQUIRED = {
    "id", "schema_version", "revision", "level", "category", "primary_intent",
    "secondary_intents", "language", "provenance", "user_context", "initial_query",
    "inputs", "constraints", "tools_available", "expected_workflow", "deliverables",
    "feedback", "messy_conditions", "rubric", "fixture_status", "capability_tags",
    "reference_contract", "context_conditions", "preference_memory", "project_state",
    "edit_parameters", "structured_artifacts", "human_checkpoints", "verification_contract",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: row is not an object")
        rows.append(value)
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset_catalog(errors: list[str]) -> dict[str, tuple[Path, dict[str, Any]]]:
    assets: dict[str, tuple[Path, dict[str, Any]]] = {}
    for root, manifest_name in ASSET_PACKS:
        for row in read_jsonl(root / manifest_name):
            asset_id = row.get("asset_id")
            if not asset_id or asset_id in assets:
                errors.append(f"asset manifest duplicate/missing id: {asset_id!r}")
                continue
            path = root / row["path"]
            if not path.is_file():
                errors.append(f"missing asset file: {path}")
                continue
            if path.stat().st_size != row.get("bytes"):
                errors.append(f"{asset_id}: byte count mismatch")
            if sha256(path) != row.get("sha256"):
                errors.append(f"{asset_id}: sha256 mismatch")
            try:
                with Image.open(path) as image:
                    if image.size != (row.get("width"), row.get("height")):
                        errors.append(f"{asset_id}: dimensions mismatch")
                    if image.mode != row.get("mode"):
                        errors.append(f"{asset_id}: mode mismatch")
            except OSError as exc:
                errors.append(f"{asset_id}: unreadable image: {exc}")
            assets[asset_id] = (root, row)
    return assets


def require_strings(value: Any, label: str, errors: list[str], *, minimum: int = 1) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum:
        errors.append(f"{label}: expected at least {minimum} string(s)")
        return []
    if any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{label}: contains non-string/empty item")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{label}: duplicate items")
    return value


def validate_row(row: dict[str, Any], assets: dict[str, tuple[Path, dict[str, Any]]], errors: list[str]) -> set[str]:
    case_id = row.get("id", "<missing-id>")
    prefix = case_id
    missing = REQUIRED - row.keys()
    if missing:
        errors.append(f"{prefix}: missing fields {sorted(missing)}")
        return set()
    if row["schema_version"] != "0.3":
        errors.append(f"{prefix}: schema_version is not 0.3")
    if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
        errors.append(f"{prefix}: invalid id")
    if row["level"] not in {"L3", "L4"} or f"-{row['level']}-" not in case_id:
        errors.append(f"{prefix}: invalid/inconsistent level")
    if row["category"] not in CATEGORIES:
        errors.append(f"{prefix}: invalid category")
    if row["primary_intent"] not in INTENTS:
        errors.append(f"{prefix}: invalid primary intent")
    secondaries = require_strings(row["secondary_intents"], f"{prefix}.secondary_intents", errors, minimum=0)
    if set(secondaries) - INTENTS or row["primary_intent"] in secondaries:
        errors.append(f"{prefix}: invalid secondary intent set")
    if row["language"] not in {"zh-CN", "en", "mixed"}:
        errors.append(f"{prefix}: invalid language")
    if not isinstance(row["initial_query"], str) or len(row["initial_query"].strip()) < 20:
        errors.append(f"{prefix}: initial query too short")
    if row["fixture_status"] != "ready":
        errors.append(f"{prefix}: fixture is not ready")

    revision = row["revision"]
    if revision.get("base_dataset") not in {"briefs.v0.2.jsonl", "reddit_brief_seeds_2026-08-30.jsonl"}:
        errors.append(f"{prefix}.revision: invalid base dataset")
    if not isinstance(revision.get("business_scope_changed"), bool):
        errors.append(f"{prefix}.revision: business_scope_changed must be boolean")
    require_strings(revision.get("protocol_changes"), f"{prefix}.revision.protocol_changes", errors)

    provenance = row["provenance"]
    if provenance.get("kind") not in {
        "reverse_constructed", "internal_scenario", "controlled_synthetic",
        "anonymized_real", "public_corpus_grounded",
    }:
        errors.append(f"{prefix}: invalid provenance kind")
    require_strings(provenance.get("source_refs"), f"{prefix}.provenance.source_refs", errors)
    if provenance.get("customer_data") not in {True, False}:
        errors.append(f"{prefix}: provenance customer_data must be boolean")

    inputs = row["inputs"]
    if not isinstance(inputs, list) or not inputs:
        errors.append(f"{prefix}: no inputs")
        inputs = []
    input_ids: set[str] = set()
    provided_ids: set[str] = set()
    asset_input_ids: set[str] = set()
    referenced_assets: set[str] = set()
    has_missing = False
    for item in inputs:
        input_id = item.get("id")
        if not isinstance(input_id, str) or not input_id or input_id in input_ids:
            errors.append(f"{prefix}: invalid/duplicate input id {input_id!r}")
            continue
        input_ids.add(input_id)
        availability = item.get("availability")
        if availability == "intentionally_missing":
            has_missing = True
            if item.get("asset_id") or item.get("content"):
                errors.append(f"{prefix}.{input_id}: missing input carries content")
            continue
        if availability != "provided":
            errors.append(f"{prefix}.{input_id}: invalid availability")
            continue
        provided_ids.add(input_id)
        asset_id, content = item.get("asset_id"), item.get("content")
        if bool(asset_id) == bool(content):
            errors.append(f"{prefix}.{input_id}: needs exactly one of asset_id/content")
        if asset_id:
            asset_input_ids.add(input_id)
            referenced_assets.add(asset_id)
            if asset_id not in assets:
                errors.append(f"{prefix}.{input_id}: unknown asset {asset_id}")

    constraints = row["constraints"]
    for key in ("hard", "soft", "negative"):
        require_strings(constraints.get(key), f"{prefix}.constraints.{key}", errors)
    require_strings(row["tools_available"], f"{prefix}.tools_available", errors)

    workflow = row["expected_workflow"]
    minimum = 4 if row["level"] == "L4" else 3
    if not isinstance(workflow, list) or len(workflow) < minimum:
        errors.append(f"{prefix}: {row['level']} needs >= {minimum} checkpoints")
        workflow = []
    checkpoints = []
    for item in workflow:
        checkpoints.append(item.get("checkpoint"))
        require_strings(item.get("required_outcomes"), f"{prefix}.workflow.{item.get('checkpoint')}", errors)
    if len(checkpoints) != len(set(checkpoints)):
        errors.append(f"{prefix}: duplicate workflow checkpoints")

    deliverables = row["deliverables"]
    if not isinstance(deliverables, list) or not deliverables:
        errors.append(f"{prefix}: no deliverables")
        deliverables = []
    deliverable_ids = []
    for item in deliverables:
        deliverable_ids.append(item.get("id"))
        require_strings(item.get("formats"), f"{prefix}.deliverable.formats", errors)
        require_strings(item.get("requirements"), f"{prefix}.deliverable.requirements", errors)
        if item.get("stage") not in {"intermediate", "final"} or not isinstance(item.get("count"), int) or item["count"] < 1:
            errors.append(f"{prefix}: invalid deliverable {item.get('id')}")
    if len(deliverable_ids) != len(set(deliverable_ids)) or "final" not in {item.get("stage") for item in deliverables}:
        errors.append(f"{prefix}: duplicate deliverable id or no final deliverable")
    if row["level"] == "L4" and "intermediate" not in {item.get("stage") for item in deliverables}:
        errors.append(f"{prefix}: L4 needs an intermediate deliverable")

    feedback = row["feedback"]
    if not isinstance(feedback, list):
        errors.append(f"{prefix}: feedback must be a list")
        feedback = []
    if row["level"] == "L4" and not feedback:
        errors.append(f"{prefix}: L4 needs feedback")
    for index, item in enumerate(feedback):
        if item.get("after_checkpoint") not in checkpoints:
            errors.append(f"{prefix}.feedback[{index}]: unknown checkpoint")
        for key in ("turn_id", "session_id", "input_version", "expected_version", "message"):
            if not isinstance(item.get(key), str) or not item[key]:
                errors.append(f"{prefix}.feedback[{index}]: missing {key}")
        require_strings(item.get("expected_changes"), f"{prefix}.feedback[{index}].changes", errors)
        require_strings(item.get("invariants"), f"{prefix}.feedback[{index}].invariants", errors)

    if has_missing and not any(item.get("type") == "missing_asset" for item in row["messy_conditions"]):
        errors.append(f"{prefix}: missing input lacks missing_asset recovery condition")

    weights = row["rubric"].get("checkpoint_weights")
    if not isinstance(weights, dict) or len(weights) < 3 or any(not isinstance(x, (int, float)) or x < 0 for x in weights.values()):
        errors.append(f"{prefix}: invalid rubric weights")
    elif abs(sum(weights.values()) - 1.0) > 1e-9:
        errors.append(f"{prefix}: rubric weights sum to {sum(weights.values())}")
    require_strings(row["rubric"].get("hard_gates"), f"{prefix}.rubric.hard_gates", errors)

    contracts = row["reference_contract"]
    contract_ids = {item.get("input_id") for item in contracts if isinstance(item, dict)}
    if contract_ids != asset_input_ids or len(contracts) != len(contract_ids):
        errors.append(f"{prefix}: reference contracts {sorted(str(x) for x in contract_ids)} != asset inputs {sorted(asset_input_ids)}")
    for item in contracts:
        require_strings(item.get("allowed_influence"), f"{prefix}.reference_contract.allowed_influence", errors)

    conditions = row["context_conditions"]
    if not isinstance(conditions, list) or not conditions:
        errors.append(f"{prefix}: no context condition")
    for condition in conditions:
        included = condition.get("include_input_ids")
        if not isinstance(included, list) or set(included) - provided_ids:
            errors.append(f"{prefix}: condition includes unavailable input")
        if condition.get("id") == "reference_grounded" and set(included or []) != provided_ids:
            errors.append(f"{prefix}: reference_grounded must include all provided inputs")

    state = row["project_state"]
    if state.get("starting_version") != "v0" or set(state.get("editable_targets", [])) != set(deliverable_ids):
        errors.append(f"{prefix}: invalid project state")
    if (
        feedback
        and row["revision"].get("base_dataset") == "reddit_brief_seeds_2026-08-30.jsonl"
        and state.get("resume_policy") != "checkpoint_and_version"
    ):
        errors.append(f"{prefix}: feedback episode must use checkpoint_and_version")

    artifact_names = {item.get("name") for item in row["structured_artifacts"]}
    if not {"verification.json", "trajectory.jsonl"} <= artifact_names:
        errors.append(f"{prefix}: missing verification/trajectory artifacts")
    if row["level"] == "L4" and not row["human_checkpoints"]:
        errors.append(f"{prefix}: L4 needs human checkpoint")
    for item in row["human_checkpoints"]:
        if item.get("after_checkpoint") not in checkpoints or item.get("required") is not True:
            errors.append(f"{prefix}: invalid human checkpoint")

    verification = row["verification_contract"]
    require_strings(verification.get("checks"), f"{prefix}.verification.checks", errors)
    if verification.get("evidence_required") is not True or verification.get("failure_policy") != "block_delivery_on_hard_gate":
        errors.append(f"{prefix}: invalid verification policy")
    return referenced_assets


def main() -> int:
    errors: list[str] = []
    rows = read_jsonl(DATASET)
    assets = asset_catalog(errors)
    ids = [row.get("id") for row in rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate dataset ids")
    referenced_assets: set[str] = set()
    for row in rows:
        referenced_assets |= validate_row(row, assets, errors)

    core = [row for row in rows if row["revision"]["base_dataset"] == "briefs.v0.2.jsonl"]
    external = [row for row in rows if row["revision"]["base_dataset"] == "reddit_brief_seeds_2026-08-30.jsonl"]
    if (len(rows), len(core), len(external)) != (35, 24, 11):
        errors.append(f"expected total/core/external 35/24/11, found {len(rows)}/{len(core)}/{len(external)}")

    base_by_id = {row["id"]: row for row in read_jsonl(BASE)}
    for row in core:
        base = base_by_id.get(row["id"])
        if not base:
            errors.append(f"{row['id']}: not in v0.2 core")
            continue
        expected = json.loads(json.dumps(base))
        expected["schema_version"] = "0.3"
        expected["revision"] = {
            "base_dataset": "briefs.v0.2.jsonl",
            "base_brief_id": base["id"],
            "business_scope_changed": False,
            "protocol_changes": ["schema-only migration into the v0.3 core partition; episode contract unchanged"],
        }
        if row != expected:
            errors.append(f"{row['id']}: v0.3 changed a frozen v0.2 core field")

    seed_rows = [row for row in read_jsonl(SEEDS) if row.get("record_type") == "case"]
    ready_seed_ids = {row["id"] for row in seed_rows if row.get("brief_readiness") == "ready_to_author"}
    imported_seed_ids = {row["revision"]["base_brief_id"] for row in external}
    if imported_seed_ids != ready_seed_ids:
        errors.append(f"external partition does not exactly match 11 ready seeds: {sorted(imported_seed_ids ^ ready_seed_ids)}")
    for row in external:
        if row["provenance"]["kind"] != "public_corpus_grounded" or row["provenance"]["customer_data"]:
            errors.append(f"{row['id']}: external provenance boundary violated")

    pairs = (
        ("v03-robot-speech-bubble-source", "v03-robot-speech-bubble-mask"),
        ("v03-australian-empty-road", "v03-australian-road-edit-mask"),
    )
    for source_id, mask_id in pairs:
        source = assets[source_id][1]
        mask = assets[mask_id][1]
        if (source["width"], source["height"]) != (mask["width"], mask["height"]) or mask["mode"] != "L":
            errors.append(f"mask geometry mismatch: {source_id} / {mask_id}")

    summary = {
        "schema_version": "0.3",
        "rows": len(rows),
        "core_rows": len(core),
        "external_rows": len(external),
        "levels": dict(Counter(row["level"] for row in rows)),
        "categories": dict(Counter(row["category"] for row in rows)),
        "primary_intents": dict(Counter(row["primary_intent"] for row in rows)),
        "referenced_assets": len(referenced_assets),
        "dataset_sha256": sha256(DATASET),
        "errors": len(errors),
    }
    (HERE / "v0.3-validation-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
