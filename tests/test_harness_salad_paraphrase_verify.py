import copy
import hashlib
import json
import unittest
from scripts.harness_salad_paraphrase_verify import analyze, final_answer
from scripts.harness_salad_paraphrase import PHRASES, SELECTED_ARMS, REPLICATES, ARMS

def fixture():
    rows=[]
    for task,phrases in PHRASES.items():
        for phrase_id,prompt,expected in phrases:
            for arm in SELECTED_ARMS:
                for rep in REPLICATES:
                    rows.append({
                        "task":task,"phrase_id":phrase_id,"replicate":rep,
                        "arm":arm,"prompt":prompt,
                        "prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
                        "instruction_sha256":hashlib.sha256(ARMS[arm].encode()).hexdigest(),
                        "expected_sha256":hashlib.sha256(expected.encode()).hexdigest(),
                        "answer":expected,
                        "answer_sha256":hashlib.sha256(expected.encode()).hexdigest(),
                        "exact":True,"final_semantic":True,"usage":{"prompt_tokens":10,"completion_tokens":3},
                        "latency_s":1,"error":None,"model_returned":"synthetic"})
    d={"total":72,"results":rows,"phrases":PHRASES,"arms":{k:ARMS[k] for k in SELECTED_ARMS}}
    r={"stopped":True,"source_commit":"synthetic",
       "provider_result_sha256":hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()}
    return d,r

class ParaphraseVerifierTests(unittest.TestCase):
    def test_balanced_design(self):
        d,r=fixture()
        v=analyze(d,r)
        self.assertEqual(v["n"],72)
        self.assertEqual(v["by_arm"]["baseline"]["exact"],18)

    def test_tampered_oracle(self):
        d,r=fixture()
        d["results"][0]["answer"]="wrong"
        r["provider_result_sha256"]=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,"answer hash mutated"):
            analyze(d,r)

    def test_missing_pair(self):
        d,r=fixture()
        d["results"].pop()
        r["provider_result_sha256"]=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError,"incomplete"):
            analyze(d,r)

    def test_final_match_strict(self):
        self.assertTrue(final_answer("Explanation\nFinal answer: 650","650"))
        self.assertFalse(final_answer("650 or 546","650"))

if __name__=="__main__":unittest.main()
