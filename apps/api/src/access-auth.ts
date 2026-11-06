function decodePart(value:string){return Uint8Array.from(atob(value.replace(/-/g,'+').replace(/_/g,'/').padEnd(Math.ceil(value.length/4)*4,'=')),c=>c.charCodeAt(0));}
function decodeJson(value:string){return JSON.parse(new TextDecoder().decode(decodePart(value)));}
export async function verifyCloudflareAccess(req:Request,teamDomain:string,audience:string){
 const token=req.headers.get('cf-access-jwt-assertion');if(!token)return false;
 const parts=token.split('.');if(parts.length!==3)return false;
 try{
  const header=decodeJson(parts[0]),payload=decodeJson(parts[1]);
  if(header.alg!=='RS256'||payload.iss!==`https://${teamDomain}`)return false;
  const aud=Array.isArray(payload.aud)?payload.aud:[payload.aud];if(!aud.includes(audience))return false;
  const now=Math.floor(Date.now()/1000);if(typeof payload.exp!=='number'||payload.exp<=now||typeof payload.iat!=='number'||payload.iat>now+60)return false;
  const response=await fetch(`https://${teamDomain}/cdn-cgi/access/certs`);if(!response.ok)return false;
  const jwks=await response.json<any>();const jwk=jwks.keys?.find((k:any)=>k.kid===header.kid&&k.kty==='RSA');if(!jwk)return false;
  const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
  const data=new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  return await crypto.subtle.verify('RSASSA-PKCS1-v1_5',key,decodePart(parts[2]),data);
 }catch{return false;}
}
