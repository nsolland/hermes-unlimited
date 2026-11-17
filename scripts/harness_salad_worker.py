"""Salad-only instruction-ablation experiment (NOT a Hermes CLI agent run).

The whole model request loop executes within one dedicated Salad container.
Comparison isolates a verification instruction; exact deterministic task
oracles are supplied only to the verifier, never to the model request.
"""
from __future__ import annotations
import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

MODEL = "qwen3.5-9b"
ENDPOINT = "https://ai.salad.cloud/v1/chat/completions"
TIMEOUT_SECONDS = 35
MAX_ATTEMPTS = 40
MAX_SECONDS = 1600
RESERVE_PER_ATTEMPT_USD = Decimal("0.01")
MODEL_BUDGET_USD = Decimal("0.40")
BASE = "Follow the supplied task exactly. Return only its final answer."
CHECK = (BASE + " Independently verify the result by a different method before responding. "
         "Keep verification private, and return only the final answer.")
PRICE_INPUT_PER_M = Decimal("0.06")
PRICE_OUTPUT_PER_M = Decimal("0.09")


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def send(prompt, extra_rule, key):
    payload = {
        "model": MODEL, "temperature": 0, "max_tokens": 160,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {"role": "system", "content": extra_rule},
            {"role": "user", "content": prompt + "\nReturn only the answer."},
        ],
    }
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    req = urllib.request.Request(ENDPOINT, data=data, method="POST",
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "User-Agent": "HermesHarness-SaladResearch/1"})
    began = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            reply = json.load(response)
        choice = reply["choices"][0]["message"]
        answer = (choice.get("content") or "").strip()
        usage = reply.get("usage") or {}
        in_t, out_t = usage.get("prompt_tokens"), usage.get("completion_tokens")
        measured = isinstance(in_t, int) and isinstance(out_t, int) and in_t >= 0 and out_t >= 0
        cost = ((Decimal(in_t) * PRICE_INPUT_PER_M + Decimal(out_t) * PRICE_OUTPUT_PER_M) /
                Decimal("1000000")) if measured else None
        return {
            "answer": answer[:500], "answer_sha256": sha(answer), "usage": usage,
            "model_returned": reply.get("model"), "estimated_usd": str(cost) if cost is not None else None,
            "error": None, "elapsed_seconds": round(time.monotonic()-began, 3),
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError,
            KeyError, IndexError, TypeError) as exc:
        return {"answer": "", "answer_sha256": sha(""), "usage": {},
                "model_returned": None, "estimated_usd": None,
                "error": type(exc).__name__, "elapsed_seconds": round(time.monotonic()-began, 3)}


def run():
    if os.environ.get("SYNAPSE_EXECUTION_ENV") != "SALAD":
        raise RuntimeError("SALAD_ENV_REQUIRED")
    key = os.environ.get("SALAD_AI_GATEWAY_API_KEY")
    if not key:
        raise RuntimeError("MISSING_SALAD_GATEWAY_KEY")
    source = Path("/tmp/salad_job/experiments/harness/tasks_v2.json")
    tasks = json.loads(source.read_text())
    if len(tasks) != 20:
        raise RuntimeError("TASK_MANIFEST_MUST_HAVE_20")
    if any(not isinstance(t.get("id"), str) or not isinstance(t.get("prompt"), str)
           or not isinstance(t.get("expected"), str) for t in tasks):
        raise RuntimeError("INVALID_TASK_MANIFEST")
    if len({x["id"] for x in tasks}) != 20:
        raise RuntimeError("DUPLICATE_TASK_IDS")
    task_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    order = [(i, arm) for i in range(20) for arm in ("baseline", "checker")]
    rng_seed = int(os.environ.get("HERMES_HARNESS_ORDER_SEED", "1116"))
    if not (1 <= rng_seed < 2**31):
        raise RuntimeError("INVALID_ORDER_SEED")
    random.Random(rng_seed).shuffle(order)
    started = time.monotonic()
    results = []
    spent_observed = Decimal(0)
    for i, arm in order:
        if len(results) >= MAX_ATTEMPTS:
            raise RuntimeError("MAX_ATTEMPTS")
        if (Decimal(len(results)+1) * RESERVE_PER_ATTEMPT_USD > MODEL_BUDGET_USD):
            raise RuntimeError("RESERVED_BUDGET")
        if time.monotonic()-started >= MAX_SECONDS:
            raise RuntimeError("TIME_BUDGET")
        task = tasks[i]
        response = send(task["prompt"], BASE if arm == "baseline" else CHECK, key)
        if response["estimated_usd"] is not None:
            spent_observed += Decimal(response["estimated_usd"])
        expected = task["expected"]
        correct = response["error"] is None and response["answer"] == expected
        results.append({
            "task": task["id"], "arm": arm, "exact_match": correct,
            "expected_sha256": sha(expected), "observed_answer": response["answer"],
            "answer_sha256": response["answer_sha256"],
            "model_requested": MODEL, "model_returned": response["model_returned"],
            "usage": response["usage"], "estimated_usd": response["estimated_usd"],
            "error": response["error"], "elapsed_seconds": response["elapsed_seconds"],
        })
    summary = {}
    for arm in ("baseline", "checker"):
        a = [r for r in results if r["arm"] == arm]
        summary[arm] = {
            "n": len(a), "correct": sum(r["exact_match"] for r in a),
            "errors": sum(r["error"] is not None for r in a),
            "mean_seconds": round(sum(r["elapsed_seconds"] for r in a)/len(a),3),
        }
    result = {
        "experiment": "HERMES-HARNESS-SALAD-01",
        "classification": "SALAD_GATEWAY_INSTRUCTION_ABLATION_NOT_HERMES_CLI",
        "execution_environment": os.environ.get("SYNAPSE_EXECUTION_ENV"),
        "model_requested": MODEL,
        "model_rng_pinned": False,
        "temperature": 0,
        "task_manifest_sha256": task_sha256,
        "order_seed": rng_seed,
        "max_requests": MAX_ATTEMPTS,
        "reserved_budget_ceiling_usd": str(MODEL_BUDGET_USD),
        "observed_model_cost_usd": str(spent_observed),
        "model_usage_complete": all(r["estimated_usd"] is not None for r in results),
        "results": results,
        "summary": summary,
        "limitations": [
            "Salad AI Gateway prompt comparison, not Hermes agent harness execution",
            "Host container runtime not independently hardware-attested",
            "No actual AGENTS.md file loading (instructions sent in API system messages)",
            "No model internal RNG seed; no proof of backend node identity",
            "Gateway billing estimates not provider invoice and container costs separate"
        ],
    }
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
