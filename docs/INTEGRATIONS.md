# Integration contracts

- **Stock media:** Pexels/Pixabay credentials can be saved as provider secrets. A production search/download connector must respect each provider's rate limits, attribution rules and media licence. The current UI records credentials; provider-specific media search endpoints are not yet implemented.
- **Email / WhatsApp:** Configure a trusted delivery webhook behind server-side credentials. WhatsApp requires Meta WhatsApp Business Cloud API setup and approved templates/recipient consent. No message is sent by merely saving a credential.
- **AI API keys:** Store provider-specific JSON objects (for example `{ "apiKey": "..." }`) using Settings. Never include keys in workflow payloads. The current control plane stores them encrypted; model-specific generation adapters are not implemented in this baseline.
- **Local models:** Register a model ID, revision, source, checksum and licence; stage approved files in R2. The tool runtime reads `MODEL_DIR` after cache hydration.
- **OpenMontage:** `openmontage-integration` calls a separately deployed compatible `/api/jobs` endpoint. The exact API contract must be aligned to your deployed original instance before enabling final assembly.
