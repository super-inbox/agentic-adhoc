#!/usr/bin/env python3
"""Run one blinded, multimodal Codex ranking per 99designs contest."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT_DIR = HERE.parent
EVAL_DIR = EXPERIMENT_DIR.parents[1]
DATASET_PATH = EXPERIMENT_DIR / "dataset" / "contests.jsonl"
SCHEMA_PATH = EXPERIMENT_DIR / "schemas" / "rank-output.schema.json"
RUNS_DIR = EXPERIMENT_DIR / "runs"
RUN_INDEX = EXPERIMENT_DIR / "run-index.jsonl"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING = "max"
DEFAULT_TIMEOUT_SECONDS = 420
LOCAL_HOME = str(Path.home())


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sanitize_log(text: str) -> str:
    return text.replace(LOCAL_HOME, "<LOCAL_HOME>")


def load_cases() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def prompt_for(case: dict[str, Any]) -> str:
    option_ids = [option["option_id"] for option in case["input"]["options"]]
    legend = "\n".join(
        f"- Attached image {index + 1} = option {option_id}"
        for index, option_id in enumerate(option_ids)
    )
    return f"""You are the evaluator in a blinded, single-turn design-ranking benchmark.
Do not call tools, browse, inspect files, or create/edit assets. Judge only the attached pixels and
the visible brief excerpt. Do not use filenames, hidden metadata, presumed contest status, or
designer identity. The excerpt is known to be incomplete, so do not invent omitted requirements.

Rank every option from best to worst for this specific visible brief. Balance brief fit with visual
hierarchy, craft, legibility, distinctiveness, and production plausibility. `ranking` must contain
each of {json.dumps(option_ids)} exactly once, and `best_option` must equal its first item.
Set confidence from 0 to 1. Explain the decision concisely and state material uncertainty caused by
cropping, low resolution, or missing brief context.

Image legend (attachment order is authoritative):
{legend}

Visible public brief excerpt:
{case['input']['brief_text']}

