# OpenMontage Cloud Studio

Independent cloud control plane for video-production workflows. This repository does **not** contain or fork the original OpenMontage source. It integrates with a separately deployed OpenMontage instance through an HTTP adapter contract.

## What is implemented

- Responsive Vite/React control dashboard and workflow editor.
- Cloudflare Worker API, D1 schema/migrations, R2 signed-object access, AES-GCM encrypted provider secrets.
- Workflow/job CRUD, compute routing (`automatic|github|kaggle`), authenticated GitHub dispatch, worker callbacks, scheduled due-job dispatch, Telegram/email/WhatsApp notification adapters.
- Kaggle kernel submission adapter using the Kaggle CLI process and a generated `kernel-metadata.json`; GPU tasks only.
- Separate tool contracts and Docker runtime definitions on real Git branches (see `branches/`).
- Persistent model registry/cache manifest. R2 is the durable cache; GitHub Actions cache is only an opportunistic cache.

## Important verification boundary

This is a functional control-plane implementation, not a claim that heavyweight model inference has been run. No model weights are bundled. GPU inference, Kaggle account/quota availability, provider credentials, and a separately deployed OpenMontage endpoint must be supplied and tested in your accounts. The tool branches deliberately fail clearly when required model/runtime assets are absent; they do not return fake video outputs. See `docs/VERIFICATION.md` and `docs/LICENCES.md`.

## Repository branches

`main`, `ai-video-generation`, `character-consistency`, `lip-sync`, `cinematic-realism`, `openmontage-integration`. All are real Git branches and are included in `openmontage-cloud-studio.bundle`.

## Quick start

1. Create a Cloudflare D1 database and R2 bucket.
2. Configure Worker secrets (`ENCRYPTION_KEY`, `APP_AUTH_TOKEN`, `GITHUB_TOKEN`, optional provider credentials).
3. Set D1 database ID and R2 bucket binding in `apps/api/wrangler.toml`.
4. Apply migrations: `cd apps/api && npx wrangler d1 migrations apply DB --remote`.
5. Deploy Worker: `npx wrangler deploy`.
6. Deploy `apps/web` to Netlify with `VITE_API_BASE_URL` and `VITE_APP_TOKEN` configured. For production, replace the simple bearer-token login gate with an OIDC/Cloudflare Access identity integration before exposing it publicly.
7. Configure GitHub repository secrets `CONTROL_PLANE_URL` and `WORKER_CALLBACK_TOKEN`; add the Worker dispatch credentials on the Cloudflare side.
8. Upload this repository to a new GitHub repository. Do not upload it over `Judikayz/openmontage`.

Detailed steps: `docs/DEPLOYMENT.md`.
