import { encryptSecret, decryptSecret } from './crypto';
import { routeJob, validateToolBranch } from './routing';
import { presignR2Put, presignR2Get, presignR2MultipartPart } from './r2-presign';
import { verifyCloudflareAccess } from './access-auth';
import type { Env, JobInput } from './types';
const json=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status,headers:{'content-type':'application/json','access-control-allow-origin':'null','access-control-allow-headers':'authorization,content-type,x-worker-callback-token,x-model-import-token,cf-access-jwt-assertion','access-control-allow-methods':'GET,POST,PUT,DELETE,OPTIONS'}});
const now=()=>new Date().toISOString(); const id=()=>crypto.randomUUID();
async function auth(req:Request,env:Env){if(env.APP_AUTH_TOKEN&&req.headers.get('authorization')===`Bearer ${env.APP_AUTH_TOKEN}`)return true;if(!env.CF_ACCESS_TEAM_DOMAIN||!env.CF_ACCESS_AUD)return false;return verifyCloudflareAccess(req,env.CF_ACCESS_TEAM_DOMAIN,env.CF_ACCESS_AUD);}
async function getGitHubConfig(env:Env){
 let saved:any=null;
 const row=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='github'").first<any>();
 if(row){try{saved=JSON.parse(await decryptSecret(row.ciphertext,row.iv,env.ENCRYPTION_KEY));}catch{throw new Error('Saved GitHub credential could not be decrypted; save it again in Settings');}}
 const token=typeof saved==='string'?saved:(saved?.token??saved?.accessToken??env.GITHUB_TOKEN);
 const owner=(typeof saved==='object'&&saved?.owner)||env.GITHUB_OWNER;
 const repo=(typeof saved==='object'&&saved?.repo)||env.GITHUB_REPO;
 const ref=(typeof saved==='object'&&saved?.ref)||'main';
 if(!token||!owner||!repo)throw new Error('GitHub is not configured. Save a GitHub token in Settings and set GITHUB_OWNER and GITHUB_REPO as Worker variables, or save token, owner and repo as JSON.');
 return {token,owner,repo,ref};
}
async function githubDispatch(env:Env,workflow:string,inputs:Record<string,string>){
 const gh=await getGitHubConfig(env);
 const url=`https://api.github.com/repos/${gh.owner}/${gh.repo}/actions/workflows/${workflow}/dispatches`;
 const r=await fetch(url,{method:'POST',headers:{authorization:`Bearer ${gh.token}`,'content-type':'application/json','accept':'application/vnd.github+json','x-github-api-version':'2022-11-28','user-agent':'omcs-control-plane'},body:JSON.stringify({ref:gh.ref,inputs})});
 if(!r.ok)throw new Error(`GitHub ${workflow} dispatch failed (${r.status}): ${await r.text()}`);
}
async function dispatchGitHub(_env:Env,jobId:string,tool:string,modelIds:string[]=[]){
 await githubDispatch(_env,'dispatch-job.yml',{job_id:jobId,tool,model_ids:modelIds.join(',')});
}
async function dispatchModelImport(env:Env,modelId:string){
 await githubDispatch(env,'model-import.yml',{model_id:modelId});
}
async function getR2Credentials(env:Env){
 const row=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='r2'").first<any>();
 if(!row) throw new Error('Cloudflare R2 credentials are not configured in Settings');
 const value=JSON.parse(await decryptSecret(row.ciphertext,row.iv,env.ENCRYPTION_KEY));
 for(const k of ['accountId','accessKeyId','secretAccessKey','bucketName']) if(!value[k]) throw new Error(`R2 setting ${k} is missing`);
 if(env.MODEL_BUCKET_NAME&&value.bucketName!==env.MODEL_BUCKET_NAME)throw new Error(`R2 bucket must match the Worker MODELS binding (${env.MODEL_BUCKET_NAME})`);
 return value;
}
function parseHfRepo(value:string){
 let repo=value.trim(); if(repo.startsWith('https://huggingface.co/')) repo=repo.slice('https://huggingface.co/'.length).split(/[?#]/)[0].replace(/\/$/,'');
 if(!/^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(repo)) throw new Error('Use a public Hugging Face model URL or owner/model ID');
 return repo;
}
async function workerAuth(req:Request,env:Env){return !!env.MODEL_IMPORT_WORKER_TOKEN && req.headers.get('x-model-import-token')===env.MODEL_IMPORT_WORKER_TOKEN;}
async function getHFToken(env:Env){const row=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='huggingface'").first<any>();if(!row)return undefined;const v=JSON.parse(await decryptSecret(row.ciphertext,row.iv,env.ENCRYPTION_KEY));return v.token??v.accessToken;}
async function createJob(env:Env,input:JobInput){
 if(!input.tool)throw new Error('tool is required');
 validateToolBranch(input.tool);
 if(!input.payload||typeof input.payload!=='object'||Array.isArray(input.payload)) throw new Error('tool and object payload are required');
 const provider=routeJob(input), jobId=id(), ts=now();
 if(input.idempotencyKey){const old=await env.DB.prepare('SELECT id,status,provider FROM jobs WHERE idempotency_key=?').bind(input.idempotencyKey).first<any>();if(old)return old;}
 await env.DB.prepare('INSERT INTO jobs(id,workflow_id,status,provider,tool,payload_json,idempotency_key,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)').bind(jobId,input.workflowId??null,'queued',provider,input.tool,JSON.stringify(input.payload),input.idempotencyKey??null,ts,ts).run();
 try { if(provider==='github') await dispatchGitHub(env,jobId,input.tool,Array.isArray((input.payload as any).modelIds)?(input.payload as any).modelIds:[]); else await dispatchKaggle(env,jobId,input); await env.DB.prepare('UPDATE jobs SET status=?,updated_at=? WHERE id=?').bind(provider==='github'?'dispatched':'submitted',now(),jobId).run(); }
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
 if(req.method==='OPTIONS')return new Response(null,{status:204,headers:{'access-control-allow-origin':'null','access-control-allow-headers':'authorization,content-type,x-worker-callback-token,x-model-import-token,cf-access-jwt-assertion','access-control-allow-methods':'GET,POST,PUT,DELETE,OPTIONS'}});
 const url=new URL(req.url), path=url.pathname;
 if(path==='/health')return json({ok:true,service:'omcs-api'});
 if(path.startsWith('/callback/')){if(!env.WORKER_CALLBACK_TOKEN||req.headers.get('x-worker-callback-token')!==env.WORKER_CALLBACK_TOKEN)return json({error:'Unauthorized'},401);const jobId=path.split('/').pop()!;const b=await req.json<any>();if(!['completed','failed','running'].includes(b.status))return json({error:'Invalid callback status'},400);if(b.message)await env.DB.prepare('INSERT INTO job_logs(id,job_id,level,message,created_at) VALUES(?,?,?,?,?)').bind(id(),jobId,b.level??'info',String(b.message).slice(0,4000),now()).run();const result=await env.DB.prepare('UPDATE jobs SET status=?,result_json=?,error=?,updated_at=? WHERE id=?').bind(b.status,b.result?JSON.stringify(b.result):null,b.error??null,now(),jobId).run();if(!result.meta?.changes)return json({error:'Job not found'},404);if(b.result?.assetKey){const key=String(b.result.assetKey);const head=await env.MODELS.head(key);if(head)await env.DB.prepare('INSERT OR IGNORE INTO assets(id,object_key,content_type,size,metadata_json,created_at) VALUES(?,?,?,?,?,?)').bind(id(),key,b.result.contentType??'application/octet-stream',head.size,JSON.stringify({name:b.result.fileName??key,jobId}),now()).run();}return json({ok:true});}
 if(path.startsWith('/internal/jobs/')){
  if(!env.WORKER_CALLBACK_TOKEN||req.headers.get('x-worker-callback-token')!==env.WORKER_CALLBACK_TOKEN)return json({error:'Unauthorized'},401);
  const jobId=path.split('/').pop()!;
  if(req.method!=='GET')return json({error:'Method not allowed'},405);
  const job=await env.DB.prepare('SELECT id,status,provider,tool,payload_json FROM jobs WHERE id=?').bind(jobId).first<any>();
  if(!job)return json({error:'Job not found'},404);
  await env.DB.prepare('UPDATE jobs SET status=?,updated_at=? WHERE id=?').bind('running',now(),jobId).run();
  return json({id:job.id,status:'running',provider:job.provider,tool:job.tool,payload:JSON.parse(job.payload_json)});
 }
 if(path==='/internal/assets/download'&&req.method==='GET'){
  if(!env.WORKER_CALLBACK_TOKEN||req.headers.get('x-worker-callback-token')!==env.WORKER_CALLBACK_TOKEN)return json({error:'Unauthorized'},401);
  const key=url.searchParams.get('key');if(!key||key.includes('..'))return json({error:'Valid asset key is required'},400);
  const obj=await env.ASSETS.get(key)??await env.MODELS.get(key);if(!obj)return json({error:'Asset not found'},404);
  return new Response(obj.body,{headers:{'content-type':obj.httpMetadata?.contentType??'application/octet-stream','content-length':String(obj.size),'cache-control':'private, no-store'}});
 }
 if(path==='/internal/assets/upload-url'&&req.method==='POST'){
  if(!env.WORKER_CALLBACK_TOKEN||req.headers.get('x-worker-callback-token')!==env.WORKER_CALLBACK_TOKEN)return json({error:'Unauthorized'},401);
  const b=await req.json<any>();if(!b.name||!b.contentType) return json({error:'name and contentType are required'},400);
  const key=`generated/${id()}/${String(b.name).replace(/[^A-Za-z0-9._-]/g,'_')}`;
  const r2=await getR2Credentials(env);const uploadUrl=await presignR2Put({accountId:r2.accountId,accessKeyId:r2.accessKeyId,secretAccessKey:r2.secretAccessKey,bucket:r2.bucketName,key,expires:900});
  return json({key,uploadUrl,expiresIn:900});
 }
 if(path.startsWith('/internal/models/')){
  if(!(await workerAuth(req,env))) return json({error:'Unauthorized'},401);
  const parts=path.split('/').filter(Boolean), modelId=parts[2], action=parts[3];
  const model=await env.DB.prepare('SELECT * FROM models WHERE id=?').bind(modelId).first<any>();
  if(!model)return json({error:'Model not found'},404);
  if(action==='hf-token'&&req.method==='GET'){const token=await getHFToken(env);return json({token:token??null});}
  if(action==='manifest'&&req.method==='GET'){
   let manifest=model.manifest_json?JSON.parse(model.manifest_json):null;
   if(!manifest){const hfToken=await getHFToken(env);const response=await fetch(`https://huggingface.co/api/models/${model.repo_id}/tree/${encodeURIComponent(model.revision)}?recursive=true&expand=true`,{headers:hfToken?{authorization:`Bearer ${hfToken}`}:{}});if(!response.ok)throw new Error(`Hugging Face manifest request failed (${response.status})`);const entries=await response.json<any[]>();manifest=entries.filter(x=>x.type==='file').map(x=>({path:x.path,size:Number(x.size??0),sha256:typeof x.lfs?.oid==='string'&&x.lfs.oid.startsWith('sha256:')?x.lfs.oid.slice(7):null})).filter(x=>x.size>=0);if(!manifest.length)throw new Error('No model files were found in this repository/revision');const total=manifest.reduce((n:number,x:any)=>n+x.size,0);await env.DB.prepare('UPDATE models SET manifest_json=?,file_count=?,total_bytes=?,status=?,updated_at=? WHERE id=?').bind(JSON.stringify(manifest),manifest.length,total,'downloading',now(),modelId).run();}
   return json({id:modelId,repo_id:model.repo_id,revision:model.revision,files:manifest});
  }
  if(action==='upload-url'&&req.method==='POST'){
   const b=await req.json<any>();const manifest=JSON.parse(model.manifest_json??'[]');if(!manifest.some((f:any)=>f.path===b.path))return json({error:'File is not part of the registered model manifest'},400);
   const r2=await getR2Credentials(env);const key=`models/${modelId}/${String(b.path).split('/').map((x:string)=>x.replace(/[^A-Za-z0-9._-]/g,'_')).join('/')}`;
   const uploadUrl=await presignR2Put({accountId:r2.accountId,accessKeyId:r2.accessKeyId,secretAccessKey:r2.secretAccessKey,bucket:r2.bucketName,key,expires:900});
   const updated=manifest.map((f:any)=>f.path===b.path?{...f,objectKey:key}:f);await env.DB.prepare('UPDATE models SET manifest_json=?,updated_at=? WHERE id=?').bind(JSON.stringify(updated),now(),modelId).run();return json({uploadUrl,key,expiresIn:900});
  }
  if(action==='multipart-init'&&req.method==='POST'){
   const b=await req.json<any>();const manifest=JSON.parse(model.manifest_json??'[]');const file=manifest.find((f:any)=>f.path===b.path);if(!file)return json({error:'File is not part of the model manifest'},400);
   const key=`models/${modelId}/${String(b.path).split('/').map((x:string)=>x.replace(/[^A-Za-z0-9._-]/g,'_')).join('/')}`;
   const upload=await env.MODELS.createMultipartUpload(key);const updated=manifest.map((f:any)=>f.path===b.path?{...f,objectKey:key,multipartUploadId:upload.uploadId}:f);
   await env.DB.prepare('UPDATE models SET manifest_json=?,status=?,updated_at=? WHERE id=?').bind(JSON.stringify(updated),'uploading',now(),modelId).run();return json({key,uploadId:upload.uploadId});
  }
  if(action==='multipart-part-url'&&req.method==='POST'){
   const b=await req.json<any>();const manifest=JSON.parse(model.manifest_json??'[]');const file=manifest.find((f:any)=>f.path===b.path);if(!file?.multipartUploadId||!file.objectKey)return json({error:'Multipart upload not initialized'},400);
   const partNumber=Number(b.partNumber);if(!Number.isInteger(partNumber)||partNumber<1||partNumber>10000)return json({error:'partNumber must be between 1 and 10000'},400);
   const r2=await getR2Credentials(env);const uploadUrl=await presignR2MultipartPart({accountId:r2.accountId,accessKeyId:r2.accessKeyId,secretAccessKey:r2.secretAccessKey,bucket:r2.bucketName,key:file.objectKey,uploadId:file.multipartUploadId,partNumber,expires:900});return json({uploadUrl,partNumber});
  }
  if(action==='multipart-complete'&&req.method==='POST'){
   const b=await req.json<any>();const manifest=JSON.parse(model.manifest_json??'[]');const file=manifest.find((f:any)=>f.path===b.path);if(!file?.multipartUploadId||!file.objectKey)return json({error:'Multipart upload not initialized'},400);
   if(!Array.isArray(b.parts)||!b.parts.length) return json({error:'parts are required'},400);
   const upload=env.MODELS.resumeMultipartUpload(file.objectKey,file.multipartUploadId);const completed=await upload.complete(b.parts.map((p:any)=>({partNumber:Number(p.partNumber),etag:String(p.etag)})));
   const updated=manifest.map((f:any)=>f.path===b.path?{...f,multipartUploadId:null,multipartComplete:true,etag:completed.etag}:f);await env.DB.prepare('UPDATE models SET manifest_json=?,updated_at=? WHERE id=?').bind(JSON.stringify(updated),now(),modelId).run();return json({ok:true,etag:completed.etag});
  }
  if(action==='download-url'&&req.method==='GET'){
   const filePath=url.searchParams.get('path')??'';const manifest=JSON.parse(model.manifest_json??'[]');const file=manifest.find((f:any)=>f.path===filePath);if(!file?.objectKey)return json({error:'Stored model file not found'},404);
   const r2=await getR2Credentials(env);const downloadUrl=await presignR2Get({accountId:r2.accountId,accessKeyId:r2.accessKeyId,secretAccessKey:r2.secretAccessKey,bucket:r2.bucketName,key:file.objectKey,expires:900});return json({downloadUrl,size:file.size,path:file.path});
  }
  if(action==='complete'&&req.method==='POST'){
   const manifest=JSON.parse(model.manifest_json??'[]');let stored=0;for(const f of manifest){if(!f.objectKey)throw new Error(`Upload URL was not requested for ${f.path}`);if(f.multipartUploadId)throw new Error(`Multipart upload is incomplete for ${f.path}`);const head=await env.MODELS.head(f.objectKey);if(!head)throw new Error(`R2 object missing: ${f.path}`);if(f.size&&head.size!==f.size)throw new Error(`Size mismatch for ${f.path}: expected ${f.size}, got ${head.size}`);stored+=head.size;}
   await env.DB.prepare('UPDATE models SET status=?,stored_bytes=?,object_keys_json=?,error=NULL,updated_at=? WHERE id=?').bind('ready',stored,JSON.stringify(manifest.map((f:any)=>f.objectKey)),now(),modelId).run();return json({id:modelId,status:'ready',fileCount:manifest.length,storedBytes:stored});
  }
  if(action==='failed'&&req.method==='POST'){const b=await req.json<any>();await env.DB.prepare('UPDATE models SET status=?,error=?,updated_at=? WHERE id=?').bind('failed',String(b.error??'Import failed').slice(0,2000),now(),modelId).run();return json({ok:true});}
 }
 if(!(await auth(req,env)))return json({error:'Unauthorized'},401);
 try {
  if(path==='/api/projects'&&req.method==='GET'){const r=await env.DB.prepare('SELECT * FROM projects ORDER BY updated_at DESC').all();return json(r.results);}
  if(path==='/api/projects'&&req.method==='POST'){const b=await req.json<any>();if(!b.name)throw new Error('Project name is required');const pid=id(),ts=now();await env.DB.prepare('INSERT INTO projects(id,name,description,settings_json,created_at,updated_at) VALUES(?,?,?,?,?,?)').bind(pid,String(b.name).slice(0,160),String(b.description??''),JSON.stringify(b.settings??{}),ts,ts).run();return json({id:pid,name:b.name},201);}
  if(path.startsWith('/api/projects/')){const pid=path.split('/')[3];if(req.method==='DELETE'){await env.DB.prepare('DELETE FROM projects WHERE id=?').bind(pid).run();return json({ok:true});}if(req.method==='PUT'){const b=await req.json<any>();await env.DB.prepare('UPDATE projects SET name=?,description=?,settings_json=?,updated_at=? WHERE id=?').bind(b.name,b.description??'',JSON.stringify(b.settings??{}),now(),pid).run();return json({ok:true});}}
  if(path==='/api/characters'&&req.method==='GET'){const r=await env.DB.prepare('SELECT * FROM characters ORDER BY updated_at DESC').all();return json((r.results??[]).map((x:any)=>({...x,reference_asset_keys:JSON.parse(x.reference_asset_keys_json),attributes:JSON.parse(x.attributes_json)})));}
  if(path==='/api/characters'&&req.method==='POST'){const b=await req.json<any>();if(!b.name)throw new Error('Character name is required');const cid=id(),ts=now();await env.DB.prepare('INSERT INTO characters(id,project_id,name,description,reference_asset_keys_json,attributes_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)').bind(cid,b.projectId??null,String(b.name).slice(0,120),String(b.description??''),JSON.stringify(b.referenceAssetKeys??[]),JSON.stringify(b.attributes??{}),ts,ts).run();return json({id:cid,name:b.name},201);}
  if(path.startsWith('/api/characters/')){const cid=path.split('/')[3];if(req.method==='DELETE'){await env.DB.prepare('DELETE FROM characters WHERE id=?').bind(cid).run();return json({ok:true});}if(req.method==='PUT'){const b=await req.json<any>();await env.DB.prepare('UPDATE characters SET name=?,description=?,reference_asset_keys_json=?,attributes_json=?,updated_at=? WHERE id=?').bind(b.name,b.description??'',JSON.stringify(b.referenceAssetKeys??[]),JSON.stringify(b.attributes??{}),now(),cid).run();return json({ok:true});}}
  if(path==='/api/assets'&&req.method==='GET'){const r=await env.DB.prepare('SELECT id,object_key,content_type,size,metadata_json,created_at FROM assets ORDER BY created_at DESC LIMIT 250').all();return json((r.results??[]).map((x:any)=>({...x,name:JSON.parse(x.metadata_json??'{}').name})));}
  if(path==='/api/models'&&req.method==='GET'){const r=await env.DB.prepare('SELECT id,name,source_url,repo_id,revision,model_type,status,total_bytes,stored_bytes,file_count,error,created_at,updated_at FROM models ORDER BY created_at DESC').all();return json(r.results);}
  if(path==='/api/models'&&req.method==='POST'){
   const b=await req.json<any>();if(!b.name||!b.sourceUrl||!b.modelType)throw new Error('name, sourceUrl and modelType are required');const repo=parseHfRepo(String(b.sourceUrl));const hfToken=await getHFToken(env);const metaResponse=await fetch(`https://huggingface.co/api/models/${repo}`,{headers:hfToken?{authorization:`Bearer ${hfToken}`}:{}});if(!metaResponse.ok)throw new Error(`Hugging Face model lookup failed (${metaResponse.status}); check the public model ID`);const meta=await metaResponse.json<any>();const revision=String(b.revision??meta.sha??'main');const modelId=id(),ts=now();
   await env.DB.prepare('INSERT INTO models(id,name,source_url,repo_id,revision,model_type,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)').bind(modelId,String(b.name).slice(0,120),String(b.sourceUrl),repo,revision,String(b.modelType), 'registered',ts,ts).run();
   return json({id:modelId,name:b.name,repoId:repo,revision,status:'registered'},201);
  }
  if(path.startsWith('/api/models/')&&path.endsWith('/import')&&req.method==='POST'){const modelId=path.split('/')[3];const m=await env.DB.prepare('SELECT id,status FROM models WHERE id=?').bind(modelId).first<any>();if(!m)return json({error:'Model not found'},404);if(['queued','downloading','uploading'].includes(m.status))return json({id:modelId,status:m.status});await env.DB.prepare('UPDATE models SET status=?,error=NULL,updated_at=? WHERE id=?').bind('queued',now(),modelId).run();try{await dispatchModelImport(env,modelId);}catch(e){await env.DB.prepare('UPDATE models SET status=?,error=?,updated_at=? WHERE id=?').bind('failed',String(e),now(),modelId).run();throw e;}return json({id:modelId,status:'queued'},202);}
  if(path.startsWith('/api/models/')&&req.method==='DELETE'){const modelId=path.split('/')[3];const m=await env.DB.prepare('SELECT object_keys_json FROM models WHERE id=?').bind(modelId).first<any>();if(!m)return json({error:'Model not found'},404);for(const key of JSON.parse(m.object_keys_json??'[]'))await env.MODELS.delete(key);await env.DB.prepare('DELETE FROM models WHERE id=?').bind(modelId).run();return json({ok:true});}
  if(path==='/api/workflows'&&req.method==='GET'){const r=await env.DB.prepare('SELECT * FROM workflows ORDER BY updated_at DESC').all();return json(r.results);}
  if(path==='/api/workflows'&&req.method==='POST'){const b=await req.json<any>();if(!b.name||!b.config)throw new Error('name and config required');const wid=id(),ts=now();await env.DB.prepare('INSERT INTO workflows(id,name,config_json,created_at,updated_at) VALUES(?,?,?,?,?)').bind(wid,b.name,JSON.stringify(b.config),ts,ts).run();return json({id:wid,name:b.name,config:b.config},201);}
  if(path.startsWith('/api/workflows/')){const wid=path.split('/').pop()!;if(req.method==='DELETE'){await env.DB.prepare('DELETE FROM workflows WHERE id=?').bind(wid).run();return json({ok:true});}if(req.method==='PUT'){const b=await req.json<any>();await env.DB.prepare('UPDATE workflows SET name=?,config_json=?,updated_at=? WHERE id=?').bind(b.name,JSON.stringify(b.config),now(),wid).run();return json({ok:true});}}
  if(path==='/api/jobs'&&req.method==='POST')return json(await createJob(env,await req.json<JobInput>()),202);
  if(path==='/api/jobs'&&req.method==='GET'){const r=await env.DB.prepare('SELECT id,workflow_id,status,provider,tool,error,created_at,updated_at FROM jobs ORDER BY created_at DESC LIMIT 100').all();return json(r.results);}
  if(path.startsWith('/api/jobs/')&&path.endsWith('/logs')){const jid=path.split('/')[3];const r=await env.DB.prepare('SELECT id,level,message,created_at FROM job_logs WHERE job_id=? ORDER BY created_at').bind(jid).all();return json(r.results);}
  if(path.startsWith('/api/jobs/')){const jid=path.split('/').pop()!;const r=await env.DB.prepare('SELECT * FROM jobs WHERE id=?').bind(jid).first<any>();return r?json({...r,payload_json:undefined,result_json:r.result_json?JSON.parse(r.result_json):null}):json({error:'Not found'},404);}
  if(path==='/api/secrets'&&req.method==='GET'){const r=await env.DB.prepare('SELECT provider,updated_at FROM secrets').all();return json(r.results);}
  if(path.startsWith('/api/secrets/')&&req.method==='DELETE'){const provider=decodeURIComponent(path.split('/').pop()!);await env.DB.prepare('DELETE FROM secrets WHERE provider=?').bind(provider).run();return json({ok:true});}
  if(path==='/api/secrets'&&req.method==='POST'){const b=await req.json<any>();if(!b.provider||!b.value)throw new Error('provider and value required');const enc=await encryptSecret(JSON.stringify(b.value),env.ENCRYPTION_KEY);await env.DB.prepare('INSERT INTO secrets(id,provider,ciphertext,iv,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(provider) DO UPDATE SET ciphertext=excluded.ciphertext,iv=excluded.iv,updated_at=excluded.updated_at').bind(id(),b.provider,enc.ciphertext,enc.iv,now()).run();return json({provider:b.provider,saved:true});}
  if(path==='/api/assets'&&req.method==='POST'){const b=await req.json<any>();const key=`uploads/${id()}/${String(b.name??'asset').replace(/[^a-zA-Z0-9._-]/g,'_')}`;const bytes=Uint8Array.from(atob(b.base64),c=>c.charCodeAt(0));await env.ASSETS.put(key,bytes,{httpMetadata:{contentType:b.contentType??'application/octet-stream'}});await env.DB.prepare('INSERT INTO assets(id,object_key,content_type,size,metadata_json,created_at) VALUES(?,?,?,?,?,?)').bind(id(),key,b.contentType??null,bytes.length,JSON.stringify({name:b.name}),now()).run();return json({key,size:bytes.length},201);}
  if(path.startsWith('/api/assets/')){const key=decodeURIComponent(path.slice('/api/assets/'.length));const obj=await env.ASSETS.get(key)??await env.MODELS.get(key);if(!obj)return json({error:'Not found'},404);return new Response(obj.body,{headers:{'content-type':obj.httpMetadata?.contentType??'application/octet-stream','cache-control':'private, max-age=60'}});}
  if(path==='/api/schedules'&&req.method==='GET'){const r=await env.DB.prepare('SELECT * FROM schedules ORDER BY next_run_at').all();return json(r.results);}
  if(path==='/api/schedules'&&req.method==='POST'){const b=await req.json<any>();if(!b.workflowId||!b.nextRunAt||!b.cron)throw new Error('workflowId, cron and nextRunAt required');const sid=id();await env.DB.prepare('INSERT INTO schedules(id,workflow_id,cron,timezone,enabled,next_run_at,created_at) VALUES(?,?,?,?,1,?,?)').bind(sid,b.workflowId,b.cron,b.timezone??'Africa/Lagos',b.nextRunAt,now()).run();return json({id:sid},201);}
  if(path==='/api/integrations/test'&&req.method==='POST'){const b=await req.json<any>();if(b.provider==='r2'){const r2=await getR2Credentials(env);const key=`system/credential-test/${id()}.txt`;const signed=await presignR2Put({accountId:r2.accountId,accessKeyId:r2.accessKeyId,secretAccessKey:r2.secretAccessKey,bucket:r2.bucketName,key,expires:300});const probe=await fetch(signed,{method:'PUT',body:'openmontage-r2-connection-test'});if(!probe.ok)throw new Error(`R2 credential test failed (${probe.status})`);await env.MODELS.delete(key);return json({ok:true});}if(b.provider==='github'){const gh=await getGitHubConfig(env);const r=await fetch('https://api.github.com/user',{headers:{authorization:`Bearer ${gh.token}`,accept:'application/vnd.github+json','user-agent':'omcs-control-plane'}});if(!r.ok)throw new Error(`GitHub token test failed (${r.status})`);const user=await r.json<any>();return json({ok:true,login:user.login});}if(b.provider==='huggingface'){const row=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='huggingface'").first<any>();if(!row)throw new Error('Hugging Face token is not configured');const v=JSON.parse(await decryptSecret(row.ciphertext,row.iv,env.ENCRYPTION_KEY));const token=v.token??v.accessToken;if(!token)throw new Error('Hugging Face token field is missing');const r=await fetch('https://huggingface.co/api/whoami-v2',{headers:{authorization:`Bearer ${token}`}});if(!r.ok)throw new Error(`Hugging Face test failed (${r.status})`);const user=await r.json<any>();return json({ok:true,name:user.name??user.email});}if(b.provider==='gemini'){const row=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='gemini'").first<any>();if(!row)throw new Error('Gemini API key is not configured');const v=JSON.parse(await decryptSecret(row.ciphertext,row.iv,env.ENCRYPTION_KEY));const key=v.apiKey??v.token??v.key;if(!key)throw new Error('Gemini apiKey field is missing');const r=await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(key)}`);if(!r.ok)throw new Error(`Gemini API test failed (${r.status})`);return json({ok:true});}if(b.provider==='kaggle'){const row=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='kaggle'").first<any>();if(!row)throw new Error('Kaggle credentials are not configured');const v=JSON.parse(await decryptSecret(row.ciphertext,row.iv,env.ENCRYPTION_KEY));if(!v.username||!v.key)throw new Error('Kaggle username and key are required');const authz='Basic '+btoa(`${v.username}:${v.key}`);const r=await fetch('https://www.kaggle.com/api/v1/competitions/list',{headers:{authorization:authz}});if(!r.ok)throw new Error(`Kaggle API test failed (${r.status})`);return json({ok:true});}if(b.provider==='telegram'){const s=await env.DB.prepare("SELECT ciphertext,iv FROM secrets WHERE provider='telegram'").first<any>();if(!s)throw new Error('Telegram is not configured');const v=JSON.parse(await decryptSecret(s.ciphertext,s.iv,env.ENCRYPTION_KEY));const r=await fetch(`https://api.telegram.org/bot${v.botToken}/getMe`);return json({ok:r.ok});}return json({ok:false,error:'Connectivity test not implemented for this provider'},400);}
  return json({error:'Not found'},404);
 }catch(e){return json({error:String(e instanceof Error?e.message:e)},400);}
}
export default {fetch:async(req:Request,env:Env)=>{const response=await handle(req,env);const headers=new Headers(response.headers);const origin=req.headers.get('origin');const allowed=env.ALLOWED_ORIGIN??'';if(origin&&origin===allowed){headers.set('access-control-allow-origin',origin);headers.set('access-control-allow-credentials','true');headers.append('vary','Origin');}return new Response(response.body,{status:response.status,statusText:response.statusText,headers});},async scheduled(_event:ScheduledController,env:Env,ctx:ExecutionContext){ctx.waitUntil(runScheduler(env));}};
async function runScheduler(env:Env){const due=await env.DB.prepare('SELECT * FROM schedules WHERE enabled=1 AND next_run_at<=? LIMIT 25').bind(now()).all<any>();for(const s of due.results??[]){const lease=`schedule:${s.id}:${s.next_run_at}`;try{await env.DB.prepare('UPDATE schedules SET next_run_at=? WHERE id=? AND next_run_at=?').bind(new Date(Date.now()+5*60*1000).toISOString(),s.id,s.next_run_at).run();const wf=await env.DB.prepare('SELECT * FROM workflows WHERE id=?').bind(s.workflow_id).first<any>();if(wf){const c=JSON.parse(wf.config_json);await createJob(env,{workflowId:wf.id,tool:c.tool??'openmontage-integration',compute:c.compute??'automatic',requiresGpu:!!c.requiresGpu,payload:c,idempotencyKey:lease});}}catch(e){console.error('schedule dispatch failed',s.id,String(e));}}}
