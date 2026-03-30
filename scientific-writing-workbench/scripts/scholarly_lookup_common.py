#!/usr/bin/env python3
"""Shared helpers for scholarly metadata lookup and normalization."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from extract_metadata import detect_metadata

USER_AGENT = "scientific-writing-workbench/1.0"


def http_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def http_text(url: str, accept: str | None = None) -> str:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def decode_openalex_abstract(inverted_index: dict | None) -> str:
    if not inverted_index:
        return ""
    positions: dict[int, str] = {}
    for token, offsets in inverted_index.items():
        for offset in offsets:
            positions[offset] = token
    return " ".join(positions[index] for index in sorted(positions))


def author_list_to_string(authors: list[dict] | None) -> str:
    names = []
    for author in authors or []:
        given = normalize_whitespace(author.get("given", ""))
        family = normalize_whitespace(author.get("family", ""))
        full_name = normalize_whitespace(" ".join(part for part in (given, family) if part))
        if full_name:
            names.append(full_name)
    return ", ".join(names)


def openalex_authors_to_string(authorships: list[dict] | None) -> str:
    names = []
    for authorship in authorships or []:
        author = authorship.get("author", {})
        display_name = normalize_whitespace(author.get("display_name", ""))
        if display_name:
            names.append(display_name)
    return ", ".join(names)


def crossref_item_to_record(item: dict) -> dict[str, object]:
    year_parts = item.get("issued", {}).get("date-parts", [[]])
    year = year_parts[0][0] if year_parts and year_parts[0] else None
    title = normalize_whitespace((item.get("title") or [""])[0])
    abstract = normalize_whitespace(re.sub(r"<[^>]+>", " ", item.get("abstract", "") or ""))
    doi = normalize_whitespace(item.get("DOI", ""))
    url = normalize_whitespace(item.get("URL", "")) or (f"https://doi.org/{doi}" if doi else "")
    return {
        "provider": "crossref",
        "title": title,
        "authors": author_list_to_string(item.get("author")),
        "year": year,
        "journal": normalize_whitespace((item.get("container-title") or [""])[0]),
        "doi": doi,
        "pmid": "",
        "url": url,
        "abstract": abstract,
        "publication_type_raw": normalize_whitespace(item.get("type", "")),
        "cited_by_count": item.get("is-referenced-by-count", 0),
        "source_quality_hint": normalize_whitespace((item.get("publisher") or "")),
    }


def europepmc_item_to_record(item: dict) -> dict[str, object]:
    abstract = normalize_whitespace(item.get("abstractText", "") or item.get("abstract", ""))
    journal = normalize_whitespace(item.get("journalTitle", ""))
    if not journal and isinstance(item.get("journalInfo"), dict):
        journal = normalize_whitespace(
            item["journalInfo"].get("journal", {}).get("title", "") or item["journalInfo"].get("journal", {}).get("medlineAbbreviation", "")
        )
    pub_type = item.get("pubType", "")
    if not pub_type and isinstance(item.get("pubTypeList"), dict):
        pub_types = item["pubTypeList"].get("pubType", [])
        pub_type = ", ".join(pub_types) if isinstance(pub_types, list) else str(pub_types)
    pub_type = normalize_whitespace(str(pub_type))
    url = ""
    if item.get("pmid"):
        url = f"https://pubmed.ncbi.nlm.nih.gov/{item.get('pmid')}/"
    elif isinstance(item.get("fullTextUrlList"), dict):
        full_text_urls = item["fullTextUrlList"].get("fullTextUrl", [])
        if full_text_urls:
            first_url = full_text_urls[0]
            if isinstance(first_url, dict):
                url = normalize_whitespace(first_url.get("url", ""))
            else:
                url = normalize_whitespace(str(first_url))
    return {
        "provider": "europepmc",
        "title": normalize_whitespace(item.get("title", "")),
        "authors": normalize_whitespace(item.get("authorString", "")),
        "year": int(item["pubYear"]) if str(item.get("pubYear", "")).isdigit() else None,
        "journal": journal,
        "doi": normalize_whitespace(item.get("doi", "")),
        "pmid": normalize_whitespace(item.get("pmid", "")),
        "url": url,
        "abstract": abstract,
        "publication_type_raw": pub_type,
        "cited_by_count": int(item.get("citedByCount", 0) or 0),
        "source_quality_hint": journal,
    }


def openalex_item_to_record(item: dict) -> dict[str, object]:
    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}
    pmid = ""
    ids = item.get("ids") or {}
    if ids.get("pmid"):
        pmid = ids["pmid"].rstrip("/").split("/")[-1]
    doi = normalize_whitespace((item.get("doi") or "").replace("https://doi.org/", ""))
    return {
        "provider": "openalex",
        "title": normalize_whitespace(item.get("display_name", "") or item.get("title", "")),
        "authors": openalex_authors_to_string(item.get("authorships")),
        "year": item.get("publication_year"),
        "journal": normalize_whitespace(source.get("display_name", "")),
        "doi": doi,
        "pmid": pmid,
        "url": normalize_whitespace(primary_location.get("landing_page_url", "") or item.get("id", "")),
        "abstract": normalize_whitespace(decode_openalex_abstract(item.get("abstract_inverted_index"))),
        "publication_type_raw": normalize_whitespace(item.get("type", "")),
        "cited_by_count": int(item.get("cited_by_count", 0) or 0),
        "source_quality_hint": normalize_whitespace(source.get("host_organization_name", "")),
    }


def arxiv_entry_to_record(entry_xml: str) -> dict[str, object]:
    title_match = re.search(r"<title>\s*(.*?)\s*</title>", entry_xml, flags=re.DOTALL)
    id_match = re.search(r"<id>\s*(.*?)\s*</id>", entry_xml, flags=re.DOTALL)
    summary_match = re.search(r"<summary>\s*(.*?)\s*</summary>", entry_xml, flags=re.DOTALL)
    published_match = re.search(r"<published>\s*(\d{4})", entry_xml)
    author_matches = re.findall(r"<name>\s*(.*?)\s*</name>", entry_xml, flags=re.DOTALL)
    return {
        "provider": "arxiv",
        "title": normalize_whitespace(title_match.group(1) if title_match else ""),
        "authors": ", ".join(normalize_whitespace(match) for match in author_matches),
        "year": int(published_match.group(1)) if published_match else None,
        "journal": "arXiv",
        "doi": "",
        "pmid": "",
        "url": normalize_whitespace(id_match.group(1) if id_match else ""),
        "abstract": normalize_whitespace(summary_match.group(1) if summary_match else ""),
        "publication_type_raw": "preprint",
        "cited_by_count": 0,
        "source_quality_hint": "arXiv",
    }


def crossref_search(query: str, limit: int) -> list[dict[str, object]]:
    url = f"https://api.crossref.org/works?query.bibliographic={urllib.parse.quote(query)}&rows={limit}"
    items = http_json(url).get("message", {}).get("items", [])
    return [crossref_item_to_record(item) for item in items]


def crossref_by_doi(doi: str) -> dict[str, object] | None:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}"
    item = http_json(url).get("message")
    return crossref_item_to_record(item) if item else None


def europepmc_search(query: str, limit: int) -> list[dict[str, object]]:
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
        f"query={urllib.parse.quote(query)}&format=json&pageSize={limit}&resultType=core"
    )
    items = http_json(url).get("resultList", {}).get("result", [])
    return [europepmc_item_to_record(item) for item in items]


def europepmc_by_pmid(pmid: str) -> dict[str, object] | None:
    query = urllib.parse.quote(f"EXT_ID:{pmid} AND SRC:MED")
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&pageSize=1&resultType=core"
    items = http_json(url).get("resultList", {}).get("result", [])
    return europepmc_item_to_record(items[0]) if items else None


def openalex_search(query: str, limit: int) -> list[dict[str, object]]:
    url = f"https://api.openalex.org/works?search={urllib.parse.quote(query)}&per-page={limit}"
    items = http_json(url).get("results", [])
    return [openalex_item_to_record(item) for item in items]


def arxiv_search(query: str, limit: int) -> list[dict[str, object]]:
    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query=all:{urllib.parse.quote(query)}&start=0&max_results={limit}"
    )
    xml_text = http_text(url)
    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, flags=re.DOTALL)
    return [arxiv_entry_to_record(entry) for entry in entries[:limit]]


def arxiv_by_id(identifier: str) -> dict[str, object] | None:
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(identifier)}"
    xml_text = http_text(url)
    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, flags=re.DOTALL)
    return arxiv_entry_to_record(entries[0]) if entries else None


def local_lookup(query: str, paths: list[str], limit: int) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
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
            snippet = normalize_whitespace(text[:2000])
            metadata = detect_metadata(text[:4000])
            results.append(
                {
                    "provider": "local",
                    "title": candidate.name,
                    "authors": "",
                    "year": None,
                    "journal": "",
                    "doi": (metadata["identifiers"]["doi"] or [""])[0],
                    "pmid": (metadata["identifiers"]["pmid"] or [""])[0],
                    "url": (metadata["identifiers"]["url"] or [""])[0],
                    "abstract": snippet,
                    "publication_type_raw": "local_document",
                    "cited_by_count": 0,
                    "source_quality_hint": "",
                    "source": str(candidate),
                    "title_candidate": metadata.get("title_candidate") or "",
                }
            )
            if len(results) >= limit:
                return results
    return results


def dedupe_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for record in records:
        doi = normalize_whitespace(str(record.get("doi", ""))).lower()
        pmid = normalize_whitespace(str(record.get("pmid", ""))).lower()
        title = normalize_title(str(record.get("title", "")))
        year = str(record.get("year", "") or "")
        if doi:
            key = f"doi:{doi}"
        elif pmid:
            key = f"pmid:{pmid}"
        else:
            key = f"title:{title}|year:{year}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped
