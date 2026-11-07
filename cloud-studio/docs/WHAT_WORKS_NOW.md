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
| Narrated Demo: your own clips or recording plus a description (or your own script) become a narrated MP4. The recording plays on continuously, loops if the narration is longer (and says so), images are labelled as stills | `cloud-studio/branches/narrated-demo/test_narrated_demo.py`: 12 checks with real FFmpeg and a time-coded test video; refuses when you give it no footage, nothing to say, or a missing file |
| Workers can read only the Gemini key | Local Worker: GitHub and R2 credentials return 403, a wrong token returns 401, the browser API shows no secret values |
| API auth, encrypted secrets, saved GitHub token used for dispatch | Local Worker plus 12 unit tests |

## Narrated Demo: what is and is not proven
- Proven here: everything in the table above, using a robotic offline voice (espeak-ng) and a mock Gemini.
- Not proven here (my sandbox cannot reach these): the natural voice (edge-tts; if it fails the worker falls back to the robotic voice and says so in the job result), the real Gemini service, and a run on a real GitHub runner.
- The narration comes only from what you type (or your own script). Gemini, if its key and default model are saved in Settings, writes it more fully; otherwise a plain template is used.

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
4. To add a voice-over to your clips or screen recording: tick the footage, fill in section 3, press Create narrated demo.
5. Finish a video with denoise and colour grade if wanted.
6. Watch progress on the Jobs page.

Clips from Flow are short (about 8 seconds), so a one-minute video is roughly 8 clips.
