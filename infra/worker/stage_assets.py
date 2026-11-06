#!/usr/bin/env python3
"""Download referenced user assets from the authenticated control plane and rewrite payload paths."""
import base64,json,os,pathlib,urllib.parse,urllib.request
base=os.environ['CONTROL_PLANE_URL'].rstrip('/');token=os.environ['WORKER_CALLBACK_TOKEN'];job=json.loads(os.environ['JOB_PAYLOAD_JSON']);root=pathlib.Path(os.environ.get('OMCS_ASSET_DIR','/tmp/omcs-assets'));root.mkdir(parents=True,exist_ok=True);cache={}
def fetch(key):
 if key in cache:return cache[key]
 req=urllib.request.Request(base+'/internal/assets/download?key='+urllib.parse.quote(key,safe=''),headers={'x-worker-callback-token':token})
 with urllib.request.urlopen(req,timeout=600) as response:data=response.read()
 suffix=pathlib.Path(key).suffix or '.bin';target=root/(str(len(cache))+suffix);target.write_bytes(data);cache[key]=str(target);return str(target)
def walk(value,parent=''):
 if isinstance(value,dict):
  for k,v in list(value.items()):
   if k in ('inputVideo','videoAsset','audioAsset') and isinstance(v,str):value[k]=fetch(v)
   elif k in ('referenceAssets','inputVideos','assetKeys') and isinstance(v,list):value[k]=[fetch(x) if isinstance(x,str) else x for x in v]
   else:walk(v,k)
 elif isinstance(value,list):
  for item in value:walk(item,parent)
walk(job)
out=pathlib.Path('/tmp/omcs-job-payload.json');out.write_text(json.dumps(job,separators=(',',':')))
print(f'Staged {len(cache)} unique asset(s); payload={out}')
