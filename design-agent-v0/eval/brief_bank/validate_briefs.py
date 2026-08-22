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
V01_BRIEFS = HERE / "briefs.v0.1.jsonl"
DEFAULT_BRIEFS = HERE / "briefs.v0.2.jsonl"
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
REQUIRED_V02_FIELDS = {
    "revision",
    "capability_tags",
    "reference_contract",
    "context_conditions",
    "preference_memory",
    "project_state",
    "edit_parameters",
    "structured_artifacts",
    "human_checkpoints",
    "verification_contract",
}
DEEP_REVISION_IDS = {
    "DAB-L4-BID-001",
    "DAB-L4-CAM-003",
    "DAB-L4-PSF-003",
    "DAB-L4-ECO-003",
    "DAB-L4-MFA-003",
    "DAB-L4-CFR-001",
    "DAB-L4-CFR-003",
    "DAB-L4-CFRY-002",
}
EXPLORATION_IDS = {
    "DAB-L4-BID-001",
    "DAB-L4-BID-003",
    "DAB-L4-CAM-001",
    "DAB-L4-PSF-001",
    "DAB-L4-ECO-001",
    "DAB-L4-RTO-001",
}
STRUCTURED_EDIT_IDS = {
    "DAB-L3-CAM-002",
    "DAB-L3-MFA-001",
    "DAB-L4-MFA-002",
    "DAB-L3-CFR-002",
    "DAB-L4-CFR-003",
    "DAB-L4-RTO-003",
}
CONTEXT_ABLATION_IDS = {
    "DAB-L4-BID-001",
    "DAB-L4-CAM-001",
    "DAB-L4-ECO-001",
    "DAB-L4-RTO-001",
}
CAPABILITY_TAGS = {
    "tool_execution",
    "workflow_orchestration",
    "multi_reference_binding",
    "multi_turn_revision",
    "state_recovery",
    "creative_exploration",
    "structured_editing",
    "context_ablation",
    "production_execution",
}
CONTEXT_CONDITIONS = {"zero_shot", "reference_grounded", "personalized"}
STRUCTURED_ARTIFACT_NAMES = {
    "preview.png",
    "design_document.json",
    "change_set.json",
    "verification.json",
    "trajectory.jsonl",
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

    version = row.get("schema_version")
    required_fields = REQUIRED_FIELDS | (REQUIRED_V02_FIELDS if version == "0.2" else set())
    missing = sorted(required_fields - row.keys())
    if missing:
        errors.append(f"{prefix}: missing fields {missing}")
        return

    if version not in {"0.1", "0.2"}:
        errors.append(f"{prefix}: schema_version must be 0.1 or 0.2")
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
        if version == "0.2":
            for key in ("turn_id", "session_id", "input_version", "expected_version"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    errors.append(f"{label}.{key}: required for v0.2")
            if not isinstance(item.get("requires_confirmation"), bool):
                errors.append(f"{label}.requires_confirmation: expected boolean")
            if item.get("resume_from_version") is not None and not isinstance(
                item["resume_from_version"], str
            ):
                errors.append(f"{label}.resume_from_version: expected string")

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

    if version == "0.2":
        validate_v02_protocol(row, checkpoints=checkpoints, errors=errors)


def validate_v02_protocol(
    row: dict[str, Any], *, checkpoints: set[str], errors: list[str]
) -> None:
    """Validate the contracts added for designer-feedback evaluation in v0.2."""
    case_id = row["id"]
    prefix = f"{case_id}.v0.2"

    revision = row["revision"]
    if not isinstance(revision, dict):
        errors.append(f"{prefix}.revision: expected object")
    else:
        if revision.get("base_dataset") != "briefs.v0.1.jsonl":
            errors.append(f"{prefix}.revision.base_dataset: must point to frozen v0.1")
        if revision.get("base_brief_id") != case_id:
            errors.append(f"{prefix}.revision.base_brief_id: must match id")
        if revision.get("business_scope_changed") is not False:
            errors.append(f"{prefix}.revision.business_scope_changed: must be false")
        require_nonempty_strings(
            revision.get("protocol_changes"),
            label=f"{prefix}.revision.protocol_changes",
            errors=errors,
        )

    tags = row["capability_tags"]
    if not isinstance(tags, list) or not tags:
        errors.append(f"{prefix}.capability_tags: expected non-empty list")
        tags = []
    elif len(tags) != len(set(tags)):
        errors.append(f"{prefix}.capability_tags: duplicates are not allowed")
    unknown_tags = set(tags) - CAPABILITY_TAGS
    if unknown_tags:
        errors.append(f"{prefix}.capability_tags: unknown tags {sorted(unknown_tags)}")
    base_tag = "tool_execution" if row["level"] == "L3" else "workflow_orchestration"
    if base_tag not in tags:
        errors.append(f"{prefix}.capability_tags: missing {base_tag}")

    provided_input_ids = {
        item.get("id")
        for item in row["inputs"]
        if isinstance(item, dict) and item.get("availability") == "provided"
    }
    asset_input_ids = {
        item.get("id")
        for item in row["inputs"]
        if isinstance(item, dict)
        and item.get("availability") == "provided"
        and item.get("asset_id")
    }
    contracts = row["reference_contract"]
    if not isinstance(contracts, list):
        errors.append(f"{prefix}.reference_contract: expected list")
        contracts = []
    contract_ids: set[str] = set()
    optional_ids: set[str] = set()
    for index, item in enumerate(contracts):
        label = f"{prefix}.reference_contract[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label}: expected object")
            continue
        input_id = item.get("input_id")
        if input_id in contract_ids:
            errors.append(f"{label}: duplicate input_id {input_id}")
        if isinstance(input_id, str):
            contract_ids.add(input_id)
        if not isinstance(item.get("reference_role"), str) or not item["reference_role"]:
            errors.append(f"{label}.reference_role: required")
        require_nonempty_strings(
            item.get("allowed_influence"), label=f"{label}.allowed_influence", errors=errors
        )
        if not isinstance(item.get("identity_policy"), str) or not item["identity_policy"]:
            errors.append(f"{label}.identity_policy: required")
        if not isinstance(item.get("optional_for_zero_shot"), bool):
            errors.append(f"{label}.optional_for_zero_shot: expected boolean")
        elif item["optional_for_zero_shot"] and isinstance(input_id, str):
            optional_ids.add(input_id)
    if contract_ids != asset_input_ids:
        errors.append(
            f"{prefix}.reference_contract: expected asset input IDs "
            f"{sorted(asset_input_ids)}, found {sorted(contract_ids)}"
        )

    conditions = row["context_conditions"]
    if not isinstance(conditions, list) or not conditions:
        errors.append(f"{prefix}.context_conditions: expected non-empty list")
        conditions = []
    condition_ids: set[str] = set()
    for index, condition in enumerate(conditions):
        label = f"{prefix}.context_conditions[{index}]"
        if not isinstance(condition, dict):
            errors.append(f"{label}: expected object")
            continue
        condition_id = condition.get("id")
        if condition_id not in CONTEXT_CONDITIONS:
            errors.append(f"{label}.id: invalid condition")
        elif condition_id in condition_ids:
            errors.append(f"{label}.id: duplicate {condition_id}")
        else:
            condition_ids.add(condition_id)
        included = condition.get("include_input_ids")
        if not isinstance(included, list) or len(included) != len(set(included)):
            errors.append(f"{label}.include_input_ids: expected unique list")
            included_set: set[str] = set()
        else:
            included_set = set(included)
        unknown_inputs = included_set - provided_input_ids
        if unknown_inputs:
            errors.append(f"{label}.include_input_ids: unavailable inputs {sorted(unknown_inputs)}")
        memory_enabled = condition.get("include_preference_memory")
        if not isinstance(memory_enabled, bool):
            errors.append(f"{label}.include_preference_memory: expected boolean")
        if condition_id == "reference_grounded" and included_set != provided_input_ids:
            errors.append(f"{label}: reference_grounded must include every provided input")
        if condition_id == "personalized":
            if included_set != provided_input_ids or memory_enabled is not True:
                errors.append(f"{label}: personalized needs all inputs and preference memory")
        if condition_id == "zero_shot":
            if included_set != provided_input_ids - optional_ids:
                errors.append(f"{label}: zero_shot may omit only optional reference inputs")
            if not isinstance(condition.get("query_override"), str) or len(
                condition["query_override"].strip()
            ) < 20:
                errors.append(f"{label}.query_override: required for zero_shot")
        if not isinstance(condition.get("purpose"), str) or not condition["purpose"].strip():
            errors.append(f"{label}.purpose: required")

    expected_conditions = (
        CONTEXT_CONDITIONS if case_id in CONTEXT_ABLATION_IDS else {"reference_grounded"}
    )
    if condition_ids != expected_conditions:
        errors.append(
            f"{prefix}.context_conditions: expected {sorted(expected_conditions)}, "
            f"found {sorted(condition_ids)}"
        )

    memory = row["preference_memory"]
    if not isinstance(memory, dict):
        errors.append(f"{prefix}.preference_memory: expected object")
    else:
        accepted = memory.get("accepted_signals")
        rejected = memory.get("rejected_signals")
        if not isinstance(accepted, list) or not isinstance(rejected, list):
            errors.append(f"{prefix}.preference_memory: accepted/rejected signals must be lists")
        elif case_id in CONTEXT_ABLATION_IDS:
            if memory.get("scope") != "project" or not accepted or not rejected:
                errors.append(f"{prefix}.preference_memory: ablation case needs project signals")
        elif memory.get("scope") != "none" or accepted or rejected:
            errors.append(f"{prefix}.preference_memory: non-ablation case must be empty")

    state = row["project_state"]
    if not isinstance(state, dict):
        errors.append(f"{prefix}.project_state: expected object")
    else:
        if state.get("starting_version") != "v0":
            errors.append(f"{prefix}.project_state.starting_version: expected v0")
        require_nonempty_strings(
            state.get("locked_invariants"),
            label=f"{prefix}.project_state.locked_invariants",
            errors=errors,
        )
        require_nonempty_strings(
            state.get("editable_targets"),
            label=f"{prefix}.project_state.editable_targets",
            errors=errors,
        )
        expected_resume = "checkpoint_and_version" if case_id in DEEP_REVISION_IDS else "checkpoint_only"
        if state.get("resume_policy") != expected_resume:
            errors.append(f"{prefix}.project_state.resume_policy: expected {expected_resume}")

    parameters = row["edit_parameters"]
    if not isinstance(parameters, list):
        errors.append(f"{prefix}.edit_parameters: expected list")
        parameters = []
    parameter_names: set[str] = set()
    for index, parameter in enumerate(parameters):
        label = f"{prefix}.edit_parameters[{index}]"
        if not isinstance(parameter, dict):
            errors.append(f"{label}: expected object")
            continue
        name = parameter.get("name")
        if name in parameter_names:
            errors.append(f"{label}: duplicate parameter {name}")
        if isinstance(name, str):
            parameter_names.add(name)
        for key in ("name", "target", "value_type", "allowed_change", "verification"):
            if not isinstance(parameter.get(key), str) or not parameter[key].strip():
                errors.append(f"{label}.{key}: required")
    if case_id in (DEEP_REVISION_IDS | STRUCTURED_EDIT_IDS) and not parameters:
        errors.append(f"{prefix}.edit_parameters: targeted case needs explicit parameters")

    artifacts = row["structured_artifacts"]
    if not isinstance(artifacts, list):
        errors.append(f"{prefix}.structured_artifacts: expected list")
        artifacts = []
    artifact_names: set[str] = set()
    for index, artifact in enumerate(artifacts):
        label = f"{prefix}.structured_artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{label}: expected object")
            continue
        name = artifact.get("name")
        if name in artifact_names:
            errors.append(f"{label}: duplicate artifact {name}")
        if isinstance(name, str):
            artifact_names.add(name)
        if artifact.get("required") is not True:
            errors.append(f"{label}.required: v0.2 artifacts must be required")
        if not isinstance(artifact.get("validation"), str) or not artifact["validation"].strip():
            errors.append(f"{label}.validation: required")
    if not {"verification.json", "trajectory.jsonl"} <= artifact_names:
        errors.append(f"{prefix}.structured_artifacts: verification and trajectory are required")
    if case_id in STRUCTURED_EDIT_IDS and artifact_names != STRUCTURED_ARTIFACT_NAMES:
        errors.append(
            f"{prefix}.structured_artifacts: structured-edit case needs "
            f"{sorted(STRUCTURED_ARTIFACT_NAMES)}"
        )

    human = row["human_checkpoints"]
    if not isinstance(human, list):
        errors.append(f"{prefix}.human_checkpoints: expected list")
        human = []
    if row["level"] == "L4" and not human:
        errors.append(f"{prefix}.human_checkpoints: L4 needs a human decision")
    for index, checkpoint in enumerate(human):
        label = f"{prefix}.human_checkpoints[{index}]"
        if not isinstance(checkpoint, dict):
            errors.append(f"{label}: expected object")
            continue
        if checkpoint.get("after_checkpoint") not in checkpoints:
            errors.append(f"{label}.after_checkpoint: must name an existing checkpoint")
        if checkpoint.get("required") is not True:
            errors.append(f"{label}.required: must be true")
        if not isinstance(checkpoint.get("evidence"), str) or not checkpoint["evidence"].strip():
            errors.append(f"{label}.evidence: required")

    verification = row["verification_contract"]
    if not isinstance(verification, dict):
        errors.append(f"{prefix}.verification_contract: expected object")
    else:
        checks = require_nonempty_strings(
            verification.get("checks"),
            label=f"{prefix}.verification_contract.checks",
            errors=errors,
        )
        if len(checks) != len(set(checks)):
            errors.append(f"{prefix}.verification_contract.checks: duplicates not allowed")
        if verification.get("evidence_required") is not True:
            errors.append(f"{prefix}.verification_contract.evidence_required: must be true")
        if verification.get("failure_policy") != "block_delivery_on_hard_gate":
            errors.append(f"{prefix}.verification_contract.failure_policy: invalid")

    feedback = row["feedback"]
    turn_ids = [item.get("turn_id") for item in feedback if isinstance(item, dict)]
    if len(turn_ids) != len(set(turn_ids)):
        errors.append(f"{prefix}.feedback: duplicate turn IDs")
    for index, item in enumerate(feedback, 1):
        if not isinstance(item, dict):
            continue
        if item.get("input_version") != f"v{index - 1}" or item.get("expected_version") != f"v{index}":
            errors.append(f"{prefix}.feedback[{index - 1}]: non-contiguous state versions")

    if case_id in DEEP_REVISION_IDS:
        sessions = {item.get("session_id") for item in feedback if isinstance(item, dict)}
        if len(feedback) < 3 or len(sessions) < 2:
            errors.append(f"{prefix}.feedback: deep-revision case needs 3 turns across 2 sessions")
        if not any(item.get("resume_from_version") for item in feedback if isinstance(item, dict)):
            errors.append(f"{prefix}.feedback: deep-revision case needs an explicit resume version")
        for tag in ("multi_turn_revision", "state_recovery"):
            if tag not in tags:
                errors.append(f"{prefix}.capability_tags: deep-revision case missing {tag}")

    if case_id in EXPLORATION_IDS:
        workflow_names = [item.get("checkpoint") for item in row["expected_workflow"]]
        expected_flow = ["understand", "diverge", "cluster", "select", "converge", "deliver"]
        if workflow_names != expected_flow:
            errors.append(f"{prefix}.expected_workflow: exploration protocol must be {expected_flow}")
        if "creative_exploration" not in tags:
            errors.append(f"{prefix}.capability_tags: missing creative_exploration")
        if not any(item.get("id") == "exploration-map" for item in row["deliverables"]):
            errors.append(f"{prefix}.deliverables: exploration-map required")

    if case_id in STRUCTURED_EDIT_IDS:
        if "structured_editing" not in tags:
            errors.append(f"{prefix}.capability_tags: missing structured_editing")
        required_tools = {"design_object_inspector", "layer_graph_editor", "change_set_exporter"}
        if not required_tools <= set(row["tools_available"]):
            errors.append(f"{prefix}.tools_available: structured edit tools missing")


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
    versions = {row.get("schema_version") for row in rows}
    version = next(iter(versions)) if len(versions) == 1 else "mixed"

    if len(rows) != 24:
        errors.append(f"brief bank must contain 24 base episodes, found {len(rows)}")
    if versions - {"0.1", "0.2"} or len(versions) != 1:
        errors.append(f"dataset must contain one supported schema version, found {sorted(map(str, versions))}")
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
        errors.append("publish set must contain only fixture_status=ready rows")

    expanded_runs = len(rows)
    deep_revision_count = 0
    exploration_count = 0
    structured_edit_count = 0
    context_ablation_count = 0
    if version == "0.2":
        tagged_ids = lambda tag: {
            row.get("id")
            for row in rows
            if tag in row.get("capability_tags", [])
        }
        expected_tag_sets = {
            "multi_turn_revision": DEEP_REVISION_IDS,
            "state_recovery": DEEP_REVISION_IDS,
            "creative_exploration": EXPLORATION_IDS,
            "structured_editing": STRUCTURED_EDIT_IDS,
            "context_ablation": CONTEXT_ABLATION_IDS,
        }
        for tag, expected_ids in expected_tag_sets.items():
            actual_ids = tagged_ids(tag)
            if actual_ids != expected_ids:
                errors.append(
                    f"v0.2 {tag} coverage mismatch: expected {sorted(expected_ids)}, "
                    f"found {sorted(actual_ids)}"
                )
        deep_revision_count = len(tagged_ids("multi_turn_revision"))
        exploration_count = len(tagged_ids("creative_exploration"))
        structured_edit_count = len(tagged_ids("structured_editing"))
        context_ablation_count = len(tagged_ids("context_ablation"))
        expanded_runs = sum(
            len(row.get("context_conditions", []))
            for row in rows
            if isinstance(row.get("context_conditions"), list)
        )
        if expanded_runs != 32:
            errors.append(f"v0.2 must expand to 32 context-condition runs, found {expanded_runs}")

        try:
            base_rows = {row["id"]: row for row in load_jsonl(V01_BRIEFS)}
        except (OSError, ValueError) as exc:
            errors.append(f"cannot verify frozen v0.1 base: {exc}")
            base_rows = {}
        if set(base_rows) != ids:
            errors.append("v0.2 base episode IDs must exactly match frozen v0.1")
        stable_fields = (
            "level",
            "category",
            "primary_intent",
            "secondary_intents",
            "language",
            "provenance",
            "user_context",
            "inputs",
            "messy_conditions",
            "fixture_status",
        )
        for row in rows:
            base = base_rows.get(row.get("id"))
            if not base:
                continue
            for field in stable_fields:
                if row.get(field) != base.get(field):
                    errors.append(f"{row['id']}: v0.2 changed frozen business field {field}")
            base_final = [item for item in base["deliverables"] if item.get("stage") == "final"]
            new_final = [item for item in row["deliverables"] if item.get("stage") == "final"]
            if new_final != base_final:
                errors.append(f"{row['id']}: v0.2 changed frozen final deliverables")

    summary = {
        "schema_version": version,
        "rows": len(rows),
        "expanded_runs": expanded_runs,
        "levels": dict(sorted(levels.items())),
        "categories": dict(sorted(categories.items())),
        "primary_intents": dict(sorted(intents.items())),
        "provenance": dict(sorted(provenance.items())),
        "messy_cases": messy_count,
        "messy_ratio": messy_ratio,
        "referenced_assets": len(validated_assets),
        "deep_multi_turn_cases": deep_revision_count,
        "creative_exploration_cases": exploration_count,
        "structured_edit_cases": structured_edit_count,
        "context_ablation_cases": context_ablation_count,
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
            f"version={summary['schema_version']} rows={summary['rows']} "
            f"runs={summary['expanded_runs']} L3={summary['levels'].get('L3', 0)} "
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
    print(f"PASS: L3/L4 brief bank {summary['schema_version']} is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
