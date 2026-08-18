"""Loader shim — the published branch imports this but does not contain it.

run_full_comparison.py does `from dataset_builder import build_cases` and only
uses `case["input"]["task_id"]`, while the committed dataset.jsonl rows already
carry input/expected/metadata/tags (Braintrust dataset shape). So this reads the
committed dataset rather than reconstructing anything: the scoring contract
(success_criteria, negative_constraints, deliverable_contract, dimension_criteria)
comes from the file, not from here.
"""
from __future__ import annotations
import json, os
from pathlib import Path

HERE = Path(__file__).resolve().parent

def build_cases(dataset_path: str | os.PathLike | None = None) -> list[dict]:
    p = Path(dataset_path) if dataset_path else (
        HERE / "dataset.jsonl")
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
