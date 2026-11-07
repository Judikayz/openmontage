# Model Library operations

The Model Library registers Hugging Face model repositories and stores their pinned files in Cloudflare R2. It supports public repositories and private/gated repositories when a valid Hugging Face token is saved in Integrations and the account has access.

## Cloud setup

1. Create a private R2 bucket named `omcs-models` and an R2 S3 API token scoped to that bucket with Object Read & Write permissions.
2. Save `accountId`, `accessKeyId`, `secretAccessKey` and `bucketName=omcs-models` in Integrations.
3. Test the R2 connection.
4. Apply D1 migrations `0001_init.sql` through `0004_user_roles.sql`.
5. Configure Worker secrets: `ENCRYPTION_KEY`, `MODEL_IMPORT_WORKER_TOKEN`, `WORKER_CALLBACK_TOKEN`, and GitHub dispatch fallback credentials if they are not saved in Integrations.
6. Add GitHub Actions secrets `CONTROL_PLANE_URL`, `MODEL_IMPORT_WORKER_TOKEN` and `WORKER_CALLBACK_TOKEN`.

`ENCRYPTION_KEY` must be a base64-encoded 32-byte random key. Generate one with `openssl rand -base64 32`. Do not reuse provider keys as encryption keys.

## Import behaviour

At registration, the API resolves and pins the Hugging Face commit SHA. The importer reads the recursive repository file manifest, downloads each file with retry and HTTP resume, verifies expected size and Hugging Face LFS SHA-256 when provided, and uploads to R2. Files up to 5 GiB use a presigned single PUT. Larger files use multipart upload with 128 MiB parts and a completion manifest. The Worker verifies stored object sizes before marking a model `ready`.

The importer does not automatically install or execute repository scripts. A successful import means the files were stored and verified; it does not prove that a model is compatible with a worker runtime, that its licence permits your intended use, or that it will fit available runner memory/disk/GPU resources.

## Runtime cache

`payload.modelIds` should contain model IDs returned by `GET /api/models`. GitHub Actions restores model files to `OMCS_MODEL_CACHE/<model-id>/...`. R2 is the durable source of truth; GitHub cache is disposable and may be evicted. A worker must select a compatible pipeline/runtime and read the staged model path. Kaggle has a separate staging boundary and must be handled by the configured trusted dispatcher.
