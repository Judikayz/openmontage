#!/usr/bin/env python3
"""Voice-over tool (uses the ElevenLabs API key saved in Settings).

mode "revoice": your clips already contain a character speaking. Each clip's speech is sent to ElevenLabs
Voice Changer (speech-to-speech), which returns the SAME speech, timing and delivery in one chosen voice.
Because the words and timing are unchanged, the mouth movements in the video still line up. The video itself is
not altered, and mouths are not re-rendered.

mode "narrate": speak text you supply over your footage, in the same chosen voice (text-to-speech).

There is no offline or robotic fallback: if the voice service fails, the job fails with the reason.
"""
import argparse, json, os, pathlib, re, subprocess, sys, tempfile
import requests

W, H = 1280, 720
EL = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io").rstrip("/")


def log(msg): print(msg, file=sys.stderr, flush=True)


def run(cmd, **kw): return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=kw.pop("timeout", 3600), **kw)


def probe(path, entries="format=duration"):
    return run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", str(path)]).stdout.strip()


def duration(path): return float(probe(path))


def has_audio(path): return bool(run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)]).stdout.strip())


def get_cred(cp, token, provider):
    r = requests.get(f"{cp.rstrip('/')}/internal/credentials/{provider}", headers={"x-worker-callback-token": token}, timeout=30)
    if r.status_code == 404: return None
    r.raise_for_status(); return r.json()


def check_voice_reply(r):
    if r.status_code == 200: return
    why = {401: "ElevenLabs rejected the API key", 402: "ElevenLabs says the plan or credits do not allow this", 403: "ElevenLabs refused the request (plan or permissions)", 404: "ElevenLabs could not find that voice ID or model", 422: "ElevenLabs rejected the request settings", 429: "ElevenLabs rate limit or concurrency limit reached"}.get(r.status_code, f"ElevenLabs returned an error ({r.status_code})")
    raise SystemExit(f"{why}: {r.text[:200]}")


SETTINGS = json.dumps({"stability": 0.5, "similarity_boost": 0.75})


def revoice_audio(clip, work, i, cfg, remove_noise):
    """Send one clip's speech to Voice Changer. Returns the converted audio file."""
    if not has_audio(clip): raise SystemExit(f"Clip {i + 1} has no audio track to convert: {pathlib.Path(clip).name}")
    src = work / f"src{i}.wav"; run(["ffmpeg", "-y", "-i", clip, "-vn", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(src)])
    with src.open("rb") as f:
        r = requests.post(f"{EL}/v1/speech-to-speech/{cfg['voiceId']}", params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": cfg["apiKey"]},
                          data={"model_id": cfg["sts_model"], "remove_background_noise": "true" if remove_noise else "false", "seed": str(cfg["seed"]), "voice_settings": SETTINGS},
                          files={"audio": (src.name, f, "audio/wav")}, timeout=900)
    check_voice_reply(r); out = work / f"conv{i}.mp3"; out.write_bytes(r.content)
    if out.stat().st_size < 1000: raise SystemExit(f"ElevenLabs returned no audio for clip {i + 1}")
    return out


def speak(text, work, i, cfg):
    r = requests.post(f"{EL}/v1/text-to-speech/{cfg['voiceId']}", params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": cfg["apiKey"], "accept": "audio/mpeg"},
                      json={"text": text, "model_id": cfg["tts_model"], "seed": cfg["seed"], "voice_settings": json.loads(SETTINGS)}, timeout=300)
    check_voice_reply(r); out = work / f"say{i}.mp3"; out.write_bytes(r.content)
    if out.stat().st_size < 1000: raise SystemExit("ElevenLabs returned no audio")
    return out


def dims(clip):
    w, h = probe(clip, "stream=width,height").split("\n")[0].split(","); return int(w), int(h)


def revoice_join(clips, converted, work, out):
    """Replace each clip's audio with the converted audio and join in order. Returns per-clip length differences."""
    w, h = dims(clips[0]); parts, diffs = [], []
    for i, (clip, conv) in enumerate(zip(clips, converted)):
        dv, da = duration(clip), duration(conv); diffs.append(round(da - dv, 2)); piece = work / f"piece{i}.mp4"
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
        run(["ffmpeg", "-y", "-i", clip, "-i", str(conv), "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, "-af", "apad", "-t", f"{dv:.3f}", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-ar", "44100", "-ac", "2", str(piece)]); parts.append(piece)
    lst = work / "list.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)]); return diffs


def write_script(name, desc, points, notes, key, model, language):
    if key and model:
        base = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
        prompt = (f"Write a clear, friendly, detailed voice-over in {language} for a demo video of {name}. Use ONLY the details below. Do not invent features, prices, numbers or claims. "
                  f"One paragraph of 3 to 5 sentences for the intro and one for each key point. {notes or ''} Reply with JSON only: [{{\"text\":\"...\"}}].\nDESCRIPTION: {desc}\nKEY POINTS: {json.dumps(points)}")
        try:
            r = requests.post(f"{base}/v1beta/models/{model}:generateContent", params={"key": key}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=120); r.raise_for_status()
            segs = json.loads(re.search(r"\[.*\]", r.json()["candidates"][0]["content"]["parts"][0]["text"], re.S).group(0))
            if len(segs) == 1 + len(points) and all(isinstance(s.get("text"), str) and s["text"].strip() for s in segs): return [s["text"].strip() for s in segs], "gemini"
            log("gemini answer did not match the key points; using template")
        except Exception as e: log(f"gemini script failed ({e}); using template")
    return [f"Introducing {name}. {desc}".strip()] + [p.rstrip(".") + "." for p in points], "template"


