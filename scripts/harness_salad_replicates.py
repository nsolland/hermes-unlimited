"""Independent task-cluster analysis of three completed Salad replicas."""
import hashlib
import json
import random
from collections import Counter
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.harness_salad_verify import verify

BASE = ROOT / "experiments/harness"
TASKS = (BASE / "tasks_v2.json").read_bytes()


def read_round(label, raw_path, receipt_path):
    raw_bytes = Path(raw_path).read_bytes()
    data = json.loads(raw_bytes)
    rec = json.loads(Path(receipt_path).read_bytes())
    check = verify(data, rec, TASKS)
    return {
        "label": label, "data": data, "receipt": rec, "check": check,
        "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }


def evaluate(rounds):
    tasks = sorted({r["task"] for d in rounds for r in d["data"]["results"]})
    if len(tasks) != 20:
        raise RuntimeError("Expected twenty tasks")
    seeds = [d["data"]["order_seed"] for d in rounds]
    if len(set(seeds)) != len(seeds):
        raise RuntimeError("Duplicate task-order seeds")
    by_pair = {}
    for d in rounds:
        seed = d["data"]["order_seed"]
        for record in d["data"]["results"]:
            key=(seed,record["task"],record["arm"])
            if key in by_pair:
                raise RuntimeError("Duplicate observation")
            by_pair[key] = record
    for seed in seeds:
        for task in tasks:
            for arm in ("baseline","checker"):
                if (seed,task,arm) not in by_pair:
                    raise RuntimeError("Unpaired data")
    n=len(seeds)*len(tasks)
    rows={arm:[by_pair[(seed,task,arm)] for seed in seeds for task in tasks]
          for arm in ("baseline","checker")}
    summaries={}
    for arm,series in rows.items():
        summaries[arm]={
            "n":len(series),
            "correct":sum(int(x["exact_match"]) for x in series),
            "correct_fraction":sum(int(x["exact_match"]) for x in series)/len(series),
            "mean_seconds":round(sum(x["elapsed_seconds"] for x in series)/len(series),4),
            "error_count":sum(int(x["error"] is not None) for x in series),
        }
    differences=[]
    per_task={}
    task_delta_means={}
    for task in tasks:
        values=[]
        for seed in seeds:
            c=by_pair[(seed,task,"checker")]
            b=by_pair[(seed,task,"baseline")]
            v=int(c["exact_match"])-int(b["exact_match"])
            differences.append(v)
            values.append(v)
        task_delta_means[task] = sum(values)/len(values)
        per_task[task]={
            "difference_mean":round(sum(values)/len(values),4),
            "baseline_correct":sum(by_pair[(seed,task,"baseline")]["exact_match"] for seed in seeds),
            "checker_correct":sum(by_pair[(seed,task,"checker")]["exact_match"] for seed in seeds),
        }
    rng=random.Random(20261116)
    boot=[]
    for _ in range(10000):
        sampled=[tasks[rng.randrange(len(tasks))] for _ in tasks]
        boot.append(sum(task_delta_means[t] for t in sampled)/len(tasks))
    boot.sort()
    cost=Decimal(0)
    all_usage=True
    for d in rounds:
        for r in d["data"]["results"]:
            if r.get("estimated_usd") is None:
                all_usage=False
            else:
                cost+=Decimal(r["estimated_usd"])
    out={
        "classification":"EXPLORATORY_SALAD_GATEWAY_INSTRUCTION_ABLATION",
        "unique_tasks":20,
        "replicas":len(rounds),
        "task_order_seeds":seeds,
        "actual_model_requests":2*n,
        "by_arm":summaries,
        "checker_minus_baseline_correct_fraction":round(sum(differences)/n,4),
        "task_cluster_bootstrap_95_percentile_interval":[round(boot[250],4),round(boot[9749],4)],
        "bootstrap_iterations":len(boot),
        "per_task":per_task,
        "reported_gateway_model_usd":str(cost),
        "usage_complete":all_usage,
        "source_rounds":[{"label":d["label"],"source_commit":d["receipt"]["source_commit"],
                         "provider_group":d["receipt"]["group"],"result_raw_sha256":d["raw_sha256"],
                         "stop_verified":d["check"]["stop_confirmed"]} for d in rounds],
        "limitations":[
            "Only 20 elementary tasks; task-cluster CI does not eliminate benchmark selection bias",
            "Order seeds do not control model RNG or backend hardware",
            "One first-run worker source commit differs solely from later parameterized order implementation",
            "Not Hermes CLI; instructions sent as Salad Gateway system messages",
            "No independent attestation of backend weights or hardware",
            "Estimated model price excludes actual Salad container charges",
        ],
    }
    return out


if __name__ == "__main__":
    rounds = [read_round(label, BASE / f"20261116_salad_{label}_raw.json",
                         BASE / f"20261116_salad_{label}_receipt.json")
              for label in ("a1", "b2", "c2")]
    summary = evaluate(rounds)
    out = BASE / "20261116_salad_three_replica_analysis.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k:v for k,v in summary.items() if k != "per_task"}, indent=2, sort_keys=True))
