#!/usr/bin/env python3
"""Counterfactual control: stale self-claims must not rescue unchanged pixels."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from google import genai

from evidence_v03 import EXP, DESIGN_AGENT_ROOT, input_manifest, selected_runs
from judge_v03 import MODEL, judge


HERE = Path(__file__).resolve().parent
CONTROL_ID = "DAB-L3-RDT-005"


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required")
    selected = [row for row in selected_runs() if row[1]["id"] == CONTROL_ID]
    if len(selected) != 1:
        raise RuntimeError(f"expected one completed {CONTROL_ID} run, got {len(selected)}")
    run, brief, result, query = selected[0]
    actual_rows = {
        row["run"]: row
        for row in (
            json.loads(line)
            for line in (HERE / "rubric-v03-judged.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    actual = actual_rows.get(str(run.relative_to(EXP)))
    if not actual or actual.get("error") is not None:
        raise RuntimeError("positive control has not been judged")

    bound = {item["input_id"]: item for item in input_manifest(run)}
    source = DESIGN_AGENT_ROOT / bound["edit-target"]["source_path"]
    with tempfile.TemporaryDirectory(prefix="judge-v03-negative-") as temporary:
        control = Path(temporary)
        (control / "outputs" / "v0").mkdir(parents=True)
        shutil.copy2(run / "input-manifest.json", control / "input-manifest.json")
        shutil.copy2(run / "trajectory.jsonl", control / "trajectory.jsonl")
        # Retain stale candidate-authored claims but replace every visible result
        # with the byte-identical, unedited source.
        for name in ("verification.json", "change_set.json"):
            candidate = run / "outputs" / "v0" / name
            if candidate.is_file():
                shutil.copy2(candidate, control / "outputs" / "v0" / name)
        project_state = run / "outputs" / "project-state.json"
        if project_state.is_file():
            shutil.copy2(project_state, control / "outputs" / "project-state.json")
        shutil.copy2(source, control / "outputs" / "v0" / "edited-cartoon.png")
        shutil.copy2(source, control / "outputs" / "v0" / "preview.png")
        negative = judge(genai.Client(api_key=key), control, brief, result, query)

    actual_scores = actual.get("scores") or {}
    negative_scores = negative.get("scores") or {}
    negative_gates = negative.get("hard_gates") or []
    passed = (
        (actual_scores.get("edit_fidelity") or {}).get("score", -1) >= 4
        and (negative_scores.get("edit_fidelity") or {}).get("score", 6) <= 2
        and any(gate.get("verdict") != "MET" for gate in negative_gates)
    )
    record = {
        "schema_version": "brief-bank-v0.3-judge-control/1.0",
        "judge_model": MODEL,
        "positive_run": str(run.relative_to(EXP)),
        "control": "replace edited result and preview with byte-identical unedited source while retaining candidate-authored claims",
        "positive_edit_fidelity": (actual_scores.get("edit_fidelity") or {}).get("score"),
        "negative_edit_fidelity": (negative_scores.get("edit_fidelity") or {}).get("score"),
        "negative_hard_gates": negative_gates,
        "passed": passed,
    }
    (HERE / "judge-validation-v03.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
