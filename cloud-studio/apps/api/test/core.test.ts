import {describe,it,expect} from 'vitest';import{routeJob,validateToolBranch,assertToolEnabled,WORKER_READABLE_CREDENTIALS}from'../src/routing';import{encryptSecret,decryptSecret}from'../src/crypto';
const key=btoa(String.fromCharCode(...new Uint8Array(32).fill(7)));
describe('compute routing',()=>{it('sends CPU to GitHub in automatic mode',()=>expect(routeJob({tool:'x',payload:{}})).toBe('github'));it('sends GPU task to Kaggle',()=>expect(routeJob({tool:'x',requiresGpu:true,payload:{}})).toBe('kaggle'));it('rejects forced Kaggle for CPU',()=>expect(()=>routeJob({tool:'x',compute:'kaggle',payload:{}})).toThrow());it('honours forced GitHub',()=>expect(routeJob({tool:'x',compute:'github',requiresGpu:true,payload:{}})).toBe('github'));});
describe('secret encryption',()=>{it('round trips encrypted values',async()=>{const x=await encryptSecret('private-value',key);expect(await decryptSecret(x.ciphertext,x.iv,key)).toBe('private-value');expect(x.ciphertext).not.toContain('private-value');});});

describe('tool branch validation',()=>{it('accepts a packaged tool branch',()=>expect(validateToolBranch('ai-video-generation')).toBe('ai-video-generation'));it('rejects unknown branch names',()=>expect(()=>validateToolBranch('unknown-branch')).toThrow('Unsupported tool branch'));});
import {presignR2MultipartPart} from '../src/r2-presign';
describe('R2 multipart presigning',()=>{it('signs a numbered multipart upload part with its upload ID',async()=>{const url=await presignR2MultipartPart({accountId:'account',accessKeyId:'access',secretAccessKey:'secret',bucket:'models',key:'models/demo/weights.bin',uploadId:'upload-123',partNumber:2});const parsed=new URL(url);expect(parsed.searchParams.get('partNumber')).toBe('2');expect(parsed.searchParams.get('uploadId')).toBe('upload-123');expect(parsed.searchParams.get('X-Amz-Signature')).toMatch(/^[a-f0-9]{64}$/);});});

describe('worker-readable credentials',()=>{it('exposes only the Gemini and ElevenLabs keys',()=>{expect([...WORKER_READABLE_CREDENTIALS].sort()).toEqual(['elevenlabs','gemini']);for(const p of ['github','r2','kaggle','huggingface','proxy','demo-signup'])expect(WORKER_READABLE_CREDENTIALS).not.toContain(p);});});
describe('untested tools are disabled by default',()=>{
 it('allows the verified CPU tools',()=>{expect(()=>assertToolEnabled('openmontage-integration',false)).not.toThrow();expect(()=>assertToolEnabled('cinematic-realism',false,'github')).not.toThrow();expect(()=>assertToolEnabled('voiceover',false)).not.toThrow();expect(validateToolBranch('voiceover')).toBe('voiceover');});
 it('blocks GPU and model tools',()=>{for(const t of ['ai-video-generation','character-consistency','lip-sync'])expect(()=>assertToolEnabled(t,false)).toThrow(/experimental/);});
 it('blocks Kaggle unless experimental',()=>{expect(()=>assertToolEnabled('cinematic-realism',false,'kaggle')).toThrow(/Kaggle/);expect(()=>assertToolEnabled('lip-sync',true,'kaggle')).not.toThrow();});
});
