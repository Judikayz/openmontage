"""Real tests: real ffmpeg + espeak-ng, mock control plane. Run: python test_narrated_demo.py"""
import http.server, json, os, pathlib, re, subprocess, sys, tempfile, threading
HERE = pathlib.Path(__file__).parent; tmp = pathlib.Path(tempfile.gettempdir()); GEM = {"on": False, "bad": False}
class CP(http.server.BaseHTTPRequestHandler):
    def _j(s, code, obj): s.send_response(code); s.send_header("content-type", "application/json"); s.end_headers(); s.wfile.write(json.dumps(obj).encode())
    def do_GET(s):
        if s.path.endswith("/gemini") and GEM["on"]: return s._j(200, {"apiKey": "k", "defaultModel": "m"})
        s.send_response(404); s.end_headers()
    def do_POST(s):
        body = json.loads(s.rfile.read(int(s.headers.get("content-length", 0))))
        if ":generateContent" in s.path:
            n = max(body["contents"][0]["parts"][0]["text"].count("KEY POINTS") and json.loads(body["contents"][0]["parts"][0]["text"].split("KEY POINTS: ")[1]).__len__() + 1 - (1 if GEM["bad"] else 0), 1)
            return s._j(200, {"candidates": [{"content": {"parts": [{"text": json.dumps([{"text": f"MOCK NARRATION {i}"} for i in range(n)])}]}}]})
        s._j(200, {"key": "assets/" + body["name"], "uploadUrl": "http://localhost:8799/put/" + body["name"]})
    def do_PUT(s):
        n = int(s.headers.get("content-length", 0)); (tmp / ("up_" + s.path.rsplit("/", 1)[-1])).write_bytes(s.rfile.read(n)); s.send_response(200); s.end_headers()
    def log_message(*a): pass
threading.Thread(target=http.server.HTTPServer(("localhost", 8799), CP).serve_forever, daemon=True).start()
def worker(payload):
    env = dict(os.environ, DEMO_TTS="espeak", WORKER_CALLBACK_TOKEN="cb", GEMINI_BASE_URL="http://localhost:8799", JOB_PAYLOAD_JSON=json.dumps(payload))
    p = subprocess.run([sys.executable, str(HERE / "worker.py"), "--job-id", "t", "--control-plane", "http://localhost:8799"], env=env, capture_output=True, text=True, timeout=600)
    return p, (json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else None)
def ff(*a): return subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *a], check=True)
def streams(f): return sorted(set(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.split()))
def psnr(a, b):
    o = subprocess.run(["ffmpeg", "-i", str(a), "-i", str(b), "-lavfi", "psnr", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"average:(\S+)", o); return 99.0 if not m or m.group(1) == "inf" else float(m.group(1))
ok = True
def check(name, cond, extra=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))
# footage: a 60s "screen recording" with a moving pattern and running time, plus a still image
# smooth colour that depends on time, so any frame reveals which moment of the recording it came from
ff("-f", "lavfi", "-i", "nullsrc=size=1280x720:rate=24:duration=60,geq=r='128+127*sin(T*0.5)':g='128+127*sin(T*0.5+2)':b='128+127*sin(T*0.5+4)',format=yuv420p", "-c:v", "libx264", "-crf", "12", str(tmp / "rec.mp4"))
ff("-f", "lavfi", "-i", "color=c=blue:s=800x600:d=1", "-frames:v", "1", str(tmp / "img.png"))
base = {"productName": "Brew Mug", "description": "A self-heating mug that keeps drinks warm.", "features": ["Keeps drinks at 55 degrees for three hours", "Charges on a magnetic base"]}
p, r = worker({**base, "inputVideos": [str(tmp / "rec.mp4")]})
check("clips + description make a video with audio", r and streams(tmp / "up_brew-mug-demo.mp4") == ["audio", "video"], (p.stderr[-250:] if not r else f"{r['seconds']}s, script={r['script']}"))
if r:
    d1 = r["segment_seconds"][0]; T = d1 + 1.0
    def rgb(src, t):
        ff("-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", str(tmp / "px.raw")); return list((tmp / "px.raw").read_bytes()[:3])
    dist = lambda a, b: sum(abs(x - y) for x, y in zip(a, b))
    got = rgb(tmp / "up_brew-mug-demo.mp4", T); cont, restart = dist(got, rgb(tmp / "rec.mp4", T)), dist(got, rgb(tmp / "rec.mp4", T - d1))
    check("recording plays on continuously (not restarted per sentence)", cont < 25 and restart > 60, f"colour distance vs continuous {cont}, vs restart {restart}")
    check("report lists narration and says footage not looped", "Introducing Brew Mug" in (tmp / "up_brew-mug-demo.md").read_text() and r["footage_looped"] is False)
p, r = worker({**base, "productName": "Short", "inputVideos": [str(tmp / "rec.mp4")], "script": ["Hello. " * 40]})
check("your own script is used word for word", r and r["script"] == "your own script" and "Hello. Hello." in (tmp / "up_short-demo.md").read_text())
ff("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(tmp / "tiny.mp4"))
p, r = worker({**base, "productName": "Loopy", "inputVideos": [str(tmp / "tiny.mp4")]}); check("short footage is looped and the report says so", r and r["footage_looped"] is True)
p, r = worker({**base, "productName": "Stills", "referenceAssets": [str(tmp / "img.png")]}); check("images are labelled as still frames", r and r["footage"] == "still images" and "still frames" in (tmp / "up_stills-demo.md").read_text())
GEM["on"] = True; p, r = worker({**base, "productName": "Gem", "inputVideos": [str(tmp / "rec.mp4")]})
check("uses gemini when its key and model are saved", r and r["script"] == "gemini" and "MOCK NARRATION 0" in (tmp / "up_gem-demo.md").read_text(), (r or {}).get("script", p.stderr[-200:]))
GEM["bad"] = True; p, r = worker({**base, "productName": "Gem2", "inputVideos": [str(tmp / "rec.mp4")]}); check("falls back to the template when gemini's answer does not fit", r and r["script"] == "template", (r or {}).get("script", ""))
GEM["on"] = GEM["bad"] = False
p, _ = worker({**base}); check("refuses when no footage is supplied", p.returncode != 0 and "does not generate" in p.stderr)
p, _ = worker({"productName": "X", "inputVideos": [str(tmp / "rec.mp4")]}); check("refuses when there is nothing to say", p.returncode != 0 and "description or your own" in p.stderr)
p, _ = worker({**base, "inputVideos": ["/nope.mp4"]}); check("refuses when a footage file is missing", p.returncode != 0 and "not found" in p.stderr)
print("ALL PASSED" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
