from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analyze_results import load_results, summarize, wilson_interval
from summarize_pytest import properties, scenario_from_nodeid


class AnalysisTests(unittest.TestCase):
    def test_wilson_interval_contains_observed_rate(self) -> None:
        low, high = wilson_interval(8, 10)
        self.assertLess(low, 0.8)
        self.assertGreater(high, 0.8)
        self.assertGreaterEqual(low, 0)
        self.assertLessEqual(high, 1)

    def test_pytest_properties_supports_list_pairs(self) -> None:
        parsed = properties(
            {
                "user_properties": [
                    ["clean_test_case_id", "09_crashpod"],
                    ["actual_correctness_score", 1],
                ]
            }
        )
        self.assertEqual(parsed["clean_test_case_id"], "09_crashpod")
        self.assertEqual(parsed["actual_correctness_score"], 1)

    def test_scenario_falls_back_to_nodeid(self) -> None:
        nodeid = (
            "tests/llm/test_ask_holmes.py::"
            "test_ask_holmes[17_oom_kill-openai/qwen-plus-default]"
        )
        self.assertEqual(scenario_from_nodeid(nodeid), "17_oom_kill")

    def test_summary_groups_variant_and_scenario(self) -> None:
        data = pd.DataFrame(
            [
                {
                    "variant": "tool_agent",
                    "scenario_id": "09_crashpod",
                    "correctness": 1,
                    "holmes_duration_seconds": 2.0,
                    "duration_seconds": 2.5,
                    "total_tokens": 100,
                    "tool_calls": 3,
                    "outcome": "passed",
                },
                {
                    "variant": "tool_agent",
                    "scenario_id": "09_crashpod",
                    "correctness": 0,
                    "holmes_duration_seconds": 4.0,
                    "duration_seconds": 4.5,
                    "total_tokens": 200,
                    "tool_calls": 5,
                    "outcome": "failed",
                },
            ]
        )
        result = summarize(data).iloc[0]
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["latency_p50_s"], 3.0)
        self.assertEqual(result["tokens_median"], 150.0)
        self.assertEqual(result["setup_or_runtime_failures"], 1)

    def test_csv_field_order_keeps_variant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.csv"
            with output.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["run_id", "variant"])
                writer.writeheader()
                writer.writerow({"run_id": "r1", "variant": "tool_agent"})
            self.assertIn("r1,tool_agent", output.read_text(encoding="utf-8"))

    def test_loader_excludes_generated_summary(self) -> None:
        columns = {
            "variant": ["direct_llm"],
            "scenario_id": ["09_crashpod"],
            "correctness": [0],
            "duration_seconds": [1.0],
            "holmes_duration_seconds": [None],
            "tool_calls": [0],
            "total_tokens": [100],
            "outcome": ["passed"],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pd.DataFrame(columns).to_csv(root / "pilot.csv", index=False)
            pd.DataFrame(columns).to_csv(root / "summary_by_scenario.csv", index=False)
            loaded = load_results(root, include_pilot=True)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded.iloc[0]["source_file"], "pilot.csv")

    def test_loader_excludes_pilot_by_default(self) -> None:
        common = {
            "variant": "direct_llm",
            "scenario_id": "09_crashpod",
            "correctness": 0,
            "duration_seconds": 1.0,
            "holmes_duration_seconds": None,
            "tool_calls": 0,
            "total_tokens": 100,
            "outcome": "passed",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pd.DataFrame([{**common, "phase": "pilot"}]).to_csv(
                root / "pilot.csv", index=False
            )
            pd.DataFrame([{**common, "phase": "formal"}]).to_csv(
                root / "formal.csv", index=False
            )
            loaded = load_results(root)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded.iloc[0]["phase"], "formal")


if __name__ == "__main__":
    unittest.main()
