"""Salad-only counterfactual paraphrase test for two diverging tasks.

Models receive only equivalent problem statements and one instruction arm.
This test cannot observe hidden activations or determine neuron-level causation.
"""
import hashlib
import json
import os
import random
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from harness_salad_worker import send, MODEL
from harness_salad_mechanism import ARMS, semantic_match

PHRASES = {
    "squares": [
        ("original","Calculate the sum of i*i for integers i=1 through 12.", "650"),
        ("exponent","Evaluate 1^2 + 2^2 + ... + 12^2, including both endpoints.", "650"),
        ("sigma","For k in {1, 2, ..., 12}, calculate the sum of k squared.", "650"),
    ],
    "logic": [
        ("original","How many integers from 1 to 30 inclusive are divisible by 3 but not by 2?", "5"),
        ("odd_multiples","Among the whole numbers 1 through 30, count the odd multiples of 3.", "5"),
        ("modular","Count integers n such that 1 <= n <= 30, n mod 3 = 0, and n mod 2 = 1.", "5"),
    ],
}
SELECTED_ARMS = ("baseline","verify","length_control","decompose")
REPLICATES = (501,502,503)
MAX_CALLS = 2*3*4*3
MAX_COST_USD = Decimal("0.06")
MAX_WALL = 1000

def h(s): return hashlib.sha256(s.encode()).hexdigest()

def main():
    if os.environ.get("SYNAPSE_EXECUTION_ENV") != "SALAD":
        raise RuntimeError("SALAD_REQUIRED")
    key=os.environ.get("SALAD_AI_GATEWAY_API_KEY")
    if not key: raise RuntimeError("MISSING_GATEWAY_KEY")
    plan=[(task,phrase_id,phrase,expect,arm,rep) for task,phrases in PHRASES.items()
         for phrase_id,phrase,expect in phrases for arm in SELECTED_ARMS for rep in REPLICATES]
    if len(plan)!=MAX_CALLS or len({(p[0],p[1],p[4],p[5]) for p in plan})!=MAX_CALLS:
        raise RuntimeError("UNBALANCED_PROTOCOL")
    random.Random(20261117).shuffle(plan)
    started=time.monotonic()
    records=[]
    spent=Decimal(0)
    for task,phrase_id,prompt,expected,arm,rep in plan:
        if spent>=MAX_COST_USD or time.monotonic()-started>MAX_WALL:
            raise RuntimeError("BUDGET_LIMIT")
        answer=send(prompt,ARMS[arm],key)
        if answer["estimated_usd"] is not None:
            spent += Decimal(answer["estimated_usd"])
        text=answer["answer"]
        records.append({
            "task":task,"phrase_id":phrase_id,"replicate":rep,"arm":arm,
            "prompt":prompt,"prompt_sha256":h(prompt),"instruction_sha256":h(ARMS[arm]),
            "expected_sha256":h(expected),"answer":text,"answer_sha256":h(text),
            "exact":answer["error"] is None and text==expected,
            "final_semantic":answer["error"] is None and semantic_match(task,text,expected),
            "usage":answer["usage"],"model_returned":answer["model_returned"],
            "estimated_usd":answer["estimated_usd"],"error":answer["error"],
            "latency_s":answer["elapsed_seconds"]
        })
    summary={}
    for arm in SELECTED_ARMS:
        a=[r for r in records if r["arm"]==arm]
        summary[arm]={"n":len(a),"correct":sum(r["exact"] for r in a),
                      "final_semantic":sum(r["final_semantic"] for r in a),
                      "mean_latency_s":round(sum(r["latency_s"] for r in a)/len(a),3)}
    print(json.dumps({
        "experiment":"HERMES-HARNESS-SALAD-PARAPHRASE-01",
        "scope":"SALAD_GATEWAY_BEHAVIORAL_PARAPHRASE_NOT_HERMES_CLI",
        "model_requested":MODEL,"temperature":0,"model_rng_seed_pinned":False,
        "phrases":PHRASES,"arms":{k:ARMS[k] for k in SELECTED_ARMS},
        "replicate_labels":list(REPLICATES),"order_seed":20261117,
        "total":len(records),"results":records,"by_arm":summary,
        "reported_model_cost_usd":str(spent),
        "limitations":["Tasks and paraphrases selected after prior observed effects",
            "Only surface equivalent wordings and model outputs are observed",
            "No activation, attention or residual-stream observation",
            "Prompt wording and token count vary across paraphrases",
            "Inference RNG/weights not cryptographically pinned"]
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
