#!/usr/bin/env python3
"""Write the reproducibility manifest for Brief Bank v0.3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
FILES = {
    "dataset": HERE / "briefs.v0.3.jsonl",
    "initial_query_projection": HERE / "initial_queries.v0.3.jsonl",
    "schema": HERE / "brief.v0.3.schema.json",
    "builder": HERE / "build_v03.py",
    "validator": HERE / "validate_v03.py",
    "projection_builder": HERE / "export_initial_queries.py",
    "base_dataset": HERE / "briefs.v0.2.jsonl",
    "public_seed_index": EVAL / "reddit_briefs" / "reddit_brief_seeds_2026-08-30.jsonl",
    "v03_asset_manifest": EVAL / "assets" / "brief-bank-v0.3" / "manifest.jsonl",
    "v03_generation_log": EVAL / "assets" / "brief-bank-v0.3" / "generation.jsonl",
    "v03_mask_builder": EVAL / "assets" / "brief-bank-v0.3" / "build_masks.py",
    "v02_asset_manifest": EVAL / "assets" / "reference-pack-v0.2" / "manifest.jsonl",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> int:
    missing = [str(path) for path in FILES.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing freeze inputs: " + ", ".join(missing))
    manifest = {
        "schema_version": "brief-bank-freeze-v0.3",
        "frozen_at": "2026-09-04",
        "dataset_partition": {
            "core_v0_2_migrated_rows": 24,
            "public_corpus_grounded_external_rows": 11,
            "total_episodes": 35,
            "projected_context_condition_runs": 43,
        },
        "files": {
            name: {
                "path": str(path.relative_to(EVAL)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                **({"rows": rows(path)} if path.suffix == ".jsonl" else {}),
            }
            for name, path in FILES.items()
        },
        "lineage": {
            "core_business_scope_changed": False,
            "external_selection_rule": "record_type=case AND brief_readiness=ready_to_author",
            "external_seed_count": 11,
            "reference_material_records_imported_as_cases": 0,
        },
        "rights_and_claim_boundary": {
            "public_posts": "task/failure patterns only; stored as paraphrased seed references",
            "pixel_fixtures": "project_owned_test_fixture",
            "customer_data": False,
            "benchmark_status": "harness-ready with completed Codex baseline; no cross-Agent result is claimed",
        },
    }
    output = HERE / "freeze-manifest.v0.3.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output} sha256={sha256(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
