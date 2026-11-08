"""Real tests: real ffmpeg, mock ElevenLabs/Gemini/control plane. Run: python test_voiceover.py
The mock voice service pitch-shifts the uploaded speech (same length), so we can prove the pipeline
swaps the audio, keeps timing, keeps clip order, and sends identical voice settings for every clip."""
import email, email.policy, http.server, json, os, pathlib, subprocess, sys, tempfile, threading
import numpy as np
HERE = pathlib.Path(__file__).parent; tmp = pathlib.Path(tempfile.gettempdir())
S = {"creds": "ok", "status": 200, "gem": False, "bad": False}; CALLS = []
def tone(freq, secs, extra=()):
    return subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={secs}", *extra, "-f", "mp3", "-"], capture_output=True, check=True).stdout
class H(http.server.BaseHTTPRequestHandler):
    def _j(s, code, obj): s.send_response(code); s.send_header("content-type", "application/json"); s.end_headers(); s.wfile.write(json.dumps(obj).encode())
    def do_GET(s):
        if s.path.endswith("/elevenlabs"):
            if S["creds"] == "missing": s.send_response(404); s.end_headers(); return
            return s._j(200, {"apiKey": "bad" if S["creds"] == "bad" else "xi-test", "voiceId": "VOICE1"})
        if s.path.endswith("/gemini") and S["gem"]: return s._j(200, {"apiKey": "k", "defaultModel": "m"})
        s.send_response(404); s.end_headers()
    def do_POST(s):
        body = s.rfile.read(int(s.headers.get("content-length", 0)))
        if s.path.startswith("/v1/speech-to-speech/") or s.path.startswith("/v1/text-to-speech/"):
            key = s.headers.get("xi-api-key")
            if key == "bad": return s._j(401, {"detail": "invalid api key"})
            if S["status"] != 200: return s._j(S["status"], {"detail": "plan limit"})
            if s.path.startswith("/v1/speech-to-speech/"):
                msg = email.message_from_bytes(b"Content-Type: " + s.headers["content-type"].encode() + b"\r\n\r\n" + body, policy=email.policy.default); f = {}
                for part in msg.iter_parts(): f[part.get_param("name", header="content-disposition")] = part.get_payload(decode=True)
                CALLS.append({"kind": "sts", "voice": s.path.split("?")[0].rsplit("/", 1)[-1], "key": key, "model": f["model_id"].decode(), "seed": f["seed"].decode(), "noise": f["remove_background_noise"].decode(), "settings": f["voice_settings"].decode()})
                (tmp / "mock_in.wav").write_bytes(f["audio"])  # shift pitch by x1.3 but keep the length
                out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(tmp / "mock_in.wav"), "-af", "asetrate=44100*1.3,aresample=44100,atempo=0.769231", "-f", "mp3", "-"], capture_output=True, check=True).stdout
            else:
                j = json.loads(body); CALLS.append({"kind": "tts", "voice": s.path.split("?")[0].rsplit("/", 1)[-1], "key": key, "text": j["text"], "model": j["model_id"], "seed": str(j["seed"])})
                out = tone(600, round(0.08 * len(j["text"].split()) + 0.3, 2))
            s.send_response(200); s.send_header("content-type", "audio/mpeg"); s.end_headers(); s.wfile.write(out); return
        if ":generateContent" in s.path:
            n = json.loads(json.loads(body)["contents"][0]["parts"][0]["text"].split("KEY POINTS: ")[1]).__len__() + 1 - (1 if S["bad"] else 0)
            return s._j(200, {"candidates": [{"content": {"parts": [{"text": json.dumps([{"text": f"GEMINI PART {i}"} for i in range(max(n, 1))])}]}}]})
        d = json.loads(body); s._j(200, {"key": "assets/" + d["name"], "uploadUrl": "http://localhost:8799/put/" + d["name"]})
    def do_PUT(s):
        n = int(s.headers.get("content-length", 0)); (tmp / ("up_" + s.path.split("?")[0].rsplit("/", 1)[-1])).write_bytes(s.rfile.read(n)); s.send_response(200); s.end_headers()
    def log_message(*a): pass
