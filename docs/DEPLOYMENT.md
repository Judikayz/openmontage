# Deployment guide (phone-friendly)

## Cloudflare
1. In Cloudflare dashboard create a D1 database named `omcs` and an R2 bucket named `omcs-assets`.
2. Edit `apps/api/wrangler.toml`: replace `database_id`; keep binding names `DB` and `ASSETS`.
3. Install Wrangler in a local/CI environment: `npm install -g wrangler`; authenticate with `wrangler login`.
4. From `apps/api`, run `wrangler d1 migrations apply omcs --remote`, then `wrangler deploy`.
5. Add Worker secrets in Cloudflare dashboard > Workers > Settings > Variables: `APP_AUTH_TOKEN`, `ENCRYPTION_KEY` (32 random bytes, base64), `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`, `WORKER_CALLBACK_TOKEN`. Optional: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `EMAIL_WEBHOOK_URL`, `WHATSAPP_WEBHOOK_URL`.
6. Do not put Cloudflare API tokens in frontend settings. They are deployment/admin credentials and should remain in the operator's secret manager.

## GitHub
1. Create a new repository, e.g. `openmontage-cloud-studio`; do not overwrite `Judikayz/openmontage`.
2. Push `main` and the tool branches from the supplied Git bundle (see `docs/BRANCHES.md`).
3. Add repository Actions secrets `CONTROL_PLANE_URL` and `WORKER_CALLBACK_TOKEN`.
4. Enable Actions. Standard GitHub-hosted runners are CPU-only; workflows do not claim GPU access.

## Netlify
1. Import the new GitHub repository, set base directory `apps/web`, build command `npm ci && npm run build`, publish directory `dist`.
2. Set `VITE_API_BASE_URL` to the deployed Worker URL and `VITE_APP_TOKEN` to the same app bearer token configured as `APP_AUTH_TOKEN`.
3. For production/public use, put Cloudflare Access or a real identity provider in front of the app. The bearer token approach is a private MVP gate, not multi-user identity management.

## Kaggle
Install Kaggle CLI in the GitHub orchestration environment, supply Kaggle credentials only to the secure orchestration runtime, and configure username/kernel owner. The adapter generates kernel metadata and submits via `kaggle kernels push`; the account must have GPU quota and accepted competition/dataset terms where applicable. Never pass Kaggle API keys as workflow-dispatch inputs.

## Model caching
Use R2 as persistent source of truth for model artifacts. GitHub cache is an optional layer keyed by model + revision + lockfile hash; eviction is normal. Avoid checking model weights into Git or baking them into Docker images.
