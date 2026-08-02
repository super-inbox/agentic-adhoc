from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List


def _allowed_statuses(expected: Dict[str, Any]) -> List[str]:
    value = expected.get("status", "COMPLETED")
    return [str(item) for item in value] if isinstance(value, list) else [str(value)]


def score_case(case: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
    """Score a terminal API response against one versioned single-turn case."""
    expected = case.get("expected") or {}
    trace = response.get("trace") or []
    seen_stages = {
        str(step.get("stage"))
        for step in trace
        if step.get("status") in ("RUNNING", "COMPLETED", "FAILED")
    }
    required_stages = set(expected.get("required_stages") or ["UNDERSTAND"])
    artifacts = response.get("artifacts") or []
    artifact_kinds = {str(artifact.get("kind")) for artifact in artifacts}

    checks: Dict[str, bool] = {
        "terminal_status": str(response.get("status")) in _allowed_statuses(expected),
        "required_stages": required_stages.issubset(seen_stages),
        "min_artifacts": len(artifacts) >= int(expected.get("min_artifacts", 0)),
    }
    if expected.get("task_type") is not None:
        checks["route"] = response.get("task_type") == expected["task_type"]
    if expected.get("skill_id") is not None:
        checks["skill"] = response.get("skill_id") == expected["skill_id"]
    if "code" in expected:
        checks["code"] = response.get("code") == expected["code"]
    if "verdict_passed" in expected:
        verdict = response.get("verdict") or {}
        checks["verdict"] = verdict.get("passed") is expected["verdict_passed"]
    if "max_iterations" in expected:
        checks["retry_budget"] = int(response.get("iterations") or 0) <= int(
            expected["max_iterations"]
        )
    if expected.get("artifact_kinds"):
        checks["artifact_kinds"] = set(expected["artifact_kinds"]).issubset(artifact_kinds)
    if expected.get("artifacts_reachable"):
        probes = response.get("_artifact_probe") or []
        checks["artifacts_reachable"] = (
            len(probes) == len(artifacts)
            and bool(probes)
            and all(probe.get("reachable") is True for probe in probes)
        )

    stage_coverage = (
        len(required_stages & seen_stages) / len(required_stages)
        if required_stages
        else 1.0
    )
    return {
        "id": case["id"],
        "task_type": expected.get("task_type"),
        "coverage": case.get("coverage", "unknown"),
        "passed": all(checks.values()),
        "checks": checks,
        "stage_coverage": round(stage_coverage, 4),
        "actual_status": response.get("status"),
        "actual_task_type": response.get("task_type"),
        "actual_code": response.get("code"),
        "iterations": int(response.get("iterations") or 0),
        "artifact_count": len(artifacts),
        "trace_steps": len(trace),
    }


def aggregate_results(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(results)
    total = len(rows)
    routed = [row for row in rows if "route" in row.get("checks", {})]
    verified = [row for row in rows if "verdict" in row.get("checks", {})]
    abstained = [
        row
        for row in rows
        if row.get("checks", {}).get("terminal_status") is not None
        and row.get("actual_status") == "ABSTAINED"
    ]
    by_coverage: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_coverage[str(row.get("coverage", "unknown"))].append(row)

    def rate(subset: List[Dict[str, Any]], predicate) -> float:
        return (
            sum(1 for item in subset if predicate(item)) / len(subset)
            if subset
            else 0.0
        )

    return {
        "total": total,
        "case_pass_rate": round(rate(rows, lambda row: row["passed"]), 4),
        "routing_accuracy": round(
            rate(routed, lambda row: row["checks"].get("route", False)), 4
        ),
        "verification_pass_rate": round(
            rate(verified, lambda row: row["checks"].get("verdict", False)), 4
        ),
        "mean_stage_coverage": round(
            sum(row.get("stage_coverage", 0.0) for row in rows) / total, 4
        )
        if total
        else 0.0,
        "abstained_count": len(abstained),
        "by_coverage": {
            key: {
                "n": len(group),
                "pass_rate": round(rate(group, lambda row: row["passed"]), 4),
                "failed_ids": [row["id"] for row in group if not row["passed"]],
            }
            for key, group in sorted(by_coverage.items())
        },
        "failed_ids": [row["id"] for row in rows if not row["passed"]],
    }


def render_markdown(summary: Dict[str, Any]) -> str:
    def pct(value: float) -> str:
        return f"{float(value) * 100:.1f}%"

    lines = [
        "# Design Agent — single-turn runtime eval",
        "",
        f"- Cases: **{summary['total']}**",
        f"- End-to-end pass rate: **{pct(summary['case_pass_rate'])}**",
        f"- Routing accuracy: **{pct(summary['routing_accuracy'])}**",
        f"- Verification pass rate: **{pct(summary['verification_pass_rate'])}**",
        f"- Mean required-stage coverage: **{pct(summary['mean_stage_coverage'])}**",
        "",
        "## Coverage gaps",
        "",
        "| coverage | n | pass rate | failed cases |",
        "|---|---:|---:|---|",
    ]
    for name, group in summary["by_coverage"].items():
        failed = ", ".join(group["failed_ids"]) or "—"
        lines.append(f"| {name} | {group['n']} | {pct(group['pass_rate'])} | {failed} |")
    return "\n".join(lines) + "\n"
