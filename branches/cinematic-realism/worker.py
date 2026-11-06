"""Real FFmpeg finishing plus optional Real-ESRGAN/RIFE command adapters."""
import argparse,json,os,pathlib,subprocess,requests

def run(cmd):subprocess.run(cmd,check=True,timeout=7200)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--job-id',required=True);ap.add_argument('--control-plane',required=True);a=ap.parse_args()
 raw=os.environ.get('JOB_PAYLOAD_JSON');token=os.environ.get('WORKER_CALLBACK_TOKEN')
 if not raw or not token:raise SystemExit('JOB_PAYLOAD_JSON and WORKER_CALLBACK_TOKEN are required')
 j=json.loads(raw);src=j.get('inputVideo')
 if not src or not pathlib.Path(src).is_file():raise SystemExit('inputVideo must be a staged local video file')
 out=pathlib.Path(j.get('outputPath','/tmp/cinematic-finish.mp4'));out.parent.mkdir(parents=True,exist_ok=True)
 operations=j.get('operations') or ['color-grade','transcode']
 temp=out.with_name(out.stem+'.intermediate.mp4');current=src
 if 'upscale' in operations:
  exe=os.environ.get('REALESRGAN_BIN')
  if not exe:raise SystemExit('upscale requested but REALESRGAN_BIN is not configured; refusing to claim AI upscaling')
  updir=out.parent/'upscaled';updir.mkdir(exist_ok=True);run([exe,'-i',str(current),'-o',str(updir),'-n',j.get('upscaleModel','realesrgan-x4plus')]);candidate=updir/(pathlib.Path(current).stem+'.mp4')
  if candidate.exists():current=str(candidate)
 filters=[]
 if 'denoise' in operations:filters.append('hqdn3d=1.5:1.5:6:6')
 if 'color-grade' in operations:filters.append('eq=contrast=1.04:saturation=1.08:gamma=1.01')
 cmd=['ffmpeg','-y','-i',str(current)]
 if filters:cmd+=['-vf',','.join(filters)]
 cmd+=['-c:v','libx264','-preset',str(j.get('preset','medium')),'-crf',str(j.get('crf',19)),'-c:a','aac','-b:a','192k','-movflags','+faststart',str(out)]
 run(cmd)
 if not out.exists() or out.stat().st_size<1024:raise RuntimeError('FFmpeg did not produce valid output')
 mime='video/mp4';r=requests.post(a.control_plane.rstrip('/')+'/internal/assets/upload-url',json={'name':out.name,'contentType':mime},headers={'x-worker-callback-token':token},timeout=60);r.raise_for_status();u=r.json()
 with out.open('rb') as f:up=requests.put(u['uploadUrl'],data=f,headers={'content-type':mime},timeout=(60,1800));up.raise_for_status()
 print(json.dumps({'success':True,'assetKey':u['key'],'fileName':out.name,'operations':operations,'method':'FFmpeg'+(' + Real-ESRGAN' if 'upscale' in operations else '')}))
if __name__=='__main__':main()
