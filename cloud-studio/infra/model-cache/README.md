# Persistent model library and cache

## Storage roles

- **Cloudflare R2 (`omcs-models`)** is the durable model repository.
- **GitHub Actions cache** is a best-effort acceleration layer. It can be evicted, is quota-limited, and must never be treated as the source of truth.
- A runner still needs a local copy of the selected model while it executes. A cache hit avoids the R2 transfer; a cache miss restores from R2. The original Hugging Face host is used only during the first import (or an explicit re-import).
- Docker images contain code and dependencies, not multi-gigabyte model weights.

## Add/import flow

1. Save Cloudflare R2 Account ID, Access Key ID, Secret Access Key and bucket `omcs-models` in **Settings → Cloudflare R2 model storage**.
2. Configure `MODEL_IMPORT_WORKER_TOKEN` as a Cloudflare Worker secret and as a GitHub Actions repository secret with the same high-entropy random value. This is a narrowly scoped runner-to-control-plane credential; it is not an R2 key.
3. Configure `CONTROL_PLANE_URL` as a GitHub Actions repository secret, pointing to the deployed Worker URL.
4. In **Model Library**, enter a display name, public Hugging Face model URL/ID and model category, then select **Add model and import**.
5. The Worker registers the model and dispatches `.github/workflows/cloud-studio-model-import.yml`. The runner retrieves the manifest, downloads each file, checks its declared size and any Hugging Face LFS SHA-256 digest, requests a 15-minute presigned R2 PUT URL, and uploads directly to R2. R2 credentials never enter workflow inputs or runner environment variables.
6. The Worker checks every uploaded R2 object and marks the model `ready`. The Model Library displays status and stored bytes.

Downloads retry and resume with HTTP Range while the GitHub runner job remains alive; an entire runner loss restarts the current file because partial downloads are not persisted in R2. The import currently supports **public Hugging Face model repositories**. Private/gated repositories, arbitrary HTTP URLs, Git LFS credential negotiation and individual files larger than R2's 5 GiB single-PUT limit are rejected/not supported; use a public accessible model and ensure no individual file exceeds that limit. A failed import can be retried from the Model Library. A deleted model also deletes its registered R2 objects.

## Use models in a job

Include registered model IDs in a GitHub-executed job payload:

```json
{
  "tool": "ai-video-generation",
  "compute": "github",
  "payload": {
    "modelIds": ["MODEL_LIBRARY_ID"],
    "prompt": "..."
  }
}
```

The CPU dispatch workflow restores `~/.cache/omcs-models` with `actions/cache@v4`; on a cache miss, `restore_models.py` fetches short-lived signed GET URLs from the control plane and restores the model from R2. Tool workers receive `OMCS_MODEL_CACHE` as the cache root. Tool-specific adapters must select their model directory under that root. GitHub cache eviction only causes an R2 transfer, never a re-download from the original provider.

For Kaggle GPU jobs, the Kaggle notebook must fetch the same registered model artifacts from the control plane using a separate, short-lived download handoff; the current Kaggle submission adapter does not yet perform model staging. Do not assume a GitHub runner cache is accessible from Kaggle.

## Security

- R2 credentials are AES-256-GCM encrypted in D1 using the Worker-only `ENCRYPTION_KEY`.
- The browser only submits credentials over HTTPS; the API never returns their values.
- Presigned upload/download URLs are short-lived (15 minutes) and scoped to one object and one HTTP method.
- The importer authenticates with `MODEL_IMPORT_WORKER_TOKEN`, which must be set in both the Worker and GitHub repository secrets. Never put it in workflow-dispatch inputs.
- The dashboard API is intended to be protected by Cloudflare Access. Do not expose a static API bearer token in `VITE_*` frontend variables.

## Limits and operational notes

- GitHub-hosted runner disk, time, network and cache quotas still apply. Very large repositories may exceed runner disk or execution limits even if individual files fit R2's object limit.
- GitHub Actions cache is not permanent and is subject to repository cache limits/eviction. R2 is authoritative.
- Model code and weight licences are separate. Check the upstream model card and licence before use, especially commercial use.
- The import verifies file sizes and upstream LFS SHA-256 digests when exposed by Hugging Face. It does not certify model quality or runtime compatibility.
