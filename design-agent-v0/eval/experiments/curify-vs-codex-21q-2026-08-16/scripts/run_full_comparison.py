#!/usr/bin/env python3
"""Score the latest 21-case Curify and Codex runs with the shared judge-v2 rubric."""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from braintrust import Attachment


HERE = Path(__file__).resolve().parent
BRAINTRUST_EVAL = HERE.parents[1]
if str(BRAINTRUST_EVAL) not in sys.path:
    sys.path.insert(0, str(BRAINTRUST_EVAL))

from dataset_builder import build_cases  # noqa: E402
from judge_v2 import GeminiIndependentJudgeV2  # noqa: E402
from scorers import benchmark_judge_v2_scores, runtime_scores  # noqa: E402


ENV_PATH = Path(
    os.environ.get("DESIGN_AGENT_EVAL_ENV")
    or BRAINTRUST_EVAL / ".auth/phase1.env"
)
RESULTS_PATH = Path(
    os.environ.get("COMPARISON_RESULTS_PATH")
    or HERE / "full-comparison.judge-v2.results.jsonl"
).resolve()
SUMMARY_PATH = Path(
    os.environ.get("COMPARISON_SUMMARY_PATH")
    or RESULTS_PATH.with_name("full-comparison.summary.json")
).resolve()
CANDIDATES = {
    "curify-web": {
        # Override to score a FRESH run instead of the published 2026-08-16
        # export: CURIFY_RUNS_ROOT=scripts/runs after run_curify_benchmark.cjs.
        # Without it the judge silently re-scores the old artifacts and the
        # summary reads as a result for the new build.
        "root": Path(os.environ.get("CURIFY_RUNS_ROOT")
                     or HERE.parent / "curify-jwang-vercel-275f7d0a/runs"),
        "artifact_subdir": "",
        "identity": {
            "agent": "curify-web",
            "candidate": "curify-web-jwang-vercel@275f7d0a",
            "frontend_commit": "275f7d0a111b8fe0c4c5a5409c548932d003cb9f",
        },
    },
    "codex-cli": {
        # An optional completion-run root can contain only the cases being
        # supplemented. Missing task directories fall back to the frozen
        # published runs below.
        "root": Path(
            os.environ.get("CODEX_RUNS_ROOT")
            or HERE.parent / "codex-v0.2/runs"
        ),
        "artifact_subdir": "outputs",
        "identity": {
            "agent": "codex-cli",
            "cli_version": "0.146.0",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "max",
            "session_mode": "ephemeral",
        },
    },
}


class UnavailableJudge:
    def __init__(self, model: str, reason: str):
        self.model_name = model
        self.reason = reason

    async def evaluate(self, _request: Any) -> Any:
        raise RuntimeError(self.reason)


def _load_env() -> None:
    if not ENV_PATH.exists():
        return
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


# Published-layout fallbacks. `export_for_agentic.mjs` reorganises the working
# tree into candidates/<name>/… before publishing, but these roots still point at
# the pre-export working-directory names, so a fresh clone cannot re-judge
# anything: every task fails with "No run directory". Codex keeps a full run dir
# after export; Curify publishes only the final outputs, with the per-task
# metadata that result.json carried moved into curify-output-paths.jsonl.
PUBLISHED_ROOTS = {
    "curify-web": HERE.parent / "candidates/curify/outputs",
    "codex-cli": HERE.parent / "candidates/codex/runs",
}
_CURIFY_INDEX = HERE.parent / "curify-output-paths.jsonl"


