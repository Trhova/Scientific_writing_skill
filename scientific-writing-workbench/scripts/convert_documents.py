#!/usr/bin/env python3
"""Convert common document formats into plain text or Markdown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scholarly_lookup_common import convert_file_to_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert PDFs and office files into text or Markdown.")
    parser.add_argument("inputs", nargs="+", help="Input files to convert.")
    parser.add_argument("--output-dir", help="Directory for converted outputs.")
    parser.add_argument("--manifest", action="store_true", help="Emit a JSON conversion manifest to stderr.")
    parser.add_argument("--enable-ocr", action="store_true", help="Enable OCR fallback for PDFs after normal extraction fails.")
    return parser.parse_args()


def write_output(source: Path, content: str, output_dir: Path | None) -> None:
    if output_dir is None:
        print(f"# Source: {source}")
        print()
        print(content.rstrip())
        print()
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source.name}.md"
    output_path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else None
    manifest = []
    failures = 0

    for raw_input in args.inputs:
        path = Path(raw_input)
        if not path.exists():
            print(f"warning: {path} does not exist", file=sys.stderr)
            manifest.append({"source": str(path), "status": "missing", "warnings": ["file does not exist"], "method": "missing"})
            failures += 1
            continue

        try:
            content, warnings, method = convert_file_to_text(path, enable_ocr=args.enable_ocr)
        except Exception as exc:
            content = ""
            warnings = [str(exc)]
            method = "failed"

        status = "ok" if content else "warning"
        if not content:
            failures += 1
        else:
            write_output(path, content, output_dir)

        manifest.append({"source": str(path), "status": status, "warnings": warnings, "method": method})

    if args.manifest:
        print(json.dumps(manifest, indent=2, ensure_ascii=True), file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
