#!/usr/bin/env python3
"""Validate and freeze the completed Codex 21q single-turn quality baseline."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
REPO_ROOT = HERE.parents[4]
BASELINE = EXPERIMENT / "baselines/codex-single-turn-v1"
DATASET_PATH = EXPERIMENT / "dataset.jsonl"
RAW_JUDGE_PATH = BASELINE / "judge-v2.1.results.jsonl"
CANONICAL_RESULTS_PATH = BASELINE / "results.jsonl"
SUMMARY_PATH = BASELINE / "summary.json"
MANIFEST_PATH = BASELINE / "manifest.json"
REPORT_PATH = BASELINE / "README.md"
ORIGINAL_RUN_SUMMARY_PATH = EXPERIMENT / "codex-run-summary.json"
BATCH_MANIFEST_PATH = EXPERIMENT / "batch-manifest.json"
PUBLISHED_RUNS = EXPERIMENT / "candidates/codex/runs"
COMPLETION_RUNS = HERE / "runs"

EXPECTED_CANDIDATE = {
    "agent_name": "codex-cli",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "max",
    "service_tier": "default",
    "session_mode": "ephemeral",
}
EXPECTED_CLI_VERSION = "codex-cli 0.146.0"
DIMENSIONS = (
    "brief_adherence",
    "visual_quality",
    "creative_diversity",
    "brand_consistency",
    "refinement_ability",
    "cross_asset_consistency",
    "production_readiness",
    "efficiency",
)
PORTABLE_TEXT_SUFFIXES = {".json", ".jsonl", ".log", ".md", ".txt"}
TEMP_RUN_PATTERN = re.compile(
    r"/(?:private/)?var/folders/[^/\s'\"<>]+/[^/\s'\"<>]+/T/"
    r"codex-design-benchmark-[^/\s'\"<>]+"
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tree_sha256(root: Path) -> str:
    rows: list[tuple[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rows.append((path.relative_to(root).as_posix(), _sha256(path)))
    return _json_sha256(rows)


def _portable(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _within(path: Path, roots: tuple[Path, ...]) -> bool:
    resolved = path.resolve()
    return any(resolved.is_relative_to(root.resolve()) for root in roots)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _redact_host_paths(text: str) -> str:
    """Remove host-specific paths while preserving replay-relevant trace text."""
    redacted = TEMP_RUN_PATTERN.sub("REDACTED_RUN_WORKSPACE", text)
    redacted = redacted.replace(str(REPO_ROOT.resolve()), "REPO_ROOT")
    redacted = redacted.replace(str(Path.home().resolve()), "REDACTED_USER_HOME")
    return redacted


def _sanitize_completion_run_text() -> None:
    for path in sorted(item for item in COMPLETION_RUNS.rglob("*") if item.is_file()):
        if path.suffix.lower() not in PORTABLE_TEXT_SUFFIXES:
            continue
        original = path.read_text(encoding="utf-8")
        redacted = _redact_host_paths(original)
        if redacted != original:
            _atomic_text(path, redacted)


def _portable_raw_judgments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    portable_rows = []
    for source in rows:
        row = copy.deepcopy(source)
        raw_run_dir = row.get("run_dir")
        if raw_run_dir:
            run_dir = Path(str(raw_run_dir))
            if run_dir.is_absolute():
                if not _within(run_dir, (PUBLISHED_RUNS, COMPLETION_RUNS)):
                    raise ValueError(f"judge row points outside allowed run roots: {run_dir}")
                row["run_dir"] = _portable(run_dir)
        portable_rows.append(row)
    return portable_rows


def _score(record: dict[str, Any], name: str) -> float | None:
    value = record.get("benchmark_scores", {}).get(name, {}).get("score")
    return None if value is None else float(value)


def _latest_successful_judgments(
    rows: list[dict[str, Any]], expected_ids: set[str]
) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("candidate_name") != "codex-cli" or row.get("error"):
            continue
        available = (
            row.get("benchmark_scores", {})
            .get("independent_judge_available", {})
            .get("score")
        )
        if available == 1:
            selected[str(row["task_id"])] = row
    if set(selected) != expected_ids:
        missing = sorted(expected_ids - set(selected))
        extra = sorted(set(selected) - expected_ids)
        raise ValueError(f"judge coverage is not 21/21; missing={missing}, extra={extra}")
    return selected


def _validate_run(
    task_id: str,
    row: dict[str, Any],
    case: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_dir = Path(str(row["run_dir"]))
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    if not _within(run_dir, (PUBLISHED_RUNS, COMPLETION_RUNS)):
        raise ValueError(f"{task_id}: selected run is outside allowed roots: {run_dir}")
    result_path = run_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("task_id") != task_id:
        raise ValueError(f"{task_id}: result task mismatch")
    if result.get("outcome") != "completed" or result.get("exit_code") != 0:
        raise ValueError(f"{task_id}: selected run is not completed")
    if result.get("candidate") != EXPECTED_CANDIDATE:
        raise ValueError(f"{task_id}: candidate configuration drift")
    if result.get("cli_version") != EXPECTED_CLI_VERSION:
        raise ValueError(f"{task_id}: CLI version drift")
    required_assets = int(case["expected"]["input_contract"]["asset_count"])
    if len(result.get("uploaded_assets") or []) != required_assets:
        raise ValueError(f"{task_id}: input asset count mismatch")
    if result.get("omitted_assets"):
        raise ValueError(f"{task_id}: selected run omitted input assets")

    outputs = run_dir / "outputs"
    for artifact in result.get("artifacts") or []:
        artifact_path = outputs / str(artifact["filename"])
        if not artifact_path.is_file():
            raise ValueError(f"{task_id}: missing artifact {artifact_path.name}")
        if artifact.get("byte_size") != artifact_path.stat().st_size:
            raise ValueError(f"{task_id}: artifact byte-size mismatch: {artifact_path.name}")
        if artifact.get("sha256") != _sha256(artifact_path):
            raise ValueError(f"{task_id}: artifact hash mismatch: {artifact_path.name}")

    usage = (result.get("trace_summary") or {}).get("usage") or {}
    run_record = {
        "task_id": task_id,
        "run_path": _portable(run_dir),
        "result_sha256": _sha256(result_path),
        "run_tree_sha256": _tree_sha256(run_dir),
        "outcome": result["outcome"],
        "latency_ms": result.get("latency_ms"),
        "artifact_count": len(result.get("artifacts") or []),
        "input_asset_count": len(result.get("uploaded_assets") or []),
        "usage": usage,
        "selection_reason": (
            "posthoc_completion_rerun_after_original_timeout"
            if task_id == "TIQ-098"
            else "original_frozen_run"
        ),
    }
    return result, run_record


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 6) if values else None


def _nearest_rank(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * fraction + 0.999999) - 1))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing frozen manifest if its content hash changed.",
    )
    args = parser.parse_args()

    _sanitize_completion_run_text()

    dataset = _jsonl(DATASET_PATH)
    cases = {str(row["input"]["task_id"]): row for row in dataset}
    if len(dataset) != len(cases) or len(cases) != 21:
        raise ValueError("frozen dataset must contain exactly 21 unique task IDs")

    raw_judgments = _portable_raw_judgments(_jsonl(RAW_JUDGE_PATH))
    _atomic_text(
        RAW_JUDGE_PATH,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in raw_judgments
        ),
    )
    selected = _latest_successful_judgments(raw_judgments, set(cases))
    selected_results: dict[str, dict[str, Any]] = {}
    selected_runs: list[dict[str, Any]] = []
    canonical_rows: list[dict[str, Any]] = []
    for task_id in sorted(cases):
        row = selected[task_id]
        result, run_record = _validate_run(task_id, row, cases[task_id])
        selected_results[task_id] = result
        selected_runs.append(run_record)
        portable_row = copy.deepcopy(row)
        portable_row["run_dir"] = run_record["run_path"]
        canonical_rows.append(portable_row)

    canonical_text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in canonical_rows
    )
    _atomic_text(CANONICAL_RESULTS_PATH, canonical_text)

    dimension_summary: dict[str, dict[str, Any]] = {}
    for name in DIMENSIONS:
        values = [
            value
            for value in (_score(row, name) for row in canonical_rows)
            if value is not None
        ]
        dimension_summary[name] = {"n": len(values), "mean": _mean(values)}

    gate_counts: Counter[str] = Counter()
    for row in canonical_rows:
        gates = (
            row["benchmark_scores"]["benchmark_total_score"]["metadata"]["hard_gates"]
        )
        for name, passed in gates.items():
            gate_counts[name] += bool(passed)

    category_summary: dict[str, dict[str, Any]] = {}
    for category in sorted({str(case["metadata"]["category"]) for case in dataset}):
        task_ids = [
            task_id
            for task_id, case in cases.items()
            if case["metadata"]["category"] == category
        ]
        values = [_score(selected[task_id], "weighted_design_score") for task_id in task_ids]
        category_summary[category] = {
            "n": len(task_ids),
            "weighted_design_mean": _mean([float(value) for value in values if value is not None]),
        }

    latencies = [float(result["latency_ms"]) for result in selected_results.values()]
    usage_totals: Counter[str] = Counter()
    for run in selected_runs:
        for name, value in run["usage"].items():
            if isinstance(value, (int, float)):
                usage_totals[name] += value

    first_attempt = json.loads(ORIGINAL_RUN_SUMMARY_PATH.read_text(encoding="utf-8"))
    judge_failures = [
        {
            "task_id": row.get("task_id"),
            "error": (
                row.get("benchmark_scores", {})
                .get("independent_judge_available", {})
                .get("metadata", {})
                .get("error")
            ),
        }
        for row in raw_judgments
        if (
            row.get("candidate_name") == "codex-cli"
            and (
                row.get("benchmark_scores", {})
                .get("independent_judge_available", {})
                .get("score")
                != 1
            )
        )
    ]
    weighted = [_score(row, "weighted_design_score") for row in canonical_rows]
    totals = [_score(row, "benchmark_total_score") for row in canonical_rows]
    case_passes = sum(_score(row, "benchmark_case_pass") == 1 for row in canonical_rows)

    summary = {
        "schema_version": "codex-21q-single-turn-summary-v1",
        "baseline_id": "codex-21q-single-turn-v1",
        "candidate": {**EXPECTED_CANDIDATE, "cli_version": EXPECTED_CLI_VERSION},
        "coverage": {
            "dataset_cases": 21,
            "selected_completed_runs": 21,
            "independent_judge_completed": 21,
            "independent_judge_blocked": 0,
        },
        "first_attempt_reliability": {
            "completed": int(first_attempt["outcomes"]["completed"]),
            "total": int(first_attempt["cases"]),
            "timeout_task_ids": list(first_attempt.get("timeout_task_ids") or []),
            "automatic_retries": int(first_attempt.get("automatic_retries") or 0),
        },
        "selected_quality_baseline": {
            "completed": 21,
            "posthoc_completion_reruns": ["TIQ-098"],
            "weighted_design_mean": _mean([float(value) for value in weighted if value is not None]),
            "benchmark_total_mean": _mean([float(value) for value in totals if value is not None]),
            "case_passes": case_passes,
            "pass_threshold": 0.7,
        },
        "dimensions": dimension_summary,
        "hard_gates": {name: {"passed": count, "total": 21} for name, count in sorted(gate_counts.items())},
        "categories": category_summary,
        "latency_ms": {
            "n": len(latencies),
            "mean": round(statistics.fmean(latencies), 3),
            "median": statistics.median(latencies),
            "p95_nearest_rank": _nearest_rank(latencies, 0.95),
            "max": max(latencies),
        },
        "selected_usage": dict(sorted(usage_totals.items())),
        "judge_attempts": {
            "raw": len(raw_judgments),
            "selected_successful": 21,
            "failed_response_contract_attempts": judge_failures,
        },
        "lowest_weighted_cases": [
            {
                "task_id": row["task_id"],
                "weighted_design_score": _score(row, "weighted_design_score"),
                "benchmark_total_score": _score(row, "benchmark_total_score"),
            }
            for row in sorted(
                canonical_rows,
                key=lambda item: _score(item, "weighted_design_score") or 0.0,
            )[:5]
        ],
    }
    _atomic_text(
        SUMMARY_PATH,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    batch_manifest = json.loads(BATCH_MANIFEST_PATH.read_text(encoding="utf-8"))
    file_hashes = {
        "dataset.jsonl": _sha256(DATASET_PATH),
        "judge-v2.1.results.jsonl": _sha256(RAW_JUDGE_PATH),
        "results.jsonl": _sha256(CANONICAL_RESULTS_PATH),
        "summary.json": _sha256(SUMMARY_PATH),
        "scripts/freeze_codex_single_turn.py": _sha256(Path(__file__)),
        "scripts/judge_v2.py": _sha256(HERE / "judge_v2.py"),
        "scripts/run_codex_benchmark.mjs": _sha256(HERE / "run_codex_benchmark.mjs"),
        "scripts/run_full_comparison.py": _sha256(HERE / "run_full_comparison.py"),
        "scripts/scorers.py": _sha256(HERE / "scorers.py"),
    }
    freeze_core = {
        "baseline_id": "codex-21q-single-turn-v1",
        "dataset_sha256": file_hashes["dataset.jsonl"],
        "raw_judge_sha256": file_hashes["judge-v2.1.results.jsonl"],
        "canonical_results_sha256": file_hashes["results.jsonl"],
        "harness_sha256": {
            name: digest
            for name, digest in file_hashes.items()
            if name.startswith("scripts/")
        },
        "candidate": {**EXPECTED_CANDIDATE, "cli_version": EXPECTED_CLI_VERSION},
        "judge": {"name": "judge-v2.1", "model": "gemini-2.5-pro", "temperature": 0},
        "selected_runs": selected_runs,
    }
    baseline_sha256 = _json_sha256(freeze_core)
    old_manifest = (
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if MANIFEST_PATH.exists()
        else None
    )
    if (
        old_manifest
        and old_manifest.get("baseline_sha256") != baseline_sha256
        and not args.force
    ):
        raise SystemExit(
            "Frozen baseline content changed; inspect the diff and rerun with --force only "
            "when intentionally creating a replacement snapshot."
        )
    frozen_at = (
        old_manifest.get("frozen_at")
        if old_manifest and old_manifest.get("baseline_sha256") == baseline_sha256
        else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    manifest = {
        "schema_version": "codex-21q-single-turn-freeze-v1",
        "baseline_id": "codex-21q-single-turn-v1",
        "status": "frozen",
        "frozen_at": frozen_at,
        "baseline_sha256": baseline_sha256,
        "dataset": {
            "name": batch_manifest["dataset"]["name"],
            "pack_version": batch_manifest["dataset"]["pack_version"],
            "row_count": 21,
            "published_file_sha256": file_hashes["dataset.jsonl"],
            "upstream_pre_export_sha256": batch_manifest["dataset"].get("sha256"),
            "task_ids": sorted(cases),
        },
        "candidate": {**EXPECTED_CANDIDATE, "cli_version": EXPECTED_CLI_VERSION},
        "protocol": {
            "user_turns": 1,
            "session_per_selected_run": "ephemeral",
            "automatic_generation_retries": 0,
            "first_attempt_result": "20/21 completed; TIQ-098 timed out at 15 minutes",
            "quality_baseline_selection": "latest completed run per task",
            "posthoc_completion_reruns": ["TIQ-098"],
            "reliability_and_quality_are_reported_separately": True,
        },
        "judge": {
            "name": "judge-v2.1",
            "model": "gemini-2.5-pro",
            "temperature": 0,
            "candidate_identity_hidden": True,
            "coverage": "21/21",
            "raw_attempts": len(raw_judgments),
            "canonical_selection": "latest successful judgment per task",
            "evidence_adapter": "supported raster images + text evidence; SVG retained for contracts but not sent as inline image",
            "response_contract": "Prompt-enforced JSON for the first 20 successful rows; schema-constrained retry for AR-012 after two malformed responses; rubric and scoring prompt unchanged",
        },
        "selected_runs": selected_runs,
        "file_sha256": file_hashes,
        "notes": [
            "This freezes a Codex-only quality baseline; it is not a new Curify comparison.",
            "Historical Flash and partial Pro scores are excluded from canonical results.",
            "The posthoc TIQ-098 rerun must not be used to claim 21/21 first-attempt reliability.",
            "AR-012 required a response-format retry; the two omitted-dimension attempts remain in the raw judge ledger.",
            "Host-specific home and temporary paths are redacted in the committed raw ledger and completion-run text files.",
        ],
    }
    _atomic_text(
        MANIFEST_PATH,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    def pct(value: float | None) -> str:
        return "—" if value is None else f"{value:.3f}"

    report = f"""# Codex 21q single-turn baseline v1

