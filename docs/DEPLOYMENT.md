# Deployment guide

## 1. Cloudflare resources

1. Create D1 database `omcs`.
2. Create R2 buckets `omcs-assets` and private `omcs-models`.
3. Edit `apps/api/wrangler.toml`: set D1 `database_id`, exact `ALLOWED_ORIGIN`, and `ADMIN_EMAIL` to the owner's Cloudflare Access email. Confirm bucket bindings.
4. Apply all migrations from `apps/api/migrations` in order (`0001` through `0004`) with `npx wrangler d1 migrations apply omcs --remote`.
5. Generate an AES key with `openssl rand -base64 32`; set Worker secret `ENCRYPTION_KEY`.
6. Set Worker secrets `MODEL_IMPORT_WORKER_TOKEN` and `WORKER_CALLBACK_TOKEN` to separate random values.
7. Set `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`, `ALLOWED_ORIGIN`, `ADMIN_EMAIL` and `MODEL_BUCKET_NAME=omcs-models` as Worker variables. Deploy with `npx wrangler deploy`.

## 2. Cloudflare Access and roles

Create a Cloudflare Access self-hosted application for the Worker API hostname. Allow only the intended team members. The owner email configured in `ADMIN_EMAIL` is administrator. In the dashboard Users page, the administrator can assign `admin`, `editor` or read-only `viewer` roles to additional Access emails. Adding a role does not invite a person to Cloudflare Access; they must already be admitted by the Access policy.

The Worker verifies the Access JWT signature, issuer, audience and expiry. Do not deploy the API publicly without Access protection. For local development, use a separate non-production setup.

## 3. Integrations

Use the dashboard Integrations page to save credentials as structured fields. Provider values are encrypted in D1 and are never returned to the browser.

- GitHub: token, owner, repository and dispatch ref. The token needs Actions workflow-dispatch permission.
- Hugging Face: token for private/gated model import.
- Gemini: API key and optional default model for prompt enhancement.
- R2: S3 credentials scoped to `omcs-models`.
- Kaggle: username, API key and trusted dispatcher URL. Also set Worker secret `KAGGLE_DISPATCHER_TOKEN` and configure the same token in the dispatcher. See `KAGGLE.md`.

## 4. GitHub repository and Actions

Restore the included Git bundle and push the six branches listed in `BRANCHES.md`. In repository **Settings → Secrets and variables → Actions**, add:

- `CONTROL_PLANE_URL`: deployed Worker URL.
- `MODEL_IMPORT_WORKER_TOKEN`: same value as the Worker secret.
- `WORKER_CALLBACK_TOKEN`: same value as the Worker secret.

Enable GitHub Actions. For lip-sync, optionally add `WAV2LIP_REPO_URL` as a GitHub Actions secret pointing to a licensed Wav2Lip checkout. Standard GitHub-hosted runners are CPU-only; GPU-required jobs route to Kaggle and require the trusted dispatcher. Model import and CPU-compatible workflows run on GitHub Actions.

## 5. Frontend

Deploy `apps/web` to Netlify with base directory `apps/web`, build command `npm install && npm run build`, publish directory `dist`, and only `VITE_API_BASE_URL` pointing to the Worker. Never put provider credentials or API bearer tokens in `VITE_*` variables. The Worker `ALLOWED_ORIGIN` must exactly match the deployed site origin.

## 6. Model storage

Follow `MODEL_LIBRARY.md`. The configured R2 S3 credentials must point to `omcs-models`, matching the `MODELS` binding. The `ASSETS` binding is used for small browser uploads. Model files larger than 5 GiB use multipart R2 uploads. Model weights are not included in the repository.

## 7. Local verification

Run `npm install && npm run build` in `apps/web`, and `npm install && npm run typecheck && npm test` in `apps/api` in an environment with npm registry access. Run Python syntax checks for worker and model-cache scripts. Static checks do not replace live Cloudflare, R2, GitHub, Kaggle or model-inference tests.
