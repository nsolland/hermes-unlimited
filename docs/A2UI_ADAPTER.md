# A2UI 1.0 presentation adapter (experimental)

The public Hermes Unlimited plugin now includes a bounded **read-only** A2UI 1.0
message builder at `unlimited/a2ui_adapter.py`. It is intentionally not a
renderer, browser/MCP transport, task executor, or authority grant.

The host supplies its trusted JustYou verifier when constructing
`ProviderStore`. The adapter reads tenant-scoped companies or requests through
that store and returns version 1.0 `createSurface` envelopes from the official
A2UI Basic Catalog. No caller-supplied `verified` flags are accepted.

Example:

```python
from unlimited.a2ui_adapter import company_surface, encode_jsonl
from unlimited.runtime import ProviderStore

# verify_identity must be a trusted JustYou host callback.
store = ProviderStore(database_path, verify_identity)
message = company_surface(store, provider_id, tenant_id, trusted_identity,
                          surface_id="companies_01")
wire = encode_jsonl([message])
# Send wire to a registered A2UI 1.0 renderer via the host's ordered transport.
```

Properties:
- Explicit v1.0 envelope, Basic Catalog ID, root component and adjacency list.
- Fixed component allowlist: Text, Column, Row and Card; no HTML or JS.
- Strict surface IDs, component IDs, references, JSON and 64-KiB message bound.
- No interactive actions, renderer RPC, unsolicited effects or user-triggered
  execution. Actions need a separate authenticated, capability-scoped dispatcher.
- `sendDataModel` is false and the data model is empty; rendered labels are
  intentionally restricted to company names and request identifiers/states.
- The adapter does not independently prove full A2UI schema compliance. Its
  validator covers only the outgoing read-only subset generated here.

Local validation: `python -m unittest tests.test_a2ui_adapter -v`

Still required before an interactive Captain's Bridge release:
1. Pin upstream A2UI JSON schemas and validate envelopes with its official validator.
2. Mount a real React, SwiftUI or MCP Apps renderer and exercise the wire format.
3. Implement a separate authenticated, JustYou-bound event dispatcher with
   tenant/capability checks, replay protection and negative tests.
4. Run the local full suite, exact-SHA smoke, and cross-tenant live acceptance.

Reference: https://a2ui.org/specification/v1.0-a2ui/

## Native Hermes tool registration

The plugin registers `unlimited_a2ui_surface` through the existing
`register_company_tools` entrypoint. The host calls it with:

- `{"view":"companies","surface_id":"companies_1"}`
- `{"view":"requests","company_id":"acme","surface_id":"requests_1"}`

It returns a validated A2UI 1.0 envelope as a JSON tool result. Provider,
tenant and trusted JustYou identity are resolved only from the Hermes host
scope, never from tool arguments. The tool does not start tasks or execute any
effects, and is not yet an automatic renderer/MCP Apps transport. The host must
still register a renderer and explicitly forward returned envelopes to it.

Verified on the Mac worker against exact SHA with `python3 -m unittest discover
-s tests -q`: 102 tests, 1 skipped, 0 errors. Both generated createSurface
examples were also validated against the official A2UI 1.0 `agent_to_renderer`,
`common_types` and Basic Catalog JSON schemas fetched on 12 November 2026.
The upstream schema checks are currently an external acceptance check, not
an offline dependency of the repository tests.
