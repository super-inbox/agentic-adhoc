#!/usr/bin/env python3
"""Condition-aware independent multimodal judge for Brief Bank v0.2.

V3 fixes evidence defects found after completing the earlier judge-v2 pass:

* evaluates the condition-specific projected query (zero-shot query overrides
  included) instead of always using the base brief query;
* attaches labelled source/reference images and labelled final artifacts;
* supplies a complete evaluator-computed file inventory, so excluding
  candidate self-verification does not make existing files look missing;
* treats requirements for intentionally omitted optional context as N/A;
* scores the L3-only ``tool_execution`` dimension in the same pass.

Candidate-authored verification, metrics, change sets, masks, and narrative
claims are excluded as proof. The raw v2 output remains an audit artifact but
must not be used as the canonical quality result.
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

from judge_rubric_v02 import selected_runs
from judge_tool_execution_v02 import (
    manifest_and_sources,
    output_inventory,
    production_file_facts,
)

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parent.parent
BRIEFS = EVAL / "brief_bank" / "briefs.v0.2.jsonl"
QUERIES = EVAL / "brief_bank" / "initial_queries.v0.2.jsonl"
MODEL = os.environ.get("JUDGE_MODEL", "gemini-2.5-pro")
MAX_INPUT_IMAGES = int(os.environ.get("JUDGE_V3_MAX_INPUT_IMAGES", "6"))
MAX_OUTPUT_IMAGES = int(os.environ.get("JUDGE_V3_MAX_OUTPUT_IMAGES", "10"))
TEXT_CAP = 6000

ALL_DIMS = [
    "brief_understanding",
    "tool_execution",
    "revision_fidelity",
    "cross_asset_consistency",
]

PROMPT = """You are an independent evaluator of one design-agent benchmark
run. Work violation-first and use only the evaluator-computed facts and actual
labelled images supplied here.

EVIDENCE RULES
1. The CONDITION-SPECIFIC USER REQUEST is authoritative. If a base hard gate or
   workflow item requires an optional reference intentionally omitted from this
   condition, mark it NOT_APPLICABLE and do not penalize the candidate.
2. If a required output file is absent from OUTPUT INVENTORY, it is absent.
   Never infer it from a candidate claim or from a filename mentioned in text.
3. Compare labelled INPUT and OUTPUT images directly. Matching SHA-256 hashes
   mean two files are byte-for-byte identical.
4. Candidate-authored verification.json, project-state, metrics, change-set,
   masks, scripts, and final-response claims are excluded as evidence. Business
   deliverable text is included only because it is itself an output to grade;
   it cannot prove a visual or production property merely by asserting it.
5. Missing required assets are failures, not N/A, for an applicable dimension.
6. Do not require exact tool names or a single golden workflow. A different
   implementation is valid if observable outputs satisfy the request.

CONTEXT CONDITION
{condition}

CONDITION-SPECIFIC USER REQUEST
{query}

ALLOWED INPUT CONTEXT FOR THIS CONDITION
{input_context}

APPLICABLE SCORED DIMENSIONS
{applicable_dimensions}

BASE HARD GATES
{hard_gates}

HARD CONSTRAINTS
{hard_constraints}

NEGATIVE CONSTRAINTS
{negative_constraints}

DELIVERABLE REQUIREMENTS
{deliverables}

EXPECTED OBSERVABLE WORKFLOW
{workflow}

REQUIRED HUMAN CHECKPOINTS
{human_checkpoints}

CLIENT FEEDBACK REVEALED ACROSS TURNS
{feedback}

LOCKED INVARIANTS
{invariants}

INPUT MANIFEST
{input_manifest}

OUTPUT INVENTORY
Paths, byte counts, SHA-256 values, and PNG dimensions below are independently
read from disk by the evaluator.
{inventory}

BUSINESS DELIVERABLE TEXT
{business_text}

INDEPENDENT PRODUCTION-FILE FACTS
{production_facts}

STEP 1 — Check every applicable hard gate, hard/negative constraint, countable
deliverable requirement, human checkpoint, and feedback invariant. Return
VIOLATED / MET / CANNOT_TELL / NOT_APPLICABLE with a concrete evidence path,
hash, dimension, visible feature, or short deliverable quote. CANNOT_TELL is not
MET. Do not use NOT_APPLICABLE merely because an expected output is missing.

STEP 2 — Score only the listed APPLICABLE SCORED DIMENSIONS from those checks.
Use integer scores and these common anchors:
  5 = all key requirements observably met; no material violation
  4 = complete and correct with only minor soft-preference/finish issues
  3 = usable but one important requirement is weak or cannot be verified
  2 = a stated key requirement is clearly unmet
  1 = a hard gate/negative constraint is broken, wrong operation was used, or
      the requested core result is largely unusable
  0 = the task was not addressed / no meaningful result

