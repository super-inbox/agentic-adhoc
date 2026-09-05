#!/usr/bin/env python3
"""Build Brief Bank v0.3: v0.2 core plus 11 public-corpus-grounded cases."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
BASE = HERE / "briefs.v0.2.jsonl"
SEEDS = HERE.parent / "reddit_briefs" / "reddit_brief_seeds_2026-08-30.jsonl"
OUTPUT = HERE / "briefs.v0.3.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def asset_input(
    input_id: str,
    kind: str,
    role: str,
    asset_id: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    return {
        "id": input_id,
        "kind": kind,
        "role": role,
        "required": required,
        "availability": "provided",
        "asset_id": asset_id,
    }


def text_input(input_id: str, kind: str, role: str, content: str) -> dict[str, Any]:
    return {
        "id": input_id,
        "kind": kind,
        "role": role,
        "required": True,
        "availability": "provided",
        "content": content,
    }


def missing_input(input_id: str, kind: str, role: str) -> dict[str, Any]:
    return {
        "id": input_id,
        "kind": kind,
        "role": role,
        "required": True,
        "availability": "intentionally_missing",
    }


def reference(
    input_id: str,
    role: str,
    allowed: list[str],
    policy: str,
) -> dict[str, Any]:
    return {
        "input_id": input_id,
        "reference_role": role,
        "allowed_influence": allowed,
        "identity_policy": policy,
        "optional_for_zero_shot": False,
    }


def checkpoint(name: str, *outcomes: str) -> dict[str, Any]:
    return {"checkpoint": name, "required_outcomes": list(outcomes)}


def deliverable(
    deliverable_id: str,
    stage: str,
    kind: str,
    count: int,
    formats: list[str],
    *requirements: str,
) -> dict[str, Any]:
    return {
        "id": deliverable_id,
        "stage": stage,
        "type": kind,
        "count": count,
        "formats": formats,
        "requirements": list(requirements),
    }


def controlled_feedback(
    after: str,
    message: str,
    changes: list[str],
    invariants: list[str],
) -> dict[str, Any]:
    return {
        "turn_id": "feedback-01",
        "session_id": "session-01",
        "input_version": "v0",
        "expected_version": "v1",
        "after_checkpoint": after,
        "message": message,
        "expected_changes": changes,
        "invariants": invariants,
        "requires_confirmation": False,
    }


def artifacts(*extra: tuple[str, str, str]) -> list[dict[str, Any]]:
    rows = [
        {
            "name": "verification.json",
            "format": "JSON",
            "required": True,
            "validation": "Per-check pass/fail, evidence references, and hard-gate state.",
        },
        {
            "name": "trajectory.jsonl",
            "format": "JSONL",
            "required": True,
            "validation": "Observable plan, tool, artifact, checkpoint, and state-version events; no private reasoning.",
        },
    ]
    for name, fmt, validation in extra:
        rows.append({"name": name, "format": fmt, "required": True, "validation": validation})
    return rows


RUBRICS = {
    "reference": {
        "brief_adherence": 0.15,
        "visual_quality": 0.15,
        "reference_contract": 0.25,
        "workflow_completion": 0.15,
        "refinement_ability": 0.10,
        "cross_asset_consistency": 0.10,
        "production_readiness": 0.05,
        "efficiency": 0.05,
    },
    "edit": {
        "brief_adherence": 0.15,
        "visual_quality": 0.10,
        "edit_fidelity": 0.25,
        "preservation_fidelity": 0.25,
        "workflow_completion": 0.10,
        "production_readiness": 0.10,
        "efficiency": 0.05,
    },
    "workflow": {
        "brief_adherence": 0.15,
        "visual_quality": 0.15,
        "creative_diversity": 0.10,
        "workflow_completion": 0.15,
        "refinement_ability": 0.15,
        "cross_asset_consistency": 0.10,
        "production_readiness": 0.15,
        "efficiency": 0.05,
    },
    "production": {
        "brief_adherence": 0.10,
        "output_fidelity": 0.25,
        "workflow_completion": 0.15,
        "verification_quality": 0.15,
        "production_readiness": 0.25,
        "scalability": 0.05,
        "efficiency": 0.05,
    },
}


def episode(
    *,
    case_id: str,
    seed_id: str,
    level: str,
    category: str,
    primary: str,
    secondary: list[str],
    role: str,
    organization: str,
    goal: str,
    query: str,
    inputs: list[dict[str, Any]],
    hard: list[str],
    soft: list[str],
    negative: list[str],
    workflow: list[dict[str, Any]],
    deliverables: list[dict[str, Any]],
    reference_contract: list[dict[str, Any]],
    checks: list[str],
    hard_gates: list[str],
    capability_tags: list[str],
    rubric_kind: str,
    feedback: list[dict[str, Any]] | None = None,
    messy: list[dict[str, Any]] | None = None,
    edit_parameters: list[dict[str, Any]] | None = None,
    human_checkpoints: list[dict[str, Any]] | None = None,
    extra_artifacts: tuple[tuple[str, str, str], ...] = (),
) -> dict[str, Any]:
    feedback = feedback or []
    deliverable_ids = [item["id"] for item in deliverables]
    return {
        "id": case_id,
        "schema_version": "0.3",
        "revision": {
            "base_dataset": "reddit_brief_seeds_2026-08-30.jsonl",
            "base_brief_id": seed_id,
            "business_scope_changed": False,
            "protocol_changes": [
                "paraphrased public task and failure pattern into a consent-safe executable episode",
                "attached project-owned inputs and explicit scoring boundaries",
                "added observable artifacts and verification contract",
            ],
        },
        "level": level,
        "category": category,
        "primary_intent": primary,
        "secondary_intents": secondary,
        "language": "en",
        "provenance": {
            "kind": "public_corpus_grounded",
            "source_refs": [
                f"agentic-adhoc:design-agent-v0/eval/reddit_briefs/reddit_brief_seeds_2026-08-30.jsonl#{seed_id}"
            ],
            "customer_data": False,
            "notes": (
                "Task and failure mode are paraphrased from a public-corpus seed. Input images are new "
                "project-owned fixtures. Any benchmark feedback is evaluator-controlled and is not "
                "represented as the original poster's feedback."
            ),
        },
        "user_context": {
            "role": role,
            "organization_type": organization,
            "business_goal": goal,
        },
        "initial_query": query,
        "inputs": inputs,
        "constraints": {"hard": hard, "soft": soft, "negative": negative},
        "tools_available": [
            "inspect_assets",
            "extract_brief",
            "create_direction",
            "edit_image",
            "layout",
            "export_file",
            "verify_artifact",
        ],
        "expected_workflow": workflow,
        "deliverables": deliverables,
        "feedback": feedback,
        "messy_conditions": messy or [],
        "rubric": {
            "checkpoint_weights": copy.deepcopy(RUBRICS[rubric_kind]),
            "hard_gates": hard_gates,
        },
        "fixture_status": "ready",
        "capability_tags": capability_tags,
        "reference_contract": reference_contract,
        "context_conditions": [
            {
                "id": "reference_grounded",
                "include_input_ids": [
                    item["id"] for item in inputs if item["availability"] == "provided"
                ],
                "include_preference_memory": False,
                "purpose": "Run the public-corpus-grounded episode with every declared input and no remembered preferences.",
            }
        ],
        "preference_memory": {
            "scope": "none",
            "source": "none",
            "accepted_signals": [],
            "rejected_signals": [],
        },
        "project_state": {
            "project_id": f"project:{case_id.lower()}",
            "starting_version": "v0",
            "locked_invariants": hard,
            "editable_targets": deliverable_ids,
            "resume_policy": "checkpoint_and_version" if feedback else "checkpoint_only",
            "preference_memory_scope": "none",
        },
        "edit_parameters": edit_parameters or [],
        "structured_artifacts": artifacts(*extra_artifacts),
        "human_checkpoints": human_checkpoints or [],
        "verification_contract": {
            "checks": checks,
            "evidence_required": True,
            "failure_policy": "block_delivery_on_hard_gate",
        },
    }


def external_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    rows.append(episode(
        case_id="DAB-L3-RDT-001", seed_id="RBS-SET-003", level="L3",
        category="multi_format_adaptation", primary="generate", secondary=["adapt", "export"],
        role="print-on-demand designer", organization="small merchandise studio",
        goal="create one coherent printable character family without losing subject identity",
        query=(
            "Using the supplied style reference, create five distinct masked, caped action characters: "
            "an elderly woman, a cheerleader, a priest, a nun, and a fictional world leader. Each is "
            "mid-leap with a non-graphic cinematic explosion behind them. Deliver one image per character "
            "plus a proof sheet for a 14 × 8.5 inch sublimation press. Keep the set visually coherent."
        ),
        inputs=[
            asset_input("style-reference", "reference_image", "style_only", "factory-luna-club-sticker"),
            text_input("press-spec", "spec", "physical_output_spec", "14 × 8.5 inch press bed; landscape ratio 28:17; one design per printable canvas."),
        ],
        hard=[
            "Exactly five outputs, one for each named subject",
            "Every printable canvas uses the 28:17 landscape ratio",
            "All five share one repeatable visual system while remaining individually identifiable",
        ],
        soft=["Energetic, commercially printable action poses", "Consistent line weight, lighting, and explosion treatment"],
        negative=["Do not copy the reference character, words, or logo", "No real politician likeness or graphic violence"],
        workflow=[
            checkpoint("understand", "Map the five subject identities and physical-output constraint", "Declare style-only reference permission"),
            checkpoint("system", "Define shared palette, line, lighting, pose, and background rules before generation"),
            checkpoint("generate_set", "Create all five members against the locked system"),
            checkpoint("verify", "Check count, subject identity, ratio, and cross-asset consistency"),
            checkpoint("deliver", "Export five canvases and one labelled proof sheet"),
        ],
        deliverables=[
            deliverable("character-set", "final", "coherent_character_set", 5, ["PNG"], "Exactly one named subject per canvas", "Each canvas is 28:17"),
            deliverable("press-proof", "final", "print_proof_sheet", 1, ["PDF", "PNG"], "Labels all five files", "Records 14 × 8.5 inch target"),
        ],
        reference_contract=[reference("style-reference", "style_reference", ["line_language", "shape_language", "rendering_energy"], "abstract_only")],
        checks=["brief_adherence", "exact_output_count", "subject_identity", "aspect_ratio_28_17", "set_coherence", "reference_role_compliance", "print_spec_recorded"],
        hard_gates=["exactly five subjects", "28:17 ratio", "no copied reference identity", "all files open"],
        capability_tags=["tool_execution", "workflow_orchestration", "multi_reference_binding", "production_execution"],
        rubric_kind="workflow",
        edit_parameters=[{"name": "print_canvas", "target": "character-set/*", "value_type": "dimension_list", "allowed_change": "fixed 28:17 ratio", "verification": "inspect every exported canvas dimensions"}],
        extra_artifacts=(("preview.png", "PNG", "Contact proof containing all five labelled designs."),),
    ))

    rows.append(episode(
        case_id="DAB-L3-RDT-002", seed_id="RBS-REF-001", level="L3",
        category="reference_to_original", primary="generate", secondary=[],
        role="art director", organization="architecture publication",
        goal="transfer a narrowly permitted visual channel without reference bleed",
        query=(
            "Create an original brutalist civic plaza at dusk. From the supplied fantasy editorial reference, "
            "use only its colour relationships and subtle material texture. Do not inherit its composition, "
            "subject matter, typography, branding, or ornamental motifs."
        ),
        inputs=[asset_input("palette-reference", "reference_image", "palette_and_texture_only", "detail-page-quiet-ritual-reference-page")],
        hard=["The target subject is a brutalist civic plaza", "Reference influence is limited to colour relationships and material texture"],
        soft=["Architectural editorial quality", "Readable concrete massing and pedestrian scale"],
        negative=["No copied layout, product, text, logo, or decorative motif from the reference"],
        workflow=[
            checkpoint("bind_reference", "Record allowed and forbidden reference channels"),
            checkpoint("generate", "Create the unrelated target scene using only allowed channels"),
            checkpoint("verify", "Compare for palette transfer and prohibited semantic or compositional bleed"),
            checkpoint("deliver", "Export the image and reference-compliance evidence"),
        ],
        deliverables=[deliverable("brutalist-plaza", "final", "original_environment_image", 1, ["PNG"], "Unrelated subject and layout", "Palette/texture influence is documented")],
        reference_contract=[reference("palette-reference", "style_reference", ["color_palette", "material_texture"], "abstract_only")],
        checks=["brief_adherence", "visual_quality", "allowed_channel_transfer", "subject_independence", "composition_independence", "identity_noncopy"],
        hard_gates=["target is brutalist environment", "no source subject or branding", "no composition copy"],
        capability_tags=["tool_execution", "workflow_orchestration", "multi_reference_binding"],
        rubric_kind="reference",
        messy=[{"type": "constraint_conflict", "detail": "A visual reference is useful only through two permitted channels.", "expected_recovery": ["Represent reference permissions explicitly", "Verify both allowed transfer and forbidden bleed"]}],
        extra_artifacts=(("preview.png", "PNG", "Final environment preview."),),
    ))

    rows.append(episode(
        case_id="DAB-L3-RDT-003", seed_id="RBS-REF-002", level="L3",
        category="reference_to_original", primary="generate", secondary=[],
        role="campaign designer", organization="community bicycle workshop",
        goal="reuse a graphic language while explicitly replacing its colour system",
        query=(
            "Design an original poster illustration for a solar-powered community bicycle workshop. Use the "
            "supplied sticker only for its playful cut-paper shape language and friendly line treatment. Do not "
            "use its colours. The target palette is cobalt #174EA6, acid green #B7FF3C, and warm grey #E8E4DC."
        ),
        inputs=[
            asset_input("style-reference", "reference_image", "style_without_color", "factory-luna-club-sticker"),
            text_input("target-palette", "spec", "replacement_color_system", "Cobalt #174EA6; acid green #B7FF3C; warm grey #E8E4DC."),
        ],
        hard=["Use only the supplied three-colour target palette apart from neutral antialiasing", "Retain no recognisable reference character, wording, or brand"],
        soft=["Friendly, energetic community tone", "Clear poster focal hierarchy"],
        negative=["Do not transfer the reference palette", "Do not copy reference composition or identity"],
        workflow=[
            checkpoint("bind_reference", "Separate permitted shape/line style from forbidden source colour"),
            checkpoint("generate", "Create an original cycling subject in the replacement palette"),
            checkpoint("verify", "Check palette exclusion, style signal, and identity independence"),
            checkpoint("deliver", "Export poster and compliance evidence"),
        ],
        deliverables=[deliverable("cycling-poster", "final", "original_poster_illustration", 1, ["PNG"], "Uses target palette", "Contains original bicycle-workshop subject")],
        reference_contract=[reference("style-reference", "style_reference", ["shape_language", "line_treatment"], "abstract_only")],
        checks=["brief_adherence", "visual_quality", "style_channel_transfer", "target_palette_match", "source_palette_exclusion", "identity_noncopy"],
        hard_gates=["target palette used", "source palette excluded", "no copied reference identity"],
        capability_tags=["tool_execution", "workflow_orchestration", "multi_reference_binding"],
        rubric_kind="reference",
        messy=[{"type": "constraint_conflict", "detail": "The requested style and forbidden colours arrive in the same reference.", "expected_recovery": ["Extract channels separately", "Verify negative colour permission"]}],
        extra_artifacts=(("preview.png", "PNG", "Final poster preview."),),
    ))

    rows.append(episode(
        case_id="DAB-L3-RDT-004", seed_id="RBS-REF-003", level="L3",
        category="reference_to_original", primary="generate", secondary=[],
        role="illustration commissioner", organization="neighbourhood mobility project",
        goal="bind two references to mutually exclusive jobs",
        query=(
            "Create a polished illustrated future-neighbourhood scene. Reference A controls layout only: road "
            "along the bottom, building left, tree near centre, sun upper-right. Reference B controls illustration "
            "style only. Do not take style from A or layout, characters, wording, or colours from B."
        ),
        inputs=[
            asset_input("layout-reference", "reference_image", "geometry_only", "v03-layout-road-sketch"),
            asset_input("style-reference", "reference_image", "style_only", "factory-luna-club-sticker"),
        ],
        hard=["Preserve the four named spatial relationships from reference A", "Use reference B only for abstract illustration style"],
        soft=["Friendly optimistic mobility scene", "Visually coherent depth and lighting"],
        negative=["No layout transfer from B", "No line style from A", "No copied words, logo, or character from B"],
        workflow=[
            checkpoint("bind_references", "Create separate slot-to-channel contracts for A and B"),
            checkpoint("generate", "Compose the target with A geometry and B abstract style"),
            checkpoint("verify", "Check geometry retention and cross-channel contamination"),
            checkpoint("deliver", "Export image and per-reference evidence"),
        ],
        deliverables=[deliverable("future-neighbourhood", "final", "dual_reference_original", 1, ["PNG"], "Matches A geometry", "Uses B abstract style without copying identity")],
        reference_contract=[
            reference("layout-reference", "layout_reference", ["object_positions", "spatial_relationships"], "analysis_only"),
            reference("style-reference", "style_reference", ["shape_language", "line_treatment", "rendering_energy"], "abstract_only"),
        ],
        checks=["brief_adherence", "visual_quality", "layout_slot_fidelity", "style_slot_fidelity", "cross_channel_separation", "identity_noncopy"],
        hard_gates=["A supplies layout only", "B supplies style only", "no B identity copy"],
        capability_tags=["tool_execution", "workflow_orchestration", "multi_reference_binding"],
        rubric_kind="reference",
        messy=[{"type": "conflicting_references", "detail": "Two references have non-overlapping permissions that must not blend.", "expected_recovery": ["Bind each reference to its named slot", "Verify each forbidden channel separately"]}],
        extra_artifacts=(("preview.png", "PNG", "Final dual-reference result."),),
    ))

    rows.append(episode(
        case_id="DAB-L3-RDT-005", seed_id="RBS-EDIT-001", level="L3",
        category="client_feedback_revision", primary="edit", secondary=[],
        role="content producer", organization="robotics education publisher",
        goal="repair in-image copy without destabilising approved artwork",
        query=(
            "In the supplied cartoon, replace only the text inside the provided speech-bubble mask with the exact "
            "uppercase text 'SHIP IT TODAY'. Preserve the bubble shape and every pixel outside the mask. Keep the "
            "original dimensions and PNG alpha behaviour."
        ),
        inputs=[
            asset_input("edit-target", "existing_design", "approved_artwork", "v03-robot-speech-bubble-source"),
            asset_input("edit-mask", "edit_mask", "only_editable_region", "v03-robot-speech-bubble-mask"),
            text_input("replacement-copy", "copy", "exact_text", "SHIP IT TODAY"),
        ],
        hard=["Exact text is SHIP IT TODAY", "Every pixel outside the binary mask is unchanged", "Output dimensions and alpha mode match source"],
        soft=["Typography remains bold, legible, and centred within the existing bubble"],
        negative=["Do not redraw the robot, workshop, bubble outline, or background"],
        workflow=[
            checkpoint("inspect", "Validate source, mask alignment, and exact replacement string"),
            checkpoint("edit", "Apply text change only within the mask"),
            checkpoint("verify", "OCR exact copy and compute outside-mask pixel diff"),
            checkpoint("deliver", "Export edited PNG, diff evidence, and action trace"),
        ],
        deliverables=[deliverable("edited-cartoon", "final", "masked_text_edit", 1, ["PNG"], "Exact replacement text", "Outside-mask pixels unchanged")],
        reference_contract=[
            reference("edit-target", "edit_target", ["localized_edit"], "preserve_unedited_regions"),
            reference("edit-mask", "supporting_asset", ["editable_region_definition"], "analysis_only"),
        ],
        checks=["exact_text_ocr", "outside_mask_pixel_diff_zero", "source_dimensions_preserved", "alpha_mode_preserved", "file_opens"],
        hard_gates=["exact text", "zero outside-mask pixel change", "same dimensions"],
        capability_tags=["tool_execution", "workflow_orchestration", "structured_editing"],
        rubric_kind="edit",
        edit_parameters=[
            {"name": "replacement_text", "target": "edit-target/speech-bubble", "value_type": "string", "allowed_change": "SHIP IT TODAY", "verification": "OCR within edit-mask"},
            {"name": "outside_mask_change", "target": "edit-target/outside-mask", "value_type": "boolean", "allowed_change": "false", "verification": "pixel diff outside mask equals zero"},
        ],
        extra_artifacts=(("preview.png", "PNG", "Edited cartoon preview."), ("change_set.json", "JSON", "Records mask, exact copy, and touched object only.")),
    ))

    rows.append(episode(
        case_id="DAB-L3-RDT-006", seed_id="RBS-EDIT-003", level="L3",
        category="client_feedback_revision", primary="edit", secondary=[],
        role="transport campaign retoucher", organization="Australian road-safety studio",
        goal="add traffic while satisfying a binary local-domain constraint",
        query=(
            "Add exactly three realistic cars to the supplied empty Australian road, all travelling in valid "
            "left-hand traffic lanes. At least one near car must visibly be right-hand drive. Change pixels only "
            "inside the supplied road mask; preserve signs, trees, sky, and road geometry."
        ),
        inputs=[
            asset_input("edit-target", "existing_design", "approved_road_photo", "v03-australian-empty-road"),
            asset_input("edit-mask", "edit_mask", "road_surface_edit_region", "v03-australian-road-edit-mask"),
            text_input("traffic-rule", "spec", "hard_domain_constraint", "Australia: vehicles travel on the left; steering wheel/driver position is on the right."),
        ],
        hard=["Exactly three cars", "All cars occupy valid left-hand traffic lanes", "At least one visible near vehicle is right-hand drive", "No pixels outside the mask change"],
        soft=["Photorealistic scale, perspective, shadow, and road contact"],
        negative=["No vehicle may travel on the right-hand traffic side", "Do not alter signs, markings, vegetation, or sky"],
        workflow=[
            checkpoint("inspect", "Infer lane directions and validate mask"),
            checkpoint("edit", "Place three perspective-correct vehicles within the editable road"),
            checkpoint("verify", "Count cars, inspect traffic side and driver position, and diff protected pixels"),
            checkpoint("deliver", "Export edited image and constraint evidence"),
        ],
        deliverables=[deliverable("road-with-traffic", "final", "constraint_bound_local_edit", 1, ["PNG"], "Exactly three cars", "Left-hand traffic", "Outside-mask preservation")],
        reference_contract=[
            reference("edit-target", "edit_target", ["localized_object_addition"], "preserve_unedited_regions"),
            reference("edit-mask", "supporting_asset", ["editable_region_definition"], "analysis_only"),
        ],
        checks=["vehicle_count_three", "left_hand_traffic", "right_hand_drive_visible", "outside_mask_pixel_diff_zero", "perspective_contact", "file_opens"],
        hard_gates=["three cars", "left-hand traffic", "right-hand drive evidence", "zero outside-mask change"],
        capability_tags=["tool_execution", "workflow_orchestration", "structured_editing"],
        rubric_kind="edit",
        edit_parameters=[
            {"name": "vehicle_count", "target": "edit-target/road", "value_type": "number", "allowed_change": "3", "verification": "object count"},
            {"name": "traffic_side", "target": "edit-target/road", "value_type": "enum", "allowed_change": "left_hand", "verification": "multimodal traffic-rule judge"},
        ],
        extra_artifacts=(("preview.png", "PNG", "Edited road preview."), ("change_set.json", "JSON", "Records inserted vehicles and protected regions.")),
    ))

    rows.append(episode(
        case_id="DAB-L4-RDT-007", seed_id="RBS-BID-001", level="L4",
        category="brand_identity_directions", primary="generate", secondary=["evaluate_rank"],
        role="founder", organization="premium architectural surfaces brand launching in India",
        goal="build a distinctive, scalable B2B identity for specification and trade audiences",
        query=(
            "Develop three genuinely different logo directions for a premium laminate-surface brand launching "
            "in India. The identity should feel minimal, professional, modern, reliable, and high quality for "
            "architects, interior designers, and premium residential/commercial projects. Show how each direction "
            "scales from favicon to sample-book cover; wait for selection before refining."
        ),
        inputs=[text_input("client-brief", "copy", "source_brief", "Premium laminate surfaces; India launch; B2B architects/interior designers; minimal, modern, reliable; consistency and scalability required.")],
        hard=["Present exactly three distinguishable directions before refinement", "Each direction includes small-size and sample-book stress tests", "Do not select a direction without the human checkpoint"],
        soft=["Premium rather than luxury-fashion", "Credible for technical specifiers and commercial buyers"],
        negative=["No generic house, roof, or marble-vein icon shortcuts", "Do not collapse the three directions into palette variants"],
        workflow=[
            checkpoint("understand", "Operationalise vague adjectives and audience needs"),
            checkpoint("diverge", "Create three distinct strategic and visual directions"),
            checkpoint("stress_test", "Test every direction at favicon and sample-book scales"),
            checkpoint("select", "Record evaluator-controlled human selection"),
            checkpoint("refine", "Refine only the selected direction and preserve its strategy"),
            checkpoint("deliver", "Export identity starter system and verification evidence"),
        ],
        deliverables=[
            deliverable("direction-boards", "intermediate", "brand_direction_board", 3, ["PNG"], "Three distinct concepts", "Each includes two scale tests"),
            deliverable("identity-starter", "final", "selected_identity_system", 1, ["PNG", "SVG", "PDF"], "Selected mark and wordmark", "Usage and minimum-size notes"),
        ],
        reference_contract=[],
        checks=["brief_adherence", "territory_distinctness", "audience_fit", "small_size_legibility", "sample_book_fit", "human_selection_used", "state_version_continuity"],
        hard_gates=["exactly three directions", "human selection precedes refinement", "selected identity has vector master"],
        capability_tags=["tool_execution", "workflow_orchestration", "creative_exploration", "multi_turn_revision", "production_execution"],
        rubric_kind="workflow",
        feedback=[controlled_feedback("select", "Select direction B. Keep its architectural grid and restrained wordmark, but make the symbol readable at 16 px before preparing the final system.", ["Refine direction B only", "Improve 16 px symbol legibility"], ["Architectural grid", "Restrained wordmark", "B2B positioning"])],
        human_checkpoints=[{"after_checkpoint": "stress_test", "decision_type": "select_creative_territory", "required": True, "evidence": "Selected direction ID and reason are recorded before refinement."}],
        extra_artifacts=(("preview.png", "PNG", "Final selected identity preview."), ("design_document.json", "JSON", "Records vector objects, typography, and scale variants.")),
    ))

    rows.append(episode(
        case_id="DAB-L4-RDT-008", seed_id="RBS-PSF-002", level="L4",
        category="concept_to_factory_ready", primary="export", secondary=["generate"],
        role="packaging designer", organization="small consumer-goods brand",
        goal="avoid a false factory-ready claim when structural production data is missing",
        query=(
            "Prepare packaging artwork for a new carton, but the manufacturer has not supplied a dieline. "
            "Determine what can be completed safely now, request or derive the missing structural information, "
            "and do not label anything print-ready until panel geometry, bleed, folds, and safe areas are verified."
        ),
        inputs=[
            text_input("product-copy", "copy", "approved_front_and_back_copy", "Brand: North Field. Product: Herbal Balm. Net 60 g. Approved ingredients and warnings supplied in project copy."),
            missing_input("manufacturer-dieline", "spec", "factory_panel_map_bleed_and_fold_geometry"),
        ],
        hard=["Do not claim or export a factory-ready production file without verified dieline geometry", "List the exact missing structural parameters", "Separate concept-safe work from production-blocked work"],
        soft=["Minimise rework by preparing reusable hierarchy and content mapping"],
        negative=["Do not invent hidden panel dimensions", "Do not place legal copy against guessed folds"],
        workflow=[
            checkpoint("preflight", "Detect absent dieline and enumerate blocked dependencies"),
            checkpoint("clarify", "Request manufacturer file or minimum physical carton specification"),
            checkpoint("provisional_structure", "Build a clearly labelled provisional panel map only after receiving controlled dimensions"),
            checkpoint("prototype", "Require physical sample/fold check before production release"),
            checkpoint("deliver", "Deliver concept package and blocked/conditional preflight report"),
        ],
        deliverables=[
            deliverable("concept-layout", "intermediate", "non_production_packaging_concept", 1, ["PNG", "PDF"], "Clearly marked NOT PRINT READY", "Content hierarchy only"),
            deliverable("preflight-report", "final", "production_blocker_report", 1, ["JSON", "PDF"], "Enumerates missing/assumed geometry", "Records required approval and sample test"),
        ],
        reference_contract=[],
        checks=["missing_dieline_detected", "production_claim_blocked", "missing_parameters_complete", "assumptions_labelled", "prototype_required", "state_version_continuity"],
        hard_gates=["no factory-ready claim", "no invented dieline", "preflight report present"],
        capability_tags=["tool_execution", "workflow_orchestration", "multi_turn_revision", "production_execution"],
        rubric_kind="production",
        feedback=[controlled_feedback("clarify", "The supplier still has no file. The provisional carton is 120 × 70 × 210 mm, reverse-tuck, 350 gsm board. Prepare a labelled provisional structure and a physical-sample checklist; it is still not approved for print.", ["Create provisional panel map from supplied outer dimensions and carton type", "Add physical-sample verification checklist"], ["NOT PRINT READY status", "No guessed bleed/fold tolerance represented as approved"])],
        messy=[{"type": "missing_asset", "detail": "The manufacturer dieline that defines production geometry is absent.", "expected_recovery": ["Block production release", "Request source or document assumptions", "Require prototype validation"]}],
        human_checkpoints=[{"after_checkpoint": "prototype", "decision_type": "approve_production_parameters", "required": True, "evidence": "Physical sample and manufacturer geometry approval are required before print release."}],
        extra_artifacts=(("preview.png", "PNG", "Non-production concept preview with visible status."),),
    ))

    rows.append(episode(
        case_id="DAB-L4-RDT-009", seed_id="RBS-CFRY-001", level="L4",
        category="concept_to_factory_ready", primary="export", secondary=["edit"],
        role="production lead", organization="growing premium-label studio",
        goal="turn approved raster artwork into a repeatable true-vector production workflow",
        query=(
            "Convert the supplied approved raster artwork into a true vector master suitable for printing at any "
            "size. This is the pilot for a future queue of hundreds of logos and labels: record when automatic "
            "tracing is accepted, when manual node cleanup is required, and require approval of the exemplar before "
            "the batch workflow is released."
        ),
        inputs=[
            asset_input("approved-raster", "existing_design", "approved_source_artwork", "factory-orbit-coffee-artwork"),
            text_input("batch-spec", "spec", "scale_and_formats", "Pilot one exemplar; future queue 100–500 items; required masters SVG, EPS, PDF; artwork must remain visually faithful at small and large sizes."),
        ],
        hard=["Output contains editable vector paths rather than an embedded full-frame raster", "Preserve the approved artwork's geometry, wording, and colour relationships", "Human approval of the exemplar precedes batch release"],
        soft=["Minimise unnecessary nodes and document repeatable thresholds"],
        negative=["Do not silently redraw or restyle the approved artwork", "Do not represent auto-trace artifacts as final quality"],
        workflow=[
            checkpoint("inspect", "Assess source resolution, edge complexity, text, and colour regions"),
            checkpoint("vectorize", "Create vector geometry and separate editable text/shape objects"),
            checkpoint("preflight", "Detect embedded raster, open paths, node noise, and scale drift"),
            checkpoint("approve_exemplar", "Record human decision on pilot fidelity"),
            checkpoint("refine", "Apply requested node cleanup without changing approved identity"),
            checkpoint("deliver", "Export master formats plus scalable workflow report"),
        ],
        deliverables=[
            deliverable("vector-master", "final", "true_vector_master", 1, ["SVG", "EPS", "PDF"], "No full-frame raster dependency", "Geometry and colours match source"),
            deliverable("batch-workflow", "intermediate", "vectorization_decision_protocol", 1, ["JSON", "PDF"], "Defines auto-trace acceptance threshold", "Defines manual-review triggers"),
        ],
        reference_contract=[reference("approved-raster", "source_artwork", ["geometry", "wording", "color_relationships"], "preserve_identity")],
        checks=["true_vector_structure", "source_fidelity", "text_accuracy", "scale_independence", "node_quality", "human_selection_used", "batch_protocol_complete"],
        hard_gates=["true vector master", "source identity preserved", "exemplar approved before batch"],
        capability_tags=["tool_execution", "workflow_orchestration", "multi_turn_revision", "production_execution"],
        rubric_kind="production",
        feedback=[controlled_feedback("approve_exemplar", "The exemplar matches, but the small curved corners contain too many noisy nodes. Keep all approved geometry and colours; clean only those curves, rerun preflight, then freeze the batch rule.", ["Reduce noisy corner nodes", "Rerun vector preflight", "Freeze the acceptance rule"], ["Artwork geometry", "Wording", "Colour relationships"])],
        human_checkpoints=[{"after_checkpoint": "preflight", "decision_type": "approve_production_parameters", "required": True, "evidence": "Exemplar fidelity and structural preflight must be approved before batch release."}],
        edit_parameters=[{"name": "vector_cleanup", "target": "vector-master/curves", "value_type": "enum", "allowed_change": "remove redundant nodes without silhouette drift", "verification": "node count plus raster-overlay diff"}],
        extra_artifacts=(("preview.png", "PNG", "Rasterised proof of vector master."), ("design_document.json", "JSON", "Records vector objects, text, colours, and raster dependencies.")),
    ))

    rows.append(episode(
        case_id="DAB-L3-RDT-010", seed_id="RBS-CFRY-002", level="L3",
        category="concept_to_factory_ready", primary="export", secondary=["edit"],
        role="print-on-demand prepress operator", organization="custom apparel shop",
        goal="answer printability and recover artwork from a degraded product photograph",
        query=(
            "A customer supplied only this phone photograph of a printed T-shirt and asks whether the chest "
            "artwork can be reprinted. Separate the owl art from fabric, folds, lighting, and perspective; build "
            "the cleanest faithful vector reconstruction you can; then issue an evidence-backed printability verdict. "
            "Do not call it print-ready if fidelity or colour evidence is insufficient."
        ),
        inputs=[asset_input("shirt-photo", "product_image", "degraded_product_photo", "v03-owl-shirt-client-photo")],
        hard=["Do not include shirt fabric, body, lighting, or perspective in extracted artwork", "Verdict must distinguish print_ready, manual_review, and insufficient_source", "Any vector master must contain editable paths"],
        soft=["Recover the three-colour geometric owl with simple, production-friendly geometry"],
        negative=["Do not hallucinate small source details that the photograph cannot support", "Do not promise exact colour matching from uncalibrated lighting"],
        workflow=[
            checkpoint("inspect", "Assess occlusion, perspective, blur, colour uncertainty, and reconstructability"),
            checkpoint("extract", "Rectify and isolate the artwork from the substrate"),
            checkpoint("vectorize", "Reconstruct production-friendly paths and colour regions"),
            checkpoint("verify", "Compare silhouette, exclusions, vector structure, and uncertainty"),
            checkpoint("deliver", "Export proof, vector when justified, and printability verdict"),
        ],
        deliverables=[
            deliverable("recovered-artwork", "final", "substrate_removed_artwork", 1, ["PNG", "SVG"], "No shirt or body pixels", "Original owl identity retained"),
            deliverable("printability-verdict", "final", "evidence_backed_prepress_verdict", 1, ["JSON"], "Uses the three-state verdict", "Lists uncertainty and required human review"),
        ],
        reference_contract=[reference("shirt-photo", "source_artwork", ["printed_artwork_identity", "approximate_color_regions"], "preserve_identity")],
        checks=["substrate_removed", "perspective_rectified", "artwork_identity", "true_vector_structure", "uncertainty_disclosed", "printability_verdict_valid"],
        hard_gates=["no substrate in artwork", "valid evidence-backed verdict", "no false print-ready claim"],
        capability_tags=["tool_execution", "workflow_orchestration", "production_execution"],
        rubric_kind="production",
        messy=[{"type": "invalid_spec", "detail": "Only an uncalibrated photograph of the printed product is available.", "expected_recovery": ["Separate recoverable geometry from unknowable colour", "Return a conditional verdict", "Escalate uncertain fidelity to manual review"]}],
        extra_artifacts=(("preview.png", "PNG", "Recovered artwork proof beside source crop."), ("design_document.json", "JSON", "Records paths, colours, and unresolved uncertainty.")),
    ))

    rows.append(episode(
        case_id="DAB-L3-RDT-011", seed_id="RBS-CFRY-003", level="L3",
        category="concept_to_factory_ready", primary="export", secondary=[],
        role="freelance production designer", organization="small client-services studio",
        goal="convert a supplied raster mark into an inexpensive, faithful vector deliverable",
        query=(
            "Convert the supplied client raster into a true vector master without redesigning it. Preserve the "
            "silhouette, lettering, and colour boundaries; minimise redundant nodes; provide SVG and print PDF plus "
            "a raster overlay proof. Do not embed the source PNG as the vector output."
        ),
        inputs=[asset_input("client-raster", "existing_design", "source_artwork", "factory-luna-club-sticker")],
        hard=["SVG contains editable paths and no full-frame embedded source raster", "Silhouette, lettering, and colour boundaries match the source", "Both SVG and print PDF open successfully"],
        soft=["Use an economical automated path with targeted cleanup", "Keep path count and node count practical"],
        negative=["Do not redesign, simplify away identity, or replace lettering", "Do not upscale the PNG and call it vector"],
        workflow=[
            checkpoint("inspect", "Identify regions, text risk, transparency, and edge quality"),
            checkpoint("vectorize", "Trace and reconstruct editable paths"),
            checkpoint("verify", "Inspect vector structure and raster-overlay fidelity"),
            checkpoint("deliver", "Export SVG, PDF, proof, and verification evidence"),
        ],
        deliverables=[
            deliverable("vector-master", "final", "faithful_vector_master", 1, ["SVG", "PDF"], "Editable paths", "No embedded source raster"),
            deliverable("overlay-proof", "final", "source_vector_comparison", 1, ["PNG"], "Shows source and rasterised vector alignment"),
        ],
        reference_contract=[reference("client-raster", "source_artwork", ["silhouette", "lettering", "color_boundaries"], "preserve_exact")],
        checks=["true_vector_structure", "source_overlay_fidelity", "lettering_accuracy", "color_boundary_fidelity", "node_efficiency", "files_open"],
        hard_gates=["true vector structure", "source identity preserved", "SVG and PDF open"],
        capability_tags=["tool_execution", "workflow_orchestration", "production_execution"],
        rubric_kind="production",
        extra_artifacts=(("preview.png", "PNG", "Raster overlay proof."), ("design_document.json", "JSON", "Records vector objects and source comparison.")),
    ))

    return rows


def main() -> int:
    base_rows = read_jsonl(BASE)
    migrated = []
    for source in base_rows:
        row = copy.deepcopy(source)
        row["schema_version"] = "0.3"
        row["revision"] = {
            "base_dataset": "briefs.v0.2.jsonl",
            "base_brief_id": source["id"],
            "business_scope_changed": False,
            "protocol_changes": ["schema-only migration into the v0.3 core partition; episode contract unchanged"],
        }
        migrated.append(row)

    seeds = {row["id"]: row for row in read_jsonl(SEEDS) if row.get("record_type") == "case"}
    selected = external_rows()
    selected_seed_ids = {row["revision"]["base_brief_id"] for row in selected}
    expected_seed_ids = {key for key, row in seeds.items() if row.get("brief_readiness") == "ready_to_author"}
    if selected_seed_ids != expected_seed_ids:
        raise ValueError(
            f"external selection mismatch: missing={sorted(expected_seed_ids-selected_seed_ids)} "
            f"extra={sorted(selected_seed_ids-expected_seed_ids)}"
        )

    rows = migrated + selected
    OUTPUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(f"rows={len(rows)} core={len(migrated)} external={len(selected)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
