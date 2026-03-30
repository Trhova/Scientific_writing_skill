#!/usr/bin/env python3
"""Extract citation-relevant metadata from text-like inputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
PMID_RE = re.compile(r"\bPMID\s*[: ]\s*(\d{4,9})\b", re.IGNORECASE)
ARXIV_RE = re.compile(r"\barXiv\s*[: ]\s*([A-Za-z\-\.]+/\d{7}|\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract DOI, PMID, arXiv, URL, title, and year candidates from text files."
    )
    parser.add_argument("inputs", nargs="*", help="Files to inspect. Reads stdin when omitted.")
    parser.add_argument("--text", help="Raw text to inspect instead of files.")
    parser.add_argument("--json-indent", type=int, default=2, help="Indentation for JSON output.")
    return parser.parse_args()


def read_inputs(paths: Iterable[str], inline_text: str | None) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if inline_text is not None:
        items.append(("<inline>", inline_text))
    for raw_path in paths:
        path = Path(raw_path)
        try:
            items.append((str(path), path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            items.append((str(path), path.read_text(encoding="utf-8", errors="replace")))
        except OSError as exc:
            print(f"warning: could not read {path}: {exc}", file=sys.stderr)
    if not items and not sys.stdin.isatty():
        items.append(("<stdin>", sys.stdin.read()))
    return items


def normalize_identifier(match: str) -> str:
    return match.rstrip(".,;)]}>")


def guess_title(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:12]:
        if len(line) < 15:
            continue
        if DOI_RE.search(line) or PMID_RE.search(line) or ARXIV_RE.search(line):
            continue
        if len(line.split()) > 30:
            continue
        return line
    return None


def detect_metadata(text: str) -> dict[str, object]:
    dois = sorted({normalize_identifier(match.group(0)) for match in DOI_RE.finditer(text)})
    pmids = sorted({match.group(1) for match in PMID_RE.finditer(text)})
    arxiv_ids = sorted({match.group(1) for match in ARXIV_RE.finditer(text)})
    urls = sorted({normalize_identifier(match.group(0)) for match in URL_RE.finditer(text)})
    years = sorted({match.group(0) for match in YEAR_RE.finditer(text)})

    metadata: dict[str, object] = {
        "title_candidate": guess_title(text),
        "identifiers": {
            "doi": dois,
            "pmid": pmids,
            "arxiv": arxiv_ids,
            "url": urls,
        },
        "year_candidates": years,
    }
    return metadata


def main() -> int:
    args = parse_args()
    items = read_inputs(args.inputs, args.text)
    if not items:
        print("error: no readable input provided", file=sys.stderr)
        return 1

    output = []
    for source_name, text in items:
        payload = detect_metadata(text)
        payload["source"] = source_name
        output.append(payload)

    print(json.dumps(output, indent=args.json_indent, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
