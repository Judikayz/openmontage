"""Real Diffusers video inference worker. It fails closed when no compatible model/runtime exists."""
import argparse, json, os, pathlib, subprocess, tempfile, requests
from PIL import Image

def model_path(job):
    root=pathlib.Path(os.environ.get('MODEL_DIR',''))
    ids=job.get('modelIds') or []
    if not root.exists() or not ids: raise RuntimeError('Select at least one imported model and restore it from R2 before inference.')
    p=root/str(ids[0])
    if not p.exists(): raise RuntimeError(f'Model cache folder not found: {p}')
    return p

def upload(path, base, token, job_id):
    name=path.name; mime='video/mp4' if path.suffix.lower()=='.mp4' else 'application/octet-stream'
    r=requests.post(base.rstrip('/')+'/internal/assets/upload-url',json={'name':name,'contentType':mime},headers={'x-worker-callback-token':token},timeout=60);r.raise_for_status();u=r.json()
    with path.open('rb') as f: put=requests.put(u['uploadUrl'],data=f,headers={'content-type':mime},timeout=(60,1800))
    put.raise_for_status();return {'assetKey':u['key'],'fileName':name,'contentType':mime,'bytes':path.stat().st_size}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job-id',required=True);ap.add_argument('--control-plane',required=True);a=ap.parse_args()
    raw=os.environ.get('JOB_PAYLOAD_JSON'); token=os.environ.get('WORKER_CALLBACK_TOKEN')
    if not raw or not token: raise SystemExit('JOB_PAYLOAD_JSON and WORKER_CALLBACK_TOKEN are required')
    job=json.loads(raw); prompt=job.get('prompt')
    if not prompt: raise SystemExit('A non-empty prompt is required')
    path=model_path(job)
    try:
        import torch
        from diffusers import DiffusionPipeline
        from diffusers.utils import export_to_video
    except Exception as e: raise SystemExit(f'Diffusers video runtime unavailable: {e}. Install a compatible Diffusers release and model dependencies.')
    model_id=str(path)
    dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    pipeline_class=os.environ.get('OM_PIPELINE_CLASS')
    if pipeline_class:
        module,name=pipeline_class.rsplit('.',1);import importlib;pipe_cls=getattr(importlib.import_module(module),name);pipe=pipe_cls.from_pretrained(model_id,torch_dtype=dtype,local_files_only=True)
    else: pipe=DiffusionPipeline.from_pretrained(model_id,torch_dtype=dtype,local_files_only=True)
    if torch.cuda.is_available():pipe=pipe.to('cuda')
    elif os.environ.get('OM_ALLOW_CPU_INFERENCE')!='1':raise RuntimeError('This selected video model requires GPU. Set OM_ALLOW_CPU_INFERENCE=1 only after confirming its CPU support.')
    kwargs={'prompt':prompt}
    if job.get('negativePrompt'):kwargs['negative_prompt']=job['negativePrompt']
    for key in ('num_frames','num_inference_steps','guidance_scale'):
        if job.get(key) is not None:kwargs[key]=job[key]
    if job.get('seed') not in (None,''):kwargs['generator']=torch.Generator(device='cuda' if torch.cuda.is_available() else 'cpu').manual_seed(int(job['seed']))
    result=pipe(**kwargs)
    frames=getattr(result,'frames',None)
    if frames is None: raise RuntimeError('Selected pipeline did not return video frames; choose a supported video Diffusers pipeline.')
    frames=frames[0] if isinstance(frames,list) and frames and isinstance(frames[0],list) else frames
    out=pathlib.Path(job.get('outputPath','/tmp/openmontage-output.mp4'));out.parent.mkdir(parents=True,exist_ok=True)
    export_to_video(frames,str(out),fps=int(job.get('fps',24)))
    if not out.is_file() or out.stat().st_size<1024:raise RuntimeError('Pipeline did not produce a valid video file')
    result_meta=upload(out,a.control_plane,token,a.job_id)
    print(json.dumps({'success':True,'output':result_meta,'model':model_id,'device':'cuda' if torch.cuda.is_available() else 'cpu'}))
if __name__=='__main__':main()
