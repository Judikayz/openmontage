#!/usr/bin/env python3
"""Create Kaggle kernel metadata and submit through the official Kaggle CLI."""
import argparse,json,os,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--owner',required=True);p.add_argument('--slug',required=True);p.add_argument('--accelerator',default=' GPU');a=p.parse_args()
s=Path(a.source);s.mkdir(parents=True,exist_ok=True)
meta={'id':f'{a.owner}/{a.slug}','title':a.slug.replace('-',' ').title(),'code_file':'main.py','language':'python','kernel_type':'script','is_private':True,'enable_gpu':a.accelerator.strip().upper()=='GPU','enable_internet':True,'dataset_sources':[],'competition_sources':[],'kernel_sources':[]}
(s/'kernel-metadata.json').write_text(json.dumps(meta,indent=2))
if not (s/'main.py').exists(): raise SystemExit('main.py must exist before submission')
if not os.environ.get('KAGGLE_USERNAME') or not (os.environ.get('KAGGLE_KEY') or os.environ.get('KAGGLE_API_TOKEN')): raise SystemExit('Kaggle credentials missing from secure environment')
subprocess.run(['kaggle','kernels','push','-p',str(s)],check=True)
print(f'Submitted {a.owner}/{a.slug}')
