#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PREFIX="${ROOT_DIR}/.writer-skill-env"

if [ ! -d "${ENV_PREFIX}" ]; then
  echo "error: environment not found at ${ENV_PREFIX}" >&2
  echo "run scripts/setup_writer_env.sh first" >&2
  exit 1
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${ENV_PREFIX}"

echo "Python:"
python --version
echo

echo "CLI tools:"
for tool in pdftotext mutool tesseract gs; do
  if command -v "${tool}" >/dev/null 2>&1; then
    echo "  ${tool}: $(command -v "${tool}")"
  else
    echo "  ${tool}: MISSING"
  fi
done
echo

echo "Python packages:"
python - <<'PY'
modules = [
    "fitz",
    "pypdf",
    "pdfplumber",
    "pdfminer",
    "PIL",
    "pytesseract",
    "bs4",
    "lxml",
]
for name in modules:
    try:
        __import__(name)
        print(f"  {name}: OK")
    except Exception as exc:
        print(f"  {name}: MISSING ({exc})")
PY
