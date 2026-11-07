#!/usr/bin/env python3
"""Demo recorder.

mode "website" (default): opens the product site in a real Chromium browser, reads what is actually on each
page, writes a narration from those facts only, records the walkthrough and mixes the voice-over in.
It can fill a sign-up form ONLY with details the owner saved in Settings, and it stops at CAPTCHAs,
terms checkboxes and email verification. It never bypasses them and never invents identities.

mode "product": for products that are not a website or app. Builds a narrated video from clips or images
you supply. It does not generate footage; if you supply nothing it refuses.
"""
import argparse, asyncio, ipaddress, json, os, pathlib, re, shutil, socket, subprocess, sys, tempfile, time, urllib.parse
import requests

W, H = 1280, 720
SIGNUP_RE = re.compile(r"sign ?up|register|create (an )?account|get started|join", re.I)
CAPTCHA_SEL = "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='turnstile'], .g-recaptcha, .h-captcha, .cf-turnstile"
CURSOR_JS = """(()=>{const d=document.createElement('div');d.style.cssText='position:fixed;z-index:2147483647;width:18px;height:18px;border-radius:50%;background:rgba(255,80,80,.65);border:2px solid #fff;pointer-events:none;left:-50px;top:-50px;transform:translate(-50%,-50%)';
addEventListener('DOMContentLoaded',()=>document.body&&document.body.appendChild(d));addEventListener('mousemove',e=>{d.style.left=e.clientX+'px';d.style.top=e.clientY+'px'},true);})();"""


def log(msg): print(msg, file=sys.stderr, flush=True)


def run(cmd, **kw): return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=kw.pop("timeout", 3600), **kw)


def probe_duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout.strip())


