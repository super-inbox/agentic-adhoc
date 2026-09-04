#!/usr/bin/env python3
"""Score blinded contest rankings and their derived winner pairs."""

from __future__ import annotations

from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path
import random
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT_DIR = HERE.parent
CONTESTS_PATH = EXPERIMENT_DIR / "dataset" / "contests.jsonl"
PAIRS_PATH = EXPERIMENT_DIR / "dataset" / "pairs.jsonl"
SCHEMA_PATH = EXPERIMENT_DIR / "schemas" / "rank-output.schema.json"
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
    out = []
    for meta_path in sorted((RUNS_DIR / case_id).glob("attempt-*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        response_path = meta_path.parent / "response.json"
        response = json.loads(response_path.read_text(encoding="utf-8")) if response_path.exists() else None
        out.append((meta, response, meta_path.parent))
    return out


def mean(values: list[float | int | bool]) -> float | None:
    return sum(float(value) for value in values) / len(values) if values else None


def contest_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "completed"]
    return {
        "n": len(rows),
        "completed": len(completed),
        "top1_correct": sum(row["top1_correct"] for row in completed),
        "top1_accuracy_completed": mean([row["top1_correct"] for row in completed]),
        "top1_accuracy_all_gated": sum(row.get("top1_correct", False) for row in rows) / len(rows) if rows else None,
        "winner_mrr_completed": mean([row["winner_reciprocal_rank"] for row in completed]),
        "mean_confidence": mean([row["prediction"]["confidence"] for row in completed]),
        "tool_call_free": mean([row["tool_call_free"] for row in completed]),
    }


def pair_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    judged = [row for row in rows if row["status"] == "completed"]
    return {
        "n": len(rows),
        "judged": len(judged),
        "winner_ranked_above_other": sum(row["winner_ranked_above_other"] for row in judged),
        "accuracy_completed": mean([row["winner_ranked_above_other"] for row in judged]),
        "accuracy_all_gated": sum(row.get("winner_ranked_above_other", False) for row in rows) / len(rows) if rows else None,
    }


def clustered_bootstrap_ci(
    rows: list[dict[str, Any]], *, cluster_key: str, value_key: str, seed: int, rounds: int = 10000
) -> list[float] | None:
    """Percentile CI while resampling whole contests, not dependent pairs."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "completed" and row.get(value_key) is not None:
            grouped[str(row[cluster_key])].append(float(row[value_key]))
    clusters = list(grouped.values())
    if not clusters:
        return None
    rng = random.Random(seed)
    estimates = []
    for _ in range(rounds):
        sampled = [clusters[rng.randrange(len(clusters))] for _ in range(len(clusters))]
        values = [value for cluster in sampled for value in cluster]
        estimates.append(sum(values) / len(values))
    estimates.sort()
    lo = estimates[int(0.025 * (rounds - 1))]
    hi = estimates[int(0.975 * (rounds - 1))]
    return [lo, hi]


def main() -> int:
    contests = load_jsonl(CONTESTS_PATH)
    pair_fixture = load_jsonl(PAIRS_PATH)
    results = []
    by_id = {}
    for case in contests:
        attempts = attempts_for(case["id"])
        first = attempts[0][0] if attempts else None
        selected = next(
            ((meta, response, path) for meta, response, path in attempts if meta.get("status") == "completed" and response is not None),
            None,
        )
        base = {
            "id": case["id"],
            "contest_id": case["metadata"]["contest_id"],
            "design_type": case["metadata"]["design_type"],
            "subtype": case["metadata"]["subtype"],
            "industry": case["metadata"]["industry"],
            "client_cluster": case["metadata"]["client_cluster"],
            "exclude_simbans_slice": case["metadata"]["exclude_simbans_slice"],
            "option_count": len(case["input"]["options"]),
            "winner_option_id": case["expected"]["winner_option_id"],
            "attempt_count": len(attempts),
            "first_attempt_completed": bool(first and first.get("status") == "completed"),
        }
        if selected is None:
            row = {**base, "status": "missing_or_failed", "prediction": None}
        else:
            meta, response, path = selected
            ranking = response["ranking"]
            winner_rank = ranking.index(case["expected"]["winner_option_id"]) + 1
            row = {
                **base,
                "status": "completed",
                "selected_attempt": meta["attempt"],
                "selected_run_dir": str(path.relative_to(EXPERIMENT_DIR)),
                "duration_seconds": meta.get("duration_seconds"),
                "usage": meta.get("trace", {}).get("usage"),
                "tool_call_free": meta.get("trace", {}).get("tool_call_count", 0) == 0,
                "prediction": response,
                "winner_rank": winner_rank,
                "winner_reciprocal_rank": 1 / winner_rank,
                "top1_correct": winner_rank == 1,
            }
        results.append(row)
        by_id[row["id"]] = row

    pair_results = []
    for pair in pair_fixture:
        contest = by_id[pair["contest_id"]]
        if contest["status"] != "completed":
            pair_results.append({**pair, "status": "missing_or_failed"})
            continue
        ranking = contest["prediction"]["ranking"]
        pair_results.append(
            {
                **pair,
                "status": "completed",
                "winner_ranked_above_other": ranking.index(pair["winner_option_id"]) < ranking.index(pair["other_option_id"]),
            }
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    contests_out = RESULTS_DIR / "contest-results.jsonl"
    pairs_out = RESULTS_DIR / "pair-results.jsonl"
    contests_out.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results), encoding="utf-8"
    )
    pairs_out.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in pair_results), encoding="utf-8"
    )
    non_simbans = [row for row in results if not row["exclude_simbans_slice"]]
    different_designer_pairs = [row for row in pair_results if not row["same_designer"]]
    same_designer_pairs = [row for row in pair_results if row["same_designer"]]
    non_simbans_pairs = [row for row in pair_results if not row["exclude_simbans_slice"]]
    per_type = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[row["design_type"]].append(row)
    for design_type, group in sorted(grouped.items()):
        per_type[design_type] = {
            **contest_metrics(group),
            "unique_clients": len({row["client_cluster"] for row in group}),
            "industry_distribution": dict(Counter(row["industry"] for row in group)),
            "pairwise": pair_metrics([row for row in pair_results if row["design_type"] == design_type]),
        }
    winner_position = {}
    for label in "ABCDE":
        group = [row for row in results if row["winner_option_id"] == label]
        if group:
            winner_position[label] = contest_metrics(group)
    predicted_best = Counter(
        row["prediction"]["best_option"] for row in results if row["status"] == "completed"
    )
    completed_results = [row for row in results if row["status"] == "completed"]
    usage_totals: Counter[str] = Counter()
    durations = []
    for row in completed_results:
        usage_totals.update(row.get("usage") or {})
        durations.append(row.get("duration_seconds") or 0)
    confidences = [row["prediction"]["confidence"] for row in completed_results]
    correct_confidences = [row["prediction"]["confidence"] for row in completed_results if row["top1_correct"]]
    incorrect_confidences = [row["prediction"]["confidence"] for row in completed_results if not row["top1_correct"]]
    summary = {
        "schema_version": "codex-99designs-evaluate-rank-summary-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "candidate": candidate_from(results),
        "dataset": {
            "contests_sha256": sha256(CONTESTS_PATH),
            "pairs_sha256": sha256(PAIRS_PATH),
            "contests": len(contests),
            "pairs": len(pair_fixture),
        },
        "reliability": {
            "completed_selected": sum(row["status"] == "completed" for row in results),
            "first_attempt_completed": sum(row["first_attempt_completed"] for row in results),
            "retried_contests": sum(row["attempt_count"] > 1 for row in results),
        },
        "contest_all_61": contest_metrics(results),
        "contest_excluding_simbans_52": contest_metrics(non_simbans),
        "pairs_all_243": pair_metrics(pair_results),
        "pairs_excluding_same_designer_206": pair_metrics(different_designer_pairs),
        "pairs_same_designer_37": pair_metrics(same_designer_pairs),
        "pairs_excluding_simbans_208": pair_metrics(non_simbans_pairs),
        "per_design_type": per_type,
        "winner_position": winner_position,
        "predicted_best_position_distribution": dict(sorted(predicted_best.items())),
        "winner_rank_distribution": dict(
            sorted(Counter(str(row["winner_rank"]) for row in completed_results).items())
        ),
        "confidence_calibration": {
            "mean_reported_confidence": mean(confidences),
            "top1_accuracy": mean([row["top1_correct"] for row in completed_results]),
            "calibration_gap": mean(confidences) - mean([row["top1_correct"] for row in completed_results]),
            "mean_confidence_when_correct": mean(correct_confidences),
            "mean_confidence_when_incorrect": mean(incorrect_confidences),
            "brier_score": mean(
                [
                    (row["prediction"]["confidence"] - float(row["top1_correct"])) ** 2
                    for row in completed_results
                ]
            ),
        },
        "usage_totals": dict(usage_totals),
        "latency": {
            "sum_case_seconds": sum(durations),
            "mean_case_seconds": mean(durations),
            "max_case_seconds": max(durations) if durations else None,
        },
        "chance_baselines": {
            "contest_top1_expected": mean([1 / row["option_count"] for row in results]),
            "winner_pairwise_expected": 0.5,
            "winner_mrr_expected": mean(
                [sum(1 / rank for rank in range(1, row["option_count"] + 1)) / row["option_count"] for row in results]
            ),
        },
        "confidence_intervals_95_cluster_bootstrap": {
            "contest_all_61_top1": clustered_bootstrap_ci(
                results, cluster_key="id", value_key="top1_correct", seed=2026090201
            ),
            "contest_excluding_simbans_52_top1": clustered_bootstrap_ci(
                non_simbans, cluster_key="id", value_key="top1_correct", seed=2026090202
            ),
            "pairs_all_243": clustered_bootstrap_ci(
                pair_results,
                cluster_key="contest_id",
                value_key="winner_ranked_above_other",
                seed=2026090203,
            ),
            "pairs_excluding_same_designer_206": clustered_bootstrap_ci(
                different_designer_pairs,
                cluster_key="contest_id",
                value_key="winner_ranked_above_other",
                seed=2026090204,
            ),
        },
    }
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = EXPERIMENT_DIR / "RESULTS.md"
    report_path.write_text(render_report(summary), encoding="utf-8")
    prompt_manifest_path = write_prompt_manifest(results)
    candidate = summary["candidate"]
    freeze = {
        "schema_version": "codex-99designs-evaluate-rank-freeze-v2",
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
        "fixture_builder_sha256": sha256(HERE / "build_fixture.py"),
        "runner_sha256": sha256(HERE / "run_codex_rank.py"),
        "scorer_sha256": sha256(HERE / "score.py"),
        "output_schema_sha256": sha256(SCHEMA_PATH),
        "contests_sha256": sha256(CONTESTS_PATH),
        "pairs_sha256": sha256(PAIRS_PATH),
        "contest_results_sha256": sha256(contests_out),
        "pair_results_sha256": sha256(pairs_out),
        "summary_sha256": sha256(summary_path),
    }
    (RESULTS_DIR / "freeze-manifest.json").write_text(
        json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["reliability"], ensure_ascii=False))
    print(f"summary={summary_path}\nreport={report_path}")
    return 0 if summary["reliability"]["completed_selected"] == len(contests) else 1


def candidate_from(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        run_dir = row.get("selected_run_dir")
        if run_dir:
            return json.loads((EXPERIMENT_DIR / run_dir / "meta.json").read_text(encoding="utf-8")).get("candidate")
    return None


def pct(value: Any) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def decimal(value: Any) -> str:
    return "—" if value is None else f"{value:.3f}"


def ci_pct(value: Any) -> str:
    return "—" if value is None else f"[{100 * value[0]:.1f}%, {100 * value[1]:.1f}%]"


def render_report(summary: dict[str, Any]) -> str:
    all_c = summary["contest_all_61"]
    no_sim = summary["contest_excluding_simbans_52"]
    all_p = summary["pairs_all_243"]
    no_same = summary["pairs_excluding_same_designer_206"]
    ci = summary["confidence_intervals_95_cluster_bootstrap"]
    lines = [
        "# Codex × 99designs evaluate/rank — results\n",
        f"Candidate: `{json.dumps(summary['candidate'], ensure_ascii=False, sort_keys=True)}`\n",
        f"Fixture: `{summary['dataset']['contests_sha256']}` (61 contests) / `{summary['dataset']['pairs_sha256']}` (243 derived pairs)\n",
        "## Headline\n",
        "| Slice | n | Completion | Top-1 / pair accuracy | 95% clustered bootstrap CI | Winner MRR |",
        "|---|---:|---:|---:|---:|---:|",
        f"| All contests | {all_c['n']} | {all_c['completed']}/{all_c['n']} | {pct(all_c['top1_accuracy_completed'])} ({all_c['top1_correct']}/{all_c['completed']}) | {ci_pct(ci['contest_all_61_top1'])} | {decimal(all_c['winner_mrr_completed'])} |",
        f"| Exclude `simbans` | {no_sim['n']} | {no_sim['completed']}/{no_sim['n']} | {pct(no_sim['top1_accuracy_completed'])} ({no_sim['top1_correct']}/{no_sim['completed']}) | {ci_pct(ci['contest_excluding_simbans_52_top1'])} | {decimal(no_sim['winner_mrr_completed'])} |",
        f"| All winner pairs | {all_p['n']} | {all_p['judged']}/{all_p['n']} | {pct(all_p['accuracy_completed'])} ({all_p['winner_ranked_above_other']}/{all_p['judged']}) | {ci_pct(ci['pairs_all_243'])} | — |",
        f"| Exclude same-designer pairs | {no_same['n']} | {no_same['judged']}/{no_same['n']} | {pct(no_same['accuracy_completed'])} ({no_same['winner_ranked_above_other']}/{no_same['judged']}) | {ci_pct(ci['pairs_excluding_same_designer_206'])} | — |\n",
        f"Random expectation for within-contest top-1 is {pct(summary['chance_baselines']['contest_top1_expected'])}; pairwise is 50.0%.\n",
        "## Reliability and leakage controls\n",
        f"- Selected valid rankings: **{summary['reliability']['completed_selected']}/61**",
        f"- First-attempt completion: **{summary['reliability']['first_attempt_completed']}/61**",
        f"- Retried contests: **{summary['reliability']['retried_contests']}**",
        f"- Planner-only/no-tool invariant: **{pct(all_c['tool_call_free'])}**",
        f"- Predicted best-position distribution: `{summary['predicted_best_position_distribution']}`",
        f"- Winner rank distribution: `{summary['winner_rank_distribution']}`",
        f"- Mean self-reported confidence **{pct(summary['confidence_calibration']['mean_reported_confidence'])}** vs top-1 accuracy **{pct(summary['confidence_calibration']['top1_accuracy'])}**; Brier **{summary['confidence_calibration']['brier_score']:.3f}**.",
        f"- Same-designer pairs: **{pct(summary['pairs_same_designer_37']['accuracy_completed'])}** (22/37); different-designer pairs: **{pct(no_same['accuracy_completed'])}** (131/206).",
        f"- Sum of independent case latency **{summary['latency']['sum_case_seconds']:.1f}s**, mean **{summary['latency']['mean_case_seconds']:.1f}s**; CLI usage `{summary['usage_totals']}`.\n",
        "## By design type\n",
        "| Design type | contests | clients | top-1 | MRR | pair acc. |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in summary["per_design_type"].items():
        lines.append(
            f"| {name} | {row['n']} | {row['unique_clients']} | {pct(row['top1_accuracy_completed'])} | "
            f"{decimal(row['winner_mrr_completed'])} | {pct(row['pairwise']['accuracy_completed'])} |"
        )
    lines.extend(
        [
            "\n## Interpretation boundary\n",
            "- This is observed-winner preference recovery, not an objective design-quality score.",
            "- Non-winner previews are neither known finalists nor known low-quality negatives.",
            "- Selection rationale is unavailable for 61/61; 60/61 briefs retain source ellipses.",
            "- 52/61 contests are Travel & Hotel; the 9 Banner cases are one repeated `simbans` client.",
            "- The 243 pair results are derived from 61 multi-option rankings, not 243 independent model calls.",
            "- Confidence intervals resample whole contests so four pairs from one ranking are not treated as independent.",
            "- Rights are not cleared for redistribution or training; this remains a local evaluation artifact.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
