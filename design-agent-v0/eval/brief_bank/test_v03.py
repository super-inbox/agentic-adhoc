from __future__ import annotations

import json
from pathlib import Path
import unittest

import build_v03
import validate_v03


HERE = Path(__file__).resolve().parent


class BriefBankV03Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = validate_v03.read_jsonl(HERE / "briefs.v0.3.jsonl")

    def test_partition_counts(self) -> None:
        core = [row for row in self.rows if row["revision"]["base_dataset"] == "briefs.v0.2.jsonl"]
        external = [row for row in self.rows if row["revision"]["base_dataset"] == "reddit_brief_seeds_2026-08-30.jsonl"]
        self.assertEqual((len(self.rows), len(core), len(external)), (35, 24, 11))

    def test_external_selection_is_exact(self) -> None:
        seeds = validate_v03.read_jsonl(validate_v03.SEEDS)
        ready = {row["id"] for row in seeds if row.get("record_type") == "case" and row.get("brief_readiness") == "ready_to_author"}
        selected = {row["revision"]["base_brief_id"] for row in build_v03.external_rows()}
        self.assertEqual(selected, ready)

    def test_v03_semantic_validator(self) -> None:
        errors: list[str] = []
        assets = validate_v03.asset_catalog(errors)
        for row in self.rows:
            validate_v03.validate_row(row, assets, errors)
        self.assertEqual(errors, [])

    def test_projection_is_43_rows(self) -> None:
        path = HERE / "initial_queries.v0.3.jsonl"
        projected = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(projected), 43)
        self.assertTrue(all(row["layer"] == "l3_l4_brief_initial_query_v0.3" for row in projected))


if __name__ == "__main__":
    unittest.main()
