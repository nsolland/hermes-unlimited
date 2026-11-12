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
