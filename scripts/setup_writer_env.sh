#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PREFIX="${ROOT_DIR}/.writer-skill-env"
CONDA_BIN="${CONDA_EXE:-}"

if [ -z "${CONDA_BIN}" ]; then
  if command -v conda >/dev/null 2>&1; then
    CONDA_BIN="$(command -v conda)"
  elif [ -x "/home/trhova/miniconda3/bin/conda" ]; then
    CONDA_BIN="/home/trhova/miniconda3/bin/conda"
  else
    echo "error: conda is required but was not found in PATH" >&2
    echo "set CONDA_EXE or install conda before running this script" >&2
    exit 1
  fi
fi

"${CONDA_BIN}" env update \
  --prefix "${ENV_PREFIX}" \
  --file "${ROOT_DIR}/environment.yml" \
  --prune

echo
echo "Environment created or updated at:"
echo "  ${ENV_PREFIX}"
echo
echo "Activate it with:"
echo "  conda activate ${ENV_PREFIX}"
