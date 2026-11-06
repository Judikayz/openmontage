# Kaggle GPU execution

Kaggle is reserved for GPU-required production stages. The platform control plane does not execute arbitrary code on Kaggle directly. A valid Kaggle kernel source directory must contain `kernel-metadata.json`, a notebook/script entrypoint, and staged input datasets. The CLI submission flow is `kaggle kernels push -p <kernel-dir>`; monitor with `kaggle kernels status <owner>/<slug>` and retrieve output with `kaggle kernels output <owner>/<slug> -p <output-dir>`.

This repository includes `infra/kaggle/submit.py`, which creates metadata and invokes the CLI. The secure dispatcher must run in a trusted orchestration environment with Kaggle credentials mounted as environment variables. Do not pass credentials in GitHub workflow inputs. Current Worker implementation requires a separately deployed secure dispatcher URL for Kaggle submissions; this is explicitly not auto-provisioned by the Worker.
