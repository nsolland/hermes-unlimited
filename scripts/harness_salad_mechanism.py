"""SALAD-only behavioral mechanism test: instruction ablation and task interactions.

This test cannot measure hidden representations. Exact-answer scoring remains
separate from semantic answer extraction; neither is evidence of internal state.
"""
from __future__ import annotations
import hashlib
import json
import os
import random
import re
import time
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_salad_worker import BASE, CHECK, MODEL, send

TASK_IDS = ("squares", "logic", "modulus", "count", "weekday", "sum")
ARMS = {
    "baseline": BASE,
    "verify": CHECK,
    "length_control": BASE + " Keep the requested output compact, follow the exact requested result format, and avoid unnecessary introductory or concluding wording.",
    "decompose": BASE + " First identify the elementary operations needed, calculate each carefully, and then produce only the final result.",
    "self_consistency": BASE + " Solve the task using two independent approaches, compare the results, resolve conflicts, and then emit just the final answer.",
}
SEEDS = (411, 412, 413, 414)
MAX_CALLS = len(TASK_IDS) * len(ARMS) * len(SEEDS)
LIMIT_WALL_SECONDS = 1500
MAX_MODEL_COST_USD = Decimal("0.08")


def hash_bytes(b):
    return hashlib.sha256(b).hexdigest()


def semantic_match(task, text, expected):
    """Conservative final-answer parser. Does NOT search arbitrary internal text."""
    t = text.strip()
    if t == expected:
        return True
    # Multi-line reasoning may contain incidental numbers. Only read final
    # nonempty line, or a final standalone 'Answer: VALUE' sentence.
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    if not lines:
        return False
    last = lines[-1]
    last = re.sub(r"^(?:final\s+)?answer\s*:\s*", "", last, flags=re.I)
    last = last.strip().strip(".")
    return last == expected


def run():
    if os.environ.get("SYNAPSE_EXECUTION_ENV") != "SALAD":
        raise RuntimeError("SALAD_REQUIRED")
    key = os.environ.get("SALAD_AI_GATEWAY_API_KEY")
    if not key:
        raise RuntimeError("SALAD_KEY_REQUIRED")
    taskpath = Path("/tmp/salad_job/experiments/harness/tasks_v2.json")
    tasks = {t["id"]: t for t in json.loads(taskpath.read_text())}
    if len(tasks) != 20:
        raise RuntimeError("INVALID_TASK_SET")
    if len(ARMS) != 5 or len(TASK_IDS) != 6 or MAX_CALLS != 120:
        raise RuntimeError("PROTOCOL_DRIFT")
    plan = [(task, arm, seed) for task in TASK_IDS for arm in ARMS for seed in SEEDS]
    random.Random(100901).shuffle(plan)
    start = time.monotonic()
    records=[]
    spent=Decimal(0)
    for task_id, arm, seed in plan:
        if time.monotonic()-start >= LIMIT_WALL_SECONDS:
            raise RuntimeError("WALL_LIMIT")
        if spent >= MAX_MODEL_COST_USD:
            raise RuntimeError("MODEL_COST_LIMIT")
        t=tasks[task_id]
        response=send(t["prompt"], ARMS[arm], key)
        if response["estimated_usd"] is not None:
            spent += Decimal(response["estimated_usd"])
        text=response["answer"]
        exact = response["error"] is None and text == t["expected"]
        semantic = response["error"] is None and semantic_match(task_id, text, t["expected"])
        records.append({
            "task":task_id,"arm":arm,"replicate":seed,
            "prompt_sha256":hash_bytes(t["prompt"].encode()),
            "instruction_sha256":hash_bytes(ARMS[arm].encode()),
            "expected_sha256":hash_bytes(t["expected"].encode()),
            "answer":text,"answer_sha256":hash_bytes(text.encode()),
            "exact":exact,"semantic_final":semantic,
            "model_returned":response["model_returned"],"error":response["error"],
            "usage":response["usage"],"estimated_usd":response["estimated_usd"],
            "latency_s":response["elapsed_seconds"]
        })
    breakdown={}
    for arm in ARMS:
        rows=[r for r in records if r["arm"]==arm]
        breakdown[arm]={
            "n":len(rows),"exact":sum(r["exact"] for r in rows),
            "semantic_final":sum(r["semantic_final"] for r in rows),
            "api_errors":sum(r["error"] is not None for r in rows),
            "mean_input_tokens":sum((r["usage"].get("prompt_tokens") or 0) for r in rows)/len(rows),
            "mean_output_tokens":sum((r["usage"].get("completion_tokens") or 0) for r in rows)/len(rows),
            "mean_latency_s":sum(r["latency_s"] for r in rows)/len(rows)
        }
    print(json.dumps({
        "experiment":"HERMES-HARNESS-SALAD-MECHANISM-01",
        "scope":"SALAD_GATEWAY_BEHAVIORAL_ABLATION_NOT_INTERNAL_MECHANISM_NOT_HERMES_CLI",
        "model_requested":MODEL,"temperature":0,"model_rng_seed_pinned":False,
        "source_task_sha256":hash_bytes(taskpath.read_bytes()),"arms":ARMS,
        "tasks":list(TASK_IDS),"replicate_labels":list(SEEDS),"ordering_random_seed":100901,
        "total":len(records),"results":records,"by_arm":breakdown,
        "reported_model_cost_usd":str(spent),
        "limitations":["Repeated calls do not pin model RNG","No model activation or hidden state captured",
            "Length-control changes wording and instruction content; not a perfect token-matched placebo",
            "Tasks selected after seeing prior outcomes; confirmatory p-values invalid",
            "Semantic parser uses only last line; other valid prose may be missed",
            "Container and backend weight identity not independently attested"]
    },sort_keys=True),flush=True)


if __name__ == "__main__":
    run()
