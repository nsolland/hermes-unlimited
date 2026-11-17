"""Independent validation of Salad behavioral ablation output.

The scoring logic is intentionally separate from the model execution file.
"""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

TASKS = ("squares", "logic", "modulus", "count", "weekday", "sum")
ARMS = ("baseline", "verify", "length_control", "decompose", "self_consistency")
REPLICATES = (411, 412, 413, 414)


def h(value):
    return hashlib.sha256(value.encode()).hexdigest()


def final_answer_matches(response, expected):
    response = response.strip()
    if response == expected:
        return True
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    if not lines:
        return False
    final_line = re.sub(r"^(?:final\s+)?answer\s*:\s*", "", lines[-1], flags=re.I)
    return final_line.strip().strip(".") == expected


def validate(data, receipt, task_bytes):
    if receipt.get("stopped") is not True:
        raise ValueError("no confirmed Salad shutdown")
    digest = h(json.dumps(data, sort_keys=True))
    if receipt.get("provider_result_sha256") != digest:
        raise ValueError("provider digest mismatch")
    if data.get("total") != 120 or len(data.get("results", [])) != 120:
        raise ValueError("incomplete trials")
    if data.get("source_task_sha256") != hashlib.sha256(task_bytes).hexdigest():
        raise ValueError("task manifest mismatch")
    src = {row["id"]: row for row in json.loads(task_bytes)}
    if len(src) != 20 or any(t not in src for t in TASKS):
        raise ValueError("oracle missing")
    observed = {}
    for row in data["results"]:
        task, arm, replicate = row["task"], row["arm"], row["replicate"]
        key = (task, arm, replicate)
        if task not in TASKS or arm not in ARMS or replicate not in REPLICATES or key in observed:
            raise ValueError("invalid trial identity")
        expected = src[task]["expected"]
        answer = row["answer"]
        if row["expected_sha256"] != h(expected) or row["answer_sha256"] != h(answer):
            raise ValueError("answer/oracle digest mismatch")
        if row["prompt_sha256"] != h(src[task]["prompt"]):
            raise ValueError("prompt digest mismatch")
        if row["instruction_sha256"] != h(data["arms"][arm]):
            raise ValueError("instruction digest mismatch")
        exact = row["error"] is None and answer == expected
        final = row["error"] is None and final_answer_matches(answer, expected)
        if row["exact"] is not exact or row["semantic_final"] is not final:
            raise ValueError("scoring mismatch")
        observed[key] = row
    if len(observed) != len(TASKS)*len(ARMS)*len(REPLICATES):
        raise ValueError("unbalanced trial grid")
    by_arm = {}
    by_task = {}
    for arm in ARMS:
        rows = [r for (task, a, rep), r in observed.items() if a == arm]
        by_arm[arm] = {
            "n": len(rows), "exact": sum(r["exact"] for r in rows),
            "final_answer": sum(r["semantic_final"] for r in rows),
            "errors": sum(r["error"] is not None for r in rows),
            "input_tokens_mean": round(sum(r["usage"].get("prompt_tokens",0) for r in rows)/len(rows),3),
            "output_tokens_mean": round(sum(r["usage"].get("completion_tokens",0) for r in rows)/len(rows),3),
            "latency_seconds_mean": round(sum(r["latency_s"] for r in rows)/len(rows),3),
        }
    for task in TASKS:
        by_task[task] = {arm:{
            "exact":sum(observed[(task, arm, rep)]["exact"] for rep in REPLICATES),
            "final_answer":sum(observed[(task, arm, rep)]["semantic_final"] for rep in REPLICATES),
            "distinct_answers":sorted(set(observed[(task, arm, rep)]["answer"] for rep in REPLICATES))
        } for arm in ARMS}
    return {
        "source_commit":receipt.get("source_commit"),
        "provider_group":receipt.get("group"), "stopped":True,
        "model_reported":sorted(set(str(r["model_returned"]) for r in data["results"])),
        "n":120, "by_arm":by_arm, "by_task":by_task,
        "contrasts_exact_pp":{
            f"{arm}_minus_baseline":round((by_arm[arm]["exact"]-by_arm["baseline"]["exact"])/24*100,2)
            for arm in ARMS if arm != "baseline"},
        "claim_limit":"Behavioral output test only; no hidden activations, causal representation or Hermes CLI harness execution."
    }


def main():
    root=Path("experiments/harness")
    data=json.loads((root/"20261117_mechanism_raw.json").read_text())
    receipt=json.loads((root/"20261117_mechanism_receipt.json").read_text())
    out=validate(data,receipt,(root/"tasks_v2.json").read_bytes())
    (root/"20261117_mechanism_verified.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
