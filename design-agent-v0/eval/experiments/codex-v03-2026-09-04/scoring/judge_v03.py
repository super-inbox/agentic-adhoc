#!/usr/bin/env python3
"""Independent condition-aware multimodal judge for the v0.3 extension.

This scorer sees the projected user request, evaluator-computed file/pixel
facts, bound source images, and candidate outputs. Candidate self-verification
is excluded as evidence.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

from google import genai
from google.genai import types

from evidence_v03 import (
    EXP,
    business_text,
    input_manifest,
    input_sources,
    masked_edit_facts,
    output_inventory,
    production_facts,
    selected_runs,
    sha256,
    structured_artifact_facts,
    trajectory_facts,
)


HERE = Path(__file__).resolve().parent
MODEL = os.environ.get("JUDGE_MODEL", "gemini-2.5-pro")
MAX_INPUT_IMAGES = int(os.environ.get("JUDGE_V03_MAX_INPUT_IMAGES", "4"))
MAX_OUTPUT_IMAGES = int(os.environ.get("JUDGE_V03_MAX_OUTPUT_IMAGES", "12"))

DIMENSION_DEFINITIONS = {
    "brief_adherence": "Follows the condition-specific request, deliverables, hard constraints, and exclusions.",
    "visual_quality": "Visible craft, composition, hierarchy, realism/illustration finish, legibility, and absence of defects.",
    "creative_diversity": "Required alternatives are meaningfully distinct concepts, not palette or layout variants.",
    "brand_consistency": "Outputs preserve the stated brand identity and consistently apply its system.",
    "refinement_ability": "The result is structured and editable enough for a precise next revision; revealed feedback is applied cleanly when present.",
    "cross_asset_consistency": "A multi-asset set shares a coherent system while preserving each asset's role and required differences.",
    "production_readiness": "Files, dimensions, vector/raster structure, labels, preflight status, and handoff evidence are appropriate for claimed use.",
    "efficiency": "Completes the intended turns without retries or unnecessary user loops. Use the evaluator-provided deterministic score.",
    "workflow_completion": "Observable outputs and version sequence cover the necessary understand/create/checkpoint/refine/deliver stages without bypassing approval.",
    "reference_contract": "Transfers only the allowed reference channels and avoids forbidden subject, identity, layout, colour, wording, or branding transfer.",
    "edit_fidelity": "The requested local edit is semantically and visually correct, including exact copy/count/domain constraints.",
    "preservation_fidelity": "Protected or unrelated source regions are unchanged; dimensions/mode and locked content are preserved.",
    "output_fidelity": "The reconstructed/exported output faithfully preserves the approved or recoverable source identity and content.",
    "verification_quality": "Independent preflight facts and the delivered evidence support the verdict, uncertainty, blockers, and release state.",
    "scalability": "The workflow and master structure can be repeated or resized without brittle raster dependence or uncontrolled manual ambiguity.",
}

PROMPT = """You are the independent final evaluator of one Design Agent run.
Work violation-first. Grade only the condition-specific request and supplied
evidence. The benchmark candidate did not see the rubric or future feedback.

EVIDENCE POLICY
1. EVALUATOR FACTS are computed directly from disk. They override filenames,
   reports, verification.json, change_set.json, design_document.json, or other
   candidate claims.
2. A missing file is missing. A candidate statement never proves a visual,
   pixel, vector, print, or workflow property.
3. Labelled INPUT and OUTPUT images are actual pixels. Compare them directly.
4. For masked edits, outside_mask_changed_pixels must be exactly 0 when the
   gate says zero. Do not soften this requirement.
5. An SVG with an embedded source raster is not a true vector master. A PDF
   containing only a placed raster does not independently satisfy a vector gate.
6. CANNOT_TELL is not MET. Use NOT_APPLICABLE only when a dimension or check is
   genuinely outside this condition, never because the candidate omitted proof.
7. Do not demand a particular tool name or hidden chain of thought. Observable
   outputs and version/turn sequence are the evidence.

CONDITION
{condition_id}

USER REQUEST
{query}

VISIBLE INPUT CONTEXT
{input_context}

REFERENCE CONTRACT
{reference_contract}

HARD CONSTRAINTS
{hard_constraints}

NEGATIVE CONSTRAINTS
{negative_constraints}

SOFT PREFERENCES
{soft_constraints}

DELIVERABLE CONTRACT
{deliverables}

EXPECTED OBSERVABLE WORKFLOW
{workflow}

REQUIRED HUMAN CHECKPOINTS
{human_checkpoints}

FEEDBACK REVEALED AFTER THE INITIAL TURN
{feedback}

LOCKED INVARIANTS
{invariants}

