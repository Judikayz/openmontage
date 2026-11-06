#!/usr/bin/env python3
"""Import a public Hugging Face model into R2 through short-lived presigned PUT URLs."""
import hashlib, os, pathlib, sys, tempfile, time
from urllib.parse import quote
import requests

BASE = os.environ['CONTROL_PLANE_URL'].rstrip('/')
TOKEN = os.environ['MODEL_IMPORT_WORKER_TOKEN']
MODEL_ID = os.environ['MODEL_ID']
HEADERS = {'x-model-import-token': TOKEN}
HF_TOKEN = None
SESSION = requests.Session()
PARTIAL_ROOT = pathlib.Path(tempfile.gettempdir()) / f'omcs-model-import-{MODEL_ID}'
PARTIAL_ROOT.mkdir(parents=True, exist_ok=True)

def api(method, path, **kwargs):
    r = SESSION.request(method, BASE + path, headers=HEADERS, timeout=(30, 120), **kwargs)
    r.raise_for_status()
    return r.json() if r.content else {}

def fail(message):
    try: api('POST', f'/internal/models/{MODEL_ID}/failed', json={'error': message[:1800]})
    except Exception: pass
    raise RuntimeError(message)

def download_resumable(url, dest, expected):
    if dest.exists() and expected and dest.stat().st_size == expected: return
    if dest.exists() and expected and dest.stat().st_size > expected: dest.unlink()
    for attempt in range(1, 6):
        offset = dest.stat().st_size if dest.exists() else 0
        headers = {'Range': f'bytes={offset}-'} if offset else {}
        try:
            with SESSION.get(url, headers=headers, stream=True, timeout=(30, 300), allow_redirects=True) as response:
                if offset and response.status_code == 200:
                    offset = 0
                    mode = 'wb'
                elif offset and response.status_code == 206:
                    mode = 'ab'
                else:
                    response.raise_for_status()
                    mode = 'wb'
                with dest.open(mode) as out:
                    for chunk in response.iter_content(8 * 1024 * 1024):
                        if chunk: out.write(chunk)
            if expected and dest.stat().st_size != expected:
                raise IOError(f"download size {dest.stat().st_size} != expected {expected}")
            return
        except Exception:
            if attempt == 5: raise
            time.sleep(min(2 ** attempt, 30))

def upload_multipart(path, local, expected):
    init = api('POST', f'/internal/models/{MODEL_ID}/multipart-init', json={'path': path})
    parts, part_size, number = [], 128 * 1024 * 1024, 1
    with local.open('rb') as stream:
        while True:
            chunk = stream.read(part_size)
            if not chunk: break
            signed = api('POST', f'/internal/models/{MODEL_ID}/multipart-part-url', json={'path': path, 'partNumber': number})
            response = SESSION.put(signed['uploadUrl'], data=chunk, headers={'content-length': str(len(chunk))}, timeout=(30, 900))
            response.raise_for_status()
            etag = response.headers.get('ETag') or response.headers.get('etag')
            if not etag: raise RuntimeError(f'R2 did not return an ETag for multipart part {number}')
            parts.append({'partNumber': number, 'etag': etag.strip('"')})
            print(f'Uploaded multipart part {number}: {len(chunk):,} bytes', flush=True)
            number += 1
    api('POST', f'/internal/models/{MODEL_ID}/multipart-complete', json={'path': path, 'parts': parts})

def main():
    global HF_TOKEN
    token_info = api('GET', f'/internal/models/{MODEL_ID}/hf-token')
    HF_TOKEN = token_info.get('token')
    manifest = api('GET', f'/internal/models/{MODEL_ID}/manifest')
    repo, revision, files = manifest['repo_id'], manifest['revision'], manifest['files']
    total = sum(int(f.get('size', 0)) for f in files)
    print(f"Importing {repo}@{revision}: {len(files)} files, {total:,} bytes")
    for item in files:
        path, expected = item['path'], int(item.get('size', 0))
        url = f"https://huggingface.co/{repo}/resolve/{quote(revision, safe='')}/{quote(path, safe='/')}?download=true"
        print(f"Downloading {path} ({expected:,} bytes)", flush=True)
        local = PARTIAL_ROOT / hashlib.sha256(path.encode()).hexdigest()
        download_resumable(url, local, expected)
        digest = hashlib.sha256()
        with local.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''): digest.update(chunk)
        expected_sha = item.get('sha256')
        if expected_sha and digest.hexdigest().lower() != expected_sha.lower():
            local.unlink(missing_ok=True)
            fail(f"SHA-256 verification failed for {path}")
        # Refresh the signed URL on retry; R2 credentials never leave the control plane.
        if local.stat().st_size > 5 * 1024**3:
            upload_multipart(path, local, expected)
        else:
            for attempt in range(1, 4):
                signed = api('POST', f'/internal/models/{MODEL_ID}/upload-url', json={'path': path})
                try:
                    with local.open('rb') as stream:
                        uploaded = SESSION.put(signed['uploadUrl'], data=stream, headers={'content-length': str(local.stat().st_size)}, timeout=(30, 900))
                        uploaded.raise_for_status()
                    break
                except Exception:
                    if attempt == 3: raise
                    time.sleep(2 ** attempt)
        print(f"Stored {path}: {local.stat().st_size:,} bytes", flush=True)
        local.unlink(missing_ok=True)
    result = api('POST', f'/internal/models/{MODEL_ID}/complete', json={})
    print(f"Model import complete: {result}")

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        fail(str(exc))
        sys.exit(1)
