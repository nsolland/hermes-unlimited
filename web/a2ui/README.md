# Hermes A2UI 1.0 read-only browser viewer

Static browser preview for the Hermes tool `unlimited_a2ui_surface`.

Start with `python3 -m http.server 8765 --bind 127.0.0.1` from the repo root;
open `http://127.0.0.1:8765/web/a2ui/`. Paste the JSON result from the
authenticated Hermes native tool or select a local JSON file. There is no
remote API and no credential storage. Do not bind this preview to a public
interface, and do not publish customer A2UI responses as static files.

Only the validated `createSurface` subset (Text, Column, Row, Card) is rendered.
`sendDataModel` must be false and `dataModel` empty. Function calls, actions,
HTML, custom components, bindings and updateDataModel are not supported.
Validation precedes any DOM mutation; text is written using `textContent`.

**Not yet full A2UI renderer interoperability:** the current released React/Lit
npm packages lack explicit v1.0 entry points. This viewer deliberately uses the
verified v1.0 JSON message shape without depending on those older renderers.
The host must still forward tool results; no automatic Hermes-to-browser
channel, authenticated realtime transport, or write-capable dispatch exists.

## Authenticated localhost bridge (operator-hosted)

`unlimited.a2ui_bridge.make_bridge` binds only `127.0.0.1` and accepts the
**already registered, JustYou-scoped** Hermes native tool handler as a callback.
This is not a replacement for Hermes/JustYou, and never takes provider or tenant
parameters from a browser. Token generation and lifecycle belong to the host.
The browser sends an independently generated bearer token in the Authorization
header, never in URL parameters, localStorage, cookies or rendered A2UI JSON.

Example **inside a trusted Hermes host process** after plugin tool registration:

```python
from threading import Thread
from unlimited.a2ui_bridge import make_bridge, new_transport_token

# `registered_hermes_a2ui_handler` must be the actual tool handler
# registered under `unlimited_a2ui_surface` in the trusted Hermes session.
# Do not replace this with a client-side verifier or an unrestricted store.
token = new_transport_token()
server = make_bridge(registered_hermes_a2ui_handler, token=token)
Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}/"
# Hand `token` to the local human operator out of band. Never log it or
# include it in agent output, HTTP URLs, or public files.
# On session shutdown: server.shutdown(); server.server_close()
```

This implementation provides an authenticated **read-only** GET endpoint at
`/api/surface`, with `view`, `surface_id`, and optional `company_id` only.
Every request invokes the host's native handler, which re-checks the trusted
JustYou scope. It fails closed on unavailable native identity, unsupported
scope, unsafe A2UI and invalid or missing bearer tokens. No CORS is enabled.

The bridge is opt-in: it does not auto-start when Hermes starts. To use it in a
production Hermes host, a supported host integration must own registration,
secrets, process lifecycle and user-facing session launch. Do **not** run this
on an external address or place a public reverse proxy in front of it.

MCP Apps are a separate, not-yet-implemented integration: they require a
`ui://` resource, `_meta.ui.resourceUri` on the tool, host capability
negotiation and sandboxed iframe messaging. A loopback HTTP preview does not
satisfy those MCP requirements.
