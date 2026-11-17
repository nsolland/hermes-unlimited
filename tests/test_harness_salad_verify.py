import copy
import hashlib
import json
import unittest
from pathlib import Path

from scripts.harness_salad_verify import verify

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "experiments" / "harness"


class SaladEvidenceVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((BASE / "20261116_salad_a1_raw.json").read_text())
        cls.receipt = json.loads((BASE / "20261116_salad_a1_receipt.json").read_text())
        cls.tasks = (BASE / "tasks_v2.json").read_bytes()

    def test_recompute_all_40_oracles(self):
        summary = verify(self.raw, self.receipt, self.tasks)
        self.assertEqual(summary["by_arm"]["baseline"]["correct"], 16)
        self.assertEqual(summary["by_arm"]["checker"]["correct"], 16)
        self.assertEqual(summary["paired_exact_mcnemar_p_exploratory"], 1)
        self.assertTrue(summary["stop_confirmed"])

    def test_detect_tampered_answer(self):
        x = copy.deepcopy(self.raw)
        x["results"][0]["observed_answer"] = "tampered"
        receipt = copy.deepcopy(self.receipt)
        receipt["provider_result_sha256"] = hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "answer digest mismatch|incorrect model answer scoring"):
            verify(x, receipt, self.tasks)

    def test_detect_incomplete_run(self):
        x = copy.deepcopy(self.raw)
        x["results"].pop()
        receipt = copy.deepcopy(self.receipt)
        receipt["provider_result_sha256"] = hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "40 observations"):
            verify(x, receipt, self.tasks)

    def test_detect_missing_stop_receipt(self):
        receipt = copy.deepcopy(self.receipt)
        receipt["stopped"] = False
        with self.assertRaisesRegex(ValueError, "stop receipt"):
            verify(self.raw, receipt, self.tasks)


if __name__ == "__main__":
    unittest.main()
