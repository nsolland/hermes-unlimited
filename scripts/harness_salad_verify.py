"""Independently verify Salad instruction-ablation provider evidence.

No model inference. Never substitutes an exact oracle with subjective grading.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def verify(result: dict, receipt: dict, task_bytes: bytes) -> dict:
    if receipt.get("stopped") is not True or receipt.get("group") is None:
        raise ValueError("Salad stop receipt missing")
    if receipt.get("provider_result_sha256") != digest(json.dumps(result, sort_keys=True)):
        raise ValueError("provider result digest mismatch")
    if receipt.get("task_manifest_sha256") != hashlib.sha256(task_bytes).hexdigest():
        raise ValueError("task manifest digest mismatch")
    tasks = json.loads(task_bytes)
    if len(tasks) != 20:
        raise ValueError("requires exactly 20 tasks")
    expected = {t["id"]: t["expected"] for t in tasks}
    if len(expected) != 20:
        raise ValueError("duplicate task IDs")
    rows = result.get("results", [])
    if len(rows) != 40:
        raise ValueError("requires exactly 40 observations")
    keys = [(r["task"], r["arm"]) for r in rows]
    if set(keys) != {(task, arm) for task in expected for arm in ("baseline", "checker")} or len(set(keys)) != 40:
        raise ValueError("unpaired, duplicate or unknown observations")
    for r in rows:
        if r["expected_sha256"] != digest(expected[r["task"]]):
            raise ValueError("oracle digest mismatch")
        if r["answer_sha256"] != digest(r["observed_answer"]):
            raise ValueError("answer digest mismatch")
        exact = r["error"] is None and r["observed_answer"] == expected[r["task"]]
        if r["exact_match"] is not exact:
            raise ValueError("incorrect model answer scoring")
    by_arm = {}
    for arm in ("baseline", "checker"):
        subset = [r for r in rows if r["arm"] == arm]
        by_arm[arm] = {
            "n":len(subset), "correct":sum(r["exact_match"] for r in subset),
            "error_count":sum(r["error"] is not None for r in subset),
            "mean_latency_seconds":round(sum(r["elapsed_seconds"] for r in subset)/len(subset), 3),
        }
    pairs = [(next(r for r in rows if r["task"] == task and r["arm"] == "baseline"),
              next(r for r in rows if r["task"] == task and r["arm"] == "checker")) for task in sorted(expected)]
    b_only=sum(b["exact_match"] and not c["exact_match"] for b,c in pairs)
    c_only=sum(c["exact_match"] and not b["exact_match"] for b,c in pairs)
    discordant=b_only+c_only
    p=1.0 if discordant==0 else min(1.0,2*sum(math.comb(discordant,i) for i in range(min(b_only,c_only)+1))/2**discordant)
    return {
        "classification":"SALAD_INSTRUCTION_ABLATION_NOT_HERMES_CLI",
        "provider_group":receipt["group"],
        "source_commit":receipt.get("source_commit"),
        "model_returned":dict(Counter(str(r["model_returned"]) for r in rows)),
        "usage_complete":all(isinstance((r.get("usage") or {}).get("prompt_tokens"),int) and isinstance((r.get("usage") or {}).get("completion_tokens"),int) for r in rows),
        "by_arm":by_arm,
        "paired_baseline_only_correct":b_only,
        "paired_checker_only_correct":c_only,
        "paired_exact_mcnemar_p_exploratory":p,
        "delta_correct_fraction_checker_minus_baseline":round((by_arm["checker"]["correct"]-by_arm["baseline"]["correct"])/20,3),
        "model_cost_usd_reported":result.get("observed_model_cost_usd"),
        "provider_digest_verified":True,
        "task_digest_verified":True,
        "stop_confirmed":True,
        "limitations":[
            "temperature zero is not a pinned RNG",
            "provider model string is not independent model weight attestation",
            "direct Salad Gateway instruction experiment, not Hermes CLI agent",
            "exact-match evaluates formatting as well as numerical validity",
            "container and network costs not independently invoiced",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--result",required=True)
    p.add_argument("--receipt",required=True)
    p.add_argument("--tasks",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    res=verify(json.loads(Path(a.result).read_text()),
               json.loads(Path(a.receipt).read_text()),Path(a.tasks).read_bytes())
    Path(a.out).write_text(json.dumps(res,sort_keys=True,indent=2)+"\n")
    print(json.dumps(res,sort_keys=True))


if __name__=="__main__":
    main()
