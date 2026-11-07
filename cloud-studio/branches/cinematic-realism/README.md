# Cinematic finishing worker branch

This is a separate Git branch with its own runtime contract, Dockerfile and dependencies. The worker validates inputs and fails closed when model weights or an upstream runtime are not configured. It does not emit placeholder media.

- Contract: `contract/job.schema.json`
- Entrypoint: `worker.py`
- Docker: `Dockerfile`
- GPU requirement: `GPU_REQUIRED=true`
- Model weights are external and must be staged from persistent R2 cache.
