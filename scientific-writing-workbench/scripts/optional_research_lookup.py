#!/usr/bin/env python3
"""Provider-agnostic, local-first literature lookup."""

from __future__ import annotations

import argparse
import json

from paper_access import DEFAULT_PROVIDERS, collect_paper_records
from scholarly_lookup_common import local_lookup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search local notes first, then optional external literature providers.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument(
        "--provider",
        choices=["local", "crossref", "openalex", "europepmc", "arxiv", "auto"],
        default="auto",
        help="Lookup provider. 'auto' uses local first, then Europe PMC, OpenAlex, and Crossref.",
    )
    parser.add_argument("--paths", nargs="*", default=[], help="Local files or directories to inspect before external lookup.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of results per provider.")
    parser.add_argument("--enable-ocr", action="store_true", help="Enable OCR fallback for local PDFs after normal extraction fails.")
    return parser.parse_args()


def provider_tuple(provider: str) -> tuple[str, ...]:
    mapping = {
        "local": tuple(),
        "crossref": ("crossref",),
        "openalex": ("openalex",),
        "europepmc": ("europepmc",),
        "arxiv": ("arxiv",),
        "auto": DEFAULT_PROVIDERS,
    }
    return mapping[provider]


def main() -> int:
    args = parse_args()
    if args.provider == "local":
        records = local_lookup(args.query, args.paths, args.limit, enable_ocr=args.enable_ocr)
        print(json.dumps(records[: args.limit], indent=2, ensure_ascii=True))
        return 0
    records = collect_paper_records(
        paths=args.paths,
        queries=[args.query],
        limit_per_provider=args.limit,
        enable_ocr=args.enable_ocr,
        providers=provider_tuple(args.provider),
    )
    print(json.dumps(records[: args.limit], indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
