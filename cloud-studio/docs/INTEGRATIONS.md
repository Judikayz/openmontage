# Integration contracts and credentials

## Provider integrations

- **Gemini:** Save `apiKey` and optional `defaultModel` in Integrations. The backend exposes `/api/ai/prompt` for prompt enhancement and `/api/integrations/test` for API-key validation. The key remains encrypted in D1 and is not returned to the browser.
- **Hugging Face:** Save `token` for private/gated repository access and optional inference endpoint metadata. The model importer uses the token on authenticated internal routes; the runner receives it only through the authenticated importer channel. Model licence/access restrictions still apply.
- **GitHub:** Save `token`, `owner`, `repo` and `ref`. The API dispatches workflow runs using the saved token. Worker environment variables `GITHUB_TOKEN`, `GITHUB_OWNER` and `GITHUB_REPO` are fallback configuration only.
- **Kaggle:** Save `username`, `key` and secure `dispatcherUrl`. Set `KAGGLE_DISPATCHER_TOKEN` as a Worker secret and configure the same secret in the trusted dispatcher. The dispatch request does not include Kaggle credentials; the dispatcher can retrieve them from the protected `/internal/kaggle/credentials` endpoint.
- **Cloudflare R2:** Save `accountId`, `accessKeyId`, `secretAccessKey` and `bucketName` for `omcs-models`. The model bucket name must match the `MODELS` binding. The separate `ASSETS` binding stores user uploads; generated outputs use the model bucket's signed upload path in this release.

## Other providers and delivery

- **Stock media:** Pexels/Pixabay search and download APIs are not implemented in this build. Do not treat saved credentials as active connectors.
- **Email / WhatsApp:** Message delivery is not implemented. WhatsApp requires Meta Business Cloud API setup, approved templates and recipient consent.
- **Original OpenMontage application:** The `openmontage-integration` branch is an adapter contract. Align it to the actual deployed original API before enabling cross-application orchestration.

Never place API keys in workflow payloads or frontend `VITE_*` variables. All secrets should be configured through encrypted provider settings or deployment secrets.
