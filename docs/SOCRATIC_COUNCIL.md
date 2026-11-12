# Socratic Council (optional, evidence-only)

Hermes Unlimited's council adapter is in `unlimited/socratic_council.py`. It
reuses the established VALO Socratic protocol and the Research Factory LLM
Council pattern rather than introducing a separate authorization mechanism.

Flow: seven required Socratic answers -> independent expert opinions ->
anonymous candidate critiques -> chair synthesis preserving dissent and
uncertainty. Output includes a content digest and `execution_authority=false`.
A council result is advisory, never a permit, customer instruction or proof
that an external effect occurred.

The host injects async model callables, for example from AI Bridge; nothing
in this module selects provider credentials or invokes external execution.
Its opinion phase is concurrent, while critique is anonymous by candidate
label. Anonymity of labels is not proof of independence of provider, model,
training data or judge. The host must track model family and provider
diversity and keep original source evidence externally.

This module is not automatically registered as a public Hermes tool. Enabling
a live council requires host-provided model clients, tenant-scoped identity,
cost/time budgets and durable evidence capture. The present scope is the
reusable, locally testable decision-support core.

Run: `python -m unittest discover -s tests -p test_socratic_council.py -v`

Related implementations:
- `nsolland/valo-platform/src/valo_platform/decision_governance/socratic.py`
- `nsolland/valo-platform/src/valo_platform/decision_governance/council.py`
- `nsolland/research-factory/factory_runtime/llm_council.py`
