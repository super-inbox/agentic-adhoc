#!/usr/bin/env python3
"""Freeze the complete Codex × Brief Bank v0.3 result snapshot.

The 32 unchanged core conditions are explicitly carried forward from the
frozen v0.2 experiment. The 11 public-corpus-grounded extension conditions are
new executions. The two partitions are always reported separately.
"""
from __future__ import annotations

import collections
import hashlib
import json
import math
import statistics
from pathlib import Path

from evidence_v03 import (
    BRIEFS,
    EXP,
    QUERIES,
    latency_summary,
    read_jsonl,
    selected_runs,
    sha256,
    structured_artifact_facts,
)


HERE = Path(__file__).resolve().parent
V02_EXP = EXP.parent / "codex-v02-2026-08-21"
V02_SUMMARY = V02_EXP / "scoring" / "summary-v02.json"
V02_JUDGE = V02_EXP / "scoring" / "rubric-v02-judged-v3.jsonl"
PASS_THRESHOLD = 0.70


def percentile(values, quantile):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def macro_bounds(rows: list[dict], group_key: str | None = None) -> dict | None:
    if not rows:
        return None
    if group_key is None:
        groups = [[row] for row in rows]
    else:
        grouped = collections.defaultdict(list)
        for row in rows:
            grouped[row[group_key]].append(row)
        groups = list(grouped.values())
    lower = [statistics.fmean(row["score_lower_bound"] for row in group) for group in groups]
    upper = [statistics.fmean(row["score_upper_bound"] for row in group) for group in groups]
    return {
        "groups": len(groups),
        "lower_bound": round(statistics.fmean(lower), 4),
        "upper_bound": round(statistics.fmean(upper), 4),
    }


def breakdown(rows: list[dict], key: str) -> dict:
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return {name: macro_bounds(group) for name, group in sorted(grouped.items())}


def validate_core_lineage(v02_conditions: list[dict], briefs: dict, queries: dict) -> dict:
    v02_briefs = {row["id"]: row for row in read_jsonl(V02_EXP.parent.parent / "brief_bank" / "briefs.v0.2.jsonl")}
    v02_queries = {row["id"]: row for row in read_jsonl(V02_EXP.parent.parent / "brief_bank" / "initial_queries.v0.2.jsonl")}
    errors = []
    ignored_brief_fields = {"schema_version", "revision"}
    ignored_query_fields = {"episode_source", "layer"}
    for brief_id, old in v02_briefs.items():
        new = briefs.get(brief_id)
        if not new:
            errors.append(f"missing migrated brief {brief_id}")
            continue
        keys = (set(old) | set(new)) - ignored_brief_fields
        if any(old.get(key) != new.get(key) for key in keys):
            errors.append(f"business contract changed for {brief_id}")
    for condition_id, old in v02_queries.items():
        new = queries.get(condition_id)
        if not new:
            errors.append(f"missing migrated query {condition_id}")
            continue
        keys = (set(old) | set(new)) - ignored_query_fields
        if any(old.get(key) != new.get(key) for key in keys):
            errors.append(f"projected query changed for {condition_id}")
    source_ids = {row["condition_id"] for row in v02_conditions}
    if source_ids != set(v02_queries):
        errors.append("v0.2 summary does not contain exactly the 32 projected core conditions")
    if errors:
        raise RuntimeError("invalid v0.2 carry-forward: " + "; ".join(errors))
    return {
        "validated": True,
        "core_briefs": len(v02_briefs),
        "core_conditions": len(v02_queries),
        "ignored_migration_only_brief_fields": sorted(ignored_brief_fields),
        "ignored_projection_metadata_fields": sorted(ignored_query_fields),
    }