Return only the schema-constrained JSON result.
"""


def summarize_trace(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "event_count": 0,
        "tool_call_count": 0,
        "tool_types": {},
        "usage": None,
        "thread_id": None,
    }
    tool_types: dict[str, int] = {}
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        out["event_count"] += 1
        if event.get("type") == "thread.started":
            out["thread_id"] = event.get("thread_id")
        if event.get("type") == "turn.completed":
            out["usage"] = event.get("usage")
        item = event.get("item") or {}
        item_type = item.get("type")
        if event.get("type") == "item.completed" and item_type not in {None, "agent_message", "reasoning"}:
            tool_types[item_type] = tool_types.get(item_type, 0) + 1
    out["tool_types"] = tool_types
    out["tool_call_count"] = sum(tool_types.values())
    return out


def validate_response(payload: Any, option_ids: list[str]) -> list[str]:
    if not isinstance(payload, dict):
        return ["response is not an object"]
    errors = []
    ranking = payload.get("ranking")
    if not isinstance(ranking, list):
        errors.append("ranking is not an array")
    elif len(ranking) != len(option_ids) or set(ranking) != set(option_ids) or len(set(ranking)) != len(ranking):
        errors.append(f"ranking must contain {option_ids} exactly once")
    if isinstance(ranking, list) and ranking and payload.get("best_option") != ranking[0]:
        errors.append("best_option must equal ranking[0]")
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        errors.append("confidence must be a number from 0 to 1")
    return errors


def completed_attempt(case_id: str) -> bool:
    case_dir = RUNS_DIR / case_id
    if not case_dir.exists():
        return False
    for meta_path in sorted(case_dir.glob("attempt-*/meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("status") == "completed" and not meta.get("validation_errors"):
            return True
    return False


def next_attempt_dir(case_id: str) -> Path:
    case_dir = RUNS_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    nums = []
    for path in case_dir.glob("attempt-*"):
        try:
            nums.append(int(path.name.split("-")[-1]))
        except ValueError:
            pass
    attempt = max(nums, default=0) + 1
    path = case_dir / f"attempt-{attempt:02d}"
    path.mkdir()
    return path


def run_case(
    case: dict[str, Any],
    *,
    codex_bin: str,
    cli_version: str,
    model: str,
    reasoning_effort: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    attempt_dir = next_attempt_dir(case["id"])
    prompt = prompt_for(case)
    (attempt_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    started_at = utc_now()
    started = time.monotonic()
    exit_code: int | None = None
    timeout = False
    process_error: str | None = None
    stdout = ""
    stderr = ""
    payload = None
    parse_error = None
    option_manifest = []
    with tempfile.TemporaryDirectory(prefix="codex-99designs-rank-") as temp_name:
        workspace = Path(temp_name)
        image_paths = []
        for option in case["input"]["options"]:
            source = EVAL_DIR / option["image_path"]
            suffix = source.suffix.lower() or ".png"
            target = workspace / f"option-{option['option_id']}{suffix}"
            shutil.copyfile(source, target)
            data = target.read_bytes()
            if sha256_bytes(data) != option["sha256"]:
                raise RuntimeError(f"input hash changed for {case['id']} option {option['option_id']}")
            image_paths.append(target)
            option_manifest.append(
                {
                    "option_id": option["option_id"],
                    "sha256": option["sha256"],
                    "byte_size": len(data),
                    "media_type": option["media_type"],
                }
            )
        temp_response = workspace / "response.json"
        cmd = [
            codex_bin,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--color",
            "never",
            "-C",
            str(workspace),
            "-s",
            "read-only",
            "-m",
            model,
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--output-schema",
            str(SCHEMA_PATH),
            "--json",
            "-o",
            str(temp_response),
        ]
        for image_path in image_paths:
            cmd.extend(["-i", str(image_path)])
        cmd.extend(["--", prompt])
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as error:
            timeout = True
            stdout = (error.stdout or b"").decode(errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
            stderr = (error.stderr or b"").decode(errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        except Exception as error:
            process_error = f"{type(error).__name__}: {error}"
        if temp_response.exists():
            response_text = temp_response.read_text(encoding="utf-8")
            (attempt_dir / "response.json").write_text(response_text, encoding="utf-8")
            try:
                payload = json.loads(response_text)
            except json.JSONDecodeError as error:
                parse_error = f"{type(error).__name__}: {error}"
        else:
            parse_error = "response.json not created"
    duration = time.monotonic() - started
    stdout = sanitize_log(stdout)
    stderr = sanitize_log(stderr)
    (attempt_dir / "trace.jsonl").write_text(stdout, encoding="utf-8")
    (attempt_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    option_ids = [option["option_id"] for option in case["input"]["options"]]
    validation_errors = validate_response(payload, option_ids) if payload is not None else []
    status = (
        "completed"
        if exit_code == 0 and not timeout and process_error is None and parse_error is None and not validation_errors
        else "failed"
    )
    trace_summary = summarize_trace(stdout)
    meta = {
        "case_id": case["id"],
        "attempt": int(attempt_dir.name.split("-")[-1]),
        "status": status,
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": round(duration, 3),
        "exit_code": exit_code,
        "timeout": timeout,
        "process_error": process_error,
        "parse_error": parse_error,
        "validation_errors": validation_errors,
        "candidate": {
            "agent": "codex-cli",
            "cli_version": cli_version,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "session_mode": "ephemeral",
            "sandbox": "read-only",
        },
        "dataset_sha256": sha256_bytes(DATASET_PATH.read_bytes()),
        "schema_sha256": sha256_bytes(SCHEMA_PATH.read_bytes()),
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "inputs": option_manifest,
        "trace": trace_summary,
    }
    (attempt_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--case", action="append", default=[])
    parser.add_argument("--allow-model-usage", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING)
    parser.add_argument("--rerun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_model_usage:
        raise SystemExit("Model execution disabled; pass --allow-model-usage to confirm scope.")
    if args.workers < 1 or args.workers > 4:
        raise SystemExit("--workers must be between 1 and 4")
    codex_bin = shutil.which("codex")
    if not codex_bin:
        raise SystemExit("codex CLI not found")
    cli_version = subprocess.run([codex_bin, "--version"], capture_output=True, text=True, check=False).stdout.strip()
    cases = load_cases()
    wanted = {case["id"] for case in cases} if args.all else set(args.case)
    unknown = wanted - {case["id"] for case in cases}
    if unknown:
        raise SystemExit(f"Unknown case ids: {sorted(unknown)}")
    selected = [case for case in cases if case["id"] in wanted]
    if not args.rerun:
        selected = [case for case in selected if not completed_attempt(case["id"])]
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"selected={len(selected)} workers={args.workers} model={args.model}/{args.reasoning_effort}", flush=True)
    if not selected:
        return 0
    lock = threading.Lock()
    failures = 0
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                run_case,
                case,
                codex_bin=codex_bin,
                cli_version=cli_version,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                timeout_seconds=args.timeout_seconds,
            ): case
            for case in selected
        }
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            try:
                meta = future.result()
            except Exception as error:
                meta = {
                    "case_id": case["id"],
                    "status": "runner_exception",
                    "process_error": f"{type(error).__name__}: {error}",
                }
            done += 1
            failures += meta.get("status") != "completed"
            with lock:
                with RUN_INDEX.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(meta, ensure_ascii=False) + "\n")
            print(
                f"[{done:02d}/{len(selected):02d}] {case['id']} {meta.get('status')} "
                f"{meta.get('duration_seconds', 0):.1f}s tools={meta.get('trace', {}).get('tool_call_count', '?')}",
                flush=True,
            )
    print(f"done={done} failures={failures}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
