import copy
import hashlib
import json
import unittest
from scripts.harness_salad_mechanism_verify import validate, final_answer_matches
from scripts.harness_salad_mechanism import TASK_IDS, ARMS, SEEDS

def fixtures():
    tasks=[{"id":t,"prompt":t,"expected":"7"} for t in TASK_IDS]
    tasks.extend({"id":f"extra{i}","prompt":str(i),"expected":str(i)} for i in range(14))
    task_bytes=json.dumps(tasks).encode()
    items=[]
    for task in TASK_IDS:
        for arm in ARMS:
            for seed in SEEDS:
                items.append({"task":task,"arm":arm,"replicate":seed,
                    "prompt_sha256":hashlib.sha256(task.encode()).hexdigest(),
                    "instruction_sha256":hashlib.sha256(ARMS[arm].encode()).hexdigest(),
                    "expected_sha256":hashlib.sha256(b"7").hexdigest(),
                    "answer":"7","answer_sha256":hashlib.sha256(b"7").hexdigest(),
                    "error":None,"exact":True,"semantic_final":True,
                    "model_returned":"synthetic","usage":{"prompt_tokens":10,"completion_tokens":2},
                    "latency_s":0.5})
    result={"total":120,"results":items,"arms":ARMS,
            "source_task_sha256":hashlib.sha256(task_bytes).hexdigest()}
    receipt={"stopped":True,"group":"fixture",
             "provider_result_sha256":hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()}
    return result,receipt,task_bytes

class SaladMechanismVerifierTests(unittest.TestCase):
    def test_valid_balanced_data(self):
        x,r,t=fixtures()
        summary=validate(x,r,t)
        self.assertEqual(summary["n"],120)
        self.assertEqual(summary["by_arm"]["baseline"]["exact"],24)

    def test_tamper_detected(self):
        x,r,t=fixtures()
        x["results"][0]["answer"]="bad"
        r["provider_result_sha256"]=hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,"digest mismatch"):
            validate(x,r,t)

    def test_duplicate_trial_rejected(self):
        x,r,t=fixtures()
        x["results"][1]=copy.deepcopy(x["results"][0])
        r["provider_result_sha256"]=hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,"invalid trial identity"):
            validate(x,r,t)

    def test_conservative_final_parser(self):
        self.assertTrue(final_answer_matches("Work shown\nFinal answer: 7","7"))
        self.assertFalse(final_answer_matches("7 or 8","7"))

if __name__=="__main__":
    unittest.main()
