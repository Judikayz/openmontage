import argparse,json,os,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--job-id',required=True);p.add_argument('--control-plane',required=True);a=p.parse_args()
 payload=os.environ.get('JOB_PAYLOAD_JSON')
 if not payload: raise SystemExit('JOB_PAYLOAD_JSON is required; runner must fetch the authenticated job payload before inference')
 job=json.loads(payload); model=job.get('model','Wan2.2')
 if not os.environ.get('MODEL_DIR'): raise SystemExit(f'Model weights for {model} are not staged. Configure R2 model cache and MODEL_DIR; no fake output will be generated.')
 raise SystemExit('Inference adapter requires the selected upstream model runtime entrypoint. See README.md for supported integration contract.')
if __name__=='__main__':main()
