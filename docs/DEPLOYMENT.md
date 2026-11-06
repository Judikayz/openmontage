# Deployment guide

## 1. Cloudflare resources

1. Create a D1 database named `omcs`.
2. Create R2 bucket `omcs-assets` for uploaded/generated media.
3. Create a separate private R2 bucket named `omcs-models` for model weights.
4. Edit `apps/api/wrangler.toml`: replace `database_id`; set `ALLOWED_ORIGIN` to the exact Netlify site origin; keep the `ASSETS` and `MODELS` bucket bindings aligned with the bucket names above.
5. From `apps/api`, run `npx wrangler d1 migrations apply omcs --remote`, then `npx wrangler deploy`.
6. Generate an AES key with `openssl rand -base64 32`; set it using `npx wrangler secret put ENCRYPTION_KEY`.
7. Generate a separate random token for model-import workers. Set `npx wrangler secret put MODEL_IMPORT_WORKER_TOKEN`.
8. Set Worker variables `GITHUB_OWNER` and `GITHUB_REPO`, plus secret `WORKER_CALLBACK_TOKEN`. Save a GitHub fine-grained token in Settings → Other provider credentials → `github` (as a token or JSON containing `token`, `owner`, `repo`, and optional `ref`). The token needs repository Actions workflow-dispatch permission. For headless deployments, `GITHUB_TOKEN` can be set as a Worker secret instead.
9. Set Worker variables `CF_ACCESS_TEAM_DOMAIN` (team domain only, e.g. `your-team.cloudflareaccess.com`) and `CF_ACCESS_AUD` (the Access application audience tag). `MODEL_BUCKET_NAME` is `omcs-models`.

## 2. Cloudflare Access (required for production)

Create a Cloudflare Access self-hosted application for the Worker API hostname. Configure an allow policy for your own identity. Set the Worker variables `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`, and `ALLOWED_ORIGIN` to the exact Netlify origin. The Worker verifies the Cloudflare Access JWT signature, issuer, audience and expiry. The frontend uses the Access session cookie with credentialed CORS; it does not embed an API bearer token. Do not deploy the API publicly without Access protection.

## 3. GitHub repository

1. Create a new repository; do not overwrite `Judikayz/openmontage`.
2. Restore the included Git bundle and push all branches (see `docs/BRANCHES.md`).
3. In repository **Settings → Secrets and variables → Actions**, add:
   - `CONTROL_PLANE_URL`: deployed Worker URL.
   - `MODEL_IMPORT_WORKER_TOKEN`: exactly the same random value as the Worker secret.
   - `WORKER_CALLBACK_TOKEN`: shared credential used by the runner to fetch jobs and report completion.
4. Enable GitHub Actions. Standard GitHub-hosted runners are CPU-only; they do not provide GPUs.

## 4. Netlify frontend

1. Import the new repository.
2. Set base directory `apps/web`, build command `npm install && npm run build`, publish directory `dist`.
3. Set only `VITE_API_BASE_URL` to the deployed Worker URL. Never put Cloudflare, GitHub, Kaggle, R2, AI-provider or API bearer credentials in `VITE_*` variables.
4. Ensure the Worker `ALLOWED_ORIGIN` exactly matches the Netlify site origin, including `https://` and without a trailing slash.

## 5. Model storage setup

Follow `MODEL_LIBRARY.md` to enter R2 Account ID, Access Key ID, Secret Access Key and bucket name once in Settings. The bucket must be `omcs-models`. Use the Settings test button to verify the saved S3 credentials and Worker bucket binding. Then add public Hugging Face models in Model Library.

## 6. Kaggle

The Kaggle adapter uses the Kaggle CLI/kernel submission process and requires valid Kaggle account credentials, a valid kernel owner/metadata and available accelerator quota. Never pass Kaggle API keys as workflow-dispatch inputs. **The current adapter does not yet stage registered R2 model weights into Kaggle kernels**, so model-based Kaggle GPU execution is not complete.

## 7. Local checks

Run `npm install && npm run build` in `apps/web`, and `npm install && npm run typecheck && npm test` in `apps/api` in an environment with package-registry access. Run Python syntax checks for `infra/model-cache/*.py`. The current build environment used to package this update could not reach npm registry, so frontend/backend package builds were not verified here.
