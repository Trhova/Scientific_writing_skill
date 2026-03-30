#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PREFIX="${ROOT_DIR}/.writer-skill-env"

if ! command -v conda >/dev/null 2>&1; then
  echo "error: conda is required but was not found in PATH" >&2
  exit 1
fi

conda env update \
  --prefix "${ENV_PREFIX}" \
  --file "${ROOT_DIR}/environment.yml" \
  --prune

echo
echo "Environment created or updated at:"
echo "  ${ENV_PREFIX}"
echo
echo "Activate it with:"
echo "  conda activate ${ENV_PREFIX}"
