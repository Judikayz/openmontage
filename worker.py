import argparse,json,os
from pathlib import Path

def validate_profile(profile):
 refs=profile.get('referenceAssets',[])
 if len(refs)<1: raise ValueError('Character profile needs at least one persistent reference asset')
 return {'reference_count':len(refs),'identity_validation':'not_run','limitations':['Identity preservation is probabilistic; validate generated frames against reference embeddings.']}
def main():
 p=argparse.ArgumentParser();p.add_argument('--job-id',required=True);p.add_argument('--control-plane',required=True);a=p.parse_args()
 raw=os.environ.get('JOB_PAYLOAD_JSON')
 if not raw: raise SystemExit('JOB_PAYLOAD_JSON missing')
 j=json.loads(raw);print(json.dumps(validate_profile(j.get('character',{}))))
 if not os.environ.get('MODEL_DIR'): raise SystemExit('Character model weights not staged; configure R2 model cache')
 raise SystemExit('No model inference executed: configure IP-Adapter/LoRA backend and checkpoints as documented.')
if __name__=='__main__':main()
