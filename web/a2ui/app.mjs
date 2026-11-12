import {renderA2UISurface} from './renderer.mjs';
const payload=document.getElementById('payload'), status=document.getElementById('message'),mount=document.getElementById('surface');
function render(){try{if(new TextEncoder().encode(payload.value).length>65536)throw new Error('MESSAGE_TOO_LARGE');const data=JSON.parse(payload.value);renderA2UISurface(data,mount);status.textContent='Rendered validated read-only surface.';}catch(error){mount.replaceChildren();status.textContent='Rejected A2UI message: '+error.message;}}
document.getElementById('render').addEventListener('click',render);
document.getElementById('file').addEventListener('change',async event=>{const file=event.target.files?.[0];if(!file)return;if(file.size>65536){status.textContent='Rejected: file too large';return;}payload.value=await file.text();render();});
