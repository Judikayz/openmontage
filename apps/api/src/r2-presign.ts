const enc = (s:string) => encodeURIComponent(s).replace(/[!'()*]/g, c => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
const hex = (b:ArrayBuffer) => Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,'0')).join('');
const sha = async (s:string) => hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)));
async function hmac(key:Uint8Array<ArrayBuffer>|string,data:string){const raw:BufferSource=typeof key==='string'?new TextEncoder().encode(key) as Uint8Array<ArrayBuffer>:key;const k=await crypto.subtle.importKey('raw',raw,{name:'HMAC',hash:'SHA-256'},false,['sign']);return new Uint8Array(await crypto.subtle.sign('HMAC',k,new TextEncoder().encode(data))) as Uint8Array<ArrayBuffer>;}
function ymd(d:Date){return d.toISOString().replace(/[:-]|\.\d{3}/g,'');}
export async function presignR2(input:{accountId:string;accessKeyId:string;secretAccessKey:string;bucket:string;key:string;expires?:number;method?:'GET'|'PUT'}){
 const now=new Date(), stamp=ymd(now), date=stamp.slice(0,8), region='auto', service='s3', host=`${input.accountId}.r2.cloudflarestorage.com`;
 const path=`/${enc(input.bucket)}/${input.key.split('/').map(enc).join('/')}`;
 const scope=`${date}/${region}/${service}/aws4_request`;
 const params=new URLSearchParams({ 'X-Amz-Algorithm':'AWS4-HMAC-SHA256','X-Amz-Credential':`${input.accessKeyId}/${scope}`,'X-Amz-Date':stamp,'X-Amz-Expires':String(input.expires??900),'X-Amz-SignedHeaders':'host' });
 const canonicalQuery=Array.from((params as any).entries() as Iterable<[string,string]>).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>`${enc(k)}=${enc(v)}`).join('&');
 const method=input.method??'PUT';
 const canonicalRequest=`${method}\n${path}\n${canonicalQuery}\nhost:${host}\nhost\nUNSIGNED-PAYLOAD`;
 const stringToSign=`AWS4-HMAC-SHA256\n${stamp}\n${scope}\n${await sha(canonicalRequest)}`;
 const kDate=await hmac('AWS4'+input.secretAccessKey,date),kRegion=await hmac(kDate,region),kService=await hmac(kRegion,service),kSigning=await hmac(kService,'aws4_request');
 const signature=hex(await crypto.subtle.sign('HMAC',await crypto.subtle.importKey('raw',kSigning,{name:'HMAC',hash:'SHA-256'},false,['sign']),new TextEncoder().encode(stringToSign)));
 return `https://${host}${path}?${canonicalQuery}&X-Amz-Signature=${signature}`;
}
export const presignR2Put=(input:Parameters<typeof presignR2>[0])=>presignR2({...input,method:'PUT'});
export const presignR2Get=(input:Parameters<typeof presignR2>[0])=>presignR2({...input,method:'GET'});

