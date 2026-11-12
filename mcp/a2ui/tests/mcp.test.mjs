import {test} from 'node:test';
import {parse} from 'parse5';
import assert from 'node:assert/strict';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {InMemoryTransport} from '@modelcontextprotocol/sdk/inMemory.js';
import {createHermesMcpServer,fromLocalBridge} from '../server.mjs';

const surface={version:'1.0',createSurface:{surfaceId:'companies_mcp',catalogId:'https://a2ui.org/specification/v1_0/catalogs/basic/catalog.json',components:[{id:'root',component:'Column',children:['heading']},{id:'heading',component:'Text',text:'Hermes Unlimited'}],dataModel:{},sendDataModel:false}};
async function withClient(fetchSurface,fn){
 const server=createHermesMcpServer({fetchSurface,htmlReader:async()=>'<html>Hermes A2UI</html>'});
 const client=new Client({name:'hermes-a2ui-test',version:'1.0.0'});
 const [a,b]=InMemoryTransport.createLinkedPair();
 await Promise.all([server.connect(a),client.connect(b)]);
 try{await fn(client);}finally{await client.close();await server.close();}
}
test('MCP tool and UI resource registered with correct metadata',async()=>{
 await withClient(async()=>surface,async(client)=>{
  const tools=await client.listTools();
  assert.equal(tools.tools.length,2);
  assert.equal(tools.tools[0].name,'hermes_a2ui_companies');
  assert.equal(tools.tools[0]._meta.ui.resourceUri,'ui://hermes-unlimited/a2ui');
  const resources=await client.listResources();
  assert.equal(resources.resources[0].uri,'ui://hermes-unlimited/a2ui');
  const app=await client.readResource({uri:'ui://hermes-unlimited/a2ui'});
  assert.match(app.contents[0].mimeType,/text\/html;profile=mcp-app/);
  assert.match(app.contents[0].text,/Hermes A2UI/);
  const result=await client.callTool({name:'hermes_a2ui_companies',arguments:{}});
  assert.deepEqual(result.structuredContent.a2ui,surface);
  const requests=await client.callTool({name:'hermes_a2ui_requests',arguments:{company_id:'acme'}});
  assert.deepEqual(requests.structuredContent.a2ui,surface);
 });
});
test('MCP server fails closed when provider denies scope',async()=>{
 await withClient(async()=>{throw new Error('JUSTYOU_DENIED')},async(client)=>{
  const result=await client.callTool({name:'hermes_a2ui_companies',arguments:{}});
  assert.equal(result.isError,true);
  assert.doesNotMatch(JSON.stringify(result),/JUSTYOU_DENIED/);
 });
});
test('bridge transport denies external origins and missing secrets',async()=>{
 await assert.rejects(fromLocalBridge({url:'https://external.example',token:'x'.repeat(40)}),/LOOPBACK_REQUIRED/);
 await assert.rejects(fromLocalBridge({url:'http://127.0.0.1:9999',token:'short'}),/TRUSTED_BRIDGE_UNAVAILABLE/);
 await assert.rejects(fromLocalBridge({url:'http://127.0.0.1:9999',token:'x'.repeat(40)},{view:'requests',company_id:'../other'}),/INVALID_COMPANY_ID/);
});

test('MCP backend fetch uses bearer only on loopback and never adds tenant controls',async()=>{
 const {createServer}=await import('node:http');
 let observed;
 const server=createServer((req,res)=>{
   observed={url:req.url,host:req.headers.host,auth:req.headers.authorization};
   res.writeHead(200,{'Content-Type':'application/json'});
   res.end(JSON.stringify(surface));
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try {
   const port=server.address().port;
   const token='correct-local-test-token-abcdef-123456789';
   const result=await fromLocalBridge({url:`http://127.0.0.1:${port}`,token},{view:'requests',company_id:'acme'});
   assert.deepEqual(result,surface);
   assert.equal(observed.auth,'Bearer '+token);
   assert.equal(new URL(observed.url,'http://127.0.0.1').searchParams.get('view'),'requests');
   assert.equal(new URL(observed.url,'http://127.0.0.1').searchParams.get('company_id'),'acme');
   assert.doesNotMatch(observed.url,/token|tenant|provider|identity/);
 } finally {await new Promise(resolve=>server.close(resolve));}
});
test('actual built MCP Apps view is self-contained and linked to UI resource',async()=>{
 const {readFile}=await import('node:fs/promises');
 const html=await readFile(new URL('../dist/view.html',import.meta.url),'utf8');
 assert.match(html,/Hermes Unlimited/);
 assert.match(html,/Refresh companies/);
 assert.match(html,/View requests/);
 const doc=parse(html);
 const scripts=[];
 function collect(node) {if(node.tagName==='script')scripts.push(node);for(const child of node.childNodes??[])collect(child);}
 collect(doc);
 assert.equal(scripts.length,1);
 assert.ok(!scripts[0].attrs.some(x=>x.name==='src'));
 assert.ok(scripts[0].childNodes?.some(x=>x.nodeName==='#text' && x.value.length>20000));
 await withClient(async()=>surface,async(client)=>{
   // Real bundled view, not a mock, is delivered by the MCP resource.
   const serverContent=await readFile(new URL('../dist/view.html',import.meta.url),'utf8');
   const info=await client.listTools();
   assert.equal(info.tools[0]._meta.ui.resourceUri,'ui://hermes-unlimited/a2ui');
   assert.equal(serverContent,html);
 });
});

test('unsafe agent-generated components fail before MCP tool result',async()=>{
 const bad=structuredClone(surface);
 bad.createSurface.components.push({id:'action',component:'Button',action:{event:'write'}});
 await withClient(async()=>bad,async(client)=>{
   const response=await client.callTool({name:'hermes_a2ui_companies',arguments:{}});
   assert.equal(response.isError,true);
   assert.doesNotMatch(JSON.stringify(response),/write/);
 });
});
