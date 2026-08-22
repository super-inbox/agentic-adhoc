#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validate_briefs  # noqa: E402
import export_initial_queries  # noqa: E402
import build_v02  # noqa: E402


class BriefBankV01RegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = validate_briefs.load_jsonl(validate_briefs.V01_BRIEFS)

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


class BriefBankV02ValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = validate_briefs.load_jsonl(validate_briefs.DEFAULT_BRIEFS)

    def test_published_dataset_is_valid(self) -> None:
        errors, summary = validate_briefs.validate_dataset(copy.deepcopy(self.rows))
        self.assertEqual(errors, [])
        self.assertEqual(summary["schema_version"], "0.2")
        self.assertEqual(summary["rows"], 24)
        self.assertEqual(summary["expanded_runs"], 32)
        self.assertEqual(summary["deep_multi_turn_cases"], 8)
        self.assertEqual(summary["creative_exploration_cases"], 6)
        self.assertEqual(summary["structured_edit_cases"], 6)
        self.assertEqual(summary["context_ablation_cases"], 4)

    def test_checked_in_v02_dataset_is_reproducible(self) -> None:
        base = build_v02.load_rows(build_v02.DEFAULT_INPUT)
        expected = build_v02.build(base)
        actual = build_v02.load_rows(build_v02.DEFAULT_OUTPUT)
        self.assertEqual(actual, expected)

    def test_checked_in_v02_projection_is_current(self) -> None:
        actual = export_initial_queries.load_rows(HERE / "initial_queries.v0.2.jsonl")
        expected = export_initial_queries.project_rows(
            self.rows, episode_source="brief_bank/briefs.v0.2.jsonl"
        )
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 32)
        self.assertEqual(len({row["id"] for row in actual}), 32)

    def test_future_feedback_is_not_leaked_into_initial_projection(self) -> None:
        projected = export_initial_queries.project_rows(self.rows)
        rendered = "\n".join(json.dumps(row, ensure_ascii=False) for row in projected)
        for row in self.rows:
            for turn in row["feedback"]:
                self.assertNotIn(turn["message"], rendered)

    def test_deep_revision_cases_cross_sessions_and_resume_versions(self) -> None:
        deep = {
            row["id"]: row
            for row in self.rows
            if "multi_turn_revision" in row["capability_tags"]
        }
        self.assertEqual(set(deep), validate_briefs.DEEP_REVISION_IDS)
        for row in deep.values():
            self.assertEqual(len(row["feedback"]), 3)
            self.assertGreaterEqual(len({turn["session_id"] for turn in row["feedback"]}), 2)
            self.assertTrue(any(turn.get("resume_from_version") for turn in row["feedback"]))
            self.assertEqual(row["project_state"]["resume_policy"], "checkpoint_and_version")

    def test_exploration_cases_use_diverge_cluster_select_converge(self) -> None:
        expected = ["understand", "diverge", "cluster", "select", "converge", "deliver"]
        exploration = {
            row["id"]: row
            for row in self.rows
            if "creative_exploration" in row["capability_tags"]
        }
        self.assertEqual(set(exploration), validate_briefs.EXPLORATION_IDS)
        for row in exploration.values():
            self.assertEqual(
                [item["checkpoint"] for item in row["expected_workflow"]], expected
            )
            self.assertIn("8–12", row["initial_query"])
            self.assertTrue(any(item["id"] == "exploration-map" for item in row["deliverables"]))

    def test_structured_edit_cases_require_object_level_evidence(self) -> None:
        structured = {
            row["id"]: row
            for row in self.rows
            if "structured_editing" in row["capability_tags"]
        }
        self.assertEqual(set(structured), validate_briefs.STRUCTURED_EDIT_IDS)
        for row in structured.values():
            self.assertEqual(
                {item["name"] for item in row["structured_artifacts"]},
                validate_briefs.STRUCTURED_ARTIFACT_NAMES,
            )
            self.assertTrue(row["edit_parameters"])

    def test_context_ablation_only_removes_optional_visual_inputs(self) -> None:
        ablations = {
            row["id"]: row
            for row in self.rows
            if "context_ablation" in row["capability_tags"]
        }
        self.assertEqual(set(ablations), validate_briefs.CONTEXT_ABLATION_IDS)
        for row in ablations.values():
            conditions = {item["id"]: item for item in row["context_conditions"]}
            self.assertEqual(set(conditions), validate_briefs.CONTEXT_CONDITIONS)
            provided = {
                item["id"] for item in row["inputs"] if item["availability"] == "provided"
            }
            optional = {
                item["input_id"]
                for item in row["reference_contract"]
                if item["optional_for_zero_shot"]
            }
            self.assertTrue(optional)
            self.assertEqual(set(conditions["zero_shot"]["include_input_ids"]), provided - optional)
            self.assertEqual(set(conditions["reference_grounded"]["include_input_ids"]), provided)
            self.assertTrue(conditions["personalized"]["include_preference_memory"])

    def test_reference_contract_covers_every_provided_pixel_asset(self) -> None:
        for row in self.rows:
            expected = {
                item["id"]
                for item in row["inputs"]
                if item["availability"] == "provided" and item.get("asset_id")
            }
            actual = {item["input_id"] for item in row["reference_contract"]}
            self.assertEqual(actual, expected)

    def test_invalid_zero_shot_omission_is_rejected(self) -> None:
        rows = copy.deepcopy(self.rows)
        case = next(row for row in rows if row["id"] == "DAB-L4-RTO-001")
        condition = next(item for item in case["context_conditions"] if item["id"] == "zero_shot")
        condition["include_input_ids"].remove("product")
        errors, _ = validate_briefs.validate_dataset(rows)
        self.assertTrue(any("zero_shot may omit only optional" in error for error in errors))

    def test_schema_files_parse_and_target_the_expected_versions(self) -> None:
        v01 = json.loads((HERE / "brief.schema.json").read_text(encoding="utf-8"))
        v02 = json.loads((HERE / "brief.v0.2.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(v01["properties"]["schema_version"]["const"], "0.1")
        self.assertEqual(v02["properties"]["schema_version"]["const"], "0.2")


if __name__ == "__main__":
    unittest.main()
