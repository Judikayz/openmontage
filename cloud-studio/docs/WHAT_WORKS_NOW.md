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
| API auth, encrypted secrets, saved GitHub token used for dispatch | Local Worker plus 12 unit tests |
| Demo Recorder, website mode: real Chromium walkthrough, narration built from the page text, voice mixed in | `branches/demo-recorder/test_demo.py` against a local test site: 16 checks incl. sign-up stops at email verification, CAPTCHA and terms boxes; blocks private/metadata/file URLs; password never appears in the result or report |
| Demo Recorder, product mode: narrated video from your own clips or images (images are labelled as stills) | Same test file; refuses to run if you give it no footage |
| Workers can read only the Gemini, sign-up and proxy credentials | Local Worker: GitHub/R2 credentials return 403, wrong token 401, browser API shows no values |

## Demo Recorder: what is and is not proven
- Proven here: everything in the table above, using a local test site and a robotic offline voice (espeak-ng).
- Not proven here (my sandbox cannot reach these): the natural voice (edge-tts; the worker falls back to the robotic voice and says so in the job result), the real Gemini call (only a mock was tested), a real third-party website, and running on a real GitHub runner.
- Sign-up: it only uses the email/name/password you save in Settings, never invents identities, and stops at CAPTCHAs, terms boxes and email verification. The result says exactly what happened and never claims an account exists unless the site shows it. Only use it on sites whose rules allow it.
- The narration comes only from text on the pages (or your own description in product mode). Gemini, if its key and default model are saved in Settings, writes it more fully; otherwise a plainer template is used.

## Using your own IP for the recording (untested)
Save a proxy URL in Settings (provider `proxy`). The runner then sends all browser traffic through it. You must provide the proxy yourself: it has to be reachable from the internet and protected with a login (for example an HTTP proxy on your device or PC exposed through a tunnel). Chromium cannot log in to SOCKS proxies, so use an HTTP proxy with a login, or a SOCKS proxy without a login that is only reachable through your tunnel. Your device must stay online, a mobile carrier can change your IP, and sites can still flag automation.

## Switched off by default (untested)
`ai-video-generation`, `character-consistency`, `lip-sync` and all Kaggle/GPU jobs. The API rejects them.
Set `EXPERIMENTAL_TOOLS=true` on the Worker only if you want to try them at your own risk.

## Not yet tested against real services
Cloudflare deploy, real R2 presigned uploads of the finished video, a real GitHub Actions run, Hugging Face model import.

## Making videos with Google Flow clips
1. Create clips in Flow (your own account, your own method) and download them.
2. Open the Studio, go to Storage and upload the clips.
3. Go to Make Video, tick the clips in playing order, optionally pick music, press Join.
4. Finish the joined video with denoise and colour grade if wanted.
5. Watch progress on the Jobs page.

Clips from Flow are short (about 8 seconds), so a one-minute video is roughly 8 clips.