Frozen at `{frozen_at}`. Baseline SHA-256: `{baseline_sha256}`.

This is the completed Codex-only quality baseline for the 21 multimodal, single-user-turn cases. The
original first-attempt ledger is preserved separately from the selected quality runs.

## Coverage

| Item | Result |
|---|---:|
| Dataset | 21/21 |
| Original first-attempt completion | {first_attempt['outcomes']['completed']}/21 |
| Selected completed quality runs | 21/21 |
| Independent judge-v2.1 | 21/21 |
| Posthoc generation reruns | 1 (`TIQ-098`) |
| Raw judge attempts | {len(raw_judgments)} (21 selected + {len(judge_failures)} malformed) |

`TIQ-098` originally timed out at 15 minutes after producing 20 images. Its explicitly labelled
completion rerun finished in {selected_results['TIQ-098']['latency_ms'] / 60_000:.2f} minutes with 22
artifacts. Therefore first-attempt reliability remains 20/21; only the quality baseline is 21/21.

## Headline scores

| Metric | Score |
|---|---:|
| Weighted design mean | {summary['selected_quality_baseline']['weighted_design_mean']:.3f} |
| Gated benchmark total mean | {summary['selected_quality_baseline']['benchmark_total_mean']:.3f} |
| Case passes (all gates and score ≥ 0.70) | {case_passes}/21 |
| Median latency | {summary['latency_ms']['median'] / 1000:.2f} s |

