import argparse,json,os

def main():
 p=argparse.ArgumentParser();p.add_argument('--job-id',required=True);p.add_argument('--control-plane',required=True);a=p.parse_args()
 raw=os.environ.get('JOB_PAYLOAD_JSON')
 if not raw: raise SystemExit('JOB_PAYLOAD_JSON missing')
 j=json.loads(raw)
 for k in ('videoAsset','audioAsset'):
  if not j.get(k): raise SystemExit(f'{k} is required')
 if not os.environ.get('MODEL_DIR'): raise SystemExit('MuseTalk/LatentSync weights not staged')
 raise SystemExit('Lip-sync runtime is not configured; select a licensed upstream backend. No synthetic output returned.')
if __name__=='__main__':main()
