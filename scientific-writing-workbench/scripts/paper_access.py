#!/usr/bin/env python3
"""Unified paper retrieval and ingestion entry point."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from scholarly_lookup_common import (
    TEXT_EXTENSIONS,
    arxiv_by_id,
    arxiv_search,
    crossref_by_doi,
    crossref_search,
    dedupe_records,
    enrich_record_from_metadata,
    europepmc_by_pmid,
    europepmc_search,
    fetch_external_full_text,
    local_file_to_record,
    local_lookup,
    normalize_arxiv_id,
    normalize_doi,
    normalize_pmid,
    normalize_whitespace,
    openalex_search,
    paper_record,
    richness_score,
    update_access_state,
)

DEFAULT_PROVIDERS = ("europepmc", "openalex", "crossref")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve and ingest scientific papers from local files or scholarly identifiers.")
    parser.add_argument("--path", dest="paths", nargs="*", default=[], help="Local files or directories to inspect.")
    parser.add_argument("--doi", nargs="*", default=[], help="DOI identifiers to resolve.")
    parser.add_argument("--pmid", nargs="*", default=[], help="PMID identifiers to resolve.")
    parser.add_argument("--arxiv", nargs="*", default=[], help="arXiv identifiers to resolve.")
    parser.add_argument("--title", nargs="*", default=[], help="Paper titles to search.")
    parser.add_argument("--citation", nargs="*", default=[], help="Citation strings to resolve.")
    parser.add_argument("--query", nargs="*", default=[], help="Free-text literature queries.")
    parser.add_argument("--claim", nargs="*", default=[], help="Claims to turn into literature search queries.")
    parser.add_argument("--limit-per-provider", type=int, default=5, help="Maximum candidates fetched per provider.")
    parser.add_argument("--provider", nargs="*", choices=["europepmc", "openalex", "crossref", "arxiv"], help="Override external providers.")
    parser.add_argument("--enable-ocr", action="store_true", help="Enable OCR fallback after normal PDF extraction fails.")
    parser.add_argument("--full-text-fetch-limit", type=int, default=5, help="Maximum number of merged candidates to attempt open-access full-text retrieval for.")
    parser.add_argument("--json-indent", type=int, default=2, help="Indentation for JSON output.")
    return parser.parse_args()


def claim_to_queries(claim: str) -> list[str]:
    text = normalize_whitespace(claim)
    text = re.sub(r"^(?:this sentence needs a source:)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:find the best source for this claim:)\s*", "", text, flags=re.IGNORECASE)
    stripped = text.strip(" []\"'")
    if not stripped:
        return []
    variants = [stripped]
    softened = re.sub(r"\bcure(s)?\b", "treat", stripped, flags=re.IGNORECASE)
    softened = re.sub(r"\bprevent(s)?\b", "reduce risk of", softened, flags=re.IGNORECASE)
    if softened != stripped:
        variants.append(softened)
    variants.append(f"{stripped} systematic review")
    variants.append(f"{stripped} human study")
    deduped: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        key = variant.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(variant)
    return deduped[:4]


def search_external(query: str, limit_per_provider: int, providers: tuple[str, ...]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for provider in providers:
        try:
            if provider == "europepmc":
                results.extend(europepmc_search(query, limit_per_provider))
            elif provider == "openalex":
                results.extend(openalex_search(query, limit_per_provider))
            elif provider == "crossref":
                results.extend(crossref_search(query, limit_per_provider))
            elif provider == "arxiv":
                results.extend(arxiv_search(query, limit_per_provider))
        except Exception:
            continue
    return results


def resolve_identifier_records(dois: list[str], pmids: list[str], arxiv_ids: list[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for doi in dois:
        normalized = normalize_doi(doi)
        if not normalized:
            records.append(paper_record(input_type="doi", warnings=[f"unsupported DOI input: {doi}"], metadata_status="failed"))
            continue
        try:
            record = crossref_by_doi(normalized)
            if record:
                openalex_hits = openalex_search(normalized, 1)
                if openalex_hits:
                    record = dedupe_records([record, openalex_hits[0]])[0]
                record["input_type"] = "doi"
                records.append(update_access_state(record))
            else:
                records.append(paper_record(input_type="doi", doi=normalized, metadata_status="failed", warnings=["DOI not found"]))
        except Exception as exc:
            records.append(paper_record(input_type="doi", doi=normalized, metadata_status="failed", warnings=[f"DOI lookup failed: {exc}"]))
    for pmid in pmids:
        normalized = normalize_pmid(pmid)
        if not normalized:
            records.append(paper_record(input_type="pmid", warnings=[f"unsupported PMID input: {pmid}"], metadata_status="failed"))
            continue
        try:
            record = europepmc_by_pmid(normalized)
            if record:
                openalex_hits = openalex_search(normalized, 1)
                if openalex_hits:
                    record = dedupe_records([record, openalex_hits[0]])[0]
                record["input_type"] = "pmid"
                records.append(update_access_state(record))
            else:
                records.append(paper_record(input_type="pmid", pmid=normalized, metadata_status="failed", warnings=["PMID not found"]))
        except Exception as exc:
            records.append(paper_record(input_type="pmid", pmid=normalized, metadata_status="failed", warnings=[f"PMID lookup failed: {exc}"]))
    for arxiv_id in arxiv_ids:
        normalized = normalize_arxiv_id(arxiv_id)
        if not normalized:
            records.append(paper_record(input_type="arxiv", warnings=[f"unsupported arXiv input: {arxiv_id}"], metadata_status="failed"))
            continue
        try:
            record = arxiv_by_id(normalized)
            if record:
                record["input_type"] = "arxiv"
                records.append(update_access_state(record))
            else:
                records.append(paper_record(input_type="arxiv", arxiv_id=normalized, metadata_status="failed", warnings=["arXiv record not found"]))
        except Exception as exc:
            records.append(paper_record(input_type="arxiv", arxiv_id=normalized, metadata_status="failed", warnings=[f"arXiv lookup failed: {exc}"]))
    return records


def collect_local_records(paths: list[str], enable_ocr: bool) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            candidates = sorted(
                candidate for candidate in path.rglob("*") if candidate.is_file() and candidate.suffix.lower() in TEXT_EXTENSIONS
            )
        else:
            candidates = [path]
        for candidate in candidates:
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            key = str(candidate.resolve())
            if key in seen:
                continue
            seen.add(key)
            records.append(enrich_record_from_metadata(local_file_to_record(candidate, enable_ocr=enable_ocr)))
    return records


def collect_query_records(
    queries: list[str],
    paths: list[str],
    limit_per_provider: int,
    enable_ocr: bool,
    providers: tuple[str, ...],
    input_type: str,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for query in queries:
        if paths:
            for record in local_lookup(query, paths, limit_per_provider, enable_ocr=enable_ocr):
                record["input_type"] = input_type if input_type != "query" else record.get("input_type", "path")
                records.append(record)
        external_hits = search_external(query, limit_per_provider, providers)
        for hit in external_hits:
            hit["input_type"] = input_type
            records.append(hit)
    return records


def finalize_records(records: list[dict[str, object]], enable_ocr: bool, full_text_fetch_limit: int | None = 5) -> list[dict[str, object]]:
    merged = dedupe_records(records)
    enriched_records = [enrich_record_from_metadata(record) for record in merged]
    fetchable = [
        index
        for index, record in enumerate(enriched_records)
        if record.get("full_text_status") != "retrieved" and dict(record.get("provenance", {})).get("full_text_candidates")
    ]
    fetchable.sort(key=lambda index: richness_score(enriched_records[index]), reverse=True)
    fetch_indices = set(fetchable if full_text_fetch_limit is None else fetchable[:full_text_fetch_limit])
    finalized = []
    for index, enriched in enumerate(enriched_records):
        if enriched.get("full_text_status") != "retrieved" and index in fetch_indices:
            enriched = fetch_external_full_text(enriched, enable_ocr=enable_ocr)
        finalized.append(update_access_state(enriched))
    return dedupe_records(finalized)


def collect_paper_records(
    *,
    paths: list[str] | None = None,
    dois: list[str] | None = None,
    pmids: list[str] | None = None,
    arxiv_ids: list[str] | None = None,
    titles: list[str] | None = None,
    citations: list[str] | None = None,
    queries: list[str] | None = None,
    claims: list[str] | None = None,
    limit_per_provider: int = 5,
    enable_ocr: bool = False,
    providers: tuple[str, ...] = DEFAULT_PROVIDERS,
    full_text_fetch_limit: int | None = 5,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    normalized_paths = paths or []
    records.extend(collect_local_records(normalized_paths, enable_ocr=enable_ocr))
    records.extend(resolve_identifier_records(dois or [], pmids or [], arxiv_ids or []))
    records.extend(collect_query_records(titles or [], normalized_paths, limit_per_provider, enable_ocr, providers, "title"))
    records.extend(collect_query_records(citations or [], normalized_paths, limit_per_provider, enable_ocr, providers, "citation"))
    records.extend(collect_query_records(queries or [], normalized_paths, limit_per_provider, enable_ocr, providers, "query"))
    expanded_claim_queries = []
    for claim in claims or []:
        expanded_claim_queries.extend(claim_to_queries(claim))
    records.extend(collect_query_records(expanded_claim_queries, normalized_paths, limit_per_provider, enable_ocr, providers, "claim"))
    return finalize_records(records, enable_ocr=enable_ocr, full_text_fetch_limit=full_text_fetch_limit)


def main() -> int:
    args = parse_args()
    providers = tuple(args.provider) if args.provider else DEFAULT_PROVIDERS
    records = collect_paper_records(
        paths=args.paths,
        dois=args.doi,
        pmids=args.pmid,
        arxiv_ids=args.arxiv,
        titles=args.title,
        citations=args.citation,
        queries=args.query,
        claims=args.claim,
        limit_per_provider=args.limit_per_provider,
        enable_ocr=args.enable_ocr,
        providers=providers,
        full_text_fetch_limit=args.full_text_fetch_limit,
    )
    print(
        json.dumps(
            {
                "records": records,
                "summary": {
                    "count": len(records),
                    "full_text": sum(1 for record in records if record.get("access_level") == "full_text"),
                    "abstract_only": sum(1 for record in records if record.get("access_level") == "abstract_only"),
                    "metadata_only": sum(1 for record in records if record.get("access_level") == "metadata_only"),
                },
            },
            indent=args.json_indent,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
