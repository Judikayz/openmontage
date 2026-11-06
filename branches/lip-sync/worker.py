"""Wav2Lip inference adapter. Requires an explicitly supplied licensed checkout and checkpoint."""
import argparse,json,os,pathlib,subprocess,requests

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--job-id',required=True);ap.add_argument('--control-plane',required=True);a=ap.parse_args()
 raw=os.environ.get('JOB_PAYLOAD_JSON');token=os.environ.get('WORKER_CALLBACK_TOKEN')
 if not raw or not token:raise SystemExit('JOB_PAYLOAD_JSON and WORKER_CALLBACK_TOKEN are required')
 j=json.loads(raw);video=j.get('videoAsset');audio=j.get('audioAsset')
 if not video or not audio:raise SystemExit('videoAsset and audioAsset local file paths are required')
 for p in (video,audio):
  if not pathlib.Path(p).is_file():raise SystemExit(f'Input asset does not exist on runner: {p}')
 repo=pathlib.Path(os.environ.get('WAV2LIP_HOME','/opt/Wav2Lip'));checkpoint=os.environ.get('WAV2LIP_CHECKPOINT')
 if not (repo/'inference.py').is_file() or not checkpoint or not pathlib.Path(checkpoint).is_file():raise SystemExit('Configure WAV2LIP_HOME to a licensed Wav2Lip checkout and WAV2LIP_CHECKPOINT to its checkpoint file; no lip-sync simulation is performed')
 out=pathlib.Path(j.get('outputPath','/tmp/lipsynced.mp4'));out.parent.mkdir(parents=True,exist_ok=True)
 cmd=['python',str(repo/'inference.py'),'--checkpoint_path',checkpoint,'--face',str(video),'--audio',str(audio),'--outfile',str(out)]
 subprocess.run(cmd,cwd=repo,check=True,timeout=int(j.get('timeoutSeconds',7200)))
 if not out.is_file() or out.stat().st_size<1024:raise RuntimeError('Wav2Lip did not produce a valid output')
 mime='video/mp4';r=requests.post(a.control_plane.rstrip('/')+'/internal/assets/upload-url',json={'name':out.name,'contentType':mime},headers={'x-worker-callback-token':token},timeout=60);r.raise_for_status();u=r.json()
 with out.open('rb') as f:up=requests.put(u['uploadUrl'],data=f,headers={'content-type':mime},timeout=(60,1800));up.raise_for_status()
 print(json.dumps({'success':True,'assetKey':u['key'],'fileName':out.name,'method':'Wav2Lip'}))
if __name__=='__main__':main()
