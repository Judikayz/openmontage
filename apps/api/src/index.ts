import { encryptSecret, decryptSecret } from './crypto';
import { routeJob } from './routing';
import type { Env, JobInput } from './types';
const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json','access-control-allow-origin':'*','access-control-allow-headers':'authorization,content-type,x-worker-callback-token','access-control-allow-methods':'GET,POST,PUT,DELETE,OPTIONS'}});
const now=()=>new Date().toISOString(); const id=()=>crypto.randomUUID();
function auth(req:Request,env:Env){return req.headers.get('authorization')===`Bearer ${env.APP_AUTH_TOKEN}`;}
async function dispatchGitHub(env:Env,jobId:string,tool:string){
 if(!env.GITHUB_TOKEN||!env.GITHUB_OWNER||!env.GITHUB_REPO) throw new Error('GitHub dispatch is not configured');
 const url=`https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/actions/workflows/dispatch-job.yml/dispatches`;
 const r=await fetch(url,{method:'POST',headers:{authorization:`Bearer ${env.GITHUB_TOKEN}`,'content-type':'application/json','accept':'application/vnd.github+json','x-github-api-version':'2022-11-28','user-agent':'omcs-control-plane'},body:JSON.stringify({ref:'main',inputs:{job_id:jobId,tool}})});
 if(!r.ok) throw new Error(`GitHub dispatch failed (${r.status}): ${await r.text()}`);
}
async function createJob(env:Env,input:JobInput){
 if(!input.tool||!input.payload||typeof input.payload!=='object') throw new Error('tool and object payload are required');
 const provider=routeJob(input), jobId=id(), ts=now();
 if(input.idempotencyKey){const old=await env.DB.prepare('SELECT id,status,provider FROM jobs WHERE idempotency_key=?').bind(input.idempotencyKey).first<any>();if(old)return old;}
 await env.DB.prepare('INSERT INTO jobs(id,workflow_id,status,provider,tool,payload_json,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)').bind(jobId,input.workflowId??null,'queued',provider,input.tool,JSON.stringify(input.payload),input.idempotencyKey??null,ts,ts).run();
 try { if(provider==='github') await dispatchGitHub(env,jobId,input.tool); else await dispatchKaggle(env,jobId,input); await env.DB.prepare('UPDATE jobs SET status=?,updated_at=? WHERE id=?').bind(provider==='github'?'dispatched':'submitted',now(),jobId).run(); }
 catch(e){await env.DB.prepare('UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=?').bind('failed',String(e),now(),jobId).run();throw e;}
 return {id:jobId,status:provider==='github'?'dispatched':'submitted',provider,tool:input.tool};
}
async function dispatchKaggle(env:Env,jobId:string,input:JobInput){
 const row=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='kaggle'").first<any>();
 if(!row) throw new Error('Kaggle credentials are not configured in Settings');
 const credentials=JSON.parse(await decryptSecret(row.ciphertext,row.iv,env.ENCRYPTION_KEY));
 const body={jobId,tool:input.tool,payload:input.payload,kaggle:credentials};
 const endpoint=(input.payload as any).kaggleDispatcherUrl;
 if(!endpoint) throw new Error('Kaggle dispatch requires a configured secure dispatcher URL in job payload; see docs/KAGGLE.md');
 const r=await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json','x-worker-callback-token':env.WORKER_CALLBACK_TOKEN??''},body:JSON.stringify(body)});
 if(!r.ok) throw new Error(`Kaggle dispatcher rejected job (${r.status})`);
}
async function handle(req:Request,env:Env){
 if(req.method==='OPTIONS')return new Response(null,{status:204,headers:{'access-control-allow-origin':'*','access-control-allow-headers':'authorization,content-type,x-worker-callback-token','access-control-allow-methods':'GET,POST,PUT,DELETE,OPTIONS'}});
 const url=new URL(req.url), path=url.pathname;
 if(path==='/health')return json({ok:true,service:'omcs-api'});
 if(path.startsWith('/callback/')){if(req.headers.get('x-worker-callback-token')!==env.WORKER_CALLBACK_TOKEN)return json({error:'Unauthorized'},401);const jobId=path.split('/').pop()!;const b=await req.json<any>();await env.DB.prepare('UPDATE jobs SET status=?,result_json=?,error=?,updated_at=? WHERE id=?').bind(b.status,b.result?JSON.stringify(b.result):null,b.error??null,now(),jobId).run();return json({ok:true});}
 if(!auth(req,env))return json({error:'Unauthorized'},401);
 try {
  if(path==='/api/workflows'&&req.method==='GET'){const r=await env.DB.prepare('SELECT * FROM workflows ORDER BY updated_at DESC').all();return json(r.results);}
  if(path==='/api/workflows'&&req.method==='POST'){const b=await req.json<any>();if(!b.name||!b.config)throw new Error('name and config required');const wid=id(),ts=now();await env.DB.prepare('INSERT INTO workflows(id,name,config_json,created_at,updated_at) VALUES(?,?,?,?,?)').bind(wid,b.name,JSON.stringify(b.config),ts,ts).run();return json({id:wid,name:b.name,config:b.config},201);}
  if(path.startsWith('/api/workflows/')){const wid=path.split('/').pop()!;if(req.method==='DELETE'){await env.DB.prepare('DELETE FROM workflows WHERE id=?').bind(wid).run();return json({ok:true});}if(req.method==='PUT'){const b=await req.json<any>();await env.DB.prepare('UPDATE workflows SET name=?,config_json=?,updated_at=? WHERE id=?').bind(b.name,JSON.stringify(b.config),now(),wid).run();return json({ok:true});}}
  if(path==='/api/jobs'&&req.method==='POST')return json(await createJob(env,await req.json<JobInput>()),202);
  if(path==='/api/jobs'&&req.method==='GET'){const r=await env.DB.prepare('SELECT id,workflow_id,status,provider,tool,error,created_at,updated_at FROM jobs ORDER BY created_at DESC LIMIT 100').all();return json(r.results);}
  if(path.startsWith('/api/jobs/')){const jid=path.split('/').pop()!;const r=await env.DB.prepare('SELECT * FROM jobs WHERE id=?').bind(jid).first<any>();return r?json({...r,payload_json:undefined,result_json:r.result_json?JSON.parse(r.result_json):null}):json({error:'Not found'},404);}
  if(path==='/api/secrets'&&req.method==='GET'){const r=await env.DB.prepare('SELECT provider,updated_at FROM secrets').all();return json(r.results);}
  if(path==='/api/secrets'&&req.method==='POST'){const b=await req.json<any>();if(!b.provider||!b.value)throw new Error('provider and value required');const enc=await encryptSecret(JSON.stringify(b.value),env.ENCRYPTION_KEY);await env.DB.prepare('INSERT INTO secrets(id,provider,ciphertext,iv,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(provider) DO UPDATE SET ciphertext=excluded.ciphertext,iv=excluded.iv,updated_at=excluded.updated_at').bind(id(),b.provider,enc.ciphertext,enc.iv,now()).run();return json({provider:b.provider,saved:true});}
  if(path==='/api/assets'&&req.method==='POST'){const b=await req.json<any>();const key=`uploads/${id()}/${String(b.name??'asset').replace(/[^a-zA-Z0-9._-]/g,'_')}`;const bytes=Uint8Array.from(atob(b.base64),c=>c.charCodeAt(0));await env.ASSETS.put(key,bytes,{httpMetadata:{contentType:b.contentType??'application/octet-stream'}});await env.DB.prepare('INSERT INTO assets(id,object_key,content_type,size,metadata_json,created_at) VALUES(?,?,?,?,?,?)').bind(id(),key,b.contentType??null,bytes.length,JSON.stringify({name:b.name}),now()).run();return json({key,size:bytes.length},201);}
  if(path.startsWith('/api/assets/')){const key=decodeURIComponent(path.slice('/api/assets/'.length));const obj=await env.ASSETS.get(key);if(!obj)return json({error:'Not found'},404);return new Response(obj.body,{headers:{'content-type':obj.httpMetadata?.contentType??'application/octet-stream','cache-control':'private, max-age=60'}});}
  if(path==='/api/schedules'&&req.method==='GET'){const r=await env.DB.prepare('SELECT * FROM schedules ORDER BY next_run_at').all();return json(r.results);}
  if(path==='/api/schedules'&&req.method==='POST'){const b=await req.json<any>();if(!b.workflowId||!b.nextRunAt||!b.cron)throw new Error('workflowId, cron and nextRunAt required');const sid=id();await env.DB.prepare('INSERT INTO schedules(id,workflow_id,cron,timezone,enabled,next_run_at,created_at) VALUES(?,?,?,?,1,?,?)').bind(sid,b.workflowId,b.cron,b.timezone??'Africa/Lagos',b.nextRunAt,now()).run();return json({id:sid},201);}
  if(path==='/api/integrations/test'&&req.method==='POST'){const b=await req.json<any>();if(b.provider==='telegram'){const s=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='telegram'").first<any>();if(!s)throw new Error('Telegram is not configured');const v=JSON.parse(await decryptSecret(s.ciphertext,s.iv,env.ENCRYPTION_KEY));const r=await fetch(`https://api.telegram.org/bot${v.botToken}/getMe`);return json({ok:r.ok});}return json({ok:false,error:'Connectivity test not implemented for this provider'},400);}
  return json({error:'Not found'},404);
 }catch(e){return json({error:String(e instanceof Error?e.message:e)},400);}
}
export default {fetch:handle,async scheduled(_event:ScheduledController,env:Env,ctx:ExecutionContext){ctx.waitUntil(runScheduler(env));}};
async function runScheduler(env:Env){const due=await env.DB.prepare('SELECT * FROM schedules WHERE enabled=1 AND next_run_at<=? LIMIT 25').bind(now()).all<any>();for(const s of due.results??[]){const lease=`schedule:${s.id}:${s.next_run_at}`;try{await env.DB.prepare('UPDATE schedules SET next_run_at=? WHERE id=? AND next_run_at=?').bind(new Date(Date.now()+5*60*1000).toISOString(),s.id,s.next_run_at).run();const wf=await env.DB.prepare('SELECT * FROM workflows WHERE id=?').bind(s.workflow_id).first<any>();if(wf){const c=JSON.parse(wf.config_json);await createJob(env,{workflowId:wf.id,tool:c.tool??'workflow',compute:c.compute??'automatic',requiresGpu:!!c.requiresGpu,payload:c,idempotencyKey:lease});}}catch(e){console.error('schedule dispatch failed',s.id,String(e));}}}
