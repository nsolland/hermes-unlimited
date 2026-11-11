# Public reusable components

These modules are bundled in the public repository under Apache-2.0.
They are optional; no private service, customer data or credentials are bundled.
All tests are offline except where the user explicitly supplies a local backend.

## Read-only diagnostics

```bash
python -m unlimited.public_doctor
```

Checks Python, manifest, plugin entrypoint and whether the Hermes binary is on PATH.
It **does not** prove live Hermes acceptance or tenant identity.

## Local Socratic Council (actual model execution)

Requires locally running [Ollama](https://github.com/ollama/ollama) with models
installed. The CLI invokes `/api/chat` at a **loopback-only** origin. Its role
prompts are independent in the first round, followed by blind critiques and
synthesis. It produces a SHA-256 digest and preserves dissent.

Create `answers.json`:

```json
{
  "clarification": "Evaluate a concrete product launch.",
  "purpose": "Find a repeatable customer benefit.",
  "assumptions": "Customers will accept the integration.",
  "evidence": "A bounded pilot exists; market evidence is incomplete.",
  "alternatives": "Partner, build, postpone, or do nothing.",
  "consequences": "Customers, operators and maintainers bear costs.",
  "falsification": "A pilot fails on agreed acceptance criteria."
}
```

Run:

```bash
python -m unlimited.council_cli --question "Should we launch?" \
  --answers-json answers.json \
  --member explorer=llama3.2 --member skeptic=qwen2.5 \
  --chair llama3.2
```

Change model IDs to locally installed models. Separate roles do not by
themselves prove independent model families, training data or judgment.
The CLI does not initiate external effects, and its conclusion is advisory.
A real-model smoke test requires the named local models.

## Ghost draft adapter

A clean stdlib HTTP integration with [Ghost Admin API](https://ghost.org/docs/admin-api/).
Ghost itself is not vendored. Supply a trusted Ghost origin and an Admin API key
in the calling application, e.g. from a profile-scoped secret manager. The
adapter does not read secrets from disk or environment by itself.

```python
from unlimited.ghost_adapter import GhostAdmin

client = GhostAdmin("https://example.org", trusted_admin_key)
draft = client.create_draft("Title", "<p>Content</p>")
readback = client.read_post(draft["id"])
assert readback["status"] == "draft"
```

**No automatic publication.** The adapter supports draft creation and
readback only. The upstream Ghost API requires a valid Admin API key. Tests use
a fake transport and do not claim a live Ghost smoke.

## Completion Lite

```python
from unlimited.completion_lite import Task, Observation, ready, assess

tasks = [Task("research"), Task("delivery", ("research",))]
assert ready(tasks, {}) == ("research",)
results = {"research": Observation("COMPLETED", "verified-proof-digest", True)}
assert ready(tasks, results) == ("delivery",)
assert assess(tasks, results)["goal_verified"] is False
```

The module requires the caller to supply independently verified receipts and
does not verify signatures itself. It cannot mark the overarching goal done.
It is a deterministic observation helper, not a worker or an authorization gate.

## Other public components already in repo

- `unlimited/comfyui.py`: live HTTP adapter to ComfyUI with bounded requests.
- `unlimited/creative_tools.py`: profile-owned creative tools.
- `unlimited/screenplay_adapter.py`: deterministic demo packaging and preflight.
- `unlimited/demo_recorder.py` / `demo_pipeline.py`: reproducible offline demos.
- `unlimited/integrations.py`: six third-party *catalog entries*, **not** six working adapters.
- `unlimited/socratic_council.py`: injectable provider-neutral deliberation engine.
- Company/service/Kanban and JustYou public core: see main README.

## External reusable projects — link, don't duplicate

- [Open Agent Contract](https://github.com/nsolland/open-agent-contract): independently maintained public MIT contract.
- [Research Factory](https://github.com/nsolland/research-factory): canonical existing LLM council logic.
- [VALO Platform](https://github.com/nsolland/valo-platform): existing Socratic question set and council roles.
- [Hermes Agent](https://github.com/NousResearch/hermes-agent): upstream agent host.
- [Ghost](https://github.com/TryGhost/Ghost), [ComfyUI](https://github.com/comfyanonymous/ComfyUI), [Postiz](https://github.com/gitroomhq/postiz-app), [VideoLingo](https://github.com/Huanshere/VideoLingo): external upstreams, separately licensed and installed.

Implementation quality should be judged on each adapter's executable path,
tests and actual upstream smoke—not on presence in a catalog.
