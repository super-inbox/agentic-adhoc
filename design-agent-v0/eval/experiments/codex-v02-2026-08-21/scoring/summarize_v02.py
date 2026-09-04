#!/usr/bin/env python3
"""Build the canonical Brief Bank v0.2 result summary from persisted evidence.

The summary never fills an unobservable rubric dimension with zero or five.
Instead it reports the score earned on observable dimensions and an honest
lower/upper bound for the full rubric.
"""
from __future__ import annotations

import collections
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parent.parent
BRIEFS = EVAL / "brief_bank" / "briefs.v0.2.jsonl"
QUERIES = EVAL / "brief_bank" / "initial_queries.v0.2.jsonl"

DETERMINISTIC = {
    "artifact_contract": "artifact_contract",
    "efficiency": "efficiency",
}
JUDGE_V3 = {
    "brief_understanding": "brief_understanding",
    "tool_execution": "tool_execution",
    "revision_fidelity": "revision_fidelity",
    "cross_asset_consistency": "cross_asset_consistency",
}
PROXY = {"workflow_completion": "workflow_completion_proxy"}


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[index]


def score_distribution(values):
    return {
        str(score): count
        for score, count in sorted(collections.Counter(values).items())
    }


def latest_by(rows, key_fn, stamp_key="started_at"):
    selected = {}
    for row in rows:
        key = key_fn(row)
        stamp = str(row.get(stamp_key) or row.get("run") or "")
        if key not in selected or stamp > selected[key][0]:
            selected[key] = (stamp, row)
    return {key: value[1] for key, value in selected.items()}


def macro_bounds(rows, group_key=None):
    if not rows:
        return None
    if group_key is None:
        groups = [[row] for row in rows]
    else:
        grouped = collections.defaultdict(list)
        for row in rows:
            grouped[row[group_key]].append(row)
        groups = list(grouped.values())
    lower = [statistics.fmean(r["score_lower_bound"] for r in group) for group in groups]
    upper = [statistics.fmean(r["score_upper_bound"] for r in group) for group in groups]
    observed = [statistics.fmean(r["observed_weight"] for r in group) for group in groups]
    normalized = [
        sum(r["observed_earned"] for r in group)
        / sum(r["observed_weight"] for r in group)
        for group in groups
        if sum(r["observed_weight"] for r in group) > 0
    ]
    return {
        "groups": len(groups),
        "lower_bound": round(statistics.fmean(lower), 4),
        "upper_bound": round(statistics.fmean(upper), 4),
        "mean_observed_weight": round(statistics.fmean(observed), 4),
        "observable_only_normalized": round(statistics.fmean(normalized), 4),
    }


def breakdown(rows, key):
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return {
        name: macro_bounds(group)
        for name, group in sorted(grouped.items())
    }


