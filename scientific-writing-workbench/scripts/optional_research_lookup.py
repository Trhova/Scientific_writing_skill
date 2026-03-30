#!/usr/bin/env python3
"""Provider-agnostic, local-first literature lookup."""

from __future__ import annotations

import argparse
import json
import sys
from scholarly_lookup_common import (
    arxiv_search,
    crossref_search,
    dedupe_records,
    europepmc_search,
    local_lookup,
    openalex_search,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search local notes first, then optional external literature providers.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument(
        "--provider",
        choices=["local", "crossref", "openalex", "europepmc", "arxiv", "auto"],
        default="auto",
        help="Lookup provider. 'auto' uses local first, then Crossref and Europe PMC.",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Local files or directories to inspect when using the local or auto provider.",
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of results per provider.")
    return parser.parse_args()
def main() -> int:
    args = parse_args()
    results: list[dict[str, object]] = []
    provider_order = {
        "local": ["local"],
        "crossref": ["crossref"],
        "openalex": ["openalex"],
        "europepmc": ["europepmc"],
        "arxiv": ["arxiv"],
        "auto": ["local", "crossref", "europepmc"],
    }[args.provider]

    for provider in provider_order:
        try:
            if provider == "local":
                results.extend(local_lookup(args.query, args.paths, args.limit))
            elif provider == "crossref":
                results.extend(crossref_search(args.query, args.limit))
            elif provider == "openalex":
                results.extend(openalex_search(args.query, args.limit))
            elif provider == "europepmc":
                results.extend(europepmc_search(args.query, args.limit))
            elif provider == "arxiv":
                results.extend(arxiv_search(args.query, args.limit))
        except Exception as exc:
            print(f"warning: provider {provider} failed: {exc}", file=sys.stderr)

    print(json.dumps(dedupe_records(results)[: args.limit], indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
