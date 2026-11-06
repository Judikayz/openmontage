#!/usr/bin/env python3
"""Restore registered models from GitHub cache (if present) or persistent R2."""
import os, pathlib, requests
BASE=os.environ['CONTROL_PLANE_URL'].rstrip('/')
TOKEN=os.environ['MODEL_IMPORT_WORKER_TOKEN']
ROOT=pathlib.Path(os.path.expanduser(os.environ.get('OMCS_MODEL_CACHE',str(pathlib.Path.home()/'.cache/omcs-models'))))
HEAD={'x-model-import-token':TOKEN}
s=requests.Session()
def api(path,params=None):
 r=s.get(BASE+path,headers=HEAD,params=params,timeout=(30,120));r.raise_for_status();return r.json()
def main():
 ids=[x.strip() for x in os.environ.get('MODEL_IDS','').split(',') if x.strip()]
 for mid in ids:
  manifest=api(f'/internal/models/{mid}/manifest')
  for f in manifest['files']:
   if not f.get('objectKey'): raise RuntimeError(f"Model {mid} is not fully imported: {f['path']}")
   target=ROOT/mid/f['path'];target.parent.mkdir(parents=True,exist_ok=True)
   if target.is_file() and target.stat().st_size==int(f.get('size',0)):
    print(f"Cache hit: {mid}/{f['path']}");continue
   signed=api(f'/internal/models/{mid}/download-url',{'path':f['path']})
   print(f"Restoring {mid}/{f['path']} from R2",flush=True)
   with s.get(signed['downloadUrl'],stream=True,timeout=(30,300)) as response:
    response.raise_for_status()
    temp=target.with_suffix(target.suffix+'.partial')
    with temp.open('wb') as out:
     for chunk in response.iter_content(8*1024*1024):
      if chunk:out.write(chunk)
    if f.get('size') and temp.stat().st_size!=int(f['size']):temp.unlink(missing_ok=True);raise RuntimeError(f"Size mismatch restoring {f['path']}")
    temp.replace(target)
 print(f"Model cache ready at {ROOT}")
if __name__=='__main__':main()
