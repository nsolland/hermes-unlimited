# Live Meeting Engine (early integration)

This is the first isolated Hermes Unlimited meeting **orchestration core**, not a live Teams or Google Meet integration.

## Scope

- Detects Teams and Google Meet by exact HTTPS hostname.
- Uses a provider-neutral transport protocol: `join`, `speak`, `leave`.
- Isolates sessions by tenant and company.
- Requires explicit operator approval to join or speak.
- Ingests transcripts strictly as **untrusted data**, never agent instructions.
- Converts meeting follow-up into **unauthorized proposals**, not auto-executed effects.
- Returns a structured session report with `external_work_verified: false`.

## Current limits

All tests use a fake meeting adapter. No real meetings are joined; no real audio is streamed; no customer is contacted. Session storage is in memory, and approvals are caller-provided booleans suitable only for isolated prototyping. **Production adapters MUST enforce server-side, identity-bound, scoped and auditable authorization**, durable storage, consent/participant notification, timeout and reconnection behavior, output voice, robust identity verification, and recipient policies.

## Next integrations

1. Reuse existing Hermes Google Meet capability when verified available.
2. Integrate Teams through a supported provider such as Recall.ai, or a native adapter where permitted.
3. Bind trusted JustYou provider/tenant identity; never allow a caller to claim it.
4. Wire authorized task proposals to existing Hermes Unlimited Kanban dispatch and harvest, maintaining approval and independent evidence boundaries.
5. Connect The Thread to company-scoped memory and Captain's Bridge to the operator overview.

Run the focused synthetic tests locally: `python -m unittest tests.test_meeting_engine -v`.

No GitHub Actions requirement.
