# OpenMontage Cloud Studio

Independent cloud control plane for video-production workflows. This repository does **not** contain, clone or recreate the original `Judikayz/openmontage` source. It connects to a separately deployed OpenMontage instance through an adapter contract.

## Model Library added

The dashboard now includes a Model Library and dedicated R2 configuration. Register a public Hugging Face repository using a model name, URL/ID and category. The control plane queues a GitHub Actions import job, inspects the repository file manifest, downloads and verifies files, and stores them in a dedicated Cloudflare R2 bucket. The R2 S3 credentials are encrypted in D1 and are never sent to GitHub Actions. The Worker issues short-lived object-scoped upload/download URLs.

GitHub-executed jobs can include registered model IDs. The runner checks the GitHub Actions cache first and restores missing files from R2. R2 is the durable source of truth; GitHub cache is temporary and may be evicted. A runner still needs local disk copies while inference runs. See `docs/MODEL_LIBRARY.md` and `infra/model-cache/README.md`.

**Current model-import boundaries:** public Hugging Face repositories only; one file must be no larger than 5 GiB (single-part PUT); GitHub runner disk/time quotas apply. Private/gated Hugging Face repositories, arbitrary download URLs, multipart uploads and Kaggle model staging are not implemented. The importer does not prove model inference compatibility or model licence suitability.

## Existing platform scope

- Responsive React/Vite dashboard and workflow editor.
- Cloudflare Worker API, D1 migrations, separate R2 asset and model buckets.
- AES-256-GCM encrypted provider credentials.
- Cloudflare Access JWT verification for dashboard API authentication; do not put API credentials in `VITE_*` variables.
- Workflow/job records, automatic/GitHub/Kaggle routing, GitHub Actions dispatch and a basic Cloudflare Cron scheduler.
- Kaggle CLI submission adapter and separate tool contracts on real Git branches.

This is not yet a fully verified production video-generation studio. No large model weights are bundled, and no real GPU inference was run in this environment. Tool-specific model execution, Kaggle R2 staging, full recurring schedule semantics, and live integration credentials still require deployment and account-level tests. Read `docs/VERIFICATION.md` before treating any component as production-ready.

## Real Git branches

`main`, `ai-video-generation`, `character-consistency`, `lip-sync`, `cinematic-realism`, `openmontage-integration`. The repository includes `openmontage-cloud-studio.bundle` with branch references.

## Quick start

1. Create Cloudflare D1 database `omcs`, R2 bucket `omcs-assets`, and private R2 bucket `omcs-models`.
2. Configure `apps/api/wrangler.toml` with your D1 database ID and exact Netlify origin.
3. Apply migrations and deploy the Worker. Set `ENCRYPTION_KEY`, `MODEL_IMPORT_WORKER_TOKEN`, GitHub dispatch credentials and callback token as Worker secrets.
4. Protect the Worker API with a Cloudflare Access application. Set `CF_ACCESS_TEAM_DOMAIN` and `CF_ACCESS_AUD` as Worker variables and allow only your account.
5. Deploy `apps/web` to Netlify with `VITE_API_BASE_URL` only. Do not add secrets or bearer tokens as frontend environment variables.
6. Add GitHub repository Actions secrets `CONTROL_PLANE_URL`, `MODEL_IMPORT_WORKER_TOKEN` and `WORKER_CALLBACK_TOKEN`.
7. Save your R2 S3 credentials once in the dashboard Settings, test the connection, then add public Hugging Face models in Model Library.

Detailed steps: `docs/DEPLOYMENT.md`, `docs/MODEL_LIBRARY.md` and `docs/BRANCHES.md`.
