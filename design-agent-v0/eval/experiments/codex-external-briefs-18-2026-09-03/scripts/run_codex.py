#!/usr/bin/env python3
"""Run independent Codex planning cases for the 18 external briefs."""

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
EXP = HERE.parent
EVAL = EXP.parents[1]
DATASET = EXP / "dataset" / "external-briefs.jsonl"
SCHEMA = EXP / "schemas" / "planner-output.schema.json"
RUNS = EXP / "runs"
INDEX = EXP / "run-index.jsonl"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING = "max"
LOCAL_HOME = str(Path.home())
INDEX_LOCK = threading.Lock()

STEP_GUIDE = """Closed workflow vocabulary:
- intake_brief: identify goals, audience, supplied inputs, constraints, success criteria and missing information
- research: investigate users, market, culture, competition or source material
- principles: establish strategic, learning or design principles that guide later choices
- process_model: define a repeatable production or operating workflow
- structure_spec: determine format, dimensions, hierarchy, content architecture or physical structure
- prototype_test: build and test a rough physical or interactive prototype
- explore_concepts: produce meaningfully different early directions
- select_direction: compare directions and obtain an explicit human/client choice
- refine: apply feedback to the selected direction while preserving accepted decisions
- identity_system: define logo, type, colour, graphic and governance rules as a system
- expand_assets: extend an approved system across a family of assets or SKUs
- learning_activities: turn learning principles into exercises or interactions
- dieline: create the packaging cutting/folding geometry
- production_file: prepare technically valid manufacturing/print-ready masters
- deliver: package, validate and hand off the agreed final assets"""

CLASS_GUIDE = """Allowed brief classes:
- brand_visual_exploration
- brand_campaign
- ecommerce_content
- education_content
- merchandise_family
- packaging_sku_series
- concept_to_production"""

DELIVERABLE_GUIDE = """Allowed deliverable concepts:
brand_strategy, logo_system, visual_identity, campaign_key_visual,
environmental_graphics, packaging_family, sku_differentiation,
structural_packaging, production_spec, mockups, ecommerce_content,
product_photography, education_content_system, merchandise_family,
brand_applications, dieline, prototype"""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def sanitize(text: str) -> str:
    return text.replace(LOCAL_HOME, "<LOCAL_HOME>")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prompt_for(case: dict[str, Any]) -> str:
    assets = case["input"]["input_assets"]
    if assets:
        legend = "\n".join(
            f"- attached image {index + 1}: asset_id={asset['asset_id']}; role={asset['role']}"
            for index, asset in enumerate(assets)
        )
        reference_instruction = f"""These are low-resolution published-outcome references, not source assets and not a style brief.
Use them only to ground your understanding of the visible deliverable family. Do not copy them and do not invent a hidden process.
Return exactly one reference_observations entry for each asset_id below:
{legend}"""
    else:
        reference_instruction = "No images are supplied. Return an empty reference_observations array."

    layer_instruction = (
        "Select an ordered workflow using only the closed vocabulary. A hidden gold sequence records one public case-study path; it is not claimed to be the only valid process."
        if case["layer"] == "case_study_workflow"
        else
        "There is deliberately no workflow-sequence gold for this portfolio layer. Propose a defensible workflow, classify the brief, and ground every image observation in visible pixels."
    )
    return f"""You are a design-agent workflow planner in a blinded external-distribution evaluation.
This is planning only. Do not browse, call tools, inspect unrelated files, generate/edit assets, or claim that work was executed.
Return only schema-constrained JSON and set execution_status to not_executed.

Visible user brief:
{case['input']['brief']}

Domain hint: {case['input']['domain']}
Reference policy: {case['input']['reference_policy']}
{reference_instruction}

{layer_instruction}
Choose the primary intent, brief class, ordered workflow steps, and deliverable concepts. Because the public brief is incomplete,
name material missing inputs and stop conditions. Assumptions must remain explicit and may not masquerade as source facts.

{CLASS_GUIDE}

{STEP_GUIDE}

{DELIVERABLE_GUIDE}
"""


