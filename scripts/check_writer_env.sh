#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PREFIX="${ROOT_DIR}/.writer-skill-env"
PYTHON_BIN="${ENV_PREFIX}/bin/python"
ENV_BIN_DIR="${ENV_PREFIX}/bin"

if [ ! -d "${ENV_PREFIX}" ]; then
  echo "error: environment not found at ${ENV_PREFIX}" >&2
  echo "run scripts/setup_writer_env.sh first" >&2
  exit 1
fi

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "error: python not found in ${ENV_PREFIX}" >&2
  echo "run scripts/setup_writer_env.sh first" >&2
  exit 1
fi

echo "Python:"
"${PYTHON_BIN}" --version
echo

echo "CLI tools:"
for tool in pdftotext mutool tesseract gs pandoc tectonic; do
  if [ -x "${ENV_BIN_DIR}/${tool}" ]; then
    echo "  ${tool}: ${ENV_BIN_DIR}/${tool}"
  elif command -v "${tool}" >/dev/null 2>&1; then
    echo "  ${tool}: $(command -v "${tool}")"
  else
    echo "  ${tool}: MISSING"
  fi
done
echo

echo "Python packages:"
"${PYTHON_BIN}" - <<'PY'
modules = [
    "fitz",
    "pypdf",
    "pdfplumber",
    "pdfminer",
    "PIL",
    "pytesseract",
    "bs4",
    "lxml",
    "markdown",
    "cairosvg",
]
for name in modules:
    try:
        __import__(name)
        print(f"  {name}: OK")
    except Exception as exc:
        print(f"  {name}: MISSING ({exc})")
PY
