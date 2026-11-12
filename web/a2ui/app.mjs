import {renderA2UISurface} from './renderer.mjs';
const payload=document.getElementById('payload'), status=document.getElementById('message'),mount=document.getElementById('surface');
function render(){try{if(new TextEncoder().encode(payload.value).length>65536)throw new Error('MESSAGE_TOO_LARGE');const data=JSON.parse(payload.value);renderA2UISurface(data,mount);status.textContent='Rendered validated read-only surface.';}catch(error){mount.replaceChildren();status.textContent='Rejected A2UI message: '+error.message;}}
document.getElementById('render').addEventListener('click',render);
document.getElementById('file').addEventListener('change',async event=>{const file=event.target.files?.[0];if(!file)return;if(file.size>65536){status.textContent='Rejected: file too large';return;}payload.value=await file.text();render();});

async function loadLive(view) {
  mount.replaceChildren();
  status.textContent='Loading authenticated Hermes surface…';
  const token=document.getElementById('bearer').value;
  const company=document.getElementById('company').value;
  const query=new URLSearchParams({view,surface_id:view==='companies'?'companies_live':'requests_live'});
  if(view==='requests')query.set('company_id',company);
  try {
    if(token.length<32)throw new Error('TOKEN_REQUIRED');
    if(view==='requests' && !/^[a-z][a-z0-9-]{1,63}$/.test(company))throw new Error('INVALID_COMPANY');
    const response=await fetch('/api/surface?'+query,{headers:{Authorization:'Bearer '+token},credentials:'omit',cache:'no-store'});
    if(!response.ok)throw new Error('ACCESS_DENIED_OR_UNAVAILABLE');
    const raw=await response.text();
    if(new TextEncoder().encode(raw).length>65536)throw new Error('MESSAGE_TOO_LARGE');
    const message=JSON.parse(raw);
    renderA2UISurface(message,mount);
    status.textContent='Authenticated Hermes surface rendered.';
  } catch(error) {
    mount.replaceChildren();status.textContent='Bridge rejected: '+error.message;
  }
}
document.getElementById('companies').addEventListener('click',()=>loadLive('companies'));
document.getElementById('requests').addEventListener('click',()=>loadLive('requests'));
