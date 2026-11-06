import argparse,json,os,requests

def main():
 p=argparse.ArgumentParser();p.add_argument('--job-id',required=True);p.add_argument('--control-plane',required=True);a=p.parse_args()
 base=os.environ.get('OPENMONTAGE_BASE_URL');token=os.environ.get('OPENMONTAGE_TOKEN')
 if not base or not token: raise SystemExit('OPENMONTAGE_BASE_URL and OPENMONTAGE_TOKEN must be configured as worker secrets')
 raw=os.environ.get('JOB_PAYLOAD_JSON')
 if not raw: raise SystemExit('JOB_PAYLOAD_JSON missing')
 payload=json.loads(raw)
 r=requests.post(base.rstrip('/')+'/api/jobs',json=payload,headers={'authorization':f'Bearer {token}'},timeout=30)
 if not r.ok: raise SystemExit(f'OpenMontage adapter request failed: HTTP {r.status_code} {r.text[:300]}')
 print(json.dumps({'accepted':True,'external':r.json()}))
if __name__=='__main__':main()
