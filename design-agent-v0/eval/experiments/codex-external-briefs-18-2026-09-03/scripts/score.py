#!/usr/bin/env python3
"""Freeze and score the 18 external-brief planning cases."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
DATASET = EXP / "dataset" / "external-briefs.jsonl"
SCHEMA = EXP / "schemas" / "planner-output.schema.json"
RUNS = EXP / "runs"
RESULTS = EXP / "results"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def mean(values) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def prf(predicted: list[str], expected: list[str]) -> tuple[float, float, float]:
    pset, eset = set(predicted), set(expected)
    overlap = len(pset & eset)
    precision = overlap / len(pset) if pset else 0.0
    recall = overlap / len(eset) if eset else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def lcs_ratio(predicted: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    table = [[0] * (len(expected) + 1) for _ in range(len(predicted) + 1)]
    for i, left in enumerate(predicted, start=1):
        for j, right in enumerate(expected, start=1):
            table[i][j] = table[i - 1][j - 1] + 1 if left == right else max(table[i - 1][j], table[i][j - 1])
    return table[-1][-1] / len(expected)


def attempts(case_id: str):
    found = []
    for path in sorted((RUNS / case_id).glob("attempt-*/meta.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        response_path = path.parent / "response.json"
        response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else None
        found.append((meta, response, path.parent))
    return found


def is_harness_preflight(run_dir: Path) -> bool:
    """Return true when Codex rejected the harness before model inference."""
    trace_path = run_dir / "trace.jsonl"
    if not trace_path.exists():
        return False
    return "invalid_json_schema" in trace_path.read_text(encoding="utf-8", errors="replace")


def score_case(case: dict[str, Any], response: dict[str, Any], meta: dict[str, Any]) -> tuple[dict, dict, float, bool]:
    expected = case["expected"]
    intent = response.get("primary_intent") == expected["primary_intent"]
    brief_class = response.get("brief_class") == expected["brief_class"]
    predicted_steps = [item.get("id") for item in response.get("workflow_steps", []) if isinstance(item, dict)]
    gold_steps = expected["workflow_steps"]
    step_precision, step_recall, step_f1 = prf(predicted_steps, gold_steps)
    step_order = lcs_ratio(predicted_steps, gold_steps)
    if expected["step_count"]:
        step_count = max(0.0, 1.0 - abs(len(predicted_steps) - expected["step_count"]) / expected["step_count"])
    else:
        step_count = None
    predicted_deliverables = response.get("deliverable_concepts") or []
    deliverable_precision, deliverable_recall, deliverable_f1 = prf(predicted_deliverables, expected["deliverable_concepts"])
    expected_assets = {item["asset_id"] for item in case["input"]["input_assets"]}
    observed_assets = {item.get("asset_id") for item in response.get("reference_observations", []) if isinstance(item, dict)}
    reference_coverage = len(expected_assets & observed_assets) / len(expected_assets) if expected_assets else 1.0
    boundary_awareness = mean([
        response.get("execution_status") == "not_executed",
        bool(response.get("missing_inputs")),
        bool(response.get("stop_conditions")),
    ])
    plan_present = bool(predicted_steps and predicted_deliverables and response.get("rationale"))

    gates = {
        "schema_valid": not meta.get("validation_errors"),
        "tool_call_free": meta.get("trace", {}).get("tool_call_count", 0) == 0,
        "not_executed": response.get("execution_status") == "not_executed",
    }
    if case["layer"] == "portfolio_reference":
        gates["all_references_observed"] = expected_assets == observed_assets
        weighted = (
            0.10 * intent
            + 0.15 * brief_class
            + 0.25 * reference_coverage
            + 0.30 * deliverable_recall
            + 0.10 * boundary_awareness
            + 0.10 * plan_present
        )
    else:
        weighted = (
            0.10 * intent
            + 0.45 * step_f1
            + 0.25 * step_order
            + 0.10 * (step_count or 0.0)
            + 0.10 * boundary_awareness
        )
    gate_pass = all(gates.values())
    total = weighted if gate_pass else 0.0
    scores = {
        "intent_exact": intent,
        "brief_class_exact": brief_class,
        "step_precision": step_precision if gold_steps else None,
        "step_recall": step_recall if gold_steps else None,
        "step_f1": step_f1 if gold_steps else None,
        "step_order_lcs": step_order if gold_steps else None,
        "step_count_match": step_count,
        "sequence_exact": predicted_steps == gold_steps if gold_steps else None,
        "deliverable_precision": deliverable_precision,
        "deliverable_recall": deliverable_recall,
        "deliverable_f1": deliverable_f1,
        "reference_coverage": reference_coverage,
        "boundary_awareness": boundary_awareness,
        "plan_present": plan_present,
        "weighted_score": weighted,
        "gated_total": total,
        "case_pass": gate_pass and total >= 0.70,
    }
    return scores, gates, total, scores["case_pass"]


def aggregate(rows: list[dict]) -> dict:
    completed = [row for row in rows if row["status"] == "completed"]
    return {
        "n": len(rows),
        "completed": len(completed),
        "first_attempt_completed": sum(row["first_attempt_completed"] for row in rows),
        "passes": sum(bool(row.get("scores", {}).get("case_pass")) for row in completed),
        "intent_exact": mean(row["scores"].get("intent_exact") for row in completed),
        "brief_class_exact": mean(row["scores"].get("brief_class_exact") for row in completed),
        "step_f1": mean(row["scores"].get("step_f1") for row in completed),
        "step_order_lcs": mean(row["scores"].get("step_order_lcs") for row in completed),
        "sequence_exact": mean(row["scores"].get("sequence_exact") for row in completed),
        "deliverable_recall": mean(row["scores"].get("deliverable_recall") for row in completed),
        "reference_coverage": mean(row["scores"].get("reference_coverage") for row in completed),
        "boundary_awareness": mean(row["scores"].get("boundary_awareness") for row in completed),
        "weighted_score": mean(row["scores"].get("weighted_score") for row in completed),
        "gated_total": mean(row["scores"].get("gated_total") for row in completed),
    }


def render(summary: dict, rows: list[dict]) -> str:
    workflow = summary["layers"]["case_study_workflow"]
    zcool = summary["layers"]["portfolio_reference"]
    misses = []
    for row in rows:
        if row["status"] != "completed" or row["scores"].get("case_pass"):
            continue
        misses.append(f"- `{row['id']}` — gated={row['scores'].get('gated_total', 0):.3f}; gates={row.get('hard_gates')}")
    miss_text = "\n".join(misses) if misses else "- None."
    return f"""# Codex × external briefs 18 — results