def _published_curify_run(task_id: str) -> tuple[Path, dict[str, Any]] | None:
    """Rebuild a run record for Curify from the published export.

    Reads the committed index rather than inventing anything: outcome, latency
    and the artifact list all come from curify-output-paths.jsonl, and the files
    are the ones actually on disk.
    """
    if not _CURIFY_INDEX.is_file():
        return None
    for line in _CURIFY_INDEX.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("task_id") != task_id:
            continue
        run_dir = PUBLISHED_ROOTS["curify-web"] / task_id
        if not run_dir.is_dir():
            return None
        raw = {
            "outcome": row.get("outcome"),
            "latency_ms": row.get("latency_ms"),
            "artifacts": [
                {"filename": Path(rel).name}
                for rel in (row.get("output_paths") or [])
            ],
            # `uploaded_assets` is the key _normalized_output actually reads.
            # Emitting only `uploaded_asset_roles` (as the first version did)
            # made loaded_count 0 for every Curify case, which tripped the
            # all_inputs_consumed hard gate and zeroed benchmark_total on all
            # 21 — a key-name mismatch that read exactly like "Curify never
            # consumes references". Codex's real result.json carries both keys,
            # so only Curify was affected and the comparison looked decisive.
            "uploaded_assets": list(row.get("uploaded_asset_roles") or []),
            "uploaded_asset_roles": row.get("uploaded_asset_roles") or [],
            "omitted_asset_roles": row.get("omitted_asset_roles") or [],
            "omitted_assets": list(row.get("omitted_asset_roles") or []),
            "estimated_credits_spent": row.get("estimated_credits"),
        }
        return run_dir, raw
    return None


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    """Structural checks that must pass BEFORE any score is read.

    Every wrong result this harness has produced came from the same place: the
    data existed on disk, but did not reach the code that scored it, and the
    summary looked plausible anyway. Three instances, all silent:

      * run_dir resolved to the OTHER candidate's directory, so one agent's
        artifacts were scored under the other's name;
      * artifacts resolved to nothing, reported as artifact_contract 0/21;
      * `uploaded_assets` was spelled `uploaded_asset_roles` in the Curify
        shim, so loaded_count was 0 on every case, which failed the
        all_inputs_consumed hard gate and zeroed benchmark_total — and read as
        "Curify never consumes reference images".

    None of these are scoring questions, so none of them show up as a bad
    score. They show up as a confident one. Returns a list of problems; the
    caller refuses to write a summary while it is non-empty.
    """
    problems: list[str] = []
    for record in records:
        name = record.get("candidate_name")
        task = record.get("task_id")
        run_dir = str(record.get("run_dir") or "")
        expected_root = PUBLISHED_ROOTS.get(name)
        if name == "curify-web" and os.environ.get("CURIFY_RUNS_ROOT"):
            expected_root = Path(os.environ["CURIFY_RUNS_ROOT"])
        if expected_root is not None and expected_root.name not in run_dir:
            problems.append(
                f"{task}/{name}: run_dir {run_dir!r} is not under this "
                f"candidate's root {expected_root}"
            )
        if not record.get("artifact_count"):
            problems.append(f"{task}/{name}: resolved 0 artifacts")
        required = record.get("required_asset_count") or 0
        if required and not record.get("loaded_asset_count"):
            problems.append(
                f"{task}/{name}: case supplies {required} asset(s) but "
                "loaded_asset_count is 0 — check the candidate's raw-record "
                "key names before believing all_inputs_consumed"
            )
    return problems


def _latest_run(
    root: Path, task_id: str, candidate_name: str
) -> tuple[Path, dict[str, Any]]:
    """Resolve a task's run directory for ONE named candidate.

    `candidate_name` is required, and is the whole point. The previous version
    took only `root` and, when the pre-export path was missing, guessed the
    published location by substring-matching the root path. That routed
    curify-web tasks into candidates/codex/runs: the results carried
    candidate_name "curify-web" alongside a codex run_dir, so one agent's
    artifacts were scored under the other's name. Resolution is now keyed on the
    candidate, and the caller asserts the returned dir belongs to it.
    """
    task_root = root / task_id
    if not task_root.exists():
        published = PUBLISHED_ROOTS.get(candidate_name)
        if published is None:
            raise FileNotFoundError(
                f"No run directory for {task_id} and no published root known for "
                f"candidate {candidate_name!r}: {task_root}"
            )
        if candidate_name == "curify-web":
            rebuilt = _published_curify_run(task_id)
            if rebuilt is None:
                raise FileNotFoundError(
                    f"No run directory for {task_id} under {published} "
                    "(and no row in curify-output-paths.jsonl)"
                )
            return rebuilt
        task_root = published / task_id
        if not task_root.is_dir():
            raise FileNotFoundError(f"No run directory for {task_id}: {task_root}")

    direct = task_root / "result.json"
    if direct.is_file():
        # Published codex layout: result.json sits directly in the task dir.
        return task_root, json.loads(direct.read_text(encoding="utf-8"))
    for run_dir in sorted(
        (item for item in task_root.iterdir() if item.is_dir()), reverse=True
    ):
        result_path = run_dir / "result.json"
        if result_path.exists():
            return run_dir, json.loads(result_path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"No result.json found for {task_id}: {task_root}")


