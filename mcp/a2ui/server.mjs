/** Read-only Hermes Unlimited MCP Apps bridge.
 * The MCP server retrieves A2UI from the already authenticated LOCAL loopback
 * bridge. The bearer token never enters tool results, UI resources or iframe.
 */
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {registerAppResource, registerAppTool, RESOURCE_MIME_TYPE} from '@modelcontextprotocol/ext-apps/server';
import {McpServer} from '@modelcontextprotocol/sdk/server/mcp.js';
import {StdioServerTransport} from '@modelcontextprotocol/sdk/server/stdio.js';
import {z} from 'zod';
import {validateSurface} from '../../web/a2ui/renderer.mjs';

const RESOURCE='ui://hermes-unlimited/a2ui';
const TOOL='hermes_a2ui_companies';
const VIEW=new URL('./dist/view.html',import.meta.url);

export async function fromLocalBridge({url, token}, args={view:'companies'}) {
  if (!url || !token || token.length<32) throw new Error('TRUSTED_BRIDGE_UNAVAILABLE');
  const base = new URL(url);
  if (base.protocol!=='http:' || base.hostname!=='127.0.0.1' || base.username || base.password || base.search || base.hash) throw new Error('LOOPBACK_REQUIRED');
  const view=args.view ?? 'companies';
  if(!['companies','requests'].includes(view))throw new Error('INVALID_VIEW');
  if(view==='requests' && (typeof args.company_id!=='string' || !/^[a-z][a-z0-9-]{1,63}$/.test(args.company_id)))throw new Error('INVALID_COMPANY_ID');
  if(view==='companies' && Object.hasOwn(args,'company_id'))throw new Error('INVALID_COMPANY_SCOPE');
  const target=new URL('/api/surface',base);
  const query=new URLSearchParams({view,surface_id:view==='companies'?'companies_mcp':'requests_mcp'});
  if(view==='requests')query.set('company_id',args.company_id);
  target.search=query.toString();
  const response=await fetch(target,{headers:{Authorization:`Bearer ${token}`},signal:AbortSignal.timeout(5000),redirect:'error',cache:'no-store'});
  if (!response.ok) throw new Error('SCOPE_OR_BRIDGE_DENIED');
  const text=await response.text();
  if (new TextEncoder().encode(text).length>65536) throw new Error('MESSAGE_TOO_LARGE');
  const value=JSON.parse(text);
  validateSurface(value);
  return value;
}

export function createHermesMcpServer({fetchSurface, htmlReader=()=>readFile(VIEW,'utf8')}={}) {
  if (typeof fetchSurface!=='function') throw new TypeError('TRUSTED_SURFACE_PROVIDER_REQUIRED');
  const server = new McpServer({name:'hermes-unlimited-a2ui',version:'0.1.0'});
  registerAppTool(server,TOOL,{
    title:'Hermes Unlimited companies',
    description:'Read-only JustYou-scoped companies displayed using A2UI 1.0; no execution',
    inputSchema:{},
    _meta:{ui:{resourceUri:RESOURCE}},
  },async ()=>{
    try {
      const data=await fetchSurface();
      validateSurface(data);
      return {content:[{type:'text',text:JSON.stringify(data)}],structuredContent:{a2ui:data}};
    } catch {
      return {isError:true,content:[{type:'text',text:'A2UI bridge unavailable or access denied'}]};
    }
  });
  registerAppTool(server,'hermes_a2ui_requests',{
    title:'Hermes Unlimited requests',
    description:'Read-only JustYou-scoped requests for one company',
    inputSchema:{company_id:z.string().regex(/^[a-z][a-z0-9-]{1,63}$/)},
    _meta:{ui:{resourceUri:RESOURCE}},
  },async ({company_id})=>{
    try {
      const data=await fetchSurface({view:'requests',company_id});
      validateSurface(data);
      return {content:[{type:'text',text:JSON.stringify(data)}],structuredContent:{a2ui:data}};
    } catch {
      return {isError:true,content:[{type:'text',text:'A2UI bridge unavailable or access denied'}]};
    }
  });
  registerAppResource(server,RESOURCE,RESOURCE,{mimeType:RESOURCE_MIME_TYPE},async()=>({
    contents:[{uri:RESOURCE,mimeType:RESOURCE_MIME_TYPE,text:await htmlReader()}],
  }));
  return server;
}

if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  const provider=(args)=>fromLocalBridge({url:process.env.HERMES_A2UI_BRIDGE_URL,token:process.env.HERMES_A2UI_BRIDGE_TOKEN},args);
  await createHermesMcpServer({fetchSurface:provider}).connect(new StdioServerTransport());
}
