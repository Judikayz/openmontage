"""Assemble existing rendered clips and optional audio into a final MP4 with FFmpeg."""
import argparse,json,os,pathlib,subprocess,requests,tempfile

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--job-id',required=True);ap.add_argument('--control-plane',required=True);a=ap.parse_args()
 raw=os.environ.get('JOB_PAYLOAD_JSON');token=os.environ.get('WORKER_CALLBACK_TOKEN')
 if not raw or not token:raise SystemExit('JOB_PAYLOAD_JSON and WORKER_CALLBACK_TOKEN are required')
 j=json.loads(raw);clips=j.get('inputVideos') or ([j['inputVideo']] if j.get('inputVideo') else [])
 if not clips:raise SystemExit('Provide inputVideos as staged local MP4 paths')
 for clip in clips:
  if not pathlib.Path(clip).is_file():raise SystemExit(f'Input clip not found: {clip}')
 out=pathlib.Path(j.get('outputPath','/tmp/openmontage-final.mp4'));out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',suffix='.txt',delete=False) as f:
  for clip in clips:f.write("file '"+str(pathlib.Path(clip).resolve()).replace("'","'\\''")+"'\n")
  manifest=f.name
 try:
  cmd=['ffmpeg','-y','-f','concat','-safe','0','-i',manifest]
  if j.get('audioAsset'):
   if not pathlib.Path(j['audioAsset']).is_file():raise SystemExit('audioAsset path not found')
   cmd+=['-i',j['audioAsset'],'-map','0:v:0','-map','1:a:0','-shortest']
  cmd+=['-c:v','libx264','-preset','medium','-crf','19','-c:a','aac','-movflags','+faststart',str(out)]
  subprocess.run(cmd,check=True,timeout=int(j.get('timeoutSeconds',7200)))
 finally:pathlib.Path(manifest).unlink(missing_ok=True)
 if not out.exists() or out.stat().st_size<1024:raise RuntimeError('Assembly produced no valid video')
 mime='video/mp4';r=requests.post(a.control_plane.rstrip('/')+'/internal/assets/upload-url',json={'name':out.name,'contentType':mime},headers={'x-worker-callback-token':token},timeout=60);r.raise_for_status();u=r.json()
 with out.open('rb') as f:up=requests.put(u['uploadUrl'],data=f,headers={'content-type':mime},timeout=(60,1800));up.raise_for_status()
 print(json.dumps({'success':True,'assetKey':u['key'],'fileName':out.name,'clipCount':len(clips),'method':'FFmpeg concat/mux'}))
if __name__=='__main__':main()