def _mime_type(path: Path, declared: str | None = None) -> str:
    if declared and declared != "application/octet-stream":
        return declared.split(";", 1)[0]
    overrides = {
        ".md": "text/markdown",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    return overrides.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or (
        "application/octet-stream"
    )


def _artifact_paths(
    candidate_name: str, run_dir: Path, raw: dict[str, Any]
) -> list[tuple[Path, str]]:
    config = CANDIDATES[candidate_name]
    base = run_dir / str(config["artifact_subdir"])
    resolved: list[tuple[Path, str]] = []
    for artifact in raw.get("artifacts") or []:
        filename = str(artifact.get("filename") or "")
        if not filename:
            continue
        artifact_path = base / filename
        if artifact_path.is_file():
            resolved.append((artifact_path, _mime_type(artifact_path, artifact.get("content_type"))))
    final_response = run_dir / "final-response.txt"
    if final_response.is_file():
        resolved.append((final_response, "text/plain"))
    return resolved


def _normalized_output(
    candidate_name: str,
    case: dict[str, Any],
    run_dir: Path,
    raw: dict[str, Any],
) -> dict[str, Any]:
    artifact_paths = _artifact_paths(candidate_name, run_dir, raw)
    artifacts = [
        {
            "filename": artifact_path.name,
            "label": f"candidate output {index + 1}",
            "content_type": content_type,
            "attachment": Attachment(
                data=artifact_path.read_bytes(),
                filename=artifact_path.name,
                content_type=content_type,
            ),
        }
        for index, (artifact_path, content_type) in enumerate(artifact_paths)
    ]
    for artifact_path, content_type in artifact_paths:
        if content_type != "application/pdf":
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="design-agent-pdf-render-") as tmp:
                output_stem = Path(tmp) / "page-1"
                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        "1",
                        "-singlefile",
                        "-png",
                        "-r",
                        "150",
                        str(artifact_path),
                        str(output_stem),
                    ],
                    check=True,
                    capture_output=True,
                )
                preview_path = output_stem.with_suffix(".png")
                artifacts.append(
                    {
                        "filename": f"{artifact_path.stem}.judge-preview.png",
                        "label": f"rendered first page of {artifact_path.name}",
                        "content_type": "image/png",
                        "evidence_only": True,
                        "attachment": Attachment(
                            data=preview_path.read_bytes(),
                            filename=f"{artifact_path.stem}.judge-preview.png",
                            content_type="image/png",
                        ),
                    }
                )
        except (OSError, subprocess.CalledProcessError):
            pass
    if candidate_name == "curify-web":
        completed = raw.get("outcome") == "completed"
        loaded_count = len(raw.get("uploaded_assets") or [])
        estimated_credits = raw.get("estimated_credits_spent")
        tool_calls = len(raw.get("states") or [])
        trace = [
            {
                "stage": {
                    "run_started": "UNDERSTAND",
                    "routed": "PLAN",
                    "planned": "PLAN",
                    "step_started": "GENERATE",
                    "step_result": "VERIFY",
                    "run_finished": "PRESENT",
                }.get(str(event.get("type") or ""), ""),
                "status": "COMPLETED",
            }
            for event in raw.get("trajectory") or []
            if event.get("type")
        ]
    else:
        completed = raw.get("outcome") in {"completed", "completed_no_saved_artifact"}
        loaded_count = len(raw.get("uploaded_assets") or [])
        estimated_credits = None
        tool_calls = (raw.get("trace_summary") or {}).get("image_tool_count")
        trace = []
    loaded_asset_ids = [
        asset["asset_id"] for asset in case["input"]["assets"][:loaded_count]
    ]
    return {
        "status": "COMPLETED" if completed else "FAILED",
        "artifacts": artifacts,
        "loaded_asset_ids": loaded_asset_ids,
        "trace": trace,
        "metrics": {
            "latency_ms": raw.get("latency_ms"),
            "estimated_credits": estimated_credits,
            "tool_calls": tool_calls,
            "model_calls": 1,
            "cost_usd": None,
        },
        "iterations": 1,
        "verdict": {"passed": False},
    }


