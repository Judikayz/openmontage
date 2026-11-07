# Architecture and trust boundaries

Netlify hosts the browser UI. The browser sends authenticated requests to the Cloudflare Worker. The Worker validates payloads, stores metadata in D1, encrypts provider secrets using AES-GCM with a Worker-only `ENCRYPTION_KEY`, and stores binary assets in R2. Cloudflare Cron dispatches due schedules; it never renders video.

CPU jobs dispatch to GitHub Actions. GPU production stages route to Kaggle only when selected/required. Kaggle submissions are generated as valid Kaggle kernels and invoked through the Kaggle CLI. Do not pass Kaggle credentials in `workflow_dispatch` inputs. The control plane keeps Kaggle credentials encrypted and the GitHub orchestration worker obtains a narrowly scoped, short-lived dispatch ticket; production deployments should use a dedicated callback exchange token and short expiry.

R2 is durable model and asset storage. GitHub Actions cache is a best-effort accelerator and may be evicted. Cache keys include model identifier, revision, and runtime lock hash. Docker images contain code/dependencies, never private model weights or credentials.

The original OpenMontage source is not present. The `openmontage-integration` branch contains only an adapter that calls a separately deployed instance.
