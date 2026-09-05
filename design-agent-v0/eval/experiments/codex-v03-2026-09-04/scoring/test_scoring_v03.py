#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest

from evidence_v03 import (
    BRIEFS,
    EXP,
    QUERIES,
    input_manifest,
    masked_edit_facts,
    read_jsonl,
    selected_runs,
    sha256,
    structured_artifact_facts,
)
from summarize_v03 import build_core_rows


class ScoringContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.briefs = {row["id"]: row for row in read_jsonl(BRIEFS)}
        cls.queries = {row["id"]: row for row in read_jsonl(QUERIES)}

    def test_dataset_shape(self):
        self.assertEqual(len(self.briefs), 35)
        self.assertEqual(len(self.queries), 43)
        self.assertEqual(sum("-RDT-" in key for key in self.queries), 11)

    def test_core_carry_forward_is_semantically_identical(self):
        rows, carry = build_core_rows(self.briefs, self.queries)
        self.assertEqual(len(rows), 32)
        self.assertTrue(carry["lineage_validation"]["validated"])

    def test_selected_runs_are_unique_and_hash_consistent(self):
        rows = selected_runs()
        ids = [query["id"] for _, _, _, query in rows]
        self.assertEqual(len(ids), len(set(ids)))
        for run, _, result, query in rows:
            self.assertEqual(result["outcome"], "completed")
            self.assertEqual(result["query_id"], query["id"])
            for item in input_manifest(run):
                self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            facts = structured_artifact_facts(run, query)
            self.assertIn("trajectory.jsonl", facts)
            self.assertTrue(facts["trajectory.jsonl"])

    def test_mask_metrics_are_evaluator_computed(self):
        for run, brief, _, _ in selected_runs():
            facts = masked_edit_facts(run, brief["id"])
            if brief["id"] not in {"DAB-L3-RDT-005", "DAB-L3-RDT-006"}:
                self.assertIsNone(facts)
                continue
            self.assertIsInstance(facts, dict)
            self.assertIn("outside_mask_changed_pixels", facts)
            self.assertGreaterEqual(facts["outside_mask_changed_pixels"], 0)
            self.assertGreater(facts["inside_mask_pixels"], 0)

    def test_judge_rows_match_completed_run_hashes(self):
        path = EXP / "scoring" / "rubric-v03-judged.jsonl"
        if not path.exists():
            self.skipTest("judge has not run")
        completed = {str(run.relative_to(EXP)) for run, _, _, _ in selected_runs()}
        for row in read_jsonl(path):
            self.assertIn(row["run"], completed)
            if row.get("error") is None:
                expected = self.briefs[row["brief_id"]]["rubric"]["checkpoint_weights"]
                self.assertEqual(set(row["scores"]), set(expected))
                self.assertEqual(
                    [gate["gate"] for gate in row["hard_gates"]],
                    self.briefs[row["brief_id"]]["rubric"]["hard_gates"],
                )


if __name__ == "__main__":
    unittest.main()
