#!/usr/bin/env python3
"""Write a content-addressed, secret-free v0.3 experiment freeze manifest."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EVAL = EXP.parent.parent
ROOT = EVAL.parent.parent


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def file_record(path: Path) -> dict:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def jsonl_rows(path: Path) -> int:
    return sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines())


def python_constant(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise RuntimeError(f"constant {name} not found in {path}")


def candidate_prompt_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    match = re.search(r"function initialPrompt\([\s\S]+?\n}\n\nfunction feedbackPrompt\([\s\S]+?\n}\n", source)
    if not match:
        raise RuntimeError("candidate prompt source block not found")
    return match.group(0)


def package_version(python: str, package: str, pythonpath: Path) -> str | None:
    command = [
        python,
        "-c",
        f"import importlib.metadata as m; print(m.version({package!r}))",
    ]
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(pythonpath)},
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    runner = EXP / "scripts" / "run_codex_v03.mjs"
    judge = EXP / "scoring" / "judge_v03.py"
    scoring_files = [
        EXP / "scoring" / "evidence_v03.py",
        judge,
        EXP / "scoring" / "summarize_v03.py",
        EXP / "scoring" / "validate_judge_v03.py",
        EXP / "scoring" / "test_scoring_v03.py",
        EXP / "scoring" / "requirements-judge.txt",
    ]
    datasets = [
        EVAL / "brief_bank" / "briefs.v0.3.jsonl",
        EVAL / "brief_bank" / "initial_queries.v0.3.jsonl",
        EVAL / "brief_bank" / "brief.v0.3.schema.json",
        EVAL / "brief_bank" / "freeze-manifest.v0.3.json",
        EVAL / "assets" / "reference-pack-v0.2" / "manifest.jsonl",
        EVAL / "assets" / "brief-bank-v0.3" / "manifest.jsonl",
    ]
    outputs = [
        EXP / "run-index.jsonl",
        EXP / "scoring" / "rubric-v03-judged.jsonl",
        EXP / "scoring" / "judge-validation-v03.json",
        EXP / "scoring" / "carry-forward-v02.json",
        EXP / "scoring" / "summary-v03.json",
        EXP / "RESULTS.md",
    ]
    missing = [str(path) for path in datasets + scoring_files + outputs + [runner] if not path.is_file()]
    if missing:
        raise RuntimeError("cannot freeze; missing files: " + ", ".join(missing))

    selected_results = {}
    for result_path in sorted((EXP / "runs").rglob("result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("outcome") != "completed" or result.get("primary_eligible") is False:
            continue
        condition_id = result.get("query_id")
        stamp = str(result.get("started_at") or result_path.parent.name)
        if condition_id not in selected_results or stamp > selected_results[condition_id][0]:
            selected_results[condition_id] = (stamp, result_path)
    run_results = [
        {
            "condition_id": condition_id,
            "path": str(result_path.relative_to(ROOT)),
            "sha256": digest(result_path),
        }
        for condition_id, (_, result_path) in sorted(selected_results.items())
    ]
    candidate_prompt = candidate_prompt_source(runner)
    judge_prompt = python_constant(judge, "PROMPT")
    bundled_python = sys.executable
    private_deps = EXP / ".private" / "judge-python"
    manifest = {
        "schema_version": "codex.brief-bank-v0.3-freeze/1.0",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "candidate": {
            "agent": "Codex CLI",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "max",
            "service_tier": "default",
            "session_mode": "persisted-thread-resume",
            "cli_version": subprocess.run(["codex", "--version"], text=True, capture_output=True, check=True).stdout.strip(),
        },
        "judge": {
            "model": "gemini-2.5-pro",
            "temperature": 0,
            "judge_version": "v0.3-artifact-grounded-1",
            "package_versions": {
                "google-genai": package_version(bundled_python, "google-genai", private_deps),
                "pypdf": package_version(bundled_python, "pypdf", private_deps),
                "Pillow": package_version(bundled_python, "Pillow", private_deps),
            },
        },
        "prompt_hashes": {
            "candidate_prompt_source_sha256": hashlib.sha256(candidate_prompt.encode()).hexdigest(),
            "judge_prompt_template_sha256": hashlib.sha256(judge_prompt.encode()).hexdigest(),
        },
        "dataset_files": [
            {**file_record(path), "rows": jsonl_rows(path) if path.suffix == ".jsonl" else None}
            for path in datasets
        ],
        "runner": file_record(runner),
        "freezer": file_record(Path(__file__).resolve()),
        "scorers": [file_record(path) for path in scoring_files],
        "result_files": [file_record(path) for path in outputs],
        "new_completed_run_results": run_results,
        "coverage": {
            "core_conditions_carried_forward": 32,
            "external_conditions_newly_executed": len(run_results),
            "total_conditions": 32 + len(run_results),
        },
        "secrets_included": False,
    }
    destination = EXP / "freeze-manifest.json"
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {destination.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
