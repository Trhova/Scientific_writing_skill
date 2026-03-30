#!/usr/bin/env python3
"""Resolve DOI, PMID, arXiv, or URL inputs into BibTeX when metadata is available."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
import urllib.error
import urllib.parse
from datetime import date

from scholarly_lookup_common import arxiv_by_id, europepmc_by_pmid, http_text, normalize_arxiv_id, normalize_doi, normalize_pmid

DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
PMID_RE = re.compile(r"^(?:PMID:?)?(\d{4,9})$", re.IGNORECASE)
ARXIV_RE = re.compile(r"^(?:arXiv:?)?([A-Za-z\-\.]+/\d{7}|\d{4}\.\d{4,5}(?:v\d+)?)$", re.IGNORECASE)
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

USER_AGENT = "scientific-writing-workbench/1.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve DOI, PMID, arXiv, or URL inputs into BibTeX."
    )
    parser.add_argument("identifiers", nargs="+", help="One or more DOI, PMID, arXiv, or URL inputs.")
    parser.add_argument("--append", help="Append BibTeX output to the given file.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of BibTeX.")
    return parser.parse_args()


def validate_public_url(identifier: str) -> str:
    parsed = urllib.parse.urlparse(identifier)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http and https URLs are supported")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("refusing localhost URL input")
    try:
        addresses = {result[4][0] for result in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise ValueError(f"could not resolve hostname: {exc}") from exc
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_multicast,
                ip.is_reserved,
                ip.is_unspecified,
            )
        ):
            raise ValueError("refusing URL that resolves to a non-public address")
    return identifier


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", value)
    return cleaned[:40] or "entry"


def make_key(authors: list[str], year: str | None, title: str | None, fallback: str) -> str:
    stem = fallback
    if authors:
        stem = authors[0].split()[-1]
    word = "entry"
    if title:
        tokens = re.findall(r"[A-Za-z0-9]+", title)
        for token in tokens:
            if len(token) > 3:
                word = token
                break
        else:
            if tokens:
                word = tokens[0]
    pieces = [slugify(stem)]
    if year:
        pieces.append(year)
    pieces.append(slugify(word))
    return "".join(pieces)


def escape_bibtex(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def bibtex_entry(entry_type: str, key: str, fields: dict[str, str]) -> str:
    lines = [f"@{entry_type}{{{key},"]
    for field_name in sorted(fields):
        field_value = fields[field_name].strip()
        if not field_value:
            continue
        lines.append(f"  {field_name} = {{{escape_bibtex(field_value)}}},")
    lines.append("}")
    return "\n".join(lines)


def doi_to_bibtex(identifier: str) -> dict[str, str]:
    headers = {"Accept": "application/x-bibtex"}
    bib = http_text(f"https://doi.org/{urllib.parse.quote(identifier, safe='/')}", accept=headers["Accept"]).strip()
    if not bib.startswith("@"):
        raise ValueError("DOI service did not return BibTeX")
    return {"type": "bibtex", "value": bib}


def pmid_to_bibtex(identifier: str) -> dict[str, str]:
    record = europepmc_by_pmid(identifier)
    if not record:
        raise ValueError(f"PMID {identifier} not found")
    authors = [name.strip() for name in (record.get("authors") or "").split(",") if name.strip()]
    year = str(record.get("year") or "") or None
    title = (record.get("title") or "").strip() or None
    fields = {
        "author": " and ".join(authors),
        "title": title or "",
        "journal": str(record.get("journal", "")).strip(),
        "year": year or "",
        "doi": str(record.get("doi", "")).strip(),
        "pmid": identifier,
        "url": str(record.get("url", "")).strip() or f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/",
    }
    key = make_key(authors, year, title, f"pmid{identifier}")
    return {"type": "bibtex", "value": bibtex_entry("article", key, fields)}


def arxiv_to_bibtex(identifier: str) -> dict[str, str]:
    record = arxiv_by_id(identifier)
    if not record:
        raise ValueError(f"arXiv record {identifier} not found")
    authors = [name.strip() for name in str(record.get("authors", "")).split(",") if name.strip()]
    title = str(record.get("title", "")).strip() or None
    year = str(record.get("year") or "")
    fields = {
        "author": " and ".join(authors),
        "title": title or "",
        "year": year,
        "archivePrefix": "arXiv",
        "eprint": identifier,
        "url": str(record.get("url", "")).strip(),
    }
    key = make_key(authors, year or None, title or None, f"arxiv{identifier}")
    return {"type": "bibtex", "value": bibtex_entry("misc", key, fields)}


def url_to_bibtex(identifier: str) -> dict[str, str]:
    safe_identifier = validate_public_url(identifier)
    html = http_text(safe_identifier)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = ""
    if title_match:
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()
    if not title:
        raise ValueError(f"could not extract a reliable title from {identifier}")
    accessed = date.today().isoformat()
    key = make_key([], None, title, "web")
    fields = {
        "title": title,
        "url": safe_identifier,
        "note": f"Accessed {accessed}",
    }
    return {"type": "bibtex", "value": bibtex_entry("misc", key, fields)}


def resolve_identifier(raw_identifier: str) -> dict[str, str]:
    identifier = raw_identifier.strip()
    pmid_match = PMID_RE.match(identifier)
    if DOI_RE.match(identifier):
        return doi_to_bibtex(normalize_doi(identifier))
    if pmid_match:
        return pmid_to_bibtex(normalize_pmid(pmid_match.group(1)))
    arxiv_match = ARXIV_RE.match(identifier)
    if arxiv_match:
        return arxiv_to_bibtex(normalize_arxiv_id(arxiv_match.group(1)))
    if URL_RE.match(identifier):
        return url_to_bibtex(identifier)
    raise ValueError(f"unsupported identifier format: {raw_identifier}")


def main() -> int:
    args = parse_args()
    resolved = []
    failures = 0
    for identifier in args.identifiers:
        try:
            resolved.append({"identifier": identifier, **resolve_identifier(identifier)})
        except (ValueError, urllib.error.URLError) as exc:
            failures += 1
            print(f"warning: {identifier}: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(resolved, indent=2, ensure_ascii=True))
    else:
        bibtex_records = "\n\n".join(item["value"] for item in resolved if item["type"] == "bibtex")
        if bibtex_records:
            print(bibtex_records)
        if args.append and bibtex_records:
            with open(args.append, "a", encoding="utf-8") as handle:
                handle.write(bibtex_records)
                handle.write("\n")

    return 1 if failures and not resolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
