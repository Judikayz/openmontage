const enc = new TextEncoder();
function b64(bytes: Uint8Array): string { return btoa(String.fromCharCode(...bytes)); }
function unb64(value: string): Uint8Array<ArrayBuffer> { return Uint8Array.from(atob(value), c => c.charCodeAt(0)) as Uint8Array<ArrayBuffer>; }
export async function encryptSecret(value: string, base64Key: string) {
  const keyBytes = unb64(base64Key); if (keyBytes.length !== 32) throw new Error('ENCRYPTION_KEY must decode to exactly 32 bytes');
  const key = await crypto.subtle.importKey('raw', keyBytes, 'AES-GCM', false, ['encrypt']);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({name:'AES-GCM',iv}, key, enc.encode(value));
  return {iv:b64(iv), ciphertext:b64(new Uint8Array(ciphertext))};
}
export async function decryptSecret(ciphertext: string, iv: string, base64Key: string) {
  const keyBytes=unb64(base64Key); if(keyBytes.length!==32) throw new Error('Invalid encryption key');
  const key=await crypto.subtle.importKey('raw',keyBytes,'AES-GCM',false,['decrypt']);
  const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:unb64(iv)},key,unb64(ciphertext));
  return new TextDecoder().decode(plain);
}
