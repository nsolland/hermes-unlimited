import copy
import json
from pathlib import Path
import unittest

from scripts.reprobridge_harness_outcomes import empirical_outcomes

BASE = Path(__file__).resolve().parents[1] / "experiments" / "harness"


class ArchivedOutcomesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((BASE / "20261116_salad_a1_raw.json").read_text())
        cls.receipt = json.loads((BASE / "20261116_salad_a1_receipt.json").read_text())
        cls.tasks = (BASE / "tasks_v2.json").read_bytes()

    def test_recomputes_actual_observations_not_claimed_savings(self):
        r = empirical_outcomes(self.raw, self.receipt, self.tasks)
        self.assertEqual(r["arms"]["baseline"]["estimated_usd"], "0.00006876")
        self.assertEqual(r["arms"]["checker"]["estimated_usd"], "0.00010068")
        self.assertEqual(r["arms"]["baseline"]["correct"], 16)
        self.assertEqual(r["arms"]["checker"]["correct"], 16)
        self.assertFalse(r["meets_20pct_cost_and_quality_gate"])
        self.assertTrue(r["verified_provider_digest"])

    def test_corrupt_provider_result_is_rejected(self):
        raw = copy.deepcopy(self.raw)
        raw["results"][0]["estimated_usd"] = "-1"
        with self.assertRaisesRegex(ValueError, "provider result digest mismatch"):
            empirical_outcomes(raw, self.receipt, self.tasks)

    def test_corrupt_task_manifest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "task manifest digest mismatch"):
            empirical_outcomes(self.raw, self.receipt, self.tasks + b"\n")
