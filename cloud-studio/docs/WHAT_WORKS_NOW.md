# What works now (and what is switched off)

Last verified by running real code, not just compiling it.

## Enabled and tested
| Feature | How it was tested |
|---|---|
| Upload clips (Storage page) | Real API call on a local Worker with local R2; clips stored and listed |
| Join clips in order, optional audio swap (`openmontage-integration`) | Real FFmpeg on 720p/24fps clips with audio, plus a mixed-size clip with no audio; output duration and streams checked |
| Denoise + subtle colour grade (`cinematic-realism`) | Real FFmpeg; output frames differ from input; AI upscale is refused unless Real-ESRGAN is configured |
| Job staging (runner downloads the uploaded clips from the control plane) | Ran the same steps as `cloud-studio-run-job.yml` against a local Worker |
| Make Video page | Real headless browser; clip order, payloads and disabled states checked |
| Voice, revoice mode: each clip's speech goes to ElevenLabs Voice Changer (speech-to-speech) and comes back in ONE voice with the same words and timing; the new audio replaces the old and the clips are joined in order | `cloud-studio/branches/voiceover/test_voiceover.py` against a MOCK of the ElevenLabs service that really changes the audio: output pitch changed, length unchanged, picture and clip order untouched, identical voice/model/seed/settings sent for every clip |
| Voice, narrate mode: speak your text (or Gemini-written text) over your footage in the same voice; recording keeps playing underneath | Same test file (mock voice service) |
| Voice failures are explained and never fall back to a robotic voice; nothing is sent to the paid service if any clip lacks audio | Same test file: bad key, plan limit, rate limit, missing settings, silent clip |
| Workers can read only the Gemini and ElevenLabs keys | Local Worker: GitHub, R2 and other credentials return 403, a wrong token returns 401, the browser API shows no secret values |
| API auth, encrypted secrets, saved GitHub token used for dispatch | Local Worker plus 12 unit tests |

## Voice: what is and is not proven
- Proven here: everything in the table, but against a MOCK of ElevenLabs. I could not call the real service from here, so the real request format (taken from ElevenLabs' public documentation) and the real sound quality are untested.
- What it keeps: the words, timing and delivery of the original speech, so the mouth movements still line up. What it does not do: re-render mouths, so a voice with very different pacing habits can look slightly off. The job report lists the per-clip length difference and warns if a clip differs by more than half a second.
- Cost: ElevenLabs charges per use under your plan. Check their pricing page before large batches.
- Gemini: I found no Gemini feature that converts the voice of an existing recording. Gemini is only used (optionally) to write narration text.

## Why there is no website recording or sign-up automation
A browser on a GitHub runner could not be tested against real websites from here, and cloud servers are often challenged or blocked by real sites (Google's included). Because I cannot show it works without blocking, it was removed instead of shipped as a maybe. You supply the AI clips and your own recording of the product; the Studio adds the voice and assembles the video.

## Switched off by default (untested)
`ai-video-generation`, `character-consistency`, `lip-sync` and all Kaggle/GPU jobs. The API rejects them.
Set `EXPERIMENTAL_TOOLS=true` on the Worker only if you want to try them at your own risk.

## Not yet tested against real services
Cloudflare deploy, real R2 presigned uploads of the finished video, a real GitHub Actions run, Hugging Face model import.

## Making videos with your own clips (for example from Google Flow)
1. Create clips in Flow (your own account, your own method) and download them.
2. Open the Studio, go to Storage and upload the clips.
3. Go to Make Video. To join clips: tick them in playing order, optionally pick music, press Join.
4. To give your AI clips one consistent voice: tick the clips in order, choose "Change the voice..." in section 3 and press the button. To speak new text over footage instead, choose "Speak new text...".
5. Finish a video with denoise and colour grade if wanted.
6. Watch progress on the Jobs page.

Clips from Flow are short (about 8 seconds), so a one-minute video is roughly 8 clips.
