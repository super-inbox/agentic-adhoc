#!/usr/bin/env python3
"""Validate the L3/L4 Design Agent Brief Bank without third-party packages."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_BRIEFS = HERE / "briefs.v0.1.jsonl"
REFERENCE_ROOT = HERE.parent / "assets" / "reference-pack-v0.2"
REFERENCE_MANIFEST = REFERENCE_ROOT / "manifest.jsonl"

CATEGORIES = {
    "brand_identity_directions",
    "existing_brand_campaign",
    "packaging_sku_family",
    "ecommerce_launch_suite",
    "multi_format_adaptation",
    "client_feedback_revision",
    "reference_to_original",
    "concept_to_factory_ready",
}
INTENTS = {"generate", "edit", "evaluate_rank", "export", "adapt"}
PROVENANCE_KINDS = {
    "reverse_constructed",
    "internal_scenario",
    "controlled_synthetic",
    "anonymized_real",
}
MESSY_TYPES = {
    "missing_asset",
    "conflicting_references",
    "late_scope_change",
    "invalid_spec",
    "ambiguous_feedback",
    "tool_failure",
    "copy_error",
    "constraint_conflict",
}
REQUIRED_FIELDS = {
    "id",
    "schema_version",
    "level",
    "category",
    "primary_intent",
    "secondary_intents",
    "language",
    "provenance",
    "user_context",
    "initial_query",
    "inputs",
    "constraints",
    "tools_available",
    "expected_workflow",
    "deliverables",
    "feedback",
    "messy_conditions",
    "rubric",
    "fixture_status",
}
ID_RE = re.compile(r"^DAB-(L3|L4)-[A-Z]{2,4}-[0-9]{3}$")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: row must be an object")
            value["__line__"] = line_number
            rows.append(value)
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_assets(errors: list[str]) -> dict[str, dict[str, Any]]:
    try:
        rows = load_jsonl(REFERENCE_MANIFEST)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        return {}
    assets: dict[str, dict[str, Any]] = {}
    for row in rows:
        asset_id = row.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            errors.append(f"reference manifest line {row['__line__']}: missing asset_id")
            continue
        if asset_id in assets:
            errors.append(f"reference manifest: duplicate asset_id {asset_id}")
            continue
        assets[asset_id] = row
    return assets


def require_nonempty_strings(
    value: Any, *, label: str, errors: list[str], minimum: int = 1
) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum:
        errors.append(f"{label}: expected at least {minimum} item(s)")
        return []
    if any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{label}: every item must be a non-empty string")
        return []
    return value


def validate_row(
    row: dict[str, Any],
    *,
    assets: dict[str, dict[str, Any]],
    validated_assets: set[str],
    errors: list[str],
) -> None:
    line = row.get("__line__", "?")
    case_id = row.get("id", f"line-{line}")
    prefix = f"{case_id} (line {line})"

    missing = sorted(REQUIRED_FIELDS - row.keys())
    if missing:
        errors.append(f"{prefix}: missing fields {missing}")
        return

    if row["schema_version"] != "0.1":
        errors.append(f"{prefix}: schema_version must be 0.1")
    if not isinstance(case_id, str) or not ID_RE.fullmatch(case_id):
        errors.append(f"{prefix}: invalid id")
    level = row["level"]
    if level not in {"L3", "L4"}:
        errors.append(f"{prefix}: level must be L3 or L4")
    elif isinstance(case_id, str) and f"-{level}-" not in case_id:
        errors.append(f"{prefix}: id and level disagree")
    if row["category"] not in CATEGORIES:
        errors.append(f"{prefix}: unknown category {row['category']!r}")
    if row["primary_intent"] not in INTENTS:
        errors.append(f"{prefix}: unknown primary_intent {row['primary_intent']!r}")
    secondaries = require_nonempty_strings(
        row["secondary_intents"], label=f"{prefix}.secondary_intents", errors=errors
    )
    if any(item not in INTENTS for item in secondaries):
        errors.append(f"{prefix}: unknown secondary intent")
    if row["primary_intent"] in secondaries:
        errors.append(f"{prefix}: primary intent repeated in secondary_intents")
    if row["language"] not in {"zh-CN", "en", "mixed"}:
        errors.append(f"{prefix}: invalid language")

    provenance = row["provenance"]
    if not isinstance(provenance, dict):
        errors.append(f"{prefix}.provenance: expected object")
    else:
        if provenance.get("kind") not in PROVENANCE_KINDS:
            errors.append(f"{prefix}.provenance: invalid kind")
        require_nonempty_strings(
            provenance.get("source_refs"), label=f"{prefix}.provenance.source_refs", errors=errors
        )
        if not isinstance(provenance.get("customer_data"), bool):
            errors.append(f"{prefix}.provenance.customer_data: expected boolean")
        if not isinstance(provenance.get("notes"), str) or not provenance["notes"].strip():
            errors.append(f"{prefix}.provenance.notes: required")

    user_context = row["user_context"]
    if not isinstance(user_context, dict):
        errors.append(f"{prefix}.user_context: expected object")
    else:
        for key in ("role", "organization_type", "business_goal"):
            if not isinstance(user_context.get(key), str) or not user_context[key].strip():
                errors.append(f"{prefix}.user_context.{key}: required")

    query = row["initial_query"]
    if not isinstance(query, str) or len(query.strip()) < 20:
        errors.append(f"{prefix}.initial_query: must be at least 20 characters")
    elif EMAIL_RE.search(query):
        errors.append(f"{prefix}.initial_query: contains an email address")

    inputs = row["inputs"]
    if not isinstance(inputs, list) or not inputs:
        errors.append(f"{prefix}.inputs: expected a non-empty list")
        inputs = []
    input_ids: set[str] = set()
    missing_input = False
    for index, item in enumerate(inputs):
        label = f"{prefix}.inputs[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: expected object")
            continue
        for key in ("id", "kind", "role", "required", "availability"):
            if key not in item:
                errors.append(f"{label}: missing {key}")
        item_id = item.get("id")
        if item_id in input_ids:
            errors.append(f"{label}: duplicate input id {item_id!r}")
        if isinstance(item_id, str):
            input_ids.add(item_id)
        if not isinstance(item.get("required"), bool):
            errors.append(f"{label}.required: expected boolean")
        availability = item.get("availability")
        if availability not in {"provided", "intentionally_missing"}:
            errors.append(f"{label}.availability: invalid value")
            continue
        if availability == "intentionally_missing":
            missing_input = True
            if item.get("asset_id") or item.get("content"):
                errors.append(f"{label}: missing input must not contain asset_id/content")
            continue
        asset_id = item.get("asset_id")
        content = item.get("content")
        if bool(asset_id) == bool(content):
            errors.append(f"{label}: provided input needs exactly one of asset_id or content")
            continue
        if asset_id:
            asset = assets.get(asset_id)
            if not asset:
                errors.append(f"{label}: unknown asset_id {asset_id}")
                continue
            if asset_id not in validated_assets:
                asset_path = (REFERENCE_ROOT / asset["path"]).resolve()
                try:
                    asset_path.relative_to(REFERENCE_ROOT.resolve())
                except ValueError:
                    errors.append(f"{label}: asset path escapes reference pack")
                    continue
                if not asset_path.is_file():
                    errors.append(f"{label}: missing fixture {asset_path}")
                    continue
                if asset_path.stat().st_size != asset.get("bytes"):
                    errors.append(f"{label}: fixture byte count mismatch for {asset_id}")
                if sha256(asset_path) != asset.get("sha256"):
                    errors.append(f"{label}: fixture sha256 mismatch for {asset_id}")
                validated_assets.add(asset_id)

    constraints = row["constraints"]
    if not isinstance(constraints, dict):
        errors.append(f"{prefix}.constraints: expected object")
    else:
        for key in ("hard", "soft", "negative"):
            require_nonempty_strings(
                constraints.get(key), label=f"{prefix}.constraints.{key}", errors=errors
            )

    require_nonempty_strings(
        row["tools_available"], label=f"{prefix}.tools_available", errors=errors
    )

    workflow = row["expected_workflow"]
    minimum_checkpoints = 4 if level == "L4" else 3
    if not isinstance(workflow, list) or len(workflow) < minimum_checkpoints:
        errors.append(
            f"{prefix}.expected_workflow: {level} needs at least {minimum_checkpoints} checkpoints"
        )
        workflow = []
    checkpoints: set[str] = set()
    for index, checkpoint in enumerate(workflow):
        label = f"{prefix}.expected_workflow[{index}]"
        if not isinstance(checkpoint, dict):
            errors.append(f"{label}: expected object")
            continue
        name = checkpoint.get("checkpoint")
        if not isinstance(name, str) or not name:
            errors.append(f"{label}.checkpoint: required")
        elif name in checkpoints:
            errors.append(f"{label}: duplicate checkpoint {name}")
        else:
            checkpoints.add(name)
        require_nonempty_strings(
            checkpoint.get("required_outcomes"),
            label=f"{label}.required_outcomes",
            errors=errors,
        )

    deliverables = row["deliverables"]
    if not isinstance(deliverables, list) or not deliverables:
        errors.append(f"{prefix}.deliverables: expected a non-empty list")
        deliverables = []
    stages: set[str] = set()
    deliverable_ids: set[str] = set()
    for index, deliverable in enumerate(deliverables):
        label = f"{prefix}.deliverables[{index}]"
        if not isinstance(deliverable, dict):
            errors.append(f"{label}: expected object")
            continue
        deliverable_id = deliverable.get("id")
        if not isinstance(deliverable_id, str) or not deliverable_id:
            errors.append(f"{label}.id: required")
        elif deliverable_id in deliverable_ids:
            errors.append(f"{label}: duplicate id {deliverable_id}")
        else:
            deliverable_ids.add(deliverable_id)
        stage = deliverable.get("stage")
        if stage not in {"intermediate", "final"}:
            errors.append(f"{label}.stage: invalid")
        else:
            stages.add(stage)
        if not isinstance(deliverable.get("count"), int) or deliverable["count"] < 1:
            errors.append(f"{label}.count: expected positive integer")
        require_nonempty_strings(deliverable.get("formats"), label=f"{label}.formats", errors=errors)
        require_nonempty_strings(
            deliverable.get("requirements"), label=f"{label}.requirements", errors=errors
        )
    if "final" not in stages:
        errors.append(f"{prefix}.deliverables: at least one final deliverable required")
    if level == "L4" and "intermediate" not in stages:
        errors.append(f"{prefix}.deliverables: L4 needs an intermediate deliverable")

    feedback = row["feedback"]
    if not isinstance(feedback, list):
        errors.append(f"{prefix}.feedback: expected list")
        feedback = []
    if level == "L4" and not feedback:
        errors.append(f"{prefix}.feedback: L4 needs at least one feedback turn")
    for index, item in enumerate(feedback):
        label = f"{prefix}.feedback[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: expected object")
            continue
        if item.get("after_checkpoint") not in checkpoints:
            errors.append(f"{label}.after_checkpoint: must name an existing checkpoint")
        if not isinstance(item.get("message"), str) or not item["message"].strip():
            errors.append(f"{label}.message: required")
        require_nonempty_strings(
            item.get("expected_changes"), label=f"{label}.expected_changes", errors=errors
        )
        require_nonempty_strings(item.get("invariants"), label=f"{label}.invariants", errors=errors)

    messy = row["messy_conditions"]
    if not isinstance(messy, list):
        errors.append(f"{prefix}.messy_conditions: expected list")
        messy = []
    for index, item in enumerate(messy):
        label = f"{prefix}.messy_conditions[{index}]"
        if not isinstance(item, dict) or item.get("type") not in MESSY_TYPES:
            errors.append(f"{label}: invalid messy condition")
            continue
        if not isinstance(item.get("detail"), str) or not item["detail"].strip():
            errors.append(f"{label}.detail: required")
        require_nonempty_strings(
            item.get("expected_recovery"), label=f"{label}.expected_recovery", errors=errors
        )
    if missing_input and not any(item.get("type") == "missing_asset" for item in messy if isinstance(item, dict)):
        errors.append(f"{prefix}: intentionally missing input needs missing_asset condition")

    rubric = row["rubric"]
    if not isinstance(rubric, dict):
        errors.append(f"{prefix}.rubric: expected object")
    else:
        weights = rubric.get("checkpoint_weights")
        if not isinstance(weights, dict) or len(weights) < 3:
            errors.append(f"{prefix}.rubric.checkpoint_weights: expected at least three dimensions")
        else:
            if any(not isinstance(value, (int, float)) or value < 0 for value in weights.values()):
                errors.append(f"{prefix}.rubric.checkpoint_weights: weights must be non-negative numbers")
            elif abs(sum(weights.values()) - 1.0) > 1e-9:
                errors.append(
                    f"{prefix}.rubric.checkpoint_weights: weights sum to {sum(weights.values()):.6f}, not 1"
                )
        require_nonempty_strings(
            rubric.get("hard_gates"), label=f"{prefix}.rubric.hard_gates", errors=errors
        )

    if row["fixture_status"] not in {"ready", "planned"}:
        errors.append(f"{prefix}.fixture_status: invalid")


def validate_dataset(rows: list[dict[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    assets = load_assets(errors)
    validated_assets: set[str] = set()
    ids: set[str] = set()
    for row in rows:
        case_id = row.get("id")
        if case_id in ids:
            errors.append(f"duplicate brief id {case_id}")
        if isinstance(case_id, str):
            ids.add(case_id)
        validate_row(row, assets=assets, validated_assets=validated_assets, errors=errors)

    levels = collections.Counter(row.get("level") for row in rows)
    categories = collections.Counter(row.get("category") for row in rows)
    intents = collections.Counter(row.get("primary_intent") for row in rows)
    provenance = collections.Counter(
        row.get("provenance", {}).get("kind")
        for row in rows
        if isinstance(row.get("provenance"), dict)
    )
    messy_count = sum(bool(row.get("messy_conditions")) for row in rows)
    messy_ratio = messy_count / len(rows) if rows else 0.0

    if len(rows) != 24:
        errors.append(f"v0.1 pilot must contain 24 rows, found {len(rows)}")
    if levels != {"L3": 8, "L4": 16}:
        errors.append(f"expected L3=8/L4=16, found {dict(levels)}")
    expected_categories = {category: 3 for category in CATEGORIES}
    if categories != expected_categories:
        errors.append(f"expected three rows per category, found {dict(categories)}")
    expected_intents = {"generate": 5, "edit": 5, "evaluate_rank": 5, "export": 5, "adapt": 4}
    if intents != expected_intents:
        errors.append(f"unexpected primary-intent distribution: {dict(intents)}")
    if not 0.30 <= messy_ratio <= 0.40:
        errors.append(f"messy ratio must be 30–40%, found {messy_ratio:.1%}")
    if any(row.get("fixture_status") != "ready" for row in rows):
        errors.append("v0.1 publish set must contain only fixture_status=ready rows")

    summary = {
        "rows": len(rows),
        "levels": dict(sorted(levels.items())),
        "categories": dict(sorted(categories.items())),
        "primary_intents": dict(sorted(intents.items())),
        "provenance": dict(sorted(provenance.items())),
        "messy_cases": messy_count,
        "messy_ratio": messy_ratio,
        "referenced_assets": len(validated_assets),
        "errors": len(errors),
    }
    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_BRIEFS)
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = parser.parse_args()

    try:
        rows = load_jsonl(args.path)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    errors, summary = validate_dataset(rows)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"rows={summary['rows']} L3={summary['levels'].get('L3', 0)} "
            f"L4={summary['levels'].get('L4', 0)} messy={summary['messy_cases']} "
            f"({summary['messy_ratio']:.1%}) assets={summary['referenced_assets']}"
        )
        print("categories:", json.dumps(summary["categories"], ensure_ascii=False, sort_keys=True))
        print("intents:", json.dumps(summary["primary_intents"], ensure_ascii=False, sort_keys=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"FAIL: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("PASS: L3/L4 brief bank is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
