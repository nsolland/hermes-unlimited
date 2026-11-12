/* Hermes Unlimited: deterministic read-only A2UI v1.0 Basic Catalog subset.
 * Never execute A2UI functions, event payloads, expressions, or HTML.
 */
const CATALOG = 'https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json';
const ID = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
const MAX_BYTES = 65536;
const FIELDS = Object.freeze({
  Column: ['id','component','children'],
  Row: ['id','component','children'],
  Card: ['id','component','child'],
  Text: ['id','component','text'],
});
const assert = (ok, reason) => { if (!ok) throw new Error(reason); };
const sameKeys = (obj, keys) => Object.keys(obj).length === keys.length && keys.every(k => Object.hasOwn(obj, k));

export function validateSurface(message) {
  assert(message && typeof message === 'object' && !Array.isArray(message), 'INVALID_MESSAGE');
  assert(sameKeys(message, ['version','createSurface']) && message.version === '1.0', 'UNSUPPORTED_MESSAGE');
  const data = message.createSurface;
  assert(data && typeof data === 'object' && !Array.isArray(data), 'INVALID_SURFACE');
  assert(sameKeys(data, ['surfaceId','catalogId','components','dataModel','sendDataModel']), 'INVALID_FIELDS');
  assert(typeof data.surfaceId === 'string' && ID.test(data.surfaceId), 'INVALID_ID');
  assert(data.catalogId === CATALOG && data.sendDataModel === false, 'CATALOG_OR_EXPORT_DENIED');
  assert(data.dataModel && typeof data.dataModel === 'object' && !Array.isArray(data.dataModel) && Object.keys(data.dataModel).length === 0, 'DATA_MODEL_DENIED');
  const nodes = data.components;
  assert(Array.isArray(nodes) && nodes.length > 0 && nodes.length <= 256, 'INVALID_COMPONENT_COUNT');
  const byId = new Map();
  for (const node of nodes) {
    assert(node && typeof node === 'object' && !Array.isArray(node), 'INVALID_COMPONENT');
    assert(typeof node.id === 'string' && ID.test(node.id), 'INVALID_COMPONENT_ID');
    assert(Object.hasOwn(FIELDS, node.component), 'COMPONENT_DENIED');
    assert(sameKeys(node, FIELDS[node.component]), 'UNSAFE_COMPONENT_FIELDS');
    assert(!byId.has(node.id), 'DUPLICATE_COMPONENT_ID');
    if (node.component === 'Text') assert(typeof node.text === 'string', 'INVALID_TEXT');
    if (node.component === 'Column' || node.component === 'Row') assert(Array.isArray(node.children), 'INVALID_CHILDREN');
    byId.set(node.id, node);
  }
  assert(byId.has('root'), 'MISSING_ROOT');
  const visiting = new Set();
  const visited = new Set();
  function walk(id, depth) {
    assert(depth <= 256 && !visiting.has(id), 'CYCLIC_COMPONENTS');
    assert(byId.has(id), 'UNKNOWN_COMPONENT_REFERENCE');
    assert(!visited.has(id), 'SHARED_COMPONENT_REFERENCE');
    visiting.add(id);
    const node = byId.get(id);
    const children = node.component === 'Card' ? [node.child] : (node.children ?? []);
    for (const child of children) {
      assert(typeof child === 'string', 'INVALID_CHILD_REFERENCE');
      walk(child, depth + 1);
    }
    visiting.delete(id);
    visited.add(id);
  }
  walk('root', 0);
  assert(visited.size === nodes.length, 'ORPHAN_COMPONENTS');
  assert(new TextEncoder().encode(JSON.stringify(message)).length <= MAX_BYTES, 'MESSAGE_TOO_LARGE');
  return byId;
}

export function renderA2UISurface(message, mount) {
  assert(mount && typeof mount.replaceChildren === 'function' && mount.ownerDocument, 'INVALID_MOUNT');
  // Validate the entire tree before changing the displayed surface.
  const nodes = validateSurface(message);
  const doc = mount.ownerDocument;
  function build(id) {
    const node = nodes.get(id);
    let element;
    switch (node.component) {
      case 'Text':
        element = doc.createElement(id === 'heading' ? 'h2' : 'p');
        element.textContent = node.text; // Never HTML, script, or Markdown.
        break;
      case 'Column':
        element = doc.createElement('section');
        element.className = 'a2ui-column';
        for (const child of node.children) element.appendChild(build(child));
        break;
      case 'Row':
        element = doc.createElement('div');
        element.className = 'a2ui-row';
        for (const child of node.children) element.appendChild(build(child));
        break;
      case 'Card':
        element = doc.createElement('article');
        element.className = 'a2ui-card';
        element.appendChild(build(node.child));
        break;
    }
    return element;
  }
  const root = build('root');
  root.dataset.a2uiSurfaceId = message.createSurface.surfaceId;
  mount.replaceChildren(root);
  return root;
}
