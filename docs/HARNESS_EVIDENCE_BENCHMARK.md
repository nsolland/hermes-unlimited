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