def summarize_trace(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {"event_count": 0, "tool_call_count": 0, "tool_types": {}, "usage": None, "thread_id": None}
    tool_types: dict[str, int] = {}
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        result["event_count"] += 1
        if event.get("type") == "thread.started":
            result["thread_id"] = event.get("thread_id")
        if event.get("type") == "turn.completed":
            result["usage"] = event.get("usage")
        item = event.get("item") or {}
        item_type = item.get("type")
        if event.get("type") == "item.completed" and item_type not in {None, "agent_message", "reasoning"}:
            tool_types[item_type] = tool_types.get(item_type, 0) + 1
    result["tool_types"] = tool_types
    result["tool_call_count"] = sum(tool_types.values())
    return result


def validate(payload: Any, case: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["response is not an object"]
    errors = []
    required = {
        "primary_intent", "brief_class", "execution_status", "workflow_steps",
        "reference_observations", "deliverable_concepts", "missing_inputs",
        "assumptions", "stop_conditions", "rationale", "confidence",
    }
    missing = sorted(required - payload.keys())
    if missing:
        errors.append(f"missing keys: {missing}")
    steps = payload.get("workflow_steps") or []
    step_ids = [step.get("id") for step in steps if isinstance(step, dict)]
    if len(step_ids) != len(set(step_ids)):
        errors.append("workflow step ids must be unique")
    expected_assets = {item["asset_id"] for item in case["input"]["input_assets"]}
    observations = payload.get("reference_observations") or []
    observed_assets = {
        item.get("asset_id") for item in observations if isinstance(item, dict) and item.get("asset_id")
    }
    if observed_assets != expected_assets:
        errors.append(f"reference observations must match {sorted(expected_assets)} exactly")
    if payload.get("execution_status") != "not_executed":
        errors.append("execution_status must be not_executed")
    return errors


def completed(case_id: str) -> bool:
    for path in sorted((RUNS / case_id).glob("attempt-*/meta.json")):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("status") == "completed" and not meta.get("validation_errors"):
            return True
    return False


def next_attempt(case_id: str) -> Path:
    root = RUNS / case_id
    root.mkdir(parents=True, exist_ok=True)
    numbers = []
    for path in root.glob("attempt-*"):
        try:
            numbers.append(int(path.name.rsplit("-", 1)[1]))
        except ValueError:
            pass
    target = root / f"attempt-{max(numbers, default=0) + 1:02d}"
    target.mkdir()
    return target


def run_case(case: dict[str, Any], *, codex_bin: str, cli_version: str, model: str, reasoning: str, timeout: int) -> dict[str, Any]:
    attempt_dir = next_attempt(case["id"])
    prompt = prompt_for(case)
    (attempt_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    started_at = utc_now()
    start = time.monotonic()
    exit_code: int | None = None
    timed_out = False
    process_error = None
    stdout = ""
    stderr = ""
    payload = None
    parse_error = None
    attachment_manifest = []

    with tempfile.TemporaryDirectory(prefix="codex-external-brief-") as temp_name:
        workspace = Path(temp_name)
        attachments = []
        for asset in case["input"]["input_assets"]:
            source = EVAL / asset["path"]
            target = workspace / f"{asset['asset_id']}{source.suffix.lower()}"
            shutil.copyfile(source, target)
            data = target.read_bytes()
            if sha256_bytes(data) != asset["sha256"]:
                raise RuntimeError(f"input hash mismatch: {case['id']} {asset['asset_id']}")
            attachments.append(target)
            attachment_manifest.append({"asset_id": asset["asset_id"], "sha256": asset["sha256"], "bytes": len(data)})
        response_path = workspace / "response.json"
        cmd = [
            codex_bin, "exec", "--ephemeral", "--skip-git-repo-check",
            "--ignore-user-config", "--ignore-rules", "--color", "never",
            "-C", str(workspace), "-s", "read-only", "-m", model,
            "-c", f'model_reasoning_effort="{reasoning}"',
            "--output-schema", str(SCHEMA), "--json", "-o", str(response_path),
        ]
        for attachment in attachments:
            cmd.extend(["-i", str(attachment)])
        cmd.extend(["--", prompt])
        try:
            proc = subprocess.run(cmd, cwd=workspace, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, check=False)
            exit_code = proc.returncode
            stdout, stderr = proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
            stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
        except Exception as error:
            process_error = f"{type(error).__name__}: {error}"
        if response_path.exists():
            response_text = response_path.read_text(encoding="utf-8")
            (attempt_dir / "response.json").write_text(response_text, encoding="utf-8")
            try:
                payload = json.loads(response_text)
            except json.JSONDecodeError as error:
                parse_error = f"{type(error).__name__}: {error}"
        else:
            parse_error = "response.json not created"

    stdout, stderr = sanitize(stdout), sanitize(stderr)
    (attempt_dir / "trace.jsonl").write_text(stdout, encoding="utf-8")
    (attempt_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    (attempt_dir / "input-manifest.json").write_text(json.dumps(attachment_manifest, indent=2) + "\n", encoding="utf-8")
    validation_errors = validate(payload, case) if payload is not None else []
    status = "completed" if exit_code == 0 and not timed_out and process_error is None and parse_error is None and not validation_errors else ("timeout" if timed_out else "error")
    attempt_number = int(attempt_dir.name.rsplit("-", 1)[1])
    meta = {
        "id": case["id"],
        "layer": case["layer"],
        "attempt": attempt_number,
        "status": status,
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": time.monotonic() - start,
        "candidate": {"agent": "codex-cli", "cli_version": cli_version, "model": model, "reasoning_effort": reasoning, "sandbox": "read-only", "session_mode": "ephemeral"},
        "dataset_row_sha256": canonical_hash(case),
        "prompt_sha256": sha256_bytes(prompt.encode()),
        "input_assets": attachment_manifest,
        "exit_code": exit_code,
        "timeout": timed_out,
        "process_error": process_error,
        "parse_error": parse_error,
        "validation_errors": validation_errors,
        "trace": summarize_trace(stdout),
    }
    (attempt_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with INDEX_LOCK:
        with INDEX.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(meta, ensure_ascii=False, sort_keys=True) + "\n")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--allow-model-usage", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning", default=DEFAULT_REASONING)
    parser.add_argument("--timeout", type=int, default=420)
    parser.add_argument("--rerun", action="store_true")
    args = parser.parse_args()
    if not args.allow_model_usage:
        raise SystemExit("Refusing model calls without --allow-model-usage")
    cases = read_jsonl(DATASET)
    selected = cases if args.all else [case for case in cases if case["id"] in set(args.ids)]
    if not selected:
        raise SystemExit("Select --all or at least one valid id")
    if not args.rerun:
        selected = [case for case in selected if not completed(case["id"])]
    if not selected:
        print("all selected cases already have a valid completion")
        return 0
    codex_bin = shutil.which("codex")
    if not codex_bin:
        raise SystemExit("codex CLI not found")
    cli_version = subprocess.run([codex_bin, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(run_case, case, codex_bin=codex_bin, cli_version=cli_version, model=args.model, reasoning=args.reasoning, timeout=args.timeout): case
            for case in selected
        }
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            try:
                meta = future.result()
                print(f"{case['id']}\t{meta['status']}\t{meta['duration_seconds']:.2f}s")
                failures += meta["status"] != "completed"
            except Exception as error:
                failures += 1
                print(f"{case['id']}\trunner_error\t{type(error).__name__}: {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
