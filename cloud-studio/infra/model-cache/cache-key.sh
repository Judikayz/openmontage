#!/usr/bin/env bash
set -euo pipefail
MODEL_ID="${1:?model id}"; REVISION="${2:?revision}"; LOCK="${3:-requirements.lock}"
HASH="$(sha256sum "$LOCK" | cut -d' ' -f1)"
printf 'model-%s-%s-%s\n' "$MODEL_ID" "$REVISION" "$HASH"
