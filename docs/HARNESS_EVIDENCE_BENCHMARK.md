# Harness evidence benchmark (experimental)

Source inspiration: [walkinglabs/learn-harness-engineering](https://github.com/walkinglabs/learn-harness-engineering) (MIT). This implementation is original and independent.

## Question

For identical task inputs and model configurations, does changing the agent harness improve **verified completion**, rather than just self-reported success?

## Comparison design

- Control: current Hermes agent setup.
- Treatments, **one independent change at a time**: (1) explicit goals and scope, (2) persisted restart state, (3) proof-based checker, (4) maker/checker separation, (5) recovery and handoff.
- Match task ID, input, model, seed, tool availability, time budget and permitted side effects across arms.
- Include at least 20 distinct tasks and 3 seeds per task per arm before drawing practical conclusions; use more tasks when variability is high. Randomize arm order.
- Predefine objective completion assertions and artifact hashes. The agent's own claim does not count as proof.
- Record independently measured wall-clock time, API cost, human interventions, scope violations and correct recovery after restart.
- Require independent evidence and checker execution; failures or missing evidence are counted as incomplete.
- Record model, harness revision, task suite hash and environment digest outside the aggregate Trial schema in the experiment manifest.
- Report paired deltas with confidence intervals computed over task clusters in the experiment report; the built-in module only provides descriptive paired means, **not** causal or statistically significant findings.

## Implementation

`unlimited.harness_benchmark.Trial` is a validated immutable row. `summarize` provides descriptive metrics per harness; `paired_delta` fails when task/seed coverage differs. These functions are **offline evaluation utilities**, not a runner, authorization gate or deployed benchmark service.

Example:

```python
from unlimited.harness_benchmark import Trial, paired_delta
baseline = Trial("task-1", "baseline", 1, True, True, False, True, True, 2, 30, 0.12)
treatment = Trial("task-1", "state+checker", 1, True, True, True, True, True, 0, 40, 0.18)
print(paired_delta([baseline, treatment], "baseline", "state+checker"))
```

Local check: `python -m unittest tests.test_harness_benchmark -v`. The public-core workflow also discovers this test module.

## Limitations

- No live agent trials have been run by this change.
- `proof_present` is an input assertion, not a cryptographic proof verifier. The independent trial collector must verify proof custody before setting it true.
- Do not use these advisory measurements as execution clearance.
- A green unit test validates the scoring functions, not actual harness effectiveness.

## Expanded reproducibility controls (v2)

The trial CLI now requires explicit `--model` and `--provider`, and defines 20 deterministic tasks with exact independent oracles. The run manifest records task-suite and runner SHA-256 hashes, trial order seed, Python/host versions, per-invocation duration, exit status and output hashes. `--limit` caps the number of invocations and rejects duplicate tasks. A valid trial has exit code 0 and the exact expected stdout (no extra narrative).

Example bounded smoke invocation:

```bash
PYTHONPATH=. python3 scripts/harness_live_trial.py \
  --provider nous --model MiniMax-M2.7 --timeout 65 --seed 21 \
  --tasks sum gcd --out /tmp/hermes-harness-v2-smoke.json
```

The explicit model/provider flags request configuration but **do not prove** which model actually responded. Neither token usage nor price, per-invocation `AGENTS.md` injection, concurrent machine load, model RNG seed, or restart behavior is independently attested. This is an experimental harness runner, not a causal harness-effect study. The next research gate requires all these confounds to be instrumented before production claims or a larger paid campaign. The 2026-11-16 pilot findings are in `experiments/harness/20261116_combined.json`.

## 20-task stress trial: terminated because the host was not suitable

The sequential 40-invocation attempt using an explicit model request and a **20-second** per-invocation timeout was stopped after **17 of 40** observations. The resource preflight inspected the same machine and failed (`HIGH_LOAD`, `SWAP_PRESSURE`): four CPUs, one-minute load ~10.53, swap usage ~77.2%. This run is **invalid for harness effectiveness** and incomplete, not a 40-trial dataset. The incomplete observations, source-checkpoint hash and preflight evidence are preserved in `experiments/harness/20261116_full20_aborted.json`. Never count the remaining 23 unrun jobs as failures or wins.

The new `scripts/harness_preflight.py` refuses to start a checkpointed experiment if the Linux host exceeds its load/swap thresholds or lacks memory headroom; this only checks resource availability, not independent workload isolation. `scripts/harness_batch_runner.py` is deliberately fail-closed on failed preflight. A fresh future controlled run must use a new output path, with sufficient wall-clock allowance calibrated from idle startup timings, model/provider routing evidence, independent rules-injection witness, and adequate replicated trials. The checkpoint resume mechanism is operational recovery, **not** statistical equivalence across different host environments.
