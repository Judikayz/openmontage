"""Reference-conditioned image generation using Diffusers IP-Adapter."""
import argparse,json,os,pathlib,requests
from PIL import Image

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--job-id',required=True);ap.add_argument('--control-plane',required=True);a=ap.parse_args()
 raw=os.environ.get('JOB_PAYLOAD_JSON');token=os.environ.get('WORKER_CALLBACK_TOKEN')
 if not raw or not token:raise SystemExit('JOB_PAYLOAD_JSON and WORKER_CALLBACK_TOKEN are required')
 j=json.loads(raw);character=j.get('character') or {};refs=character.get('referenceAssets') or j.get('referenceAssets') or []
 if not refs:raise SystemExit('At least one accessible character reference image is required')
 if not j.get('prompt'):raise SystemExit('prompt is required')
 root=pathlib.Path(os.environ.get('MODEL_DIR',''));ids=j.get('modelIds') or []
 if not ids or not (root/str(ids[0])).exists():raise SystemExit('An imported compatible SDXL/SD1.5 IP-Adapter model must be selected and restored')
 try:
  import torch
  from diffusers import StableDiffusionXLPipeline
 except Exception as e:raise SystemExit(f'Diffusers/IP-Adapter runtime unavailable: {e}')
 model=root/str(ids[0]);pipe=StableDiffusionXLPipeline.from_pretrained(str(model),torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,local_files_only=True)
 ip=os.environ.get('IP_ADAPTER_MODEL')
 if not ip:raise SystemExit('Set IP_ADAPTER_MODEL to a compatible IP-Adapter weight path/repository; identity reference conditioning will not be faked')
 pipe.load_ip_adapter(ip,subfolder=os.environ.get('IP_ADAPTER_SUBFOLDER',''),weight_name=os.environ.get('IP_ADAPTER_WEIGHT','ip-adapter_sdxl.bin'))
 if torch.cuda.is_available():pipe.to('cuda')
 ref=refs[0]
 if not os.path.isfile(ref):raise SystemExit(f'Reference asset must be staged as a local file: {ref}')
 image=Image.open(ref).convert('RGB');pipe.set_ip_adapter_scale(float(j.get('identityStrength',0.8)))
 result=pipe(prompt=j['prompt'],ip_adapter_image=image,num_inference_steps=int(j.get('steps',30)),guidance_scale=float(j.get('guidanceScale',7.0))).images[0]
 out=pathlib.Path(j.get('outputPath','/tmp/character-consistent.png'));out.parent.mkdir(parents=True,exist_ok=True);result.save(out)
 mime='image/png';r=requests.post(a.control_plane.rstrip('/')+'/internal/assets/upload-url',json={'name':out.name,'contentType':mime},headers={'x-worker-callback-token':token},timeout=60);r.raise_for_status();u=r.json()
 with out.open('rb') as f:up=requests.put(u['uploadUrl'],data=f,headers={'content-type':mime},timeout=(60,600));up.raise_for_status()
 print(json.dumps({'success':True,'assetKey':u['key'],'fileName':out.name,'identityMethod':'IP-Adapter reference conditioning','identityStrength':j.get('identityStrength',0.8)}))
if __name__=='__main__':main()