def main() -> int:
    briefs = {row["id"]: row for row in read_jsonl(BRIEFS)}
    queries = read_jsonl(QUERIES)
    expected = {row["id"] for row in queries}

    attempts = read_jsonl(EXP / "run-index.jsonl")
    latest_attempts = latest_by(
        attempts,
        lambda row: row.get("query_id")
        or f"{row.get('base_brief_id')}@{row.get('context_condition')}",
    )
    attempt_counts = collections.Counter(row.get("outcome") or "unknown" for row in attempts)
    latest_counts = collections.Counter(
        latest_attempts.get(qid, {}).get("outcome") or "missing" for qid in expected
    )

    result_rows = []
    for result_path in sorted((EXP / "runs").rglob("result.json")):
        try:
            row = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if row.get("outcome") != "completed" or row.get("primary_eligible") is False:
            continue
        row = dict(row)
        row["_run"] = str(result_path.parent.relative_to(EXP))
        key = f"{row.get('base_brief_id')}@{row.get('context_condition')}"
        row["_condition_id"] = key
        result_rows.append(row)
    selected_results = latest_by(result_rows, lambda row: row["_condition_id"])

    deterministic = {
        row["run"]: row for row in read_jsonl(HERE / "rubric-v02-partial.jsonl")
    }
    judge_v3 = {
        row["run"]: row for row in read_jsonl(HERE / "rubric-v02-judged-v3.jsonl")
        if row.get("error") is None
    }
    tool_judge_crosscheck = {
        row["run"]: row for row in read_jsonl(HERE / "tool-execution-judged-v2.jsonl")
        if row.get("error") is None
    }

    condition_rows = []
    dimension_values = collections.defaultdict(list)
    dimension_applicable = collections.Counter()
    dimension_scored = collections.Counter()
    low_scores = []

    for condition_id in sorted(expected):
        result = selected_results.get(condition_id)
        if not result:
            continue
        brief = briefs[result["base_brief_id"]]
        weights = (brief.get("rubric") or {}).get("checkpoint_weights") or {}
        run_id = result["_run"]
        det = deterministic.get(run_id, {})
        judged = judge_v3.get(run_id, {})
        values = {}

        for dimension, field in DETERMINISTIC.items():
            if dimension in weights:
                values[dimension] = det.get(field)
        for dimension, field in JUDGE_V3.items():
            if dimension in weights:
                values[dimension] = judged.get(field)

        earned = 0.0
        observed_weight = 0.0
        for dimension, weight in weights.items():
            dimension_applicable[dimension] += 1
            value = values.get(dimension)
            if value is None:
                continue
            normalized = value if dimension in DETERMINISTIC else value / 5.0
            earned += normalized * weight
            observed_weight += weight
            dimension_scored[dimension] += 1
            dimension_values[dimension].append(value)
            if dimension not in DETERMINISTIC and value <= 2:
                low_scores.append({
                    "condition_id": condition_id,
                    "brief_id": brief["id"],
                    "category": brief.get("category"),
                    "dimension": dimension,
                    "score": value,
                    "why": judged.get(dimension + "_why"),
                    "run": run_id,
                })

        unobserved_weight = max(0.0, 1.0 - observed_weight)
        condition_rows.append({
            "condition_id": condition_id,
            "brief_id": brief["id"],
            "condition": result.get("context_condition"),
            "level": brief.get("level"),
            "category": brief.get("category"),
            "primary_intent": brief.get("primary_intent"),
            "run": run_id,
            "latency_ms": result.get("latency_ms"),
            "completed_turns": result.get("completed_turns"),
            "intended_turns": result.get("intended_turns"),
            "scores": values,
            "weights": weights,
            "workflow_completion_proxy": det.get(PROXY["workflow_completion"]),
            "observed_earned": round(earned, 4),
            "observed_weight": round(observed_weight, 4),
            "score_lower_bound": round(earned, 4),
            "score_upper_bound": round(earned + unobserved_weight, 4),
            "observable_only_normalized": round(earned / observed_weight, 4)
            if observed_weight else None,
        })

    dimensions = {}
    all_dimensions = sorted(
        set(dimension_applicable) | set(DETERMINISTIC) | set(JUDGE_V3) | set(PROXY)
    )
    for dimension in all_dimensions:
        values = dimension_values.get(dimension, [])
        if dimension in DETERMINISTIC:
            scale = "0-1"
            method = "deterministic"
        elif dimension in JUDGE_V3:
            scale = "0-5"
            method = "gemini-2.5-pro condition-aware artifact-grounded judge-v3"
        elif dimension == "workflow_completion":
            scale = "0-1 proxy"
            method = "version-progression proxy; excluded from official score bounds"
        else:
            scale = None
            method = "unobservable under v0.2 protocol"
        dimensions[dimension] = {
            "applicable": dimension_applicable.get(dimension, 0),
            "scored": dimension_scored.get(dimension, 0),
            "mean": round(statistics.fmean(values), 4) if values else None,
            "distribution": score_distribution(values),
            "scale": scale,
            "method": method,
            "weights_present": sorted({
                briefs[row["brief_id"]]["rubric"]["checkpoint_weights"][dimension]
                for row in condition_rows
                if dimension in briefs[row["brief_id"]]["rubric"]["checkpoint_weights"]
            }),
        }

    # Workflow is explicitly a proxy; report it separately without treating it
    # as an official rubric score.
    proxy_values = [
        row["workflow_completion_proxy"] for row in condition_rows
        if "workflow_completion" in row["weights"]
        and row["workflow_completion_proxy"] is not None
    ]
    dimensions["workflow_completion"]["applicable"] = sum(
        "workflow_completion" in row["weights"] for row in condition_rows
    )
    dimensions["workflow_completion"]["scored"] = 0
    dimensions["workflow_completion"]["proxy_n"] = len(proxy_values)
    dimensions["workflow_completion"]["proxy_mean"] = (
        round(statistics.fmean(proxy_values), 4) if proxy_values else None
    )

    judge_rows = [
        judge_v3[row["run"]] for row in condition_rows if row["run"] in judge_v3
    ]
    violation_counts = collections.Counter(
        str(item.get("verdict") or "UNKNOWN")
        for row in judge_rows
        for item in row.get("checks") or []
    )
    tool_rows = [
        tool_judge_crosscheck[row["run"]]
        for row in condition_rows
        if row["run"] in tool_judge_crosscheck
    ]
    tool_check_counts = collections.Counter(
        str(item.get("verdict") or "UNKNOWN")
        for row in tool_rows
        for item in row.get("checks") or []
    )

    latencies = [row["latency_ms"] for row in condition_rows if row["latency_ms"] is not None]
    total_usage = collections.Counter()
    for result in selected_results.values():
        for key, value in (result.get("usage") or {}).items():
            if isinstance(value, (int, float)):
                total_usage[key] += value

    ablation = collections.defaultdict(dict)
    for row in condition_rows:
        if len(briefs[row["brief_id"]].get("context_conditions") or []) == 3:
            ablation[row["brief_id"]][row["condition"]] = {
                "brief_understanding": row["scores"].get("brief_understanding"),
                "score_lower_bound": row["score_lower_bound"],
                "score_upper_bound": row["score_upper_bound"],
                "observable_only_normalized": row["observable_only_normalized"],
            }

    snapshot = max(
        [str(row.get("finished_at") or "") for row in attempts] or [""]
    )
    summary = {
        "schema_version": "codex.brief-bank-v0.2-summary/1.0",
        "snapshot_finished_at": snapshot,
        "candidate": {
            "agent": "Codex CLI",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "max",
            "service_tier": "default",
        },
        "benchmark": {
            "base_episodes": len(briefs),
            "expected_conditions": len(expected),
        },
        "execution": {
            "attempts": len(attempts),
            "attempt_outcomes": dict(sorted(attempt_counts.items())),
            "latest_condition_outcomes": dict(sorted(latest_counts.items())),
            "unique_completed_conditions_selected": len(condition_rows),
            "missing_or_incomplete_conditions": sorted(expected - set(selected_results)),
            "latency_minutes": {
                "n": len(latencies),
                "mean": round(statistics.fmean(latencies) / 60000, 2) if latencies else None,
                "p50": round(statistics.median(latencies) / 60000, 2) if latencies else None,
                "p95_nearest_rank": round(percentile(latencies, 0.95) / 60000, 2)
                if latencies else None,
                "max": round(max(latencies) / 60000, 2) if latencies else None,
            },
            "selected_run_usage": dict(total_usage),
        },
        "score_summary": {
            "condition_macro": macro_bounds(condition_rows),
            "base_episode_macro": macro_bounds(condition_rows, "brief_id"),
            "interpretation": (
                "Bounds exclude workflow_completion and recovery when unobservable; "
                "the observable-only normalized score is diagnostic, not a full-rubric total."
            ),
        },
        "breakdowns": {
            "level": breakdown(condition_rows, "level"),
            "primary_intent": breakdown(condition_rows, "primary_intent"),
            "category": breakdown(condition_rows, "category"),
        },
        "dimensions": dimensions,
        "violation_ledger": {
            "canonical_judge_v3": dict(sorted(violation_counts.items())),
            "tool_execution_v2_crosscheck": dict(sorted(tool_check_counts.items())),
        },
        "context_ablation": dict(sorted(ablation.items())),
        "low_scores_0_to_2": sorted(
            low_scores,
            key=lambda row: (row["score"], row["dimension"], row["condition_id"]),
        ),
        "conditions": condition_rows,
        "measurement_limits": [
            "workflow_completion is only a version-progression proxy because checkpoint events are not protocol-bound",
            "recovery is unobservable because recovery events/check identifiers are not protocol-bound",
            "judge-v3 is an independent model judge, not human ground truth",
            "judge-v2 is retained only as an invalidated audit artifact because it lacked condition-aware queries and complete evaluator inventory",
            "tool-execution judge-v1 was invalidated by counterfactual controls and is excluded",
        ],
    }

    json_path = HERE / "summary-v02.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    dimension_labels = {
        "artifact_contract": "Artifact contract",
        "brief_understanding": "Brief understanding",
        "cross_asset_consistency": "Cross-asset consistency",
        "efficiency": "Efficiency",
        "recovery": "Recovery",
        "revision_fidelity": "Revision fidelity",
        "tool_execution": "Tool execution",
        "workflow_completion": "Workflow completion",
    }
    lines = [
        "# Codex × Brief Bank v0.2 — Results",
        "",
        f"Evidence snapshot: `{snapshot or 'in progress'}`.",
        "",
        "## Headline",
        "",
        f"- Candidate execution: **{len(condition_rows)}/{len(expected)}** unique conditions have a primary completed run.",
        f"- Attempt ledger: **{len(attempts)}** attempts — "
        + ", ".join(f"{key} {value}" for key, value in sorted(attempt_counts.items()))
        + ".",
    ]
    condition_macro = summary["score_summary"]["condition_macro"]
    episode_macro = summary["score_summary"]["base_episode_macro"]
    if condition_macro:
        lines += [
            f"- Observable rubric weight: **{condition_macro['mean_observed_weight']:.1%}** on average across conditions.",
            f"- Full-rubric condition-macro interval: **{condition_macro['lower_bound']:.3f}–{condition_macro['upper_bound']:.3f}**; observable-only normalized diagnostic: **{condition_macro['observable_only_normalized']:.3f}**.",
            f"- Base-episode macro interval (each of 24 briefs equal-weighted): **{episode_macro['lower_bound']:.3f}–{episode_macro['upper_bound']:.3f}**.",
        ]
    lines += [
        "",
        "No point estimate is reported for the full rubric: workflow completion and recovery are not independently observable under the v0.2 event contract.",
        "",
        "## Dimension coverage",
        "",
        "| Dimension | Coverage | Mean | Scale | Method |",
        "|---|---:|---:|---|---|",
    ]
    for dimension in sorted(dimensions):
        item = dimensions[dimension]
        if dimension == "workflow_completion":
            mean_text = (
                f"proxy {item['proxy_mean']:.3f}" if item.get("proxy_mean") is not None else "—"
            )
            coverage = f"official 0/{item['applicable']}; proxy {item.get('proxy_n', 0)}/{item['applicable']}"
        else:
            mean_text = f"{item['mean']:.3f}" if item["mean"] is not None else "—"
            coverage = f"{item['scored']}/{item['applicable']}"
        lines.append(
            f"| {dimension_labels.get(dimension, dimension)} | {coverage} | {mean_text} | "
            f"{item['scale'] or '—'} | {item['method']} |"
        )

    lines += [
        "",
        "## Performance slices",
        "",
        "These are observable-only diagnostics plus honest full-rubric bounds; they are not fully observed total scores.",
        "",
        "| Slice | Conditions | Observable diagnostic | Full-rubric interval |",
        "|---|---:|---:|---:|",
    ]
    for group_name, group in (
        ("level", summary["breakdowns"]["level"]),
        ("intent", summary["breakdowns"]["primary_intent"]),
        ("category", summary["breakdowns"]["category"]),
    ):
        for name, item in group.items():
            lines.append(
                f"| {group_name}: `{name}` | {item['groups']} | "
                f"{item['observable_only_normalized']:.3f} | "
                f"{item['lower_bound']:.3f}–{item['upper_bound']:.3f} |"
            )

    lines += [
        "",
        "## Reliability and cost shape",
        "",
    ]
    latency = summary["execution"]["latency_minutes"]
    if latency["n"]:
        lines.append(
            f"Selected successful runs: latency p50 **{latency['p50']:.2f} min**, "
            f"p95 **{latency['p95_nearest_rank']:.2f} min**, max **{latency['max']:.2f} min**."
        )
    lines += [
        "",
        "Execution success and design quality are reported separately. Historical failed and timed-out attempts remain in `run-index.jsonl`; selecting one latest successful primary attempt per condition prevents retries or duplicate runs from changing quality means.",
        "",
        "## Context ablation",
        "",
        "| Brief | zero-shot BU | reference BU | personalized BU | zero/ref/personalized observable diagnostic |",
        "|---|---:|---:|---:|---|",
    ]
    for brief_id, arms in sorted(ablation.items()):
        def arm_value(condition, field):
            value = (arms.get(condition) or {}).get(field)
            return "—" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)
        lines.append(
            f"| {brief_id} | {arm_value('zero_shot', 'brief_understanding')} | "
            f"{arm_value('reference_grounded', 'brief_understanding')} | "
            f"{arm_value('personalized', 'brief_understanding')} | "
            f"{arm_value('zero_shot', 'observable_only_normalized')} / "
            f"{arm_value('reference_grounded', 'observable_only_normalized')} / "
            f"{arm_value('personalized', 'observable_only_normalized')} |"
        )
    lines += [
        "",
        "Each ablation arm has one stochastic run, so the deltas are descriptive rather than causal estimates.",
    ]

    lines += [
        "",
        "## Low-scoring judged dimensions (0–2/5)",
        "",
    ]
    if summary["low_scores_0_to_2"]:
        for row in summary["low_scores_0_to_2"]:
            full_why = " ".join(str(row.get("why") or "").split())
            why = full_why if len(full_why) <= 220 else full_why[:217].rstrip() + "..."
            lines.append(
                f"- `{row['condition_id']}` — `{row['dimension']}` **{row['score']}/5**: {why}"
            )
    else:
        lines.append("- None in the currently scored conditions.")

    lines += [
        "",
        "## Measurement limits",
        "",
        "- `workflow_completion` is reported only as a version-count proxy and is excluded from official bounds; the trajectory does not bind required checkpoint IDs.",
        "- `recovery` remains unscored for the same event/check-vocabulary gap.",
        "- Gemini judge-v3 scores are independent model judgments, not human ground truth; raw reasons and check ledgers remain in JSONL for audit.",
        "- The earlier general judge-v2 is excluded from canonical scores: it used the base query for zero-shot arms and lacked a complete evaluator inventory, producing demonstrable false violations.",
        "- The first tool-execution judge was rejected after two counterfactual controls still received 5/5. V2 passed the same controls at 0/5 and 1/5 and excludes candidate-authored self-evidence.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "python3 scoring/score_rubric_v02.py",
        "python3 scoring/score_selfverification.py",
        "python3 scoring/summarize_v02.py",
        "```",
    ]
    markdown_path = EXP / "RESULTS.md"
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"conditions summarized: {len(condition_rows)}/{len(expected)}")
    print(f"wrote {json_path.relative_to(EVAL)}")
    print(f"wrote {markdown_path.relative_to(EVAL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
