# Kaggle GPU execution

Kaggle is used for GPU-required jobs. Cloudflare Workers cannot run Kaggle CLI or execute GPU kernels themselves, so the control plane calls a separately deployed **trusted dispatcher**.

## Configure

1. Save Kaggle `username` and API `key` in Integrations.
2. Save the HTTPS `dispatcherUrl` in the same Kaggle integration settings.
3. Set Worker secret `KAGGLE_DISPATCHER_TOKEN` to a high-entropy shared secret also configured in the dispatcher.
4. The control plane sends `{jobId, tool, payload}` to the dispatcher using the shared bearer token. It does not send Kaggle credentials in the dispatch request.
5. The trusted dispatcher can retrieve credentials from `GET /internal/kaggle/credentials` using `Authorization: Bearer <KAGGLE_DISPATCHER_TOKEN>`. Protect this endpoint and never log or persist the returned credentials.
6. The dispatcher should retrieve the job payload from `/internal/jobs/{jobId}` using `WORKER_CALLBACK_TOKEN`, prepare a Kaggle kernel, configure GPU in `kernel-metadata.json`, submit using `kaggle kernels push`, poll status, collect output, and send a signed `/callback/{jobId}` result.

## Submission contract

The included `infra/kaggle/submit.py` creates Kaggle kernel metadata and invokes the official CLI. A dispatcher must provide the `main.py` entrypoint and required input dataset(s), set `KAGGLE_USERNAME` and `KAGGLE_KEY` only in its secure process environment, and set `enable_gpu=true` for GPU jobs. Use a unique kernel slug per job to prevent concurrent jobs overwriting one another.

The dispatcher is an external component and is not provisioned automatically by this ZIP. A successful HTTP dispatch only means the dispatcher accepted the request; the job must remain `submitted/running` until a real callback confirms completion or failure. Never report GPU execution as successful before the Kaggle kernel finishes and outputs are verified.
