import json
import unittest
from pathlib import Path
from scripts.harness_salad_paraphrase_verify import analyze

BASE = Path(__file__).resolve().parents[1] / 'experiments' / 'harness'

class SaladParaphraseEvidenceTests(unittest.TestCase):
    def test_verified_actual_run_and_counterfactuals(self):
        raw = json.loads((BASE / '20261117_paraphrase_raw.json').read_text())
        receipt = json.loads((BASE / '20261117_paraphrase_receipt.json').read_text())
        result = analyze(raw, receipt)
        self.assertTrue(result['stop_confirmed'])
        self.assertEqual(result['n'], 72)
        self.assertEqual(result['by_arm']['baseline']['exact'], 8)
        self.assertEqual(result['by_arm']['verify']['exact'], 7)
        self.assertEqual(result['by_arm']['length_control']['exact'], 9)
        self.assertEqual(result['by_arm']['decompose']['exact'], 3)
        self.assertEqual(result['by_task']['logic']['original']['verify']['exact'], 3)
        self.assertEqual(result['by_task']['logic']['odd_multiples']['verify']['exact'], 0)
        self.assertEqual(result['by_task']['squares']['original']['verify']['exact'], 0)
        self.assertEqual(result['by_task']['squares']['sigma']['verify']['exact'], 3)

if __name__ == '__main__':
    unittest.main()