# ---------- safety ----------
def check_url(url):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname: raise SystemExit("url must be a public http(s) address")
    if os.environ.get("DEMO_ALLOW_PRIVATE") == "1": return
    for info in socket.getaddrinfo(p.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise SystemExit(f"refusing to open a private or internal address ({ip})")


def parse_proxy(raw):
    if not raw: return None
    u = urllib.parse.urlparse(raw)
    if u.scheme.startswith("socks") and u.username:
        raise SystemExit("Chromium cannot use SOCKS proxies that need a username/password. Use an HTTP proxy with login, or a SOCKS proxy bound to the tunnel without login.")
    proxy = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
    if u.username: proxy.update(username=urllib.parse.unquote(u.username), password=urllib.parse.unquote(u.password or ""))
    return proxy


def get_cred(cp, token, provider):
    r = requests.get(f"{cp.rstrip('/')}/internal/credentials/{provider}", headers={"x-worker-callback-token": token}, timeout=30)
    if r.status_code == 404: return None
    r.raise_for_status(); return r.json()


# ---------- reading the site ----------
FACTS_JS = """()=>{const t=s=>[...document.querySelectorAll(s)].map(e=>e.innerText.trim()).filter(Boolean);
const main=document.querySelector('main')||document.body;
return {title:document.title.trim(),description:(document.querySelector('meta[name=description]')||{}).content||'',
headings:t('h1,h2,h3').slice(0,10),buttons:t('a.button,a.btn,button,[role=button]').filter(x=>x.length<40).slice(0,8),
text:main.innerText.replace(/\\s+/g,' ').trim().slice(0,900),
hasSignupForm:!!document.querySelector('input[type=password]'),
links:[...document.querySelectorAll('a[href]')].map(a=>({href:a.href,text:a.innerText.trim()})).filter(l=>l.text&&l.text.length<40)}}"""


def gather_facts(pw, start_url, max_pages, proxy):
    browser = pw.chromium.launch(proxy=proxy, executable_path=os.environ.get("CHROMIUM_PATH") or None, args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": W, "height": H}); page = ctx.new_page()
    origin = urllib.parse.urlparse(start_url).netloc; seen, pages, signup_url, queue = set(), [], None, [start_url]
    while queue and len(pages) < max_pages:
        url = queue.pop(0).split("#")[0]
        if url in seen: continue
        seen.add(url)
        try: page.goto(url, wait_until="load", timeout=45000)
        except Exception as e: log(f"skip {url}: {e}"); continue
        f = page.evaluate(FACTS_JS); f["url"] = page.url
        for l in f.pop("links"):
            if urllib.parse.urlparse(l["href"]).netloc != origin: continue
            if SIGNUP_RE.search(l["text"]) and not signup_url: signup_url = l["href"].split("#")[0]
            elif l["href"].split("#")[0] not in seen and l["href"] not in queue and not SIGNUP_RE.search(l["text"]): queue.append(l["href"])
        if f["hasSignupForm"] and not signup_url: signup_url = page.url
        if not f["hasSignupForm"] or len(pages) == 0: pages.append(f)
    browser.close()
    return pages, signup_url


# ---------- narration ----------
def template_script(name, pages):
    segs = []
    for i, p in enumerate(pages):
        parts = []
        if i == 0: parts.append(f"Welcome. Here is a walkthrough of {name or p['title']}.")
        parts.append(f"This page is titled {p['title']}." if p["title"] else "")
        if p["description"]: parts.append(p["description"].rstrip(".") + ".")
        if p["headings"]: parts.append("The page covers: " + "; ".join(p["headings"][:5]) + ".")
        if p["buttons"]: parts.append("Available actions include " + ", ".join(p["buttons"][:4]) + ".")
        segs.append({"url": p["url"], "text": " ".join(x for x in parts if x)})
    return segs


def gemini_script(name, pages, key, model, language, extra):
    base = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
    facts = json.dumps([{k: p[k] for k in ("url", "title", "description", "headings", "buttons", "text")} for p in pages])[:14000]
    prompt = (f"Write a clear, friendly, detailed voice-over in {language} for a screen recording of the website {name or ''}. "
              "Use ONLY the facts below. Do not invent features, prices, numbers, guarantees or claims that are not in the facts. "
              f"{extra or ''} Write 3 to 6 sentences per page, in the same order. "
              'Reply with JSON only: [{"url":"...","text":"..."}] with one item per page.\nFACTS:\n' + facts)
    r = requests.post(f"{base}/v1beta/models/{model}:generateContent", params={"key": key}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120)
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    segs = json.loads(re.search(r"\[.*\]", text, re.S).group(0))
    if len(segs) != len(pages) or not all(isinstance(s.get("text"), str) and s["text"].strip() for s in segs): raise ValueError("script did not match the pages")
    return [{"url": p["url"], "text": s["text"].strip()} for p, s in zip(pages, segs)]


def synth(text, out_base, voice, language):
    """Returns (path, backend). Natural voice via edge-tts, falls back to espeak-ng and says so."""
    if os.environ.get("DEMO_TTS") != "espeak":
        try:
            import edge_tts
            path = str(out_base) + ".mp3"
            asyncio.run(edge_tts.Communicate(text, voice or "en-US-AriaNeural").save(path))
            if pathlib.Path(path).stat().st_size > 1000: return path, "edge-tts"
        except Exception as e: log(f"edge-tts unavailable ({e}); falling back to espeak-ng")
    path = str(out_base) + ".wav"
    run(["espeak-ng", "-v", (language or "en")[:2], "-s", "150", "-w", path, text]); return path, "espeak-ng (robotic fallback)"


# ---------- recording ----------
def fill_signup(page, creds):
    """Fill the visible form with owner-supplied details. Returns outcome string. Never bypasses protections."""
    if page.locator(CAPTCHA_SEL).count(): return "blocked_by_captcha: a CAPTCHA is on the form; complete sign-up yourself"
    pwd = page.locator("input[type=password]:visible")
    if not pwd.count(): return "no_signup_form_found"
    for sel, val in (("input[type=email]:visible, input[name*=mail i]:visible", creds.get("email")), ("input[name*=name i]:visible, input[name*=user i]:visible, input[placeholder*=name i]:visible", creds.get("name"))):
        el = page.locator(sel).first
        if val and el.count():
            el.click(); el.fill(""); el.type(val, delay=60)
    for i in range(pwd.count()):
        pwd.nth(i).click(); pwd.nth(i).type(creds.get("password", ""), delay=60)
    box = page.locator("input[type=checkbox]:visible")
    if box.count() and not box.first.is_checked(): return "needs_terms_agreement: a checkbox must be ticked by you; form not submitted"
    page.locator("button[type=submit]:visible, input[type=submit]:visible").first.click(); page.wait_for_timeout(2500)
    body = page.inner_text("body")[:2000]
    if re.search(r"verify|confirm your e-?mail|check your (e-?mail|inbox)", body, re.I): return "needs_email_verification: the site asked to verify the email; finish that yourself"
    err = re.search(r"(invalid|already (registered|exists|in use)|error|failed|not allowed)[^.\n]{0,80}", body, re.I)
    if err: return f"rejected_by_site: {err.group(0).strip()}"
    return "form_submitted: the site accepted the form; account creation is not independently confirmed"


def smooth_scroll(page, seconds):
    end = time.time() + seconds; total = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    page.mouse.move(W * 0.6, H * 0.4); start = time.time()
    while time.time() < end:
        frac = min(1.0, (time.time() - start) / max(seconds * 0.85, 0.1))
        page.evaluate(f"window.scrollTo(0,{max(total,0)*frac})"); page.mouse.move(W * (0.4 + 0.3 * frac), H * (0.3 + 0.4 * frac)); page.wait_for_timeout(100)


def record_walkthrough(pw, segs, audio_paths, signup_url, signup_creds, proxy, workdir):
    vdir = workdir / "video"; vdir.mkdir()
    browser = pw.chromium.launch(proxy=proxy, executable_path=os.environ.get("CHROMIUM_PATH") or None, args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(vdir), record_video_size={"width": W, "height": H})
    ctx.add_init_script(CURSOR_JS); page = ctx.new_page(); t0 = time.time(); starts = []
    for seg, ap in zip(segs, audio_paths):
        page.goto(seg["url"], wait_until="load", timeout=45000); page.wait_for_timeout(400)
        starts.append(time.time() - t0); smooth_scroll(page, probe_duration(ap) + 0.6)
    signup_outcome = None
    if signup_url and signup_creds:
        page.goto(signup_url, wait_until="load", timeout=45000); page.wait_for_timeout(800); signup_outcome = fill_signup(page, signup_creds); page.wait_for_timeout(1500)
    page.wait_for_timeout(800); ctx.close(); browser.close()
    return next(vdir.glob("*.webm")), starts, signup_outcome


def mux_walkthrough(webm, starts, audio_paths, out):
    cmd = ["ffmpeg", "-y", "-i", str(webm)]; filt = []
    for i, (s, ap) in enumerate(zip(starts, audio_paths)):
        cmd += ["-i", str(ap)]; filt.append(f"[{i+1}:a]adelay={int(s*1000)}|{int(s*1000)}[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(starts))) + f"amix=inputs={len(starts)}:normalize=0,apad[aud]")
    run(cmd + ["-filter_complex", ";".join(filt), "-map", "0:v", "-map", "[aud]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(out)])


# ---------- non-website products ----------
def compose_product(segs, audio_paths, clips, images, workdir, out):
    parts = []
    for i, (seg, ap) in enumerate(zip(segs, audio_paths)):
        dur = probe_duration(ap) + 0.5; piece = workdir / f"seg{i}.mp4"
        scale = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
        if clips: src = ["-stream_loop", "-1", "-i", clips[i % len(clips)]]
        else: src = ["-loop", "1", "-framerate", "30", "-i", images[i % len(images)]]
        run(["ffmpeg", "-y", *src, "-i", str(ap), "-t", f"{dur:.2f}", "-vf", scale, "-map", "0:v", "-map", "1:a", "-af", "apad", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", str(piece)]); parts.append(piece)
    lst = workdir / "list.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])


def product_script(name, desc, features, key, model, language):
    if key and model:
        base = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
        prompt = (f"Write a friendly voice-over in {language} presenting the product {name}. Use ONLY the details below; invent nothing. One short paragraph for the intro and one per feature. "
                  'Reply with JSON only: [{"text":"..."}].\nDESCRIPTION: ' + desc + "\nFEATURES: " + json.dumps(features))
        try:
            r = requests.post(f"{base}/v1beta/models/{model}:generateContent", params={"key": key}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120); r.raise_for_status()
            segs = json.loads(re.search(r"\[.*\]", r.json()["candidates"][0]["content"]["parts"][0]["text"], re.S).group(0))
            if len(segs) == 1 + len(features): return [{"text": s["text"].strip()} for s in segs], "gemini"
        except Exception as e: log(f"gemini script failed ({e}); using template")
    return [{"text": f"Introducing {name}. {desc}"}] + [{"text": f"{f}."} for f in features], "template"


# ---------- upload + report ----------
def upload(cp, token, path, mime):
    r = requests.post(cp.rstrip("/") + "/internal/assets/upload-url", json={"name": path.name, "contentType": mime}, headers={"x-worker-callback-token": token}, timeout=60); r.raise_for_status(); u = r.json()
    with path.open("rb") as f: requests.put(u["uploadUrl"], data=f, headers={"content-type": mime}, timeout=(60, 1800)).raise_for_status()
    return u["key"]


def write_report(path, title, mode, segs, info):
    lines = [f"# Demo: {title}", "", f"Mode: {mode}", ""] + [f"- {k}: {v}" for k, v in info.items()] + ["", "## Narration (what the voice says)", ""]
    for i, s in enumerate(segs, 1): lines += [f"### {i}. {s.get('url', 'segment')}", s["text"], ""]
    lines += ["## Limits", "- Narration is built only from text found on the site (or supplied by you).", "- Sign-up is only attempted with details you saved, and stops at CAPTCHA, terms boxes and email verification."]
    path.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--job-id", required=True); ap.add_argument("--control-plane", required=True); a = ap.parse_args()
    raw, token = os.environ.get("JOB_PAYLOAD_JSON"), os.environ.get("WORKER_CALLBACK_TOKEN")
    if not raw or not token: raise SystemExit("JOB_PAYLOAD_JSON and WORKER_CALLBACK_TOKEN are required")
    j = json.loads(raw); mode = j.get("mode", "website"); name = j.get("productName", ""); language = j.get("language", "English")
    gem = get_cred(a.control_plane, token, "gemini") or {}; key, model = gem.get("apiKey"), gem.get("defaultModel")
    work = pathlib.Path(tempfile.mkdtemp(prefix="demo-")); out = work / (re.sub(r"[^a-z0-9]+", "-", (name or "demo").lower()).strip("-") + "-demo.mp4")
    info = {}
    if mode == "product":
        desc = (j.get("description") or "").strip(); feats = [f.strip() for f in j.get("features", []) if f.strip()]
        clips, images = j.get("inputVideos") or [], j.get("referenceAssets") or []
        if not name or not desc: raise SystemExit("productName and description are required for product mode")
        if not clips and not images: raise SystemExit("Provide real clips (inputVideos) or images (referenceAssets). This tool does not generate footage.")
        segs, info["script"] = product_script(name, desc, feats, key, model, language)
        paths, backends = [], set()
        for i, s in enumerate(segs): p, b = synth(s["text"], work / f"a{i}", j.get("voice"), language); paths.append(p); backends.add(b)
        compose_product(segs, paths, clips, images, work, out); info.update(visuals="your clips" if clips else "your images (still frames, not generated video)", voice=", ".join(backends))
    else:
        url = j.get("url") or ""; check_url(url)
        proxy = parse_proxy((get_cred(a.control_plane, token, "proxy") or {}).get("url") or os.environ.get("DEMO_PROXY_URL"))
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pages, signup_url = gather_facts(pw, url, int(j.get("maxPages", 6)), proxy)
            if not pages: raise SystemExit("Could not load any page from that address")
            segs, info["script"] = None, "template"
            if key and model:
                try: segs = gemini_script(name, pages, key, model, language, j.get("notes")); info["script"] = "gemini"
                except Exception as e: log(f"gemini script failed ({e}); using template")
            segs = segs or template_script(name, pages)
            paths, backends = [], set()
            for i, s in enumerate(segs): p, b = synth(s["text"], work / f"a{i}", j.get("voice"), language); paths.append(p); backends.add(b)
            creds = get_cred(a.control_plane, token, "demo-signup") if j.get("trySignup") else None
            if j.get("trySignup") and not creds: info["signup"] = "not_attempted: no sign-up details saved in Settings"
            webm, starts, outcome = record_walkthrough(pw, segs, paths, signup_url, creds, proxy, work)
        if outcome: info["signup"] = outcome
        elif "signup" not in info: info["signup"] = "not_requested"
        mux_walkthrough(webm, starts, paths, out); info.update(pages=len(segs), voice=", ".join(backends), via_your_ip=bool(proxy))
    if not out.exists() or out.stat().st_size < 10000: raise RuntimeError("Recording produced no valid video")
    report = out.with_suffix(".md"); write_report(report, name or j.get("url", "demo"), mode, segs, info)
    video_key = upload(a.control_plane, token, out, "video/mp4"); report_key = upload(a.control_plane, token, report, "text/markdown")
    print(json.dumps({"success": True, "assetKey": video_key, "reportKey": report_key, "seconds": round(probe_duration(out), 1), "mode": mode, **info}))


if __name__ == "__main__": main()
