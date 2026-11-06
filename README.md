# OpenMontage Cloud Studio

OpenMontage Cloud Studio is a cloud control plane and worker suite for AI-assisted video production. It combines a React/Vite workspace, Cloudflare Worker API, D1 metadata, R2 object storage, GitHub Actions execution, Hugging Face model import, and separate worker branches.

## Included in this build

- Responsive workspace pages for dashboard, projects, workflow builder, AI tools, character profiles, lip-sync, cinematic finishing, model library, storage, schedules, jobs, integrations, settings and history.
- Cloudflare Worker API for projects, characters, workflows, jobs, job logs, encrypted provider secrets, models, assets and schedules.
- D1 migrations for production projects, characters, scenes, job logs, provider test history and multipart upload metadata.
- AES-GCM encrypted provider credentials. Secrets are never returned to the frontend.
- GitHub Actions job dispatch, authenticated payload retrieval, asset staging, worker execution and result callbacks.
- Hugging Face model registration with revision pinning, private/gated access token support, resumable downloads, SHA-256 verification and R2 single-part or multipart uploads.
- R2-backed model restoration for GitHub Actions workers. The GitHub cache is an optimization; R2 remains the durable store.
- Real worker adapters: Diffusers video generation, Diffusers IP-Adapter reference-conditioned image generation, Wav2Lip invocation, FFmpeg finishing, and FFmpeg clip/audio assembly. Each adapter fails explicitly when its required model/runtime/checkpoint is absent; none fabricates successful media.
- Five feature branches: `ai-video-generation`, `character-consistency`, `lip-sync`, `cinematic-realism`, `openmontage-integration`.

## Important execution boundaries

A worker adapter is not the same as a bundled model. Large model weights are not included in this ZIP. Select and import compatible model repositories, configure model-specific runtime settings, and use a GPU-capable provider for models that require one. GitHub-hosted runners are CPU runners; Kaggle GPU execution currently requires the secure dispatcher described in `docs/KAGGLE.md`. Wav2Lip requires a separately licensed checkout and checkpoint. AI upscaling requires a configured Real-ESRGAN executable. The project deliberately reports these missing dependencies instead of returning fake output.

## Setup

1. Create Cloudflare D1 database `omcs`, R2 buckets `omcs-assets` and `omcs-models`.
2. Set `database_id` and exact allowed frontend origin in `apps/api/wrangler.toml`.
3. Apply all migrations in `apps/api/migrations` and deploy the Worker.
4. Set Worker secrets: `ENCRYPTION_KEY` (base64 32-byte key), `MODEL_IMPORT_WORKER_TOKEN`, `WORKER_CALLBACK_TOKEN`. Configure GitHub dispatch variables/secrets as documented in `docs/DEPLOYMENT.md`.
5. Protect the Worker with Cloudflare Access. Do not put API keys or bearer tokens in `VITE_*` frontend variables.
6. Deploy `apps/web` with `VITE_API_BASE_URL` pointing to the Worker.
7. Add GitHub Actions secrets `CONTROL_PLANE_URL`, `MODEL_IMPORT_WORKER_TOKEN`, and `WORKER_CALLBACK_TOKEN`.
8. In Integrations, save R2 credentials as JSON: `{"accountId":"...","accessKeyId":"...","secretAccessKey":"...","bucketName":"omcs-models"}`. Test R2 before importing models.
9. Save GitHub credentials as JSON: `{"token":"...","owner":"Judikayz","repo":"openmontage","ref":"main"}`. Save Hugging Face token as `{"token":"hf_..."}` for gated/private models.
10. Register model repositories in Model Library, wait for `ready`, then select model IDs in a workflow.

## Local development

```bash
cd apps/web && npm install && npm run dev
cd apps/api && npm install && npm run typecheck && npm test
```

See `docs/DEPLOYMENT.md`, `docs/MODEL_LIBRARY.md`, `docs/INTEGRATIONS.md`, `docs/KAGGLE.md`, and `docs/IMPLEMENTATION_STATUS.md` before deployment.