def narrate_join(audio, clips, images, work, out):
    """Footage plays on continuously across the spoken parts; loops (and reports it) if narration is longer."""
    parts, offsets, secs = [], {}, []; clip_len = {c: duration(c) for c in clips}
    for i, ap in enumerate(audio):
        dur = duration(ap) + 0.5; secs.append(round(dur, 2)); piece = work / f"seg{i}.mp4"
        scale = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
        if clips:
            c = clips[i % len(clips)]; off = offsets.get(c, 0.0) % clip_len[c]; offsets[c] = off + dur; src = ["-stream_loop", "-1", "-ss", f"{off:.2f}", "-i", c]
        else: src = ["-loop", "1", "-framerate", "30", "-i", images[i % len(images)]]
        run(["ffmpeg", "-y", *src, "-i", str(ap), "-t", f"{dur:.2f}", "-vf", scale, "-map", "0:v", "-map", "1:a", "-af", "apad", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", str(piece)]); parts.append(piece)
    lst = work / "list.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts))
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
    j = json.loads(raw); mode = j.get("mode", "revoice"); clips, images = j.get("inputVideos") or [], j.get("referenceAssets") or []
    if mode not in ("revoice", "narrate"): raise SystemExit("mode must be revoice or narrate")
    if not clips and not (mode == "narrate" and images): raise SystemExit("Provide your own clips (inputVideos)" + (" or images (referenceAssets)" if mode == "narrate" else "") + ". This tool does not generate footage.")
    for f in clips + images:
        if not pathlib.Path(f).is_file(): raise SystemExit(f"Footage file not found: {f}")
    el = get_cred(a.control_plane, token, "elevenlabs")
    if not el or not el.get("apiKey") or not el.get("voiceId"): raise SystemExit("Save your ElevenLabs API key and Voice ID in Settings first. There is no fallback voice.")
    cfg = {"apiKey": el["apiKey"], "voiceId": el["voiceId"], "sts_model": el.get("modelId") or "eleven_multilingual_sts_v2", "tts_model": el.get("ttsModelId") or "eleven_multilingual_v2", "seed": int(j.get("seed", 12345))}
    work = pathlib.Path(tempfile.mkdtemp(prefix="vo-")); name = (j.get("productName") or "video").strip(); out = work / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + f"-{mode}.mp4"); info = {"mode": mode, "voice_id": cfg["voiceId"]}
    if mode == "revoice":
        for i, c in enumerate(clips):  # check everything before any paid call is made
            if not has_audio(c): raise SystemExit(f"Clip {i + 1} has no audio track to convert: {pathlib.Path(c).name}. Nothing was sent to ElevenLabs.")
        conv = [revoice_audio(c, work, i, cfg, bool(j.get("removeBackgroundNoise", True))) for i, c in enumerate(clips)]
        diffs = revoice_join(clips, conv, work, out); info.update(clips=len(clips), audio_length_difference_seconds=diffs, note="Words and timing come from the original speech, so mouth movements still line up; mouths are not re-rendered.")
        text = [f"Voice changed on {len(clips)} clip(s) using one voice, model {cfg['sts_model']}, seed {cfg['seed']}.", f"Audio length difference per clip (seconds): {diffs}"]
        if any(abs(d) > 0.5 for d in diffs): info["warning"] = "A converted clip differs from its video by more than 0.5s; check lip alignment on that clip."
    else:
        desc = (j.get("description") or "").strip(); own = [t.strip() for t in j.get("script", []) if isinstance(t, str) and t.strip()]
        if not own and not desc: raise SystemExit("Give a description or your own narration script")
        if own: texts, info["script"] = own, "your own script"
        else:
            gem = get_cred(a.control_plane, token, "gemini") or {}; texts, info["script"] = write_script(name, desc, [p.strip() for p in j.get("features", []) if p.strip()], j.get("notes"), gem.get("apiKey"), gem.get("defaultModel"), j.get("language", "English"))
        audio = [speak(t, work, i, cfg) for i, t in enumerate(texts)]; secs, looped = narrate_join(audio, clips, images, work, out)
        info.update(segment_seconds=secs, footage="clips" if clips else "still images", footage_looped=looped); text = [f"Script: {info['script']}", f"Footage: {info['footage']}; looped to fill the narration: {looped}", ""] + [f"{i}. {t}" for i, t in enumerate(texts, 1)]
    if not out.exists() or out.stat().st_size < 10000: raise RuntimeError("No valid video was produced")
    report = out.with_suffix(".md"); report.write_text("\n".join([f"# {mode.title()}: {name}", ""] + [f"- {k}: {v}" for k, v in info.items()] + [""] + text))
    print(json.dumps({"success": True, "assetKey": upload(a.control_plane, token, out, "video/mp4"), "reportKey": upload(a.control_plane, token, report, "text/markdown"), "seconds": round(duration(out), 1), **info}))


if __name__ == "__main__": main()
