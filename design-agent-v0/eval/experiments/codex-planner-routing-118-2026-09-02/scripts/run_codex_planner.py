#!/usr/bin/env python3
"""Run 118 independent Codex planner-only routing cases.

Gold fields are loaded only to enumerate cases; prompt_for deliberately exposes
only query text, language, reference presence, and input roles.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Any


HERE = Path(__file__).resolve().parent
EXPERIMENT_DIR = HERE.parent
EVAL_DIR = EXPERIMENT_DIR.parents[1]
DATASET_PATH = EVAL_DIR / "queries.jsonl"
SCHEMA_PATH = EXPERIMENT_DIR / "schemas" / "planner-output.schema.json"
RUNS_DIR = EXPERIMENT_DIR / "runs"
RUN_INDEX = EXPERIMENT_DIR / "run-index.jsonl"

DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING = "max"
DEFAULT_TIMEOUT_SECONDS = 300
LOCAL_HOME = str(Path.home())

ROUTE_INTENT_GUIDE = """Allowed content intents:
- ecommerce: commercial product/brand marketing and sales assets
- merch: merchandise, cultural products, packaging, apparel, or physical-product graphics
- education: explanatory, instructional, knowledge, or infographic content
- lifestyle: editorial, travel, personal-style, or lifestyle storytelling"""

AGENT_ROUTE_GUIDE = """Allowed top-level routes:
- image_edit_variants: modify a supplied image while preserving it as the source
- design_vote: compare/rank supplied design options and produce a decision
- virtual_tryon: place supplied garment/product references on a supplied person
- factory_export: make print/manufacturing-ready production files
- creative_explore: a broad but meaningful design brief that needs directions before production
- ask: contentless request that cannot be planned without clarification"""

TEMPLATE_IDS = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["properties"][
    "template_candidates"
]["items"]["enum"]


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


def input_roles(case: dict[str, Any]) -> list[str]:
    return [item.get("role", "unspecified") for item in case.get("input_assets", [])]


def prompt_for(case: dict[str, Any]) -> str:
    common = f"""You are the routing planner for a design agent evaluation.
This is planning and routing only. Do not call tools, browse, inspect files, or create/edit assets.
Return only the schema-constrained JSON result.

Evaluate one independent request using only the user request and input availability below.
User request: {case['query']}
Language: {case.get('language', 'unknown')}
Reference input available: {str(bool(case.get('has_reference'))).lower()}
Input roles: {json.dumps(input_roles(case), ensure_ascii=False)}
"""
    if case["layer"] == "routing_benchmark":
        catalog = "\n".join(f"- {item}" for item in TEMPLATE_IDS)
        return common + f"""
Benchmark layer: content-intent and template routing.
Set selected_route to template_retrieval. Choose one to three route_intents in priority order.
Choose up to three template_candidates in best-first order from the catalog. Return an empty
template_candidates list only when no catalog item is a defensible fit. Do not invent IDs.
needs_clarification may be true for an underspecified request, but still make the best routing decision.

{ROUTE_INTENT_GUIDE}

Available template catalog:
{catalog}

The plan must describe only future stages; do not execute them. Keep the rationale concise.
"""
    return common + f"""
Benchmark layer: top-level agent routing.
Choose exactly one selected_route from the route definitions below. Leave route_intents and
template_candidates empty because this layer does not score template retrieval. Set
needs_clarification true exactly when selected_route is ask.

{AGENT_ROUTE_GUIDE}

The plan must describe only future stages; do not execute them. Keep the rationale concise.
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
        if event.get("type") == "item.completed" and item_type not in {
            None,
            "agent_message",
            "reasoning",
        }:
            tool_types[item_type] = tool_types.get(item_type, 0) + 1
    out["tool_types"] = tool_types
    out["tool_call_count"] = sum(tool_types.values())
    return out


def basic_validate(payload: Any, case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["response is not an object"]
    required = {
        "selected_route",
        "route_intents",
        "template_candidates",
        "needs_clarification",
        "plan",
        "rationale",
    }
    missing = sorted(required - payload.keys())
    if missing:
        errors.append(f"missing keys: {missing}")
    if case["layer"] == "agent_route":
        if payload.get("route_intents") != []:
            errors.append("agent_route must leave route_intents empty")
        if payload.get("template_candidates") != []:
            errors.append("agent_route must leave template_candidates empty")
    if case["layer"] == "routing_benchmark" and payload.get("selected_route") != "template_retrieval":
        errors.append("routing_benchmark selected_route must be template_retrieval")
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
    path.mkdir(parents=False)
    return path


def run_case(
    case: dict[str, Any],
    *,
    codex_bin: str,
    model: str,
    reasoning_effort: str,
    timeout_seconds: int,
    cli_version: str,
) -> dict[str, Any]:
    attempt_dir = next_attempt_dir(case["id"])
    workspace = attempt_dir / "workspace"
    workspace.mkdir()
    prompt = prompt_for(case)
    (attempt_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    final_path = attempt_dir / "response.json"
    started_at = utc_now()
    started = time.monotonic()
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
        str(final_path),
        "--",
        prompt,
    ]
    exit_code: int | None = None
    timeout = False
    process_error: str | None = None
    stdout = ""
    stderr = ""
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
    except Exception as error:  # preserve unexpected runner failures as evidence
        process_error = f"{type(error).__name__}: {error}"
    duration = time.monotonic() - started
    stdout = sanitize_log(stdout)
    stderr = sanitize_log(stderr)
    (attempt_dir / "trace.jsonl").write_text(stdout, encoding="utf-8")
    (attempt_dir / "stderr.txt").write_text(stderr, encoding="utf-8")

    payload = None
    parse_error = None
    if final_path.exists():
        try:
            payload = json.loads(final_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            parse_error = f"{type(error).__name__}: {error}"
    else:
        parse_error = "response.json not created"
    validation_errors = basic_validate(payload, case) if payload is not None else []
    status = (
        "completed"
        if exit_code == 0 and not timeout and process_error is None and parse_error is None and not validation_errors
        else "failed"
    )
    trace_summary = summarize_trace(stdout)
    meta = {
        "case_id": case["id"],
        "layer": case["layer"],
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
        "trace": trace_summary,
    }
    (attempt_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--case", action="append", default=[])
    parser.add_argument("--allow-model-usage", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING)
    parser.add_argument("--rerun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_model_usage:
        raise SystemExit("Model execution disabled; pass --allow-model-usage to confirm scope.")
    if args.workers < 1 or args.workers > 8:
        raise SystemExit("--workers must be between 1 and 8")
    codex_bin = shutil.which("codex")
    if not codex_bin:
        raise SystemExit("codex CLI not found")
    version = subprocess.run(
        [codex_bin, "--version"], capture_output=True, text=True, check=False
    ).stdout.strip()
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
    write_lock = threading.Lock()
    done = 0
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                run_case,
                case,
                codex_bin=codex_bin,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                timeout_seconds=args.timeout_seconds,
                cli_version=version,
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
                    "layer": case["layer"],
                    "status": "runner_exception",
                    "process_error": f"{type(error).__name__}: {error}",
                }
            done += 1
            failures += meta.get("status") != "completed"
            with write_lock:
                with RUN_INDEX.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(meta, ensure_ascii=False) + "\n")
            print(
                f"[{done:03d}/{len(selected):03d}] {case['id']} {meta.get('status')} "
                f"{meta.get('duration_seconds', 0):.1f}s tools={meta.get('trace', {}).get('tool_call_count', '?')}",
                flush=True,
            )
    print(f"done={done} failures={failures}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
