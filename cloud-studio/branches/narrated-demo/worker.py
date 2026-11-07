#!/usr/bin/env python3
"""Narrated demo.

You supply the real footage (your AI video clips and/or your own screen recording of the product) and a short
description. This tool writes a voice-over from that description only (or uses your own script), speaks it, and
lays it over your footage. It does not generate footage and it does not browse or record websites.
"""
import argparse, asyncio, json, os, pathlib, re, subprocess, sys, tempfile
import requests

W, H = 1280, 720


def log(msg): print(msg, file=sys.stderr, flush=True)


def run(cmd, **kw): return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=kw.pop("timeout", 3600), **kw)


def probe_duration(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).stdout.strip())


def get_cred(cp, token, provider):
    r = requests.get(f"{cp.rstrip('/')}/internal/credentials/{provider}", headers={"x-worker-callback-token": token}, timeout=30)
    if r.status_code == 404: return None
    r.raise_for_status(); return r.json()


def write_script(name, desc, points, notes, key, model, language):
    """Gemini writes it from the supplied details only; otherwise a plain template. Returns (segments, source)."""
    if key and model:
        base = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
        prompt = (f"Write a clear, friendly, detailed voice-over in {language} for a demo video of {name}. Use ONLY the details below. "
                  "Do not invent features, prices, numbers or claims. One paragraph of 3 to 5 sentences for the intro and one for each key point. "
                  f"{notes or ''} Reply with JSON only: [{{\"text\":\"...\"}}].\nDESCRIPTION: {desc}\nKEY POINTS: {json.dumps(points)}")
        try:
            r = requests.post(f"{base}/v1beta/models/{model}:generateContent", params={"key": key}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120); r.raise_for_status()
            segs = json.loads(re.search(r"\[.*\]", r.json()["candidates"][0]["content"]["parts"][0]["text"], re.S).group(0))
            if len(segs) == 1 + len(points) and all(isinstance(s.get("text"), str) and s["text"].strip() for s in segs): return [s["text"].strip() for s in segs], "gemini"
            log("gemini answer did not match the key points; using template")
        except Exception as e: log(f"gemini script failed ({e}); using template")
    return [f"Introducing {name}. {desc}".strip()] + [p.rstrip(".") + "." for p in points], "template"


def synth(text, out_base, voice, language):
    """Natural voice via edge-tts; falls back to espeak-ng and says so in the result."""
    if os.environ.get("DEMO_TTS") != "espeak":
        try:
            import edge_tts
            path = str(out_base) + ".mp3"
            asyncio.run(edge_tts.Communicate(text, voice or "en-US-AriaNeural").save(path))
            if pathlib.Path(path).stat().st_size > 1000: return path, "edge-tts"
        except Exception as e: log(f"edge-tts unavailable ({e}); falling back to espeak-ng")
    path = str(out_base) + ".wav"
    run(["espeak-ng", "-v", (language or "en")[:2], "-s", "150", "-w", path, text]); return path, "espeak-ng (robotic fallback)"


def compose(texts, audio, clips, images, workdir, out):
    """One piece per spoken part. Clips play continuously (a recording is not restarted for every sentence)."""
    parts, offsets, secs = [], {}, []
    clip_len = {c: probe_duration(c) for c in clips}
    for i, ap in enumerate(audio):
        dur = probe_duration(ap) + 0.5; secs.append(round(dur, 2)); piece = workdir / f"seg{i}.mp4"
        scale = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
        if clips:
            c = clips[i % len(clips)]; off = offsets.get(c, 0.0) % clip_len[c]; offsets[c] = off + dur
            src = ["-stream_loop", "-1", "-ss", f"{off:.2f}", "-i", c]
        else: src = ["-loop", "1", "-framerate", "30", "-i", images[i % len(images)]]
        run(["ffmpeg", "-y", *src, "-i", str(ap), "-t", f"{dur:.2f}", "-vf", scale, "-map", "0:v", "-map", "1:a", "-af", "apad", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", str(piece)]); parts.append(piece)
    lst = workdir / "list.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])
    return secs, bool(clips) and sum(secs) > sum(clip_len.values()) + 0.5


def upload(cp, token, path, mime):
    r = requests.post(cp.rstrip("/") + "/internal/assets/upload-url", json={"name": path.name, "contentType": mime}, headers={"x-worker-callback-token": token}, timeout=60); r.raise_for_status(); u = r.json()
    with path.open("rb") as f: requests.put(u["uploadUrl"], data=f, headers={"content-type": mime}, timeout=(60, 1800)).raise_for_status()
    return u["key"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--job-id", required=True); ap.add_argument("--control-plane", required=True); a = ap.parse_args()
    raw, token = os.environ.get("JOB_PAYLOAD_JSON"), os.environ.get("WORKER_CALLBACK_TOKEN")
    if not raw or not token: raise SystemExit("JOB_PAYLOAD_JSON and WORKER_CALLBACK_TOKEN are required")
    j = json.loads(raw); name = (j.get("productName") or "").strip(); language = j.get("language", "English")
    desc = (j.get("description") or "").strip(); points = [p.strip() for p in j.get("features", []) if p.strip()]
    own = [t.strip() for t in j.get("script", []) if isinstance(t, str) and t.strip()]
    clips, images = j.get("inputVideos") or [], j.get("referenceAssets") or []
    if not name: raise SystemExit("productName is required")
    if not own and not desc: raise SystemExit("Give either a description or your own narration script")
    if not clips and not images: raise SystemExit("Provide your own clips or recording (inputVideos) or images (referenceAssets). This tool does not generate footage.")
    for f in clips + images:
        if not pathlib.Path(f).is_file(): raise SystemExit(f"Footage file not found: {f}")
    if own: texts, source = own, "your own script"
    else:
        gem = get_cred(a.control_plane, token, "gemini") or {}; texts, source = write_script(name, desc, points, j.get("notes"), gem.get("apiKey"), gem.get("defaultModel"), language)
    work = pathlib.Path(tempfile.mkdtemp(prefix="narr-")); out = work / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + "-demo.mp4")
    audio, backends = [], set()
    for i, t in enumerate(texts): p, b = synth(t, work / f"a{i}", j.get("voice"), language); audio.append(p); backends.add(b)
    secs, looped = compose(texts, audio, clips, images, work, out)
    if not out.exists() or out.stat().st_size < 10000: raise RuntimeError("No valid video was produced")
    report = out.with_suffix(".md")
    report.write_text("\n".join([f"# Narrated demo: {name}", "", f"- Script: {source}", f"- Voice: {', '.join(backends)}", f"- Footage: {'your clips/recording' if clips else 'your images (still frames, not video)'}", f"- Footage looped to fill the narration: {looped}", "", "## Narration", ""] + [f"{i}. {t}" for i, t in enumerate(texts, 1)]))
    print(json.dumps({"success": True, "assetKey": upload(a.control_plane, token, out, "video/mp4"), "reportKey": upload(a.control_plane, token, report, "text/markdown"), "seconds": round(probe_duration(out), 1), "segment_seconds": secs, "script": source, "voice": ", ".join(backends), "footage": "clips" if clips else "still images", "footage_looped": looped}))


if __name__ == "__main__": main()