def build_core_rows(briefs: dict, queries: dict) -> tuple[list[dict], dict]:
    source = json.loads(V02_SUMMARY.read_text(encoding="utf-8"))
    source_rows = source.get("conditions") or []
    lineage = validate_core_lineage(source_rows, briefs, queries)
    rows = []
    run_hashes = []
    for row in source_rows:
        brief = briefs[row["brief_id"]]
        if row["weights"] != brief["rubric"]["checkpoint_weights"]:
            raise RuntimeError(f"rubric changed for carried condition {row['condition_id']}")
        source_run = V02_EXP / row["run"]
        result_path = source_run / "result.json"
        result_hash = sha256(result_path) if result_path.is_file() else None
        run_hashes.append({"condition_id": row["condition_id"], "result_sha256": result_hash})
        rows.append(
            {
                **row,
                "execution_origin": "carried_forward_v0.2",
                "source_experiment": str(V02_EXP.relative_to(EXP.parent.parent)),
                "source_run": row["run"],
                "source_result_sha256": result_hash,
                "hard_gate_pass": None,
                "hard_gate_status": "not normalized in v0.2 canonical summary",
            }
        )
    carry = {
        "schema_version": "brief-bank-v0.3-core-carry-forward/1.0",
        "reason": "The 24 core episode business contracts, rubrics, projected queries, assets, candidate model, and execution protocol are unchanged; v0.3 adds migration-only metadata.",
        "lineage_validation": lineage,
        "source_summary": str(V02_SUMMARY.relative_to(EXP.parent.parent)),
        "source_summary_sha256": sha256(V02_SUMMARY),
        "source_judge": str(V02_JUDGE.relative_to(EXP.parent.parent)),
        "source_judge_sha256": sha256(V02_JUDGE),
        "conditions": run_hashes,
    }
    (HERE / "carry-forward-v02.json").write_text(
        json.dumps(carry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return rows, carry


def build_external_rows(briefs: dict, judge_rows: dict[str, dict]) -> list[dict]:
    rows = []
    for run, brief, result, query in selected_runs():
        run_id = str(run.relative_to(EXP))
        judged = judge_rows.get(run_id)
        if not judged or judged.get("error") is not None:
            continue
        weights = brief["rubric"]["checkpoint_weights"]
        scores = {
            dimension: (judged.get("scores", {}).get(dimension) or {}).get("score")
            for dimension in weights
        }
        missing = [dimension for dimension, value in scores.items() if value is None]
        if missing:
            raise RuntimeError(f"missing judge scores for {query['id']}: {missing}")
        earned = sum((scores[dimension] / 5.0) * weight for dimension, weight in weights.items())
        hard_gates = judged.get("hard_gates") or []
        hard_gate_pass = bool(hard_gates) and all(row.get("verdict") == "MET" for row in hard_gates)
        artifacts = structured_artifact_facts(run, query)
        rows.append(
            {
                "condition_id": query["id"],
                "brief_id": brief["id"],
                "condition": query.get("context_condition"),
                "level": brief.get("level"),
                "category": brief.get("category"),
                "primary_intent": brief.get("primary_intent"),
                "run": run_id,
                "execution_origin": "new_v0.3_execution",
                "latency_ms": result.get("latency_ms"),
                "completed_turns": result.get("completed_turns"),
                "intended_turns": result.get("intended_turns"),
                "scores": scores,
                "score_reasons": {
                    dimension: (judged.get("scores", {}).get(dimension) or {}).get("why")
                    for dimension in weights
                },
                "weights": weights,
                "observed_earned": round(earned, 4),
                "observed_weight": 1.0,
                "score_lower_bound": round(earned, 4),
                "score_upper_bound": round(earned, 4),
                "observable_only_normalized": round(earned, 4),
                "structured_artifact_contract": artifacts,
                "structured_artifact_complete": all(artifacts.values()),
                "hard_gate_pass": hard_gate_pass,
                "hard_gates": hard_gates,
                "benchmark_pass": hard_gate_pass and earned >= PASS_THRESHOLD,
                "judge_run": run_id,
            }
        )
    return rows


def dimension_summary(rows: list[dict]) -> dict:
    values = collections.defaultdict(list)
    applicable = collections.Counter()
    observed = collections.Counter()
    for row in rows:
        for dimension in row.get("weights") or {}:
            applicable[dimension] += 1
            value = (row.get("scores") or {}).get(dimension)
            if value is None:
                continue
            observed[dimension] += 1
            scale = 1.0 if dimension in {"artifact_contract", "efficiency"} and row["execution_origin"] == "carried_forward_v0.2" else 5.0
            values[dimension].append(value / scale)
    return {
        dimension: {
            "applicable": applicable[dimension],
            "scored": observed[dimension],
            "mean_normalized": round(statistics.fmean(values[dimension]), 4) if values[dimension] else None,
        }
        for dimension in sorted(applicable)
    }


def main() -> int:
    briefs = {row["id"]: row for row in read_jsonl(BRIEFS)}
    queries = {row["id"]: row for row in read_jsonl(QUERIES)}
    expected_external = {key for key in queries if "-RDT-" in key}
    judge_list = read_jsonl(HERE / "rubric-v03-judged.jsonl")
    judge_rows = {row["run"]: row for row in judge_list}
    core_rows, carry = build_core_rows(briefs, queries)
    external_rows = build_external_rows(briefs, judge_rows)
    external_ids = {row["condition_id"] for row in external_rows}
    all_rows = sorted(core_rows + external_rows, key=lambda row: row["condition_id"])

    attempts = read_jsonl(EXP / "run-index.jsonl")
    attempt_outcomes = collections.Counter(row.get("outcome") or "unknown" for row in attempts)
    latencies = [row["latency_ms"] for row in external_rows if row.get("latency_ms") is not None]
    usage = collections.Counter()
    for _, _, result, _ in selected_runs():
        for key, value in (result.get("usage") or {}).items():
            if isinstance(value, (int, float)):
                usage[key] += value

    failures = []
    for row in external_rows:
        for gate in row.get("hard_gates") or []:
            if gate.get("verdict") != "MET":
                failures.append(
                    {
                        "condition_id": row["condition_id"],
                        "gate": gate.get("gate"),
                        "verdict": gate.get("verdict"),
                        "evidence": gate.get("evidence"),
                    }
                )

    summary = {
        "schema_version": "codex.brief-bank-v0.3-summary/1.0",
        "candidate": {
            "agent": "Codex CLI",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "max",
            "service_tier": "default",
            "session_mode": "persisted-thread-resume",
        },
        "benchmark": {
            "episodes": len(briefs),
            "conditions": len(queries),
            "core_episodes": 24,
            "core_conditions_carried_forward": len(core_rows),
            "external_episodes": 11,
            "external_conditions_expected": len(expected_external),
            "external_conditions_completed_and_judged": len(external_rows),
        },
        "execution": {
            "core": {
                "origin": "carried_forward_v0.2",
                "conditions": len(core_rows),
                "source_summary_sha256": carry["source_summary_sha256"],
            },
            "external": {
                "attempts": len(attempts),
                "attempt_outcomes": dict(sorted(attempt_outcomes.items())),
                "missing_or_unjudged": sorted(expected_external - external_ids),
                "latency_minutes": {
                    "n": len(latencies),
                    "mean": round(statistics.fmean(latencies) / 60000, 2) if latencies else None,
                    "p50": round(statistics.median(latencies) / 60000, 2) if latencies else None,
                    "p95_nearest_rank": round(percentile(latencies, 0.95) / 60000, 2) if latencies else None,
                    "max": round(max(latencies) / 60000, 2) if latencies else None,
                },
                "selected_run_usage": dict(usage),
            },
        },
        "score_summary": {
            "all_43_condition_macro_interval": macro_bounds(all_rows),
            "all_35_episode_macro_interval": macro_bounds(all_rows, "brief_id"),
            "core_32_condition_macro_interval": macro_bounds(core_rows),
            "external_11_condition_macro": macro_bounds(external_rows),
            "external_hard_gate_pass": sum(row["hard_gate_pass"] for row in external_rows),
            "external_benchmark_pass": sum(row["benchmark_pass"] for row in external_rows),
            "external_benchmark_pass_rule": f"all hard gates MET and weighted score >= {PASS_THRESHOLD:.2f}",
            "interpretation": "Core retains the honest v0.2 uncertainty interval; external v0.3 conditions are fully scored by an artifact-grounded multimodal judge plus evaluator-computed file/pixel facts.",
        },
        "breakdowns": {
            "all_by_level": breakdown(all_rows, "level"),
            "all_by_intent": breakdown(all_rows, "primary_intent"),
            "external_by_category": breakdown(external_rows, "category"),
        },
        "dimensions": dimension_summary(all_rows),
        "hard_gate_failures": failures,
        "conditions": all_rows,
        "measurement_limits": [
            "The core 32 are not newly sampled; they are provenance-checked carry-forward results from the unchanged v0.2 contract.",
            "Core workflow_completion and recovery remain unobservable and therefore retain lower/upper bounds rather than point estimates.",
            "External visual and semantic scores use Gemini model judgment and are not human ground truth.",
            "A single stochastic candidate run per external condition estimates capability, not variance.",
            "The candidate saw required structured-artifact filenames but not their schema validation prose; structured artifact completion therefore measures file presence, while hidden validation prose is not used as a penalty.",
            "The judge passed a counterfactual control in which stale self-verification was retained but the edited pixels were replaced by the unchanged source.",
        ],
    }
    (HERE / "summary-v03.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    all_macro = summary["score_summary"]["all_43_condition_macro_interval"]
    core_macro = summary["score_summary"]["core_32_condition_macro_interval"]
    ext_macro = summary["score_summary"]["external_11_condition_macro"]
    lines = [
        "# Codex × Brief Bank v0.3 — Results",
        "",
        "## Headline",
        "",
        f"- Dataset coverage: **{len(all_rows)}/43 conditions** across **35 episodes**.",
        f"- Core partition: **{len(core_rows)}/32** conditions carried forward from the unchanged, frozen v0.2 baseline; interval **{core_macro['lower_bound']:.3f}–{core_macro['upper_bound']:.3f}**.",
        f"- External v0.3 extension: **{len(external_rows)}/11** conditions newly executed and independently judged; weighted macro **{ext_macro['lower_bound']:.3f}**.",
        f"- Combined 43-condition interval: **{all_macro['lower_bound']:.3f}–{all_macro['upper_bound']:.3f}**.",
        f"- External hard-gate pass: **{summary['score_summary']['external_hard_gate_pass']}/{len(external_rows)}**; score+gate pass: **{summary['score_summary']['external_benchmark_pass']}/{len(external_rows)}**.",
        "",
        "The 32 inherited rows are explicitly marked `carried_forward_v0.2`; they are not reported as fresh model calls.",
        "",
        "## External v0.3 results",
        "",
        "| Condition | Category | Weighted score | Hard gates | Benchmark pass |",
        "|---|---|---:|---:|---:|",
    ]
    for row in external_rows:
        lines.append(
            f"| `{row['condition_id']}` | `{row['category']}` | {row['score_lower_bound']:.3f} | "
            f"{'PASS' if row['hard_gate_pass'] else 'FAIL'} | {'PASS' if row['benchmark_pass'] else 'FAIL'} |"
        )
    lines += [
        "",
        "## Hard-gate failures",
        "",
    ]
    if failures:
        for item in failures:
            evidence = " ".join(str(item.get("evidence") or "").split())
            lines.append(
                f"- `{item['condition_id']}` — **{item['verdict']}** `{item['gate']}`: {evidence[:320]}"
            )
    else:
        lines.append("- None.")
    latency = summary["execution"]["external"]["latency_minutes"]
    lines += [
        "",
        "## Reliability",
        "",
        f"- New execution attempts: **{len(attempts)}** — " + ", ".join(f"{key} {value}" for key, value in sorted(attempt_outcomes.items())) + ".",
        f"- Selected external latency: p50 **{latency['p50']} min**, p95 **{latency['p95_nearest_rank']} min**, max **{latency['max']} min**.",
        "",
        "## Measurement boundaries",
        "",
        "- Core v0.2 workflow/recovery gaps remain bounds, not invented point scores.",
        "- External scores are artifact-grounded Gemini judgments with independent file, vector, PDF, and masked-pixel facts; they are not human ground truth.",
        "- The judge counterfactual passed: retaining stale candidate claims while replacing the edited output with the unchanged source reduced edit fidelity from 5/5 to 0/5.",
        "- Candidate-visible structured-artifact requirements named the files, not the hidden schema-validation prose; presence is measured, but hidden prose is not used as a penalty.",
        "- One candidate sample per external condition does not measure variance.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "BUNDLED_PY=/path/from/codex-workspace-dependencies/python/bin/python3",
        "PYTHONPATH=.private/judge-python:scoring \"$BUNDLED_PY\" scoring/judge_v03.py",
        "PYTHONPATH=.private/judge-python:scoring \"$BUNDLED_PY\" scoring/validate_judge_v03.py",
        "PYTHONPATH=.private/judge-python:scoring \"$BUNDLED_PY\" scoring/summarize_v03.py",
        "\"$BUNDLED_PY\" scripts/freeze_v03_experiment.py",
        "```",
    ]
    (EXP / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"summarized {len(all_rows)}/43 conditions ({len(external_rows)}/11 external)")
    print(f"wrote {(HERE / 'summary-v03.json').relative_to(EXP)}")
    print("wrote RESULTS.md")
    return 0 if len(all_rows) == 43 else 1


if __name__ == "__main__":
    raise SystemExit(main())
