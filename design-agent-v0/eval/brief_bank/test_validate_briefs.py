#!/usr/bin/env python3

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validate_briefs  # noqa: E402
import export_initial_queries  # noqa: E402


class BriefBankValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = validate_briefs.load_jsonl(validate_briefs.DEFAULT_BRIEFS)

    def test_published_dataset_is_valid(self) -> None:
        errors, summary = validate_briefs.validate_dataset(copy.deepcopy(self.rows))
        self.assertEqual(errors, [])
        self.assertEqual(summary["rows"], 24)
        self.assertEqual(summary["messy_cases"], 9)

    def test_l4_feedback_is_required(self) -> None:
        rows = copy.deepcopy(self.rows)
        case = next(row for row in rows if row["level"] == "L4")
        case["feedback"] = []
        errors, _ = validate_briefs.validate_dataset(rows)
        self.assertTrue(any("L4 needs at least one feedback turn" in error for error in errors))

    def test_unknown_asset_is_rejected(self) -> None:
        rows = copy.deepcopy(self.rows)
        item = next(
            item
            for row in rows
            for item in row["inputs"]
            if item.get("asset_id")
        )
        item["asset_id"] = "not-in-reference-pack"
        errors, _ = validate_briefs.validate_dataset(rows)
        self.assertTrue(any("unknown asset_id not-in-reference-pack" in error for error in errors))

    def test_rubric_weights_must_sum_to_one(self) -> None:
        rows = copy.deepcopy(self.rows)
        rows[0]["rubric"]["checkpoint_weights"]["efficiency"] = 0.5
        errors, _ = validate_briefs.validate_dataset(rows)
        self.assertTrue(any("weights sum to" in error for error in errors))

    def test_checked_in_query_projection_is_current(self) -> None:
        actual = export_initial_queries.load_rows(HERE / "initial_queries.v0.1.jsonl")
        expected = [export_initial_queries.project(row) for row in self.rows]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
