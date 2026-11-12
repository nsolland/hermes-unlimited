import { App } from '@modelcontextprotocol/ext-apps';
import { renderA2UISurface } from '../../web/a2ui/renderer.mjs';
const mount = document.getElementById('surface');
const status = document.getElementById('status');
function show(result) {
  try {
    if (result?.isError) throw Error('HOST_TOOL_ERROR');
    const raw = result?.structuredContent?.a2ui ?? result?.content?.find(item => item.type === 'text')?.text;
    if (!raw) throw Error('NO_A2UI_MESSAGE');
    const value = typeof raw === 'string' ? JSON.parse(raw) : raw;
    renderA2UISurface(value, mount);
    status.textContent = 'Hermes scoped result displayed.';
  } catch (error) {
    mount.replaceChildren();
    status.textContent = 'A2UI rejected: ' + error.message;
  }
}
const app = new App({name:'Hermes Unlimited A2UI',version:'0.1.0'});
app.ontoolresult = show;
async function refresh(name, args={}) {
  mount.replaceChildren();
  status.textContent = 'Refreshing…';
  try {
    show(await app.callServerTool({name,arguments:args}));
  } catch {
    mount.replaceChildren();status.textContent = 'Refresh denied or unavailable';
  }
}
document.getElementById('refresh').addEventListener('click',()=>refresh('hermes_a2ui_companies'));
document.getElementById('requests').addEventListener('click',()=>{
 const company_id=document.getElementById('company').value;
 if(!/^[a-z][a-z0-9-]{1,63}$/.test(company_id)){status.textContent='Invalid company ID';mount.replaceChildren();return;}
 refresh('hermes_a2ui_requests',{company_id});
});
app.connect().catch(() => {mount.replaceChildren();status.textContent='MCP host unavailable';});