Dimension meanings:
- brief_understanding: adherence to the condition-specific request, constraints,
  intended deliverables, and decision protocol.
- tool_execution (L3 only): the requested edit/adapt/evaluate/export operation
  actually happened and its concrete output is technically usable.
- revision_fidelity (L4 only): each revealed feedback delta was applied while
  locked invariants and unrelated content survived across versions.
- cross_asset_consistency (L4 only): required assets form one coherent visual
  system and preserve identity/reference roles. Missing assets lower the score.

For every non-applicable dimension return null. Return ONLY JSON:
{{"checks":[{{"item":"...","verdict":"VIOLATED|MET|CANNOT_TELL|NOT_APPLICABLE","evidence":"..."}}],
  "brief_understanding":{{"score":null,"why":"..."}},
  "tool_execution":{{"score":null,"why":"..."}},
  "revision_fidelity":{{"score":null,"why":"..."}},
  "cross_asset_consistency":{{"score":null,"why":"..."}}}}"""


def read_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_inputs():
    briefs = {row["id"].lower(): row for row in read_jsonl(BRIEFS)}
    queries = {row["id"]: row for row in read_jsonl(QUERIES)}
    return briefs, queries


def compact_inventory(run: Path):
    rows = output_inventory(run)
    # Code, cache, and font files are implementation details, not benchmark
    # deliverables. Keeping the output list focused also avoids prompt truncation.
    excluded_suffixes = {".py", ".pyc", ".ttf", ".otf"}
    return [
        row for row in rows
        if Path(row["path"]).suffix.lower() not in excluded_suffixes
        and "__pycache__" not in row["path"]
    ]


def business_texts(run: Path):
    output_root = run / "outputs"
    if not output_root.is_dir():
        return []
    excluded_names = {
        "verification.json",
        "project-state.json",
        "change_set.json",
        "design_document.json",
        "metrics.json",
    }
    excluded_tokens = ("verification", "change-set", "change_set", "metrics")
    texts = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file() or path.name in excluded_names:
            continue
        rel = str(path.relative_to(output_root))
        if any(token in rel.lower() for token in excluded_tokens):
            continue
        if path.suffix.lower() not in {".md", ".json", ".txt", ".csv"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        texts.append(f"--- {rel}\n{content[:TEXT_CAP]}")
        if len(texts) >= 18:
            break
    return texts


def choose_evenly(items, limit):
    if len(items) <= limit:
        return items
    if limit <= 1:
        return [items[-1]]
    indices = {round(i * (len(items) - 1) / (limit - 1)) for i in range(limit)}
    return [items[index] for index in sorted(indices)]


def final_images(run: Path):
    output_root = run / "outputs"
    if not output_root.is_dir():
        return []
    excluded_tokens = (
        "/qa/", "/masks/", "/layers/", "/evidence/", "/assets/",
        "-mask", "_mask", "-difference", "_difference", "-source", "_source",
        "-crop", "_crop", "verification",
    )
    paths = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        rel = f"/{path.relative_to(output_root)}".lower()
        if any(token in rel for token in excluded_tokens):
            continue
        paths.append(path)
    return choose_evenly(paths, MAX_OUTPUT_IMAGES)


def inline_image(label: str, path: Path):
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


def applicable_dimensions(brief: dict):
    weights = (brief.get("rubric") or {}).get("checkpoint_weights") or {}
    return [dimension for dimension in ALL_DIMS if dimension in weights]


def judge(client, brief: dict, query: dict, run: Path):
    manifest, sources = manifest_and_sources(run)
    sources = sources[:MAX_INPUT_IMAGES]
    dimensions = applicable_dimensions(brief)
    constraints = brief.get("constraints") or {}
    prompt = PROMPT.format(
        condition=query.get("context_condition"),
        query=query.get("query"),
        input_context=json.dumps(query.get("input_context") or [], ensure_ascii=False)[:6000],
        applicable_dimensions=json.dumps(dimensions, ensure_ascii=False),
        hard_gates=json.dumps((brief.get("rubric") or {}).get("hard_gates") or [], ensure_ascii=False),
        hard_constraints=json.dumps(constraints.get("hard") or [], ensure_ascii=False),
        negative_constraints=json.dumps(constraints.get("negative") or [], ensure_ascii=False),
        deliverables=json.dumps(brief.get("deliverables") or [], ensure_ascii=False)[:7000],
        workflow=json.dumps(brief.get("expected_workflow") or [], ensure_ascii=False)[:6000],
        human_checkpoints=json.dumps(brief.get("human_checkpoints") or [], ensure_ascii=False)[:3000],
        feedback=json.dumps(brief.get("feedback") or [], ensure_ascii=False)[:7000],
        invariants=json.dumps(
            (brief.get("project_state") or {}).get("locked_invariants") or [],
            ensure_ascii=False,
        )[:3000],
        input_manifest=json.dumps(manifest, ensure_ascii=False)[:7000],
        inventory=json.dumps(compact_inventory(run), ensure_ascii=False)[:40000],
        business_text="\n\n".join(business_texts(run))[:40000] or "(none)",
        production_facts=json.dumps(production_file_facts(run), ensure_ascii=False)[:16000]
        or "(none)",
    )
    parts = [{"text": prompt}]
    for label, path in sources:
        if path.stat().st_size <= 6_000_000:
            parts.extend(inline_image(label, path))
    for path in final_images(run):
        if path.stat().st_size <= 6_000_000:
            rel = path.relative_to(run / "outputs")
            parts.extend(inline_image(f"OUTPUT {rel} sha256={output_inventory_hash(path)}", path))

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
        raw = raw.split("```")[1].removeprefix("json").strip()
    value = json.loads(raw)
    for dimension in dimensions:
        score = (value.get(dimension) or {}).get("score")
        if not isinstance(score, (int, float)) or not 0 <= score <= 5:
            raise ValueError(f"invalid {dimension} score: {score!r}")
    return value


def output_inventory_hash(path: Path):
    # Reuse the same independently computed digest without making model-visible
    # claims from candidate-authored files.
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-new-runs", type=int, default=0)
    parser.add_argument("--condition", action="append", default=[])
    return parser.parse_args()


def write_snapshot(path: Path, rows: dict[str, dict], selected_ids: set[str]):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(rows[rid], ensure_ascii=False) + "\n"
            for rid in sorted(selected_ids)
            if rid in rows
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY is required.", file=sys.stderr)
        return 2
    briefs, queries = load_inputs()
    runs = []
    for run, brief, result in selected_runs(briefs):
        query_id = f"{brief['id']}@{result.get('context_condition') or run.parent.name}"
        query = queries.get(query_id)
        if not query or (args.condition and query_id not in args.condition):
            continue
        runs.append((run, brief, result, query))

    output_path = HERE / "rubric-v02-judged-v3.jsonl"
    rows = {}
    if output_path.exists():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["run"]] = row
    selected_ids = {str(run.relative_to(EXP)) for run, _, _, _ in runs}
    done = {
        rid for rid, row in rows.items()
        if rid in selected_ids and row.get("error") is None
    }
    # Only prune to a complete selection. A targeted canary run must not erase
    # results for conditions outside its --condition filter.
    if not args.condition:
        write_snapshot(output_path, rows, selected_ids)

    client = genai.Client(api_key=key)
    attempted = 0
    for index, (run, brief, result, query) in enumerate(runs, 1):
        rid = str(run.relative_to(EXP))
        if rid in done:
            continue
        if args.max_new_runs and attempted >= args.max_new_runs:
            break
        attempted += 1
        try:
            value = judge(client, brief, query, run)
            error = None
        except Exception as exc:
            value = {}
            error = f"{type(exc).__name__}: {exc}"[:500]
        row = {
            "run": rid,
            "brief_id": brief["id"],
            "condition": query["context_condition"],
            "level": brief.get("level"),
            "model": MODEL,
            "judge_version": "v3-condition-aware-artifact-grounded",
            "error": error,
            "checks": value.get("checks") or [],
        }
        dimensions = applicable_dimensions(brief)
        for dimension in ALL_DIMS:
            result_value = value.get(dimension) or {}
            row[dimension] = result_value.get("score") if dimension in dimensions else None
            row[dimension + "_why"] = result_value.get("why")
        rows[rid] = row
        # Preserve prior full-pass rows during a targeted canary.
        write_snapshot(output_path, rows, set(rows) if args.condition else selected_ids)
        scores = " ".join(f"{d[:4]}={row[d]}" for d in dimensions)
        print(f"  {index}/{len(runs)} {query['id']} -> {scores}"
              + (f" ERR {error}" if error else ""), flush=True)
        if error and ("RESOURCE_EXHAUSTED" in error or "spending cap" in error.lower()):
            break
        time.sleep(1)

    success = sum(1 for row in rows.values() if row.get("error") is None)
    print(f"\njudge-v3 successful rows retained: {success}")
    print(f"wrote {output_path.relative_to(EVAL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
