import argparse,json,os,subprocess

def main():
 p=argparse.ArgumentParser();p.add_argument('--job-id',required=True);p.add_argument('--control-plane',required=True);a=p.parse_args()
 raw=os.environ.get('JOB_PAYLOAD_JSON')
 if not raw: raise SystemExit('JOB_PAYLOAD_JSON missing')
 j=json.loads(raw);src=j.get('inputVideo')
 if not src: raise SystemExit('inputVideo is required')
 if not os.path.exists(src): raise SystemExit('inputVideo path does not exist')
 # Safe CPU finishing path is real FFmpeg remux/transcode only; AI enhancement needs separately staged weights.
 out=j.get('outputPath','/workspace/output.mp4')
 if j.get('operations')==['ffmpeg-transcode']:
  subprocess.run(['ffmpeg','-y','-i',src,'-c:v','libx264','-preset','medium','-crf','20','-c:a','aac',out],check=True)
  print(json.dumps({'output':out,'operations':['ffmpeg-transcode']}));return
 if not os.environ.get('MODEL_DIR'): raise SystemExit('AI finishing weights not staged; configure R2 cache for Real-ESRGAN/RIFE')
 raise SystemExit('AI enhancement backend not configured. No fake enhancement output generated.')
if __name__=='__main__':main()
