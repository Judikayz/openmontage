# Model Library operations

The Model Library provides a simple three-field registration flow: **Model name**, **Model URL / Hugging Face ID**, and **Model type**. Storage defaults to the R2 bucket configured once in Settings. At registration, the API resolves and pins the current Hugging Face commit SHA; this makes the registered model version reproducible. Register the repository again to add a newer version.

## Cloud setup

1. Create a private R2 bucket named `omcs-models`.
2. Create an R2 S3 API token/key pair scoped to that bucket with Object Read & Write permissions. Copy the Account ID, Access Key ID and Secret Access Key.
3. Enter those four values (including bucket name) in Settings. Click **Encrypt and save R2 settings**, then **Test saved R2 connection**.
4. Apply D1 migrations, including `0002_models.sql`.
5. Set Worker secrets:

```sh
npx wrangler secret put ENCRYPTION_KEY
npx wrangler secret put MODEL_IMPORT_WORKER_TOKEN
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put GITHUB_OWNER
npx wrangler secret put GITHUB_REPO
```

`ENCRYPTION_KEY` must be a base64-encoded 32-byte random key. Generate one with `openssl rand -base64 32`. Use a separate high-entropy random value for `MODEL_IMPORT_WORKER_TOKEN` and save the same value as a GitHub repository Actions secret. Do not reuse the R2 secret key as either value.

In GitHub repository **Settings → Secrets and variables → Actions → New repository secret**, add:

- `CONTROL_PLANE_URL`: deployed Worker base URL, e.g. `https://openmontage-cloud-studio-api.<account>.workers.dev`.
- `MODEL_IMPORT_WORKER_TOKEN`: same value configured as the Worker secret.

The existing CPU dispatch also requires `WORKER_CALLBACK_TOKEN` as a GitHub secret. GitHub dispatch itself requires a Worker `GITHUB_TOKEN` with Actions workflow-dispatch permission, plus `GITHUB_OWNER` and `GITHUB_REPO`.

## Protect the dashboard API

The frontend no longer embeds a static bearer token. Protect the Worker API hostname with a Cloudflare Access self-hosted application. Set Worker variables `CF_ACCESS_TEAM_DOMAIN` (e.g. `your-team.cloudflareaccess.com`), `CF_ACCESS_AUD` (the Access application AUD), and `ALLOWED_ORIGIN` (the exact deployed Netlify origin, including scheme). The Worker verifies the Cloudflare Access JWT signature, issuer, audience and expiry. Configure the Access policy to allow only your account. For local development, use a separate development authentication setup; do not publish an unprotected Worker.

## Import behaviour

Only public Hugging Face model repositories are currently supported. Enter either `owner/model` or `https://huggingface.co/owner/model`. The importer reads the repository file tree, downloads files, checks sizes and upstream LFS SHA-256 where available, uploads to R2 using one-object/one-method presigned URLs, and verifies stored object sizes before setting `ready`.

Files larger than 5 GiB are rejected because this implementation uses single-part PUT rather than multipart upload. Private/gated repos and arbitrary direct-download URLs are not supported in this version. GitHub runner storage/time quotas may also limit very large model repositories.

## Cache behaviour

A production job can pass `payload.modelIds` as a list of IDs returned by `GET /api/models`. The GitHub workflow restores a model cache and downloads missing artifacts from R2. The cache is optional and disposable; R2 remains the durable source. Tool-specific inference code must read weights from `OMCS_MODEL_CACHE/<model-id>/...`. Kaggle does not share GitHub cache and still needs its own R2 download/staging implementation.