def _score_dict(scores: list[Any]) -> dict[str, Any]:
    return {
        score.name: {
            "score": score.score,
            "metadata": score.metadata or {},
        }
        for score in scores
    }


def _existing_keys() -> set[tuple[str, str]]:
    if not RESULTS_PATH.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        judge_available = (
            record.get("benchmark_scores", {})
            .get("independent_judge_available", {})
            .get("score")
        )
        if not record.get("error") and judge_available == 1:
            keys.add((record["task_id"], record["candidate_name"]))
    return keys


async def _run(args: argparse.Namespace) -> None:
    _load_env()
    judge = (
        UnavailableJudge(args.judge_model, args.judge_unavailable_reason)
        if args.judge_unavailable_reason
        else GeminiIndependentJudgeV2(model=args.judge_model)
    )
    cases = sorted(build_cases(), key=lambda case: case["input"]["task_id"])
    candidates = list(CANDIDATES) if args.candidate == "both" else [args.candidate]
    existing = _existing_keys() if args.resume else set()
    total = len(cases) * len(candidates)
    completed_count = len(existing & {
        (case["input"]["task_id"], candidate)
        for case in cases
        for candidate in candidates
    })
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.resume and RESULTS_PATH.exists() else "w"
    with RESULTS_PATH.open(mode, encoding="utf-8") as handle:
        for case in cases:
            task_id = case["input"]["task_id"]
            for candidate_name in candidates:
                key = (task_id, candidate_name)
                if key in existing:
                    continue
                completed_count += 1
                print(
                    f"judge-v2 {completed_count}/{total}: {task_id} {candidate_name}",
                    flush=True,
                )
                try:
                    run_dir, raw = _latest_run(
                        Path(CANDIDATES[candidate_name]["root"]),
                        task_id,
                        candidate_name,
                    )
                    # Cheap invariant, expensive bug: a mislabelled run_dir
                    # silently scores the other agent's work under this name.
                    expected_root = PUBLISHED_ROOTS.get(candidate_name)
                    if candidate_name == "curify-web" and os.environ.get("CURIFY_RUNS_ROOT"):
                        expected_root = Path(os.environ["CURIFY_RUNS_ROOT"])
                    if expected_root is not None and expected_root.is_dir():
                        resolved = run_dir.resolve()
                        legacy = Path(CANDIDATES[candidate_name]["root"]).resolve()
                        if not (
                            resolved.is_relative_to(expected_root.resolve())
                            or resolved.is_relative_to(legacy)
                        ):
                            raise RuntimeError(
                                f"run_dir {resolved} does not belong to candidate "
                                f"{candidate_name!r} (expected under {expected_root})"
                            )
                    output = _normalized_output(candidate_name, case, run_dir, raw)
                    runtime = runtime_scores(case["input"], output, case["expected"])
                    benchmark = await benchmark_judge_v2_scores(
                        case["input"],
                        output,
                        case["expected"],
                        judge=judge,
                    )
                    record = {
                        "task_id": task_id,
                        "candidate_name": candidate_name,
                        "candidate_identity": CANDIDATES[candidate_name]["identity"],
                        "run_dir": str(run_dir),
                        "raw_outcome": raw.get("outcome"),
                        "latency_ms": raw.get("latency_ms"),
                        "artifact_count": sum(
                            not artifact.get("evidence_only")
                            for artifact in output["artifacts"]
                        ),
                        "judge_evidence_render_count": sum(
                            bool(artifact.get("evidence_only"))
                            for artifact in output["artifacts"]
                        ),
                        "loaded_asset_count": len(output["loaded_asset_ids"]),
                        "required_asset_count": case["expected"]["input_contract"]["asset_count"],
                        "runtime_scores": _score_dict(runtime),
                        "benchmark_scores": _score_dict(benchmark),
                        "error": None,
                    }
                except Exception as exc:
                    record = {
                        "task_id": task_id,
                        "candidate_name": candidate_name,
                        "candidate_identity": CANDIDATES[candidate_name]["identity"],
                        "error": f"{type(exc).__name__}: {str(exc)[:1000]}",
                    }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()


