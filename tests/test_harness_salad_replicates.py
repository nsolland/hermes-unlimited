import copy
import unittest
from pathlib import Path

from scripts.harness_salad_replicates import BASE, TASKS, evaluate, read_round


class SaladReplicationAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rounds = [
            read_round(label, BASE / f"20261116_salad_{label}_raw.json",
                       BASE / f"20261116_salad_{label}_receipt.json")
            for label in ("a1", "b2", "c2")
        ]

    def test_all_three_replicas_have_independent_valid_receipts(self):
        report = evaluate(self.rounds)
        self.assertEqual(report["actual_model_requests"], 120)
        self.assertEqual(report["unique_tasks"], 20)
        self.assertEqual(report["task_order_seeds"], [1116, 1117, 1118])
        self.assertEqual(report["by_arm"]["baseline"]["correct"], 48)
        self.assertEqual(report["by_arm"]["checker"]["correct"], 46)
        self.assertAlmostEqual(report["checker_minus_baseline_correct_fraction"], -0.0333, places=4)
        self.assertLess(report["task_cluster_bootstrap_95_percentile_interval"][0], 0)
        self.assertGreater(report["task_cluster_bootstrap_95_percentile_interval"][1], 0)
        self.assertTrue(all(x["stop_verified"] for x in report["source_rounds"]))

    def test_repeated_order_seed_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Duplicate task-order seeds"):
            evaluate([self.rounds[0], self.rounds[0]])

    def test_tampered_input_is_rejected_before_analysis(self):
        from scripts.harness_salad_verify import verify
        altered = copy.deepcopy(self.rounds[0]["data"])
        altered["results"][0]["answer_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify(altered, self.rounds[0]["receipt"], TASKS)


if __name__ == "__main__":
    unittest.main()
