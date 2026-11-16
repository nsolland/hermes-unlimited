"""Small, bounded live Hermes CLI harness comparison.

Use on an isolated machine with an already configured Hermes CLI. This is
experimental data collection, not production evaluation or permission.
"""
import argparse
import hashlib
import json
import random
import subprocess
import tempfile
import time
from pathlib import Path

from unlimited.harness_benchmark import Trial, paired_delta, summarize

TASKS = {
    "squares": ("Calculate the sum of i*i for integers i=1 through 12.", "650"),
    "reverse": ("Reverse the exact ASCII string 'lumen-741' character by character.", "147-nemul"),
    "sort": ("Sort these integers in increasing order: 19, -3, 8, 8, 0, 14. "
             "Return comma-separated numbers with no spaces.", "-3,0,8,8,14,19"),
    "logic": ("How many integers from 1 to 30 inclusive are divisible by 3 but not by 2?", "5"),
}
BASE_RULE = "Follow the supplied task. Return only its final answer.\n"
CHECK_RULE = (BASE_RULE +
              "Before responding, independently verify the result by a different method. "
              "Keep verification private; return only the final answer.\n")


def invoke(root: Path, task: str, seed: int, arm: str, timeout: int, model: str | None):
    workdir = root / f"{task}-{seed}-{arm}"
    workdir.mkdir(parents=True, exist_ok=False)
    prompt, expected = TASKS[task]
    (workdir / "AGENTS.md").write_text(BASE_RULE if arm == "baseline" else CHECK_RULE)
    (workdir / "task.txt").write_text(prompt + "\nReturn only the answer without explanation.\n")
    command = ["hermes", "--in", str(workdir)]
    if model:
        command += ["-m", model]
    command += ["-z", "Read task.txt and return only the requested answer."]
    started = time.monotonic()
    try:
        p = subprocess.run(command, capture_output=True, text=True, timeout=timeout, cwd=workdir)
        stdout, stderr, status = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        status = 124
    elapsed = time.monotonic() - started
    # Strict oracle rejects explanations, errors, and extra text.
    actual = stdout.strip()
    matched = status == 0 and actual == expected
    row = Trial(task, arm, seed, matched, matched, matched, matched, False, 0, elapsed, 0.0)
    record = {
        "task": task, "seed": seed, "arm": arm, "expected": expected,
        "actual": actual[:300], "exit_code": status, "seconds": round(elapsed, 3),
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "oracle_match": matched, "timed_out": status == 124,
        "note": "Cost and resume behavior unmeasured; scope refers only to exact output format; seed is trial identifier, not guaranteed model RNG seed",
    }
    return row, record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=int, default=75)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--model", default=None)
    parser.add_argument("--tasks", nargs="+", choices=list(TASKS), default=list(TASKS))
    args = parser.parse_args()
    if args.timeout < 5 or args.timeout > 180:
        parser.error("timeout must be between 5 and 180 seconds")
    rows, raw = [], []
    with tempfile.TemporaryDirectory(prefix="hermes-harness-") as tmp:
        order = [(t, a) for t in args.tasks for a in ("baseline", "checker")]
        random.Random(args.seed).shuffle(order)
        for task, arm in order:
            row, record = invoke(Path(tmp), task, args.seed, arm, args.timeout, args.model)
            rows.append(row)
            raw.append(record)
            print(f"{task} {arm} exit={record['exit_code']} correct={record['oracle_match']} time={record['seconds']}s", flush=True)
    summary = summarize(rows)
    for metrics in summary.values():
        metrics["mean_cost_usd"] = None  # no API cost capture in CLI trial
    paired = paired_delta(rows, "baseline", "checker")
    paired["cost_usd_delta"] = None
    payload = {
        "protocol": "hermes-harness-mini-v1",
        "tasks": sorted(args.tasks),
        "trial_identifier": args.seed,
        "rng_seed_control_verified": False,
        "model": args.model or "local Hermes default (not pinned)",
        "costs_measured": False,
        "records": raw,
        "summary": summary,
        "paired": paired,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