RUBRIC DIMENSIONS AND WEIGHTS
{dimensions}

HARD GATES — return exactly one verdict for every string in this list
{hard_gates}

EVALUATOR-COMPUTED INPUT MANIFEST
{manifest}

EVALUATOR-COMPUTED OUTPUT INVENTORY
{inventory}

EVALUATOR-COMPUTED PRODUCTION FILE FACTS
{production}

EVALUATOR-COMPUTED MASKED EDIT FACTS
{masked_edit}

EVALUATOR-COMPUTED TRAJECTORY FACTS
{trajectory}

EVALUATOR-COMPUTED STRUCTURED ARTIFACT PRESENCE
{structured_artifacts}

BUSINESS DELIVERABLE TEXT
This may be graded as a requested report but cannot prove pixels or file
structure merely by making claims.
{business_text}

SCORING
Use integer scores 0–5 for every listed applicable dimension:
5 = all important requirements observably met; no material defect or violation
4 = correct and complete with only minor finish/evidence weakness
3 = usable, but one important requirement is weak, incomplete, or unverified
2 = material requirement missing or execution substantially flawed
1 = hard gate broken, wrong operation, or core result largely unusable
0 = task not addressed / no meaningful result

For efficiency, copy this deterministic score exactly: {efficiency_score}.
For all other dimensions, cite concrete filenames, evaluator facts, or visible
features. If an applicable dimension cannot be fully observed, score 3 or below
as warranted; do not omit it.