def _summarize() -> None:
    all_records = [
        json.loads(line)
        for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    latest_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in all_records:
        latest_by_key[(record["task_id"], record["candidate_name"])] = record
    records = list(latest_by_key.values())
    summary: dict[str, Any] = {
        "records": len(records),
        "raw_records_including_retries": len(all_records),
        "candidates": {},
    }
    for candidate_name in CANDIDATES:
        candidate_records = [
            record
            for record in records
            if record.get("candidate_name") == candidate_name and not record.get("error")
        ]
        fully_judged = [
            record
            for record in candidate_records
            if record.get("benchmark_scores", {})
            .get("independent_judge_available", {})
            .get("score")
            == 1
        ]
        weighted = [
            record["benchmark_scores"]["weighted_design_score"]["score"]
            for record in fully_judged
            if record.get("benchmark_scores", {})
            .get("weighted_design_score", {})
            .get("score")
            is not None
        ]
        totals = [
            record["benchmark_scores"]["benchmark_total_score"]["score"]
            for record in fully_judged
            if record.get("benchmark_scores", {})
            .get("benchmark_total_score", {})
            .get("score")
            is not None
        ]
        passes = sum(
            bool(
                record.get("benchmark_scores", {})
                .get("benchmark_case_pass", {})
                .get("score")
            )
            for record in fully_judged
        )
        latencies = [
            float(record["latency_ms"])
            for record in candidate_records
            if record.get("latency_ms") is not None
        ]
        summary["candidates"][candidate_name] = {
            "scored_cases": len(candidate_records),
            "independent_judge_completed_cases": len(fully_judged),
            "independent_judge_blocked_cases": len(candidate_records) - len(fully_judged),
            "errors": sum(
                record.get("candidate_name") == candidate_name and bool(record.get("error"))
                for record in records
            ),
            "weighted_design_mean": statistics.fmean(weighted) if weighted else None,
            "benchmark_total_mean": statistics.fmean(totals) if totals else None,
            "case_passes": passes,
            "median_latency_ms": statistics.median(latencies) if latencies else None,
        }
    # Refuse to publish a summary over structurally broken records. A summary
    # is the artifact people quote, so it is the last place a silent harness
    # bug should be allowed to survive.
    problems = validate_records([r for r in records if not r.get("error")])
    summary["structural_problems"] = problems
    if problems:
        print(f"\n!! {len(problems)} STRUCTURAL PROBLEM(S) — scores are NOT valid:")
        for problem in problems[:20]:
            print(f"   - {problem}")
        if len(problems) > 20:
            print(f"   ... and {len(problems) - 20} more")
        raise SystemExit(
            "Refusing to write a summary: fix the harness, then re-run. "
            "See validate_records() for why each check exists."
        )
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge-model", default="gemini-2.5-pro")
    parser.add_argument("--judge-unavailable-reason", default=None)
    parser.add_argument(
        "--candidate", choices=["both", *CANDIDATES], default="both"
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args))
    _summarize()
    print(f"wrote {RESULTS_PATH}")
    print(f"wrote {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