## Dimensions

| Dimension | n | Mean (0–1) |
|---|---:|---:|
"""
    for name in DIMENSIONS:
        item = dimension_summary[name]
        report += f"| `{name}` | {item['n']} | {pct(item['mean'])} |\n"
    report += """

## Hard gates

| Gate | Passed |
|---|---:|
"""
    for name, count in sorted(gate_counts.items()):
        report += f"| `{name}` | {count}/21 |\n"
    report += """

The largest observed gap is brief adherence, followed by task-specific diversity/refinement. The
gated total is additionally limited by artifact-contract (13/21) and production-gate (15/21)
failures. These are measured separately from visual quality.

## Frozen files

- `results.jsonl`: exactly 21 portable, deduplicated canonical records.
- `judge-v2.1.results.jsonl`: ordered raw judge ledger, including malformed attempts.
- `summary.json`: machine-readable aggregate.
- `manifest.json`: dataset, scripts, selected runs, artifacts and hashes.

This baseline uses one stochastic generation per selected task and one successful independent
judgment per task. Gemini judgments are not human ground truth. Historical Flash scores and the
older incomplete Pro runs are excluded. Do not compare their means directly with this snapshot.
AR-012's selected judgment used the same rubric and prompt with a schema-constrained response after
two malformed responses omitted one required dimension; both failed attempts remain auditable.
Host-specific home and temporary paths are redacted from the committed publication copy.
"""
    _atomic_text(REPORT_PATH, report)
    print(f"FROZEN {baseline_sha256}")
    print(f"wrote {CANONICAL_RESULTS_PATH}")
    print(f"wrote {SUMMARY_PATH}")
    print(f"wrote {MANIFEST_PATH}")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