threading.Thread(target=http.server.HTTPServer(("localhost", 8799), H).serve_forever, daemon=True).start()
def worker(payload):
    env = dict(os.environ, WORKER_CALLBACK_TOKEN="cb", ELEVENLABS_BASE_URL="http://localhost:8799", GEMINI_BASE_URL="http://localhost:8799", JOB_PAYLOAD_JSON=json.dumps(payload))
    p = subprocess.run([sys.executable, str(HERE / "worker.py"), "--job-id", "t", "--control-plane", "http://localhost:8799"], env=env, capture_output=True, text=True, timeout=900)
    return p, (json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else None)
def ff(*a): subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *a], check=True)
def dur(f): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout)
def streams(f): return sorted(set(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.split()))
def peak_hz(f, start=0.5, secs=1.5):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(start), "-t", str(secs), "-i", str(f), "-vn", "-ac", "1", "-ar", "44100", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(float); sp = np.abs(np.fft.rfft(x * np.hanning(len(x)))); return float(np.argmax(sp) * 44100 / len(x))
def rgb(f, t):
    ff("-ss", f"{t:.2f}", "-i", str(f), "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", str(tmp / "px.raw")); return list((tmp / "px.raw").read_bytes()[:3])
ok = True
def check(name, cond, extra=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))
# two "AI clips" that already contain speech (a 440 Hz stand-in), red then blue, 3s and 4s; one silent clip
for n, col, secs in (("a", "red", 3), ("b", "blue", 4)):
    ff("-f", "lavfi", "-i", f"color=c={col}:s=1280x720:r=24:d={secs}", "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(tmp / f"v{n}.mp4"))
ff("-f", "lavfi", "-i", "color=c=green:s=1280x720:r=24:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(tmp / "silent.mp4"))
A, B = str(tmp / "va.mp4"), str(tmp / "vb.mp4")
# 1. revoice two clips
CALLS.clear(); p, r = worker({"mode": "revoice", "productName": "Rv", "inputVideos": [A, B]}); out = tmp / "up_rv-revoice.mp4"
check("revoice succeeds and returns video + audio", r and streams(out) == ["audio", "video"], p.stderr[-300:] if not r else "")
if r:
    check("video length is unchanged (timing preserved)", abs(dur(out) - 7.0) < 0.25, f"{dur(out):.2f}s vs 7.00s")
    h0, h1 = peak_hz(tmp / "va.mp4"), peak_hz(out)
    check("the speech audio was actually replaced with the converted voice", abs(h0 - 440) < 25 and abs(h1 - 572) < 40, f"original ~{h0:.0f} Hz, output ~{h1:.0f} Hz")
    c1, c2 = rgb(out, 1.0), rgb(out, 4.5)
    check("clips stay in order and the picture is untouched", c1[0] > 150 and c1[2] < 90 and c2[2] > 150 and c2[0] < 90, f"t=1s {c1}, t=4.5s {c2}")
    check("one identical voice, model, seed and settings sent for every clip", len(CALLS) == 2 and len({(c['voice'], c['model'], c['seed'], c['settings'], c['key']) for c in CALLS}) == 1 and CALLS[0]["voice"] == "VOICE1", str(CALLS[0]))
    check("background noise removal is on by default and can be switched off", CALLS[0]["noise"] == "true")
    CALLS.clear(); worker({"mode": "revoice", "productName": "Rv2", "inputVideos": [A], "removeBackgroundNoise": False}); check("noise removal flag passes through when off", CALLS and CALLS[0]["noise"] == "false")
    check("report names the clip count and timing differences", "audio_length_difference_seconds" in (tmp / "up_rv-revoice.md").read_text())
# 2. failures are clear and never fall back to another voice
CALLS.clear(); p, _ = worker({"mode": "revoice", "productName": "S", "inputVideos": [A, str(tmp / "silent.mp4")]}); check("a clip with no speech track is refused before any paid call", p.returncode != 0 and "no audio track" in p.stderr and len(CALLS) == 0, f"api calls made: {len(CALLS)}")
S["creds"] = "bad"; p, _ = worker({"mode": "revoice", "productName": "S", "inputVideos": [A]}); check("a rejected API key fails with the reason", p.returncode != 0 and "rejected the API key" in p.stderr and not (tmp / "up_s-revoice.mp4").exists())
S["creds"] = "ok"; S["status"] = 429; p, _ = worker({"mode": "revoice", "productName": "S", "inputVideos": [A]}); check("a rate limit fails with the reason (no fallback voice)", p.returncode != 0 and "rate limit" in p.stderr); S["status"] = 402
p, _ = worker({"mode": "revoice", "productName": "S", "inputVideos": [A]}); check("credits/plan problems are explained", p.returncode != 0 and "plan or credits" in p.stderr); S["status"] = 200
S["creds"] = "missing"; p, _ = worker({"mode": "revoice", "productName": "S", "inputVideos": [A]}); check("missing ElevenLabs settings tell you to save them", p.returncode != 0 and "Settings" in p.stderr and "no fallback" in p.stderr.lower()); S["creds"] = "ok"
p, _ = worker({"mode": "revoice", "productName": "S"}); check("refuses with no footage", p.returncode != 0 and "does not generate" in p.stderr)
p, _ = worker({"mode": "revoice", "productName": "S", "inputVideos": ["/nope.mp4"]}); check("refuses a missing file", p.returncode != 0 and "not found" in p.stderr)
# 3. narrate mode: same voice for every part, footage keeps playing
ff("-f", "lavfi", "-i", "nullsrc=size=1280x720:rate=24:duration=60,geq=r='128+127*sin(T*0.5)':g='128+127*sin(T*0.5+2)':b='128+127*sin(T*0.5+4)',format=yuv420p", "-c:v", "libx264", "-crf", "12", str(tmp / "rec.mp4"))
CALLS.clear(); p, r = worker({"mode": "narrate", "productName": "Nar", "description": "A mug that keeps drinks warm.", "features": ["Stays hot for hours", "Charges on a base"], "inputVideos": [str(tmp / "rec.mp4")]})
check("narrate succeeds with video + audio", r and streams(tmp / "up_nar-narrate.mp4") == ["audio", "video"], p.stderr[-300:] if not r else f"{r['seconds']}s")
if r:
    check("every spoken part uses the same voice and seed", len(CALLS) == 3 and len({(c['voice'], c['model'], c['seed']) for c in CALLS}) == 1, f"{len(CALLS)} calls")
    d1 = r["segment_seconds"][0]; T = d1 + 1.0; got = rgb(tmp / "up_nar-narrate.mp4", T); dist = lambda a, b: sum(abs(x - y) for x, y in zip(a, b))
    check("the recording plays on continuously under the narration", dist(got, rgb(tmp / "rec.mp4", T)) < 25 and dist(got, rgb(tmp / "rec.mp4", T - d1)) > 60)
CALLS.clear(); p, r = worker({"mode": "narrate", "productName": "Own", "inputVideos": [str(tmp / "rec.mp4")], "script": ["Exactly this sentence.", "And this one."]}); check("your own script is spoken word for word", r and [c["text"] for c in CALLS] == ["Exactly this sentence.", "And this one."] and r["script"] == "your own script")
S["gem"] = True; CALLS.clear(); p, r = worker({"mode": "narrate", "productName": "Gm", "description": "x", "features": ["y"], "inputVideos": [str(tmp / "rec.mp4")]}); check("gemini can write the words, ElevenLabs still speaks them", r and r["script"] == "gemini" and CALLS and CALLS[0]["text"] == "GEMINI PART 0")
S["bad"] = True; p, r = worker({"mode": "narrate", "productName": "Gm2", "description": "x", "features": ["y"], "inputVideos": [str(tmp / "rec.mp4")]}); check("a bad gemini answer falls back to the plain template text", r and r["script"] == "template"); S["gem"] = S["bad"] = False
print("ALL PASSED" if ok else "SOME FAILED"); sys.exit(0 if ok else 1)