Return ONLY JSON with this exact structure:
{{
  "hard_gates": [{{"gate":"exact original string","verdict":"MET|VIOLATED|CANNOT_TELL","evidence":"..."}}],
  "checks": [{{"item":"...","verdict":"MET|VIOLATED|CANNOT_TELL|NOT_APPLICABLE","evidence":"..."}}],
  "scores": {{"dimension":{{"score":0,"why":"..."}}}},
  "overall_note":"one concise evidence-based synthesis"
}}
"""


def choose_evenly(items: list[Path], limit: int) -> list[Path]:
    if len(items) <= limit:
        return items
    if limit <= 1:
        return [items[-1]]
    indices = {round(index * (len(items) - 1) / (limit - 1)) for index in range(limit)}
    return [items[index] for index in sorted(indices)]


def output_images(run: Path) -> list[Path]:
    root = run / "outputs"
    if not root.is_dir():
        return []
    excluded = (
        "/qa/", "/masks/", "/layers/", "/evidence/", "/assets/",
        "-mask", "_mask", "-difference", "_difference", "-source", "_source",
        "-crop", "_crop",
    )
    images = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        rel = f"/{path.relative_to(root)}".lower()
        if any(token in rel for token in excluded):
            continue
        images.append(path)
    # Always keep previews, then sample the remaining artifacts across versions.
    previews = [path for path in images if path.name.lower() == "preview.png"]
    others = [path for path in images if path not in previews]
    selected = previews[-2:] + choose_evenly(others, max(0, MAX_OUTPUT_IMAGES - len(previews[-2:])))
    return selected[:MAX_OUTPUT_IMAGES]


def inline_image(label: str, path: Path) -> list[dict]:
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }[path.suffix.lower()]
    return [
        {"text": label},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(path.read_bytes()).decode()}},
    ]


def compact_json(value, cap: int) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:cap]


def judge(client, run: Path, brief: dict, result: dict, query: dict) -> dict:
    weights = (brief.get("rubric") or {}).get("checkpoint_weights") or {}
    dimensions = {
        key: {"weight": weight, "definition": DIMENSION_DEFINITIONS[key]}
        for key, weight in weights.items()
    }
    efficiency_score = 5 if result.get("completed_turns") == result.get("intended_turns") else 0
    constraints = brief.get("constraints") or {}
    prompt = PROMPT.format(
        condition_id=query["id"],
        query=query.get("query"),
        input_context=compact_json(query.get("input_context") or [], 8000),
        reference_contract=compact_json(brief.get("reference_contract") or [], 7000),
        hard_constraints=compact_json(constraints.get("hard") or [], 5000),
        negative_constraints=compact_json(constraints.get("negative") or [], 5000),
        soft_constraints=compact_json(constraints.get("soft") or [], 4000),
        deliverables=compact_json(brief.get("deliverables") or [], 9000),
        workflow=compact_json(brief.get("expected_workflow") or [], 8000),
        human_checkpoints=compact_json(brief.get("human_checkpoints") or [], 4000),
        feedback=compact_json(brief.get("feedback") or [], 8000),
        invariants=compact_json((brief.get("project_state") or {}).get("locked_invariants") or [], 4000),
        dimensions=compact_json(dimensions, 8000),
        hard_gates=compact_json((brief.get("rubric") or {}).get("hard_gates") or [], 5000),
        manifest=compact_json(input_manifest(run), 9000),
        inventory=compact_json(output_inventory(run), 60000),
        production=compact_json(production_facts(run), 30000),
        masked_edit=compact_json(masked_edit_facts(run, brief["id"]), 12000),
        trajectory=compact_json(trajectory_facts(run, result), 10000),
        structured_artifacts=compact_json(structured_artifact_facts(run, query), 5000),
        business_text=business_text(run),
        efficiency_score=efficiency_score,
    )
    parts = [{"text": prompt}]
    for label, path in input_sources(run)[:MAX_INPUT_IMAGES]:
        if path.stat().st_size <= 7_000_000:
            parts.extend(inline_image(f"{label}; sha256={sha256(path)}", path))
    for path in output_images(run):
        if path.stat().st_size <= 7_000_000:
            parts.extend(
                inline_image(
                    f"OUTPUT {path.relative_to(run / 'outputs')}; sha256={sha256(path)}",
                    path,
                )
            )
    response = client.models.generate_content(
        model=MODEL,
        contents=[{"role": "user", "parts": parts}],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].removeprefix("json").strip()
    value = json.loads(raw)
    scores = value.get("scores") or {}
    for dimension in weights:
        score = (scores.get(dimension) or {}).get("score")
        if not isinstance(score, (int, float)) or not 0 <= score <= 5:
            raise ValueError(f"invalid {dimension} score: {score!r}")
    if (scores.get("efficiency") or {}).get("score") != efficiency_score:
        raise ValueError("judge did not copy deterministic efficiency score")
    hard_gates = value.get("hard_gates") or []
    expected_gates = (brief.get("rubric") or {}).get("hard_gates") or []
    returned = [row.get("gate") for row in hard_gates]
    if returned != expected_gates:
        raise ValueError(f"hard gate list mismatch: {returned!r}")
    return value


def write_snapshot(path: Path, rows: dict[str, dict], selected: set[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(rows[key], ensure_ascii=False) + "\n" for key in sorted(selected) if key in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-new-runs", type=int, default=0)
    parser.add_argument("--condition", action="append", default=[])
    parser.add_argument("--retry-errors", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY is required", file=sys.stderr)
        return 2
    runs = [
        row for row in selected_runs()
        if not args.condition or row[3]["id"] in set(args.condition)
    ]
    output_path = HERE / "rubric-v03-judged.jsonl"
    rows = {}
    if output_path.exists():
        for row in [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]:
            rows[row["run"]] = row
    selected_ids = {str(run.relative_to(EXP)) for run, _, _, _ in runs}
    client = genai.Client(api_key=key)
    attempted = 0
    for index, (run, brief, result, query) in enumerate(runs, 1):
        run_id = str(run.relative_to(EXP))
        prior = rows.get(run_id)
        if prior and prior.get("error") is None:
            continue
        if prior and not args.retry_errors:
            continue
        if args.max_new_runs and attempted >= args.max_new_runs:
            break
        attempted += 1
        error = None
        value = {}
        for retry in range(3):
            try:
                value = judge(client, run, brief, result, query)
                break
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:1000]
                if retry < 2:
                    time.sleep(3 * (retry + 1))
        else:
            value = {}
        if value:
            error = None
        rows[run_id] = {
            "run": run_id,
            "condition_id": query["id"],
            "brief_id": brief["id"],
            "condition": query.get("context_condition"),
            "level": brief.get("level"),
            "category": brief.get("category"),
            "model": MODEL,
            "judge_version": "v0.3-artifact-grounded-1",
            "error": error,
            "hard_gates": value.get("hard_gates") or [],
            "checks": value.get("checks") or [],
            "scores": value.get("scores") or {},
            "overall_note": value.get("overall_note"),
        }
        write_snapshot(output_path, rows, set(rows) if args.condition else selected_ids)
        score_text = " ".join(
            f"{key[:4]}={(rows[run_id]['scores'].get(key) or {}).get('score')}"
            for key in (brief.get("rubric") or {}).get("checkpoint_weights") or {}
        )
        print(
            f"{index}/{len(runs)} {query['id']} {score_text}" + (f" ERROR {error}" if error else ""),
            flush=True,
        )
        if error and ("RESOURCE_EXHAUSTED" in error or "spending cap" in error.lower()):
            break
        time.sleep(1)
    coverage = sum(1 for key in selected_ids if rows.get(key, {}).get("error") is None)
    print(f"judge coverage: {coverage}/{len(selected_ids)}")
    print(f"wrote {output_path.relative_to(EXP)}")
    return 0 if coverage == len(selected_ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
