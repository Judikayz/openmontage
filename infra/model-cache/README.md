# Persistent model cache

Store model files in R2 under `models/<provider>/<model>/<revision>/`. Keep metadata (licence, checksum, source URL, revision, file list) in a manifest. GitHub Actions may hydrate the R2 cache into its workspace, then save an opportunistic cache with key `model-${model}-${revision}-${lockhash}`. Never assume GitHub cache survives. Never cache gated/non-redistributable weights into shared R2 without checking licence and access restrictions. Never put weights or credentials in Docker layers.
