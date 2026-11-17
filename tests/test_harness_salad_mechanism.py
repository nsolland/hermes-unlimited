import hashlib
import json
import unittest
from unittest.mock import patch
from scripts import harness_salad_mechanism as m

class MechanismTests(unittest.TestCase):
    def test_design_bounded_and_independent(self):
        self.assertEqual(m.MAX_CALLS,120)
        self.assertEqual(len(m.TASK_IDS),6)
        self.assertEqual(len(m.ARMS),5)
        self.assertEqual(len(m.SEEDS),4)
        self.assertEqual(len(set(m.ARMS.values())),5)
        self.assertTrue(m.ARMS["verify"].startswith(m.ARMS["baseline"]))
        self.assertEqual(m.hash_bytes(b"123"),hashlib.sha256(b"123").hexdigest())

    def test_conservative_semantic_answer_parser(self):
        self.assertTrue(m.semantic_match("modulus","Since 13x77=1001\nAnswer: 0","0"))
        self.assertTrue(m.semantic_match("squares","650","650"))
        self.assertFalse(m.semantic_match("squares","The answer may be 650 or 546","650"))
        self.assertFalse(m.semantic_match("weekday","TUESDAY","WEDNESDAY"))
        self.assertFalse(m.semantic_match("squares","Calculation: 650\nFinal answer: 546","650"))

    def test_fails_closed_outside_salad(self):
        with patch.dict("os.environ",{"SYNAPSE_EXECUTION_ENV":"LOCAL", "SALAD_AI_GATEWAY_API_KEY":"dummy"}):
            with self.assertRaisesRegex(RuntimeError,"SALAD_REQUIRED"):
                m.run()

if __name__=="__main__":
    unittest.main()