Candidate: `{json.dumps(summary['candidate'], ensure_ascii=False, sort_keys=True)}`

## Reliability

- Selected valid runs: **{summary['reliability']['completed']}/18**
- First eligible model-attempt completion: **{summary['reliability']['first_attempt_completed']}/18**
- Retried cases: **{summary['reliability']['retried_cases']}**
- Excluded harness preflight failures: **{summary['reliability']['harness_preflight_failures']}**

## Case-study workflow layer (11)

| Metric | Result |
|---|---:|
| Completion | {workflow['completed']}/11 |
| Intent exact | {workflow['intent_exact']:.1%} |
| Step F1 | {workflow['step_f1']:.1%} |
| Ordered LCS recall | {workflow['step_order_lcs']:.1%} |
| Exact sequence | {workflow['sequence_exact']:.1%} |
| Weighted / gated mean | {workflow['weighted_score']:.3f} / {workflow['gated_total']:.3f} |
| Passes | {workflow['passes']}/11 |

This layer measures recovery of one documented case-study workflow from a newly
paraphrased task brief. It does not claim that the hidden sequence is the only
valid process and it does not measure design execution or final visual quality.

## ZCOOL portfolio-reference layer (7)

| Metric | Result |
|---|---:|
| Completion | {zcool['completed']}/7 |
| Intent exact | {zcool['intent_exact']:.1%} |
| Brief-class exact | {zcool['brief_class_exact']:.1%} |
| Reference coverage | {zcool['reference_coverage']:.1%} |
| Deliverable-concept recall | {zcool['deliverable_recall']:.1%} |
| Weighted / gated mean | {zcool['weighted_score']:.3f} / {zcool['gated_total']:.3f} |
| Passes | {zcool['passes']}/7 |

This is a low-resolution external-distribution planning canary. The published
portfolio thumbnails are outcome evidence, not a style instruction, workflow
gold, preference label, or permission to copy. No pixel-similarity score is used.

## Failed cases

{miss_text}

## Interpretation boundary

