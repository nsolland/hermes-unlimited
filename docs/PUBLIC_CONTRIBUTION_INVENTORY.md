# Public contribution inventory — Hermes Unlimited (11 Nov 2026)

This file classifies *what can be shared*, not what is production-ready.
Main is the competition baseline and MUST NOT be modified by this work.
All changes here are on feat/socratic-council pending separate review.

## Already implemented in this public repository
- Hermes Unlimited native core: provider/tenant scoped company, service and task tools; do not confuse bounded synthetic acceptance with general production readiness.
- ComfyUI: real HTTP client, and native render/result tools; requires curated workflow resolver and trusted host-owned scope.
- Screenplay: offline deterministic preflight, bounded capture and verification orchestration; live-browser backend remains separate.
- Socratic Council: deliberation core on this branch; native Hermes tool wiring and live model-client contract require verification before marking ready.
- Local demo recorder and pipeline: bounded demonstrators.

## Registered upstream integrations — NOT live adapters
- open-seo (every-app/open-seo): MCP, SEO research; review upstream SDK and license before implementation.
- postiz (gitroomhq/postiz-app): publishing through official API/CLI; upstream AGPL-3.0. Keep Postiz code separate, implement our own thin API client; check license compliance for any reused code.
- VideoLingo (Huanshere/VideoLingo): local video localization worker; Apache-2.0 upstream.
- Ghost (TryGhost/Ghost): Admin API, CMS publishing and memberships; MIT upstream.
- REA (morluto/rea): optional local analysis MCP/CLI; MIT upstream, only authorized interoperability and analysis.
- ComfyUI (comfyanonymous/ComfyUI): GPL-3.0 upstream, do not copy implementation into our own Apache-2.0 codebase.

## High-value PUBLIC contributions to implement next
1. Real tested Ghost draft/create/readback adapter and mock-server contract tests.
2. Real tested Postiz schedule/readback adapter with official OAuth and idempotency; no token bundling, no copied AGPL source.
3. Open SEO MCP request/response wrapper with source capture and hard failures.
4. VideoLingo submit/status/result worker protocol with file ownership and bounded processing.
5. Shared third-party integration contract suite: transport mocks, scope isolation, redaction, budgets, timeouts, retries, readback, and typed errors.
6. Council host adapter and demos with mock and real model execution, strict label "single-model role diversity" where applicable.
7. Reusable README + install/doctor checks for a clean clone, dependency probing and local green acceptance.
8. Optional OBS/Blender/Screenplay adapters for agent-created demos and media, separately licensed where required.

## Never copy to public without explicit clearance
- Customer/tenant data, sessions, passwords, provider tokens, unpublished pitches and financial records.
- Private Hermes Unlimited operational worker details, internal runtime endpoints, commercial pricing logic or proprietary routing rules.
- HEIMEL Enterprise continuity, authority-specific internals or signing secrets.
- Third-party source files under incompatible terms unless explicitly licensed and attribution obligations satisfied.

## Publication gates
- Own source only; explicit upstream attribution and license metadata.
- Works from a clean public clone without private package dependencies.
- Actual operational API implementation; metadata-only catalog entries labelled as such.
- Local offline tests and at least one real bounded host smoke where possible.
- Clear setup, example, capability and limitation docs.
- No GitHub Actions requirement and no automatic merger into competition main.
