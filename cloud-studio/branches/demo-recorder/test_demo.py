"""Real end-to-end tests: local test site + real Chromium + real ffmpeg + espeak-ng. Run: python test_demo.py"""
import http.server, json, os, pathlib, subprocess, sys, threading, tempfile, urllib.parse
HERE = pathlib.Path(__file__).parent
PAGES = {
 "/": "<title>Acme Tasks</title><meta name=description content='Acme Tasks keeps small teams organised.'><nav><a href=/features>Features</a> <a href=/pricing>Pricing</a> <a href=/signup>Sign up</a></nav><main><h1>Plan work together</h1><p>Shared boards, due dates and reminders.</p><a class=button href=/signup>Get started</a>"+"<p>filler</p>"*40+"</main>",
 "/features": "<title>Features</title><nav><a href=/>Home</a></nav><main><h1>Boards</h1><h2>Reminders</h2><p>Email reminders before a task is due.</p>"+"<p>x</p>"*60+"</main>",
 "/pricing": "<title>Pricing</title><nav><a href=/>Home</a></nav><main><h1>Simple pricing</h1><p>Free for up to three people.</p></main>",
 "/signup": "<title>Sign up</title><main><h1>Create account</h1><form method=post action=/signup><input type=email name=email><input name=name placeholder='Your name'><input type=password name=password><button type=submit>Create account</button></form></main>",
 "/captcha": "<title>Join</title><main><form method=post action=/captcha><input type=email name=email><input type=password name=password><div class=g-recaptcha></div><button type=submit>Go</button></form></main>",
 "/terms": "<title>Join</title><main><form method=post action=/terms><input type=email name=email><input type=password name=password><label><input type=checkbox> I agree</label><button type=submit>Go</button></form></main>",
}
class Site(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        b = PAGES.get(s.path.split("?")[0]); s.send_response(200 if b else 404); s.send_header("content-type", "text/html"); s.end_headers(); s.wfile.write((b or "nope").encode())
    def do_POST(s):
        s.rfile.read(int(s.headers.get("content-length", 0))); s.send_response(200); s.send_header("content-type", "text/html"); s.end_headers(); s.wfile.write(b"<title>Thanks</title><main>Please check your email to verify your account.</main>")
    def log_message(*a): pass
GEM = {"on": False, "bad": False}
class CP(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        prov = s.path.rsplit("/", 1)[-1]
        if prov == "gemini" and GEM["on"]: body = json.dumps({"apiKey": "k", "defaultModel": "m"}).encode(); s.send_response(200); s.send_header("content-type", "application/json"); s.end_headers(); s.wfile.write(body); return
        if prov == "demo-signup": body = json.dumps({"email": "owner@example.com", "name": "Owner", "password": "S3cret-pass!"}).encode(); s.send_response(200); s.send_header("content-type", "application/json"); s.end_headers(); s.wfile.write(body)
        else: s.send_response(404); s.end_headers()
    def do_POST(s):
        body = json.loads(s.rfile.read(int(s.headers.get("content-length", 0))))
        if ":generateContent" in s.path:
            n = body["contents"][0]["parts"][0]["text"].count('"url":') - (2 if GEM["bad"] else 1); n = max(n, 1)
            txt = json.dumps([{"url": "u", "text": f"MOCK NARRATION {i}"} for i in range(n)])
            s.send_response(200); s.send_header("content-type", "application/json"); s.end_headers(); s.wfile.write(json.dumps({"candidates": [{"content": {"parts": [{"text": txt}]}}]}).encode()); return
        s.send_response(200); s.send_header("content-type", "application/json"); s.end_headers(); s.wfile.write(json.dumps({"key": "assets/" + body["name"], "uploadUrl": "http://localhost:8799/put/" + body["name"]}).encode())
    def do_PUT(s):
        n = int(s.headers.get("content-length", 0)); (pathlib.Path(tempfile.gettempdir()) / ("up_" + s.path.rsplit("/", 1)[-1])).write_bytes(s.rfile.read(n)); s.send_response(200); s.end_headers()
    def log_message(*a): pass
for port, h in ((8801, Site), (8799, CP)): threading.Thread(target=http.server.HTTPServer(("localhost", port), h).serve_forever, daemon=True).start()
ENV = dict(os.environ, DEMO_ALLOW_PRIVATE="1", DEMO_TTS="espeak", WORKER_CALLBACK_TOKEN="cb", CHROMIUM_PATH=os.environ.get("CHROMIUM_PATH", ""), PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
def run_worker(payload, env_extra=None):
    e = dict(ENV, JOB_PAYLOAD_JSON=json.dumps(payload), **(env_extra or {}))
    p = subprocess.run([sys.executable, str(HERE / "worker.py"), "--job-id", "t", "--control-plane", "http://localhost:8799"], env=e, capture_output=True, text=True, timeout=600)
    return p, (json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else None)
def streams(path): return subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.split()
def dur(path): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout)
tmp = pathlib.Path(tempfile.gettempdir()); ok = True
def check(name, cond, extra=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))

# 1 website walkthrough with sign-up that needs verification
p, r = run_worker({"url": "http://localhost:8801/", "productName": "Acme Tasks", "maxPages": 3, "trySignup": True})
check("website demo succeeds", r, p.stderr[-300:] if not r else "")
if r:
    v = tmp / "up_acme-tasks-demo.mp4"; rep = (tmp / "up_acme-tasks-demo.md").read_text()
    check("video has video and audio", sorted(set(streams(str(v)))) == ["audio", "video"])
    check("video long enough for narration", dur(str(v)) > 8, f"{dur(str(v)):.1f}s")
    check("report uses real page facts", "Plan work together" in rep and "Email reminders" in rep or "Reminders" in rep)
    check("sign-up stopped at email verification", r["signup"].startswith("needs_email_verification"), r["signup"])
    check("password not written to report/result", "S3cret-pass!" not in rep and "S3cret-pass!" not in json.dumps(r))
# 2 captcha / terms stop
ORIG=PAGES["/"]
for path, want in (("captcha", "blocked_by_captcha"), ("terms", "needs_terms_agreement")):
    PAGES["/"] = ORIG.replace("href=/signup>", f"href=/{path}>")
    p, r = run_worker({"url": "http://localhost:8801/", "productName": "T", "maxPages": 1, "trySignup": True})
    check(f"sign-up stops at {path}", r and r["signup"].startswith(want), (r or {}).get("signup", p.stderr[-200:]))
# 2b gemini script path (mock server) and fallback when the model answer does not match
PAGES["/"] = ORIG.replace("href=/signup>", "href=/signup>"); GEM["on"] = True
p, r = run_worker({"url": "http://localhost:8801/", "productName": "G", "maxPages": 2}, {"GEMINI_BASE_URL": "http://localhost:8799"})
check("uses gemini script when configured", r and r["script"] == "gemini" and "MOCK NARRATION 0" in (tmp / "up_g-demo.md").read_text(), (r or {}).get("script", p.stderr[-200:]))
GEM["bad"] = True
p, r = run_worker({"url": "http://localhost:8801/", "productName": "H", "maxPages": 2}, {"GEMINI_BASE_URL": "http://localhost:8799"})
check("falls back to template when gemini answer is wrong", r and r["script"] == "template", (r or {}).get("script", p.stderr[-200:]))
GEM["on"] = False; GEM["bad"] = False
# 3 safety
p, _ = run_worker({"url": "http://169.254.169.254/latest/meta-data/"}, {"DEMO_ALLOW_PRIVATE": "0"}); check("blocks cloud metadata address", p.returncode != 0 and "private" in p.stderr + p.stdout)
p, _ = run_worker({"url": "file:///etc/passwd"}); check("blocks file:// urls", p.returncode != 0)
p, _ = run_worker({"url": "http://localhost:8801/", "trySignup": True}, {"DEMO_PROXY_URL": "socks5://u:p@127.0.0.1:1080"}); check("rejects authenticated SOCKS proxy clearly", p.returncode != 0 and "SOCKS" in p.stderr + p.stdout)
# 4 product mode
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(tmp / "pclip.mp4")], check=True)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=800x600:d=1", "-frames:v", "1", str(tmp / "pimg.png")], check=True)
p, r = run_worker({"mode": "product", "productName": "Brew Mug", "description": "A self-heating mug that keeps drinks warm.", "features": ["Keeps drinks at 55 degrees for three hours", "Charges on a magnetic base"], "inputVideos": [str(tmp / "pclip.mp4")]})
check("product demo from clips", r and sorted(set(streams(str(tmp / "up_brew-mug-demo.mp4")))) == ["audio", "video"], p.stderr[-300:] if not r else f"{r['seconds']}s, {r['visuals']}")
p, r = run_worker({"mode": "product", "productName": "Brew Img", "description": "A mug.", "features": ["Warm"], "referenceAssets": [str(tmp / "pimg.png")]})
check("product demo from images is labelled as stills", r and "still frames" in r["visuals"], (r or {}).get("visuals", ""))
p, _ = run_worker({"mode": "product", "productName": "X", "description": "Y", "features": []}); check("product mode refuses with no footage", p.returncode != 0 and "does not generate" in p.stderr + p.stdout)
print("ALL PASSED" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