- Planner-only: no design generation/editing was requested or scored.
- Case-study labels describe one observed process, not universal ground truth.
- ZCOOL provides no rejected directions, client feedback, or hidden production files.
- Deterministic concept recall checks scope coverage, not taste or visual quality.
- External pixels remain internal-evaluation-only identification thumbnails.
"""


def main() -> int:
    cases = read_jsonl(DATASET)
    results = []
    for case in cases:
        raw_found = attempts(case["id"])
        preflight = [item for item in raw_found if is_harness_preflight(item[2])]
        found = [item for item in raw_found if not is_harness_preflight(item[2])]
        first = found[0][0] if found else None
        selected = next(((meta, response, path) for meta, response, path in found if meta.get("status") == "completed" and response is not None), None)
        if not selected:
            results.append({
                "id": case["id"], "layer": case["layer"], "status": "missing_or_failed",
                "attempt_count": len(found), "raw_attempt_count": len(raw_found),
                "harness_preflight_failures": len(preflight),
                "first_attempt_completed": bool(first and first.get("status") == "completed"),
                "prediction": None, "scores": {}, "hard_gates": {},
            })
            continue
        meta, response, path = selected
        scores, gates, _, _ = score_case(case, response, meta)
        results.append({
            "id": case["id"], "layer": case["layer"], "status": "completed",
            "attempt_count": len(found), "raw_attempt_count": len(raw_found),
            "harness_preflight_failures": len(preflight),
            "first_attempt_completed": bool(first and first.get("status") == "completed"),
            "selected_attempt": meta["attempt"], "selected_run_dir": str(path.relative_to(EXP)),
            "duration_seconds": meta.get("duration_seconds"), "usage": meta.get("trace", {}).get("usage"),
            "expected": case["expected"], "prediction": response, "scores": scores, "hard_gates": gates,
        })

    by_layer = defaultdict(list)
    for row in results:
        by_layer[row["layer"]].append(row)
    completed = [row for row in results if row["status"] == "completed"]
    attempts_count = sum(row["attempt_count"] for row in results)
    raw_attempts_count = sum(row["raw_attempt_count"] for row in results)
    preflight_failures = sum(row["harness_preflight_failures"] for row in results)
    candidate = None
    for case in cases:
        for meta, _, _ in attempts(case["id"]):
            if meta.get("status") == "completed":
                candidate = meta.get("candidate")
                break
        if candidate:
            break
    usage = Counter()
    for row in completed:
        usage.update(row.get("usage") or {})
    summary = {
        "schema_version": "external-brief-plan-summary-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "candidate": candidate,
        "dataset": {"path": str(DATASET.relative_to(EXP)), "sha256": sha256(DATASET), "rows": len(cases)},
        "reliability": {
            "completed": len(completed), "total": len(results),
            "first_attempt_completed": sum(row["first_attempt_completed"] for row in results),
            "retried_cases": sum(row["attempt_count"] > 1 for row in results),
            "attempts": attempts_count,
            "raw_attempts": raw_attempts_count,
            "harness_preflight_failures": preflight_failures,
        },
        "layers": {key: aggregate(value) for key, value in sorted(by_layer.items())},
        "usage_totals": dict(usage),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    canonical = RESULTS / "canonical-results.jsonl"
    canonical.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results), encoding="utf-8")
    summary_path = RESULTS / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prompts = []
    for row in completed:
        path = EXP / row["selected_run_dir"] / "prompt.txt"
        prompts.append({"id": row["id"], "path": str(path.relative_to(EXP)), "sha256": sha256(path), "bytes": path.stat().st_size})
    prompt_manifest = RESULTS / "prompt-manifest.jsonl"
    prompt_manifest.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in prompts), encoding="utf-8")
    report = EXP / "RESULTS.md"
    report.write_text(render(summary, results), encoding="utf-8")
    manifest = {
        "schema_version": "external-brief-plan-freeze-v1",
        "candidate_config": candidate,
        "candidate_config_sha256": canonical_hash(candidate),
        "model_identity": {"provider": "OpenAI", "interface": "codex-cli", "model_id": (candidate or {}).get("model"), "model_weights_sha256": None, "model_weights_hash_status": "not_exposed_by_codex_cli"},
        "dataset_sha256": sha256(DATASET),
        "output_schema_sha256": sha256(SCHEMA),
        "builder_sha256": sha256(HERE / "build_dataset.py"),
        "runner_sha256": sha256(HERE / "run_codex.py"),
        "scorer_sha256": sha256(HERE / "score.py"),
        "prompt_set_sha256": sha256(prompt_manifest),
        "canonical_results_sha256": sha256(canonical),
        "summary_sha256": sha256(summary_path),
        "row_count": len(results),
    }
    (RESULTS / "freeze-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["reliability"], ensure_ascii=False))
    print(f"results={canonical}\nreport={report}")
    return 0 if len(completed) == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
