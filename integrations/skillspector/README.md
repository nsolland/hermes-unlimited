# SkillSpector in Hermes — VAIG consumer only

Hermes owns UX, skill installation workflows and customer choices. It does **not** own security risk semantics or a second NVIDIA SkillSpector scanner implementation.

Canonical ownership:

1. A quarantined collector scans version-pinned components with NVIDIA SkillSpector; VALO Platform carries the provisional collector adapter.
2. VAIG owns component risk assessment (`vaig.skill_security`) and emits a non-authoritative, content-bound security finding. `REVIEW_ELIGIBLE` does not mean approved.
3. Hermes consumes the authenticated VAIG signal via `vaig_consumer.py`. An authenticated source, matching SHA-256 and non-authoritative flags are required even to reach `REVIEW_REQUIRED`.
4. Hermes installation approval remains a separate customer-governed workflow. This adapter **cannot** approve installation or activate a skill.
5. REHT owns fresh consequence-time authorization. RACS carries contract bindings, Gateway/AI-PLS mechanically enforce the exclusive effect path, and Veritas records evidence. Scanner/VAIG findings cannot mint permits.

## Current verification boundary

`vaig_consumer.py` is a pure, fail-closed reference intake function. It does not fetch VAIG, authenticate its transport, persist results, bind to Captain's Bridge UX or intercept Hermes installation calls. The `trusted_vaig_origin` argument must be established by the host from independently validated source custody, never from a tool-result claim. No real NVIDIA scanner integration or end-to-end installation test has been completed.

Run contract tests from repository root with:

```sh
python -m unittest discover -s integrations/skillspector -p 'test_vaig_consumer.py'
```

Do not issue an Approved/Verified component badge from this adapter. All green claims require independent install/update tests and downstream assurance evidence.
