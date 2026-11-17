"""Bounded checkpointed harness experiment. Independent exact-match oracles only."""
import argparse
import hashlib
import json
import random
import tempfile
from pathlib import Path

from scripts.harness_live_trial import TASKS, invoke
from scripts.harness_preflight import inspect_host


def atomic_save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".partial")
    staging.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    staging.replace(path)


def run(args):
    output = Path(args.out)
    guard = inspect_host()
    if not guard["admissible"]:
        raise RuntimeError("host preflight rejected experiment: " + ",".join(guard["reasons"]))
    if not args.model.strip() or not args.provider.strip():
        raise ValueError("model and provider must be explicit")
    if args.timeout < 5 or args.timeout > 180:
        raise ValueError("timeout out of bounds")
    if not 1 <= args.limit <= 1000 or len(TASKS)*2 > args.limit:
        raise ValueError("limit too small or out of bounds")
    order = [(task, arm) for task in TASKS for arm in ("baseline", "checker")]
    random.Random(args.order_seed).shuffle(order)
    manifest = {
        "protocol": "hermes-harness-checkpoint-v1",
        "requested_provider": args.provider,
        "requested_model": args.model,
        "model_rng_seed_pinned": False,
        "task_order_seed": args.order_seed,
        "task_suite_sha256": hashlib.sha256(json.dumps(TASKS, sort_keys=True).encode()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "engine_sha256": hashlib.sha256(Path(invoke.__code__.co_filename).read_bytes()).hexdigest(),
        "timeout_seconds": args.timeout,
        "expected_invocations": len(order),
        "records": [],
        "notes": [
            "No claim of causal effect, live model routing independent attestation, or cost accuracy",
            "Exit 0 plus exact stdout is required; other outputs fail",
            "Task-order seed is not the model random-number seed",
            "No independent confirmation that AGENTS.md was injected on every trial",
            "Concurrent external Mac workloads are uncontrolled"
        ]
    }
    if output.exists():
        old = json.loads(output.read_text())
        for key, value in manifest.items():
            if key not in ("records", "runner_sha256", "engine_sha256") and old.get(key) != value:
                raise ValueError(f"resume manifest mismatch: {key}")
        manifest["records"] = old["records"]
    identities = [(r["task"], r["arm"]) for r in manifest["records"]]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate records in checkpoint")
    with tempfile.TemporaryDirectory(prefix="hermes-batch-") as temp:
        for task, arm in order:
            if (task, arm) in identities:
                continue
            _, record = invoke(Path(temp), task, args.order_seed, arm,
                               args.timeout, args.model, args.provider)
            manifest["records"].append(record)
            atomic_save(output, manifest)
            print(f"{len(manifest['records'])}/{len(order)} {task} {arm} "
                  f"exit={record['exit_code']} correct={record['oracle_match']} "
                  f"time={record['seconds']}", flush=True)
    manifest["complete"] = len(manifest["records"]) == len(order)
    atomic_save(output, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--order-seed", type=int, default=31)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
