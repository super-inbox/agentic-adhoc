#!/usr/bin/env python3
"""Select the first valid run per case and score both routing layers."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT_DIR = HERE.parent
EVAL_DIR = EXPERIMENT_DIR.parents[1]
DATASET_PATH = EVAL_DIR / "queries.jsonl"
MATCHER_RESULTS_PATH = EVAL_DIR / "routing_eval_results.jsonl"
SCHEMA_PATH = EXPERIMENT_DIR / "schemas" / "planner-output.schema.json"
RUNS_DIR = EXPERIMENT_DIR / "runs"
RESULTS_DIR = EXPERIMENT_DIR / "results"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_prompt_manifest(rows: list[dict[str, Any]]) -> Path:
    records = []
    for row in rows:
        run_dir = row.get("selected_run_dir")
        if not run_dir:
            continue
        prompt_path = EXPERIMENT_DIR / run_dir / "prompt.txt"
        records.append(
            {
                "id": row["id"],
                "selected_attempt": row.get("selected_attempt"),
                "prompt_path": str(prompt_path.relative_to(EXPERIMENT_DIR)),
                "prompt_sha256": sha256(prompt_path),
                "prompt_bytes": prompt_path.stat().st_size,
            }
        )
    manifest_path = RESULTS_DIR / "prompt-manifest.jsonl"
    manifest_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return manifest_path


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def attempts_for(case_id: str) -> list[tuple[dict[str, Any], dict[str, Any] | None, Path]]:
    found = []
    for meta_path in sorted((RUNS_DIR / case_id).glob("attempt-*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        response_path = meta_path.parent / "response.json"
        response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else None
        found.append((meta, response, meta_path.parent))
    return found


def prf(predicted: set[str], gold: set[str]) -> tuple[float, float, float]:
    overlap = len(predicted & gold)
    precision = overlap / len(predicted) if predicted else 0.0
    recall = overlap / len(gold) if gold else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def mean(values: list[float | int | bool | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "completed"]
    return {
        "n": len(rows),
        "completed": len(completed),
        "intent_any_hit": mean([row.get("scores", {}).get("intent_any_hit") for row in completed]),
        "intent_exact_set": mean([row.get("scores", {}).get("intent_exact_set") for row in completed]),
        "intent_precision_macro": mean([row.get("scores", {}).get("intent_precision") for row in completed]),
        "intent_recall_macro": mean([row.get("scores", {}).get("intent_recall") for row in completed]),
        "intent_f1_macro": mean([row.get("scores", {}).get("intent_f1") for row in completed]),
        "template_top1": mean([row.get("scores", {}).get("template_top1") for row in completed]),
        "template_any_hit": mean([row.get("scores", {}).get("template_any_hit") for row in completed]),
        "template_recall_macro": mean([row.get("scores", {}).get("template_recall") for row in completed]),
        "gap_abstention": mean([row.get("scores", {}).get("gap_abstention") for row in completed]),
        "joint_pass": mean([row.get("scores", {}).get("joint_pass") for row in completed]),
        "agent_route_exact": mean([row.get("scores", {}).get("agent_route_exact") for row in completed]),
        "tool_call_free": mean([row.get("scores", {}).get("tool_call_free") for row in completed]),
    }


def main() -> int:
    cases = load_jsonl(DATASET_PATH)
    results: list[dict[str, Any]] = []
    for case in cases:
        attempts = attempts_for(case["id"])
        first = attempts[0][0] if attempts else None
        selected = next(
            (
                (meta, response, path)
                for meta, response, path in attempts
                if meta.get("status") == "completed" and response is not None
            ),
            None,
        )
        if selected is None:
            results.append(
                {
                    "id": case["id"],
                    "layer": case["layer"],
                    "query": case["query"],
                    "status": "missing_or_failed",
                    "attempt_count": len(attempts),
                    "first_attempt_completed": bool(first and first.get("status") == "completed"),
                    "selected_attempt": None,
                    "prediction": None,
                    "scores": {},
                }
            )
            continue
        meta, response, path = selected
        scores: dict[str, Any] = {
            "tool_call_free": meta.get("trace", {}).get("tool_call_count", 0) == 0,
        }
        expected: dict[str, Any]
        if case["layer"] == "routing_benchmark":
            predicted_intents = set(response.get("route_intents") or [])
            gold_intents = set(case.get("expected_route_intents") or [])
            ip, ir, if1 = prf(predicted_intents, gold_intents)
            predicted_templates = response.get("template_candidates") or []
            gold_templates = set(case.get("candidate_templates") or [])
            scores.update(
                {
                    "intent_any_hit": bool(predicted_intents & gold_intents),
                    "intent_exact_set": predicted_intents == gold_intents,
                    "intent_precision": ip,
                    "intent_recall": ir,
                    "intent_f1": if1,
                    "template_top1": (predicted_templates[0] in gold_templates) if gold_templates and predicted_templates else (False if gold_templates else None),
                    "template_any_hit": bool(set(predicted_templates) & gold_templates) if gold_templates else None,
                    "template_recall": len(set(predicted_templates) & gold_templates) / len(gold_templates) if gold_templates else None,
                    "gap_abstention": (len(predicted_templates) == 0) if not gold_templates else None,
                }
            )
            template_decision = scores["template_any_hit"] if gold_templates else scores["gap_abstention"]
            scores["joint_pass"] = bool(scores["intent_any_hit"] and template_decision)
            expected = {
                "route_intents": case.get("expected_route_intents") or [],
                "candidate_templates": case.get("candidate_templates") or [],
            }
        else:
            scores["agent_route_exact"] = response.get("selected_route") == case.get("expected_route")
            expected = {"selected_route": case.get("expected_route")}
        results.append(
            {
                "id": case["id"],
                "layer": case["layer"],
                "query": case["query"],
                "language": case.get("language"),
                "theme": case.get("theme"),
                "coverage": case.get("coverage"),
                "has_reference": case.get("has_reference"),
                "status": "completed",
                "attempt_count": len(attempts),
                "first_attempt_completed": bool(first and first.get("status") == "completed"),
                "selected_attempt": meta["attempt"],
                "selected_run_dir": str(path.relative_to(EXPERIMENT_DIR)),
                "duration_seconds": meta.get("duration_seconds"),
                "usage": meta.get("trace", {}).get("usage"),
                "expected": expected,
                "prediction": response,
                "scores": scores,
            }
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    canonical_path = RESULTS_DIR / "canonical-results.jsonl"
    canonical_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results),
        encoding="utf-8",
    )
    tiq = [row for row in results if row["layer"] == "routing_benchmark"]
    agent = [row for row in results if row["layer"] == "agent_route"]
    by_coverage = {key or "null": metric_block(group) for key, group in _groups(tiq, "coverage")}
    by_theme = {key or "null": metric_block(group) for key, group in _groups(tiq, "theme")}
    route_confusion = Counter()
    for row in agent:
        if row["status"] == "completed":
            route_confusion[(row["expected"]["selected_route"], row["prediction"]["selected_route"])] += 1
    usage_totals: Counter[str] = Counter()
    durations = []
    predicted_templates: Counter[str] = Counter()
    for row in results:
        if row["status"] != "completed":
            continue
        usage_totals.update(row.get("usage") or {})
        durations.append(row.get("duration_seconds") or 0)
        if row["layer"] == "routing_benchmark":
            predicted_templates.update(row["prediction"].get("template_candidates") or [])
    matcher_rows = load_jsonl(MATCHER_RESULTS_PATH)
    matcher_with_candidates = [row for row in matcher_rows if row.get("candidate_recall") is not None]
    matcher_with_intent = [row for row in matcher_rows if row.get("intent_hit") is not None]
    matcher_gaps = [row for row in matcher_rows if row.get("coverage") == "gap"]
    summary = {
        "schema_version": "codex-planner-routing-summary-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "dataset": {
            "path": str(DATASET_PATH.relative_to(EVAL_DIR.parent)),
            "sha256": sha256(DATASET_PATH),
            "rows": len(cases),
        },
        "candidate": _candidate(results),
        "reliability": {
            "completed_selected": sum(row["status"] == "completed" for row in results),
            "total": len(results),
            "first_attempt_completed": sum(row["first_attempt_completed"] for row in results),
            "retried_cases": sum(row["attempt_count"] > 1 for row in results),
        },
        "routing_benchmark_100": metric_block(tiq),
        "agent_route_18": metric_block(agent),
        "routing_by_coverage": by_coverage,
        "routing_by_theme": by_theme,
        "agent_route_confusion": [
            {"expected": expected, "predicted": predicted, "count": count}
            for (expected, predicted), count in sorted(route_confusion.items())
        ],
        "usage_totals": dict(usage_totals),
        "latency": {
            "sum_case_seconds": sum(durations),
            "mean_case_seconds": mean(durations),
            "max_case_seconds": max(durations) if durations else None,
        },
        "most_selected_templates": [
            {"template_id": template_id, "count": count}
            for template_id, count in predicted_templates.most_common(10)
        ],
        "production_matcher_snapshot": {
            "source": str(MATCHER_RESULTS_PATH.relative_to(EVAL_DIR.parent)),
            "sha256": sha256(MATCHER_RESULTS_PATH),
            "rows": len(matcher_rows),
            "intent_overlap_reported_denominator": mean([row["intent_hit"] for row in matcher_with_intent]),
            "candidate_any_hit": mean([row["candidate_recall"] > 0 for row in matcher_with_candidates]),
            "candidate_recall_macro": mean([row["candidate_recall"] for row in matcher_with_candidates]),
            "gap_abstention": mean([row["n_matches"] == 0 for row in matcher_gaps]),
        },
    }
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = EXPERIMENT_DIR / "RESULTS.md"
    report_path.write_text(render_report(summary, results), encoding="utf-8")
    prompt_manifest_path = write_prompt_manifest(results)
    candidate = summary["candidate"]
    manifest = {
        "schema_version": "codex-planner-routing-freeze-v2",
        "candidate_config": candidate,
        "candidate_config_canonicalization": "UTF-8 JSON; sort_keys=true; separators=(',', ':')",
        "candidate_config_sha256": canonical_json_sha256(candidate),
        "model_identity": {
            "provider": "OpenAI",
            "interface": "codex-cli",
            "model_id": candidate["model"],
            "model_weights_sha256": None,
            "model_weights_hash_status": "not_exposed_by_codex_cli",
        },
        "prompt_manifest": str(prompt_manifest_path.relative_to(EXPERIMENT_DIR)),
        "prompt_count": len(results),
        "prompt_set_sha256": sha256(prompt_manifest_path),
        "dataset_sha256": sha256(DATASET_PATH),
        "output_schema_sha256": sha256(SCHEMA_PATH),
        "runner_sha256": sha256(HERE / "run_codex_planner.py"),
        "scorer_sha256": sha256(HERE / "score.py"),
        "canonical_results_sha256": sha256(canonical_path),
        "summary_sha256": sha256(summary_path),
        "row_count": len(results),
    }
    (RESULTS_DIR / "freeze-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["reliability"], ensure_ascii=False))
    print(f"results={canonical_path}\nreport={report_path}")
    return 0 if summary["reliability"]["completed_selected"] == len(results) else 1


def _groups(rows: list[dict[str, Any]], field: str):
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(field)].append(row)
    return sorted(grouped.items(), key=lambda item: str(item[0]))


def _candidate(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        if row.get("selected_run_dir"):
            meta = json.loads((EXPERIMENT_DIR / row["selected_run_dir"] / "meta.json").read_text(encoding="utf-8"))
            return meta.get("candidate")
    return None


def pct(value: Any) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    r = summary["routing_benchmark_100"]
    a = summary["agent_route_18"]
    failed = [row for row in rows if row["status"] != "completed"]
    agent_misses = [row for row in rows if row.get("scores", {}).get("agent_route_exact") is False]
    matcher = summary["production_matcher_snapshot"]
    lines = [
        "# Codex planner-only routing — results\n",
        f"Dataset: 118 rows · `{summary['dataset']['sha256']}`\n",
        f"Candidate: `{json.dumps(summary['candidate'], ensure_ascii=False, sort_keys=True)}`\n",
        "The two layers use different gold semantics and are intentionally not merged into one score.\n",
        "## Reliability\n",
        f"- Selected valid runs: **{summary['reliability']['completed_selected']}/118**",
        f"- First-attempt completion: **{summary['reliability']['first_attempt_completed']}/118**",
        f"- Retried cases: **{summary['reliability']['retried_cases']}**",
        f"- Planner-only invariant (no tool call): **{pct(mean([row.get('scores', {}).get('tool_call_free') for row in rows if row['status'] == 'completed']))}**\n",
        "## routing_benchmark (100)\n",
        "| Metric | Score |",
        "|---|---:|",
        f"| Intent any-hit | {pct(r['intent_any_hit'])} |",
        f"| Intent exact set | {pct(r['intent_exact_set'])} |",
        f"| Intent macro F1 | {pct(r['intent_f1_macro'])} |",
        f"| Template top-1 (77 labeled) | {pct(r['template_top1'])} |",
        f"| Template any-hit (77 labeled) | {pct(r['template_any_hit'])} |",
        f"| Template macro recall (77 labeled) | {pct(r['template_recall_macro'])} |",
        f"| Gap abstention (23 empty-gold) | {pct(r['gap_abstention'])} |",
        f"| Strict joint pass | {pct(r['joint_pass'])} |\n",
        "## agent_route (18)\n",
        f"Exact route accuracy: **{pct(a['agent_route_exact'])}**.\n",
        "## Same-dataset matcher context\n",
        "| Metric | Existing production matcher | Codex planner |",
        "|---|---:|---:|",
        f"| Intent any-hit / overlap | {pct(matcher['intent_overlap_reported_denominator'])} | {pct(r['intent_any_hit'])} |",
        f"| Candidate any-hit (77) | {pct(matcher['candidate_any_hit'])} | {pct(r['template_any_hit'])} |",
        f"| Candidate macro recall (77) | {pct(matcher['candidate_recall_macro'])} | {pct(r['template_recall_macro'])} |",
        f"| Gap abstention (23) | {pct(matcher['gap_abstention'])} | {pct(r['gap_abstention'])} |\n",
        "The comparison uses the existing frozen matcher output, but Codex was explicitly given the closed 35-ID catalog; treat it as a planner upper-bound, not a drop-in latency/cost comparison.\n",
        "## Cost/latency observability\n",
        f"- Sum of independent case latency: **{summary['latency']['sum_case_seconds']:.1f}s**; mean **{summary['latency']['mean_case_seconds']:.1f}s**.",
        f"- CLI usage counters: `{summary['usage_totals']}`.",
        f"- Most-selected templates: `{summary['most_selected_templates'][:3]}`.\n",
        "## Caveats\n",
        "- Reference presence and roles are passed, but not pixels; this isolates planner routing.",
        "- The 100-query intent labels and template candidates are weak/multi-valid gold, so any-hit and recall are more informative than exact-set accuracy.",
        "- A gold-empty template list is treated as an abstention target, not proof that no acceptable design workflow exists.",
    ]
    if failed:
        lines.extend(["\n## Missing/failed\n", *[f"- `{row['id']}`" for row in failed]])
    if agent_misses:
        lines.extend(
            [
                "\n## Agent-route misses\n",
                *[
                    f"- `{row['id']}` expected `{row['expected']['selected_route']}`, predicted `{row['prediction']['selected_route']}`"
                    for row in agent_misses
                ],
            ]
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
