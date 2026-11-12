# Hermes Unlimited — MCP Apps / A2UI 1.0 (read-only)

This optional stdio MCP Apps server exposes two read-only tools:

- `hermes_a2ui_companies`: no input, JustYou-scoped company surface
- `hermes_a2ui_requests`: `company_id`, JustYou-scoped request surface

Both tools are linked via `_meta.ui.resourceUri` to the declared
`ui://hermes-unlimited/a2ui` resource, which returns the self-contained,
bundled `text/html;profile=mcp-app` UI. The view receives A2UI results through
MCP Apps `App.ontoolresult`, renders only the validated read-only Text/Column/
Row/Card subset, and refreshes by `App.callServerTool` through the host.
No arbitrary HTML, scripts from A2UI, effects or model-selected authority.

Install and build from this directory:

```
npm ci
npm run build
npm test
```

Launch with a compliant MCP Apps host using **stdio** and scoped environment:

```
HERMES_A2UI_BRIDGE_URL=http://127.0.0.1:<LOCAL_PORT>
HERMES_A2UI_BRIDGE_TOKEN=<EXTERNALLY_PROVISIONED_SECRET>
node server.mjs
```

The upstream `unlimited.a2ui_bridge` process must already be running in a
trusted Hermes host process, injected with its **actual** JustYou-scoped native
`unlimited_a2ui_surface` handler. Supply the bearer token through a trusted
secret environment mechanism, not in configuration committed to Git,
arguments, model output or UI resources. Both processes must be on the same
machine; bridge only binds loopback. The MCP server reads local Hermes data
through this bridge and does **not** implement its own identity verifier.

MCP Apps support is host-dependent; hosts without the MCP UI extension receive
plain text/JSON tool output. The MCP component has been tested via an
in-memory MCP client/transport and self-contained view build, **not** yet
against a live Claude/Gemini/ChatGPT MCP Apps host. It is not a deployed service.
Only read requests are supported; write actions require a separately
verified capability- and identity-scoped dispatcher and replay protection.

References: https://apps.extensions.modelcontextprotocol.io/api/documents/overview.html
and https://a2ui.org/guides/a2ui-in-mcp-apps/ .
