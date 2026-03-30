#!/usr/bin/env python3
"""Provider-agnostic, local-first literature lookup."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "scientific-writing-workbench/1.0"


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


def http_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def local_lookup(query: str, paths: list[str], limit: int) -> list[dict[str, str]]:
    results = []
    needles = [token.lower() for token in re.findall(r"\w+", query) if len(token) > 2]
    for raw_path in paths:
        path = Path(raw_path)
        candidates = [path]
        if path.is_dir():
            candidates = [candidate for candidate in path.rglob("*") if candidate.is_file()]
        for candidate in candidates:
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lowered = text.lower()
            if needles and not all(token in lowered for token in needles[: min(3, len(needles))]):
                continue
            snippet = re.sub(r"\s+", " ", text[:500]).strip()
            results.append(
                {
                    "provider": "local",
                    "title": candidate.name,
                    "snippet": snippet,
                    "source": str(candidate),
                }
            )
            if len(results) >= limit:
                return results
    return results


def crossref_lookup(query: str, limit: int) -> list[dict[str, str]]:
    url = f"https://api.crossref.org/works?query.bibliographic={urllib.parse.quote(query)}&rows={limit}"
    items = http_json(url).get("message", {}).get("items", [])
    results = []
    for item in items:
        title = (item.get("title") or [""])[0]
        doi = item.get("DOI", "")
        year_parts = item.get("issued", {}).get("date-parts", [[]])
        year = str(year_parts[0][0]) if year_parts and year_parts[0] else ""
        results.append(
            {
                "provider": "crossref",
                "title": title,
                "year": year,
                "doi": doi,
                "type": item.get("type", ""),
                "source": f"https://doi.org/{doi}" if doi else "",
            }
        )
    return results


def europepmc_lookup(query: str, limit: int) -> list[dict[str, str]]:
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
        f"query={urllib.parse.quote(query)}&format=json&pageSize={limit}"
    )
    items = http_json(url).get("resultList", {}).get("result", [])
    return [
        {
            "provider": "europepmc",
            "title": item.get("title", ""),
            "year": item.get("pubYear", ""),
            "doi": item.get("doi", ""),
            "pmid": item.get("pmid", ""),
            "source": f"https://pubmed.ncbi.nlm.nih.gov/{item.get('pmid')}/" if item.get("pmid") else "",
        }
        for item in items
    ]


def openalex_lookup(query: str, limit: int) -> list[dict[str, str]]:
    url = f"https://api.openalex.org/works?search={urllib.parse.quote(query)}&per-page={limit}"
    items = http_json(url).get("results", [])
    return [
        {
            "provider": "openalex",
            "title": item.get("display_name", ""),
            "year": str(item.get("publication_year", "")),
            "doi": (item.get("doi") or "").replace("https://doi.org/", ""),
            "source": item.get("id", ""),
        }
        for item in items
    ]


def arxiv_lookup(query: str, limit: int) -> list[dict[str, str]]:
    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query=all:{urllib.parse.quote(query)}&start=0&max_results={limit}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        xml_text = response.read().decode("utf-8")
    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, flags=re.DOTALL)
    results = []
    for entry in entries[:limit]:
        title_match = re.search(r"<title>\s*(.*?)\s*</title>", entry, flags=re.DOTALL)
        id_match = re.search(r"<id>\s*(.*?)\s*</id>", entry, flags=re.DOTALL)
        published_match = re.search(r"<published>\s*(\d{4})", entry)
        results.append(
            {
                "provider": "arxiv",
                "title": re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "",
                "year": published_match.group(1) if published_match else "",
                "source": id_match.group(1).strip() if id_match else "",
            }
        )
    return results


def main() -> int:
    args = parse_args()
    results: list[dict[str, str]] = []
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
                results.extend(crossref_lookup(args.query, args.limit))
            elif provider == "openalex":
                results.extend(openalex_lookup(args.query, args.limit))
            elif provider == "europepmc":
                results.extend(europepmc_lookup(args.query, args.limit))
            elif provider == "arxiv":
                results.extend(arxiv_lookup(args.query, args.limit))
        except Exception as exc:
            print(f"warning: provider {provider} failed: {exc}", file=sys.stderr)

    print(json.dumps(results[: args.limit], indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
