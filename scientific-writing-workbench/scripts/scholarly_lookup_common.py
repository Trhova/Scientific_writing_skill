#!/usr/bin/env python3
"""Shared helpers for paper access, scholarly lookup, and document ingestion."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from extract_metadata import detect_metadata

USER_AGENT = "scientific-writing-workbench/1.0"
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
PMID_RE = re.compile(r"\b(\d{4,9})\b")
ARXIV_RE = re.compile(r"\b([A-Za-z\-\.]+/\d{7}|\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".docx", ".pptx", ".xlsx", ".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def http_request(url: str, accept: str | None = None) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    return urllib.request.Request(url, headers=headers)


def http_json(url: str) -> dict:
    with urllib.request.urlopen(http_request(url), timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def http_text(url: str, accept: str | None = None) -> str:
    with urllib.request.urlopen(http_request(url, accept=accept), timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def http_bytes(url: str, accept: str | None = None) -> tuple[bytes, str]:
    with urllib.request.urlopen(http_request(url, accept=accept), timeout=20) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def normalize_doi(value: str) -> str:
    text = normalize_whitespace(value).replace("https://doi.org/", "").replace("http://doi.org/", "")
    match = DOI_RE.search(text)
    return match.group(0).rstrip(".,;)]}>") if match else ""


def normalize_pmid(value: str) -> str:
    text = normalize_whitespace(value).replace("PMID:", "").replace("pmid:", "")
    match = PMID_RE.search(text)
    return match.group(1) if match else ""


def normalize_arxiv_id(value: str) -> str:
    text = normalize_whitespace(value).replace("arXiv:", "").replace("arxiv:", "")
    match = ARXIV_RE.search(text)
    return match.group(1) if match else ""


def unique_nonempty(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = normalize_whitespace(str(item))
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def paper_record(origin: str = "external_record", input_type: str = "query", **overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "record_id": "",
        "origin": origin,
        "input_type": input_type,
        "title": "",
        "authors": "",
        "year": None,
        "journal": "",
        "doi": "",
        "pmid": "",
        "arxiv_id": "",
        "url": "",
        "publication_type_raw": "",
        "abstract": "",
        "full_text": "",
        "source_path": "",
        "access_level": "metadata_only",
        "metadata_status": "missing",
        "abstract_status": "unavailable",
        "full_text_status": "unavailable",
        "provenance": {
            "metadata": [],
            "abstract": [],
            "full_text": [],
            "full_text_candidates": [],
        },
        "warnings": [],
    }
    record.update(overrides)
    update_access_state(record)
    return record


def add_warning(record: dict[str, object], message: str) -> None:
    warnings = list(record.get("warnings", []))
    message = normalize_whitespace(message)
    if message and message not in warnings:
        warnings.append(message)
        record["warnings"] = warnings


def add_provenance(
    record: dict[str, object],
    layer: str,
    provider: str,
    method: str | None = None,
    url: str | None = None,
    detail: str | None = None,
) -> None:
    provenance = dict(record.get("provenance", {}))
    entries = list(provenance.get(layer, []))
    payload = {"provider": provider}
    if method:
        payload["method"] = method
    if url:
        payload["url"] = url
    if detail:
        payload["detail"] = detail
    if payload not in entries:
        entries.append(payload)
    provenance[layer] = entries
    record["provenance"] = provenance


def add_full_text_candidate(record: dict[str, object], url: str, provider: str, kind: str) -> None:
    provenance = dict(record.get("provenance", {}))
    candidates = list(provenance.get("full_text_candidates", []))
    payload = {"url": url, "provider": provider, "kind": kind}
    if payload not in candidates:
        candidates.append(payload)
    provenance["full_text_candidates"] = candidates
    record["provenance"] = provenance


def metadata_present(record: dict[str, object]) -> bool:
    return any(
        [
            normalize_whitespace(str(record.get("title", ""))),
            normalize_whitespace(str(record.get("authors", ""))),
            normalize_whitespace(str(record.get("journal", ""))),
            normalize_doi(str(record.get("doi", ""))),
            normalize_pmid(str(record.get("pmid", ""))),
            normalize_arxiv_id(str(record.get("arxiv_id", ""))),
            record.get("year"),
        ]
    )


def compute_record_id(record: dict[str, object]) -> str:
    doi = normalize_doi(str(record.get("doi", ""))).lower()
    if doi:
        return f"doi:{doi}"
    pmid = normalize_pmid(str(record.get("pmid", ""))).lower()
    if pmid:
        return f"pmid:{pmid}"
    title_key = normalize_title(str(record.get("title", "")))
    year = str(record.get("year") or "")
    if title_key:
        return f"title:{title_key}|year:{year}"
    source_path = normalize_whitespace(str(record.get("source_path", "")))
    if source_path:
        digest = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:12]
        return f"path:{digest}"
    url = normalize_whitespace(str(record.get("url", "")))
    if url:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        return f"url:{digest}"
    digest = hashlib.sha1(repr(sorted(record.items())).encode("utf-8")).hexdigest()[:12]
    return f"record:{digest}"


def update_access_state(record: dict[str, object]) -> dict[str, object]:
    if metadata_present(record):
        record["metadata_status"] = "retrieved"
    elif record.get("metadata_status") not in {"failed"}:
        record["metadata_status"] = "missing"

    if normalize_whitespace(str(record.get("abstract", ""))):
        record["abstract_status"] = "retrieved"
    elif record.get("abstract_status") not in {"failed"}:
        record["abstract_status"] = "unavailable"

    if normalize_whitespace(str(record.get("full_text", ""))):
        record["full_text_status"] = "retrieved"
        record["access_level"] = "full_text"
    elif record.get("abstract_status") == "retrieved":
        record["access_level"] = "abstract_only"
    else:
        record["access_level"] = "metadata_only"

    record["record_id"] = compute_record_id(record)
    return record


def richness_score(record: dict[str, object]) -> int:
    score = 0
    if record.get("metadata_status") == "retrieved":
        score += 10
    if record.get("abstract_status") == "retrieved":
        score += 20
    if record.get("full_text_status") == "retrieved":
        score += 50
    if record.get("doi"):
        score += 8
    if record.get("pmid"):
        score += 7
    if record.get("authors"):
        score += 4
    if record.get("journal"):
        score += 3
    if record.get("year"):
        score += 2
    if record.get("origin") == "local_file" and record.get("full_text_status") == "retrieved":
        score += 10
    return score


def is_placeholder_title(value: str, source_path: str) -> bool:
    title = normalize_whitespace(value)
    if not title:
        return True
    if not source_path:
        return False
    source_name = Path(source_path).name
    source_stem = Path(source_path).stem
    return title in {source_name, source_stem}


def merge_records(preferred: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    base = dict(preferred if richness_score(preferred) >= richness_score(candidate) else candidate)
    other = candidate if base is preferred else preferred

    for field in ("doi", "pmid", "arxiv_id", "url", "publication_type_raw", "source_path"):
        if not base.get(field) and other.get(field):
            base[field] = other[field]

    if (not base.get("title")) or is_placeholder_title(str(base.get("title", "")), str(base.get("source_path", ""))):
        if other.get("title"):
            base["title"] = other["title"]
    if not base.get("authors") and other.get("authors"):
        base["authors"] = other["authors"]
    if not base.get("journal") and other.get("journal"):
        base["journal"] = other["journal"]
    if not base.get("year") and other.get("year"):
        base["year"] = other["year"]

    if len(normalize_whitespace(str(other.get("abstract", "")))) > len(normalize_whitespace(str(base.get("abstract", "")))):
        base["abstract"] = other["abstract"]
        base["abstract_status"] = other.get("abstract_status", "retrieved")
    if len(normalize_whitespace(str(other.get("full_text", "")))) > len(normalize_whitespace(str(base.get("full_text", "")))):
        base["full_text"] = other["full_text"]
        base["full_text_status"] = other.get("full_text_status", "retrieved")
        if other.get("origin") == "local_file":
            base["origin"] = "local_file"
            if other.get("source_path"):
                base["source_path"] = other["source_path"]

    base["warnings"] = unique_nonempty([*base.get("warnings", []), *other.get("warnings", [])])

    provenance = dict(base.get("provenance", {}))
    other_provenance = dict(other.get("provenance", {}))
    for layer in ("metadata", "abstract", "full_text", "full_text_candidates"):
        merged_entries = []
        for item in provenance.get(layer, []) + other_provenance.get(layer, []):
            if item not in merged_entries:
                merged_entries.append(item)
        provenance[layer] = merged_entries
    base["provenance"] = provenance

    if other.get("metadata_status") == "retrieved":
        base["metadata_status"] = "retrieved"
    update_access_state(base)
    return base


def dedupe_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for record in records:
        normalized = update_access_state(dict(record))
        key = compute_record_id(normalized)
        if key in merged:
            merged[key] = merge_records(merged[key], normalized)
        else:
            merged[key] = normalized
            order.append(key)
    return [merged[key] for key in order]


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


def crossref_item_to_record(item: dict, input_type: str = "query") -> dict[str, object]:
    year_parts = item.get("issued", {}).get("date-parts", [[]])
    year = year_parts[0][0] if year_parts and year_parts[0] else None
    title = normalize_whitespace((item.get("title") or [""])[0])
    abstract = normalize_whitespace(re.sub(r"<[^>]+>", " ", item.get("abstract", "") or ""))
    doi = normalize_doi(item.get("DOI", ""))
    url = normalize_whitespace(item.get("URL", "")) or (f"https://doi.org/{doi}" if doi else "")
    record = paper_record(
        origin="external_record",
        input_type=input_type,
        title=title,
        authors=author_list_to_string(item.get("author")),
        year=year,
        journal=normalize_whitespace((item.get("container-title") or [""])[0]),
        doi=doi,
        url=url,
        abstract=abstract,
        publication_type_raw=normalize_whitespace(item.get("type", "")),
    )
    add_provenance(record, "metadata", "crossref", method="api", url=url or "https://api.crossref.org")
    if abstract:
        add_provenance(record, "abstract", "crossref", method="api", url=url or "https://api.crossref.org")
    return update_access_state(record)


def europepmc_item_to_record(item: dict, input_type: str = "query") -> dict[str, object]:
    abstract = normalize_whitespace(item.get("abstractText", "") or item.get("abstract", ""))
    journal = normalize_whitespace(item.get("journalTitle", ""))
    if not journal and isinstance(item.get("journalInfo"), dict):
        journal = normalize_whitespace(
            item["journalInfo"].get("journal", {}).get("title", "")
            or item["journalInfo"].get("journal", {}).get("medlineAbbreviation", "")
        )
    pub_type = item.get("pubType", "")
    if not pub_type and isinstance(item.get("pubTypeList"), dict):
        pub_types = item["pubTypeList"].get("pubType", [])
        pub_type = ", ".join(pub_types) if isinstance(pub_types, list) else str(pub_types)
    pmid = normalize_pmid(str(item.get("pmid", "")))
    pmcid = normalize_whitespace(str(item.get("pmcid", "")))
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
    record = paper_record(
        origin="external_record",
        input_type=input_type,
        title=normalize_whitespace(item.get("title", "")),
        authors=normalize_whitespace(item.get("authorString", "")),
        year=int(item["pubYear"]) if str(item.get("pubYear", "")).isdigit() else None,
        journal=journal,
        doi=normalize_doi(str(item.get("doi", ""))),
        pmid=pmid,
        url=url,
        abstract=abstract,
        publication_type_raw=normalize_whitespace(str(pub_type)),
    )
    add_provenance(record, "metadata", "europepmc", method="api", url="https://www.ebi.ac.uk/europepmc/")
    if abstract:
        add_provenance(record, "abstract", "europepmc", method="api", url="https://www.ebi.ac.uk/europepmc/")
    if pmcid:
        add_full_text_candidate(
            record,
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/{urllib.parse.quote(pmcid)}/fullTextXML",
            "europepmc",
            "xml",
        )
    if isinstance(item.get("fullTextUrlList"), dict):
        for full_text_url in item["fullTextUrlList"].get("fullTextUrl", []):
            if isinstance(full_text_url, dict):
                candidate_url = normalize_whitespace(full_text_url.get("url", ""))
                kind = normalize_whitespace(full_text_url.get("documentStyle", "")).lower() or "link"
            else:
                candidate_url = normalize_whitespace(str(full_text_url))
                kind = "link"
            if candidate_url:
                add_full_text_candidate(record, candidate_url, "europepmc", kind)
    return update_access_state(record)


def openalex_item_to_record(item: dict, input_type: str = "query") -> dict[str, object]:
    primary_location = item.get("primary_location") or {}
    source = primary_location.get("source") or {}
    ids = item.get("ids") or {}
    pmid = ids.get("pmid", "")
    pmid = pmid.rstrip("/").split("/")[-1] if pmid else ""
    doi = normalize_doi(str(item.get("doi", "")))
    url = normalize_whitespace(primary_location.get("landing_page_url", "") or item.get("id", ""))
    record = paper_record(
        origin="external_record",
        input_type=input_type,
        title=normalize_whitespace(item.get("display_name", "") or item.get("title", "")),
        authors=openalex_authors_to_string(item.get("authorships")),
        year=item.get("publication_year"),
        journal=normalize_whitespace(source.get("display_name", "")),
        doi=doi,
        pmid=pmid,
        url=url,
        abstract=normalize_whitespace(decode_openalex_abstract(item.get("abstract_inverted_index"))),
        publication_type_raw=normalize_whitespace(item.get("type", "")),
    )
    add_provenance(record, "metadata", "openalex", method="api", url="https://api.openalex.org")
    if record.get("abstract"):
        add_provenance(record, "abstract", "openalex", method="api", url="https://api.openalex.org")
    open_access = item.get("open_access") or {}
    best_oa_location = item.get("best_oa_location") or {}
    pdf_url = normalize_whitespace(best_oa_location.get("pdf_url", ""))
    landing_page_url = normalize_whitespace(best_oa_location.get("landing_page_url", "")) or normalize_whitespace(open_access.get("oa_url", ""))
    if pdf_url:
        add_full_text_candidate(record, pdf_url, "openalex", "pdf")
    if landing_page_url:
        kind = "pdf" if landing_page_url.lower().endswith(".pdf") else "html"
        add_full_text_candidate(record, landing_page_url, "openalex", kind)
    return update_access_state(record)


def arxiv_entry_to_record(entry_xml: str, input_type: str = "query") -> dict[str, object]:
    title_match = re.search(r"<title>\s*(.*?)\s*</title>", entry_xml, flags=re.DOTALL)
    id_match = re.search(r"<id>\s*(.*?)\s*</id>", entry_xml, flags=re.DOTALL)
    summary_match = re.search(r"<summary>\s*(.*?)\s*</summary>", entry_xml, flags=re.DOTALL)
    published_match = re.search(r"<published>\s*(\d{4})", entry_xml)
    author_matches = re.findall(r"<name>\s*(.*?)\s*</name>", entry_xml, flags=re.DOTALL)
    url = normalize_whitespace(id_match.group(1) if id_match else "")
    arxiv_id = url.rstrip("/").split("/")[-1] if url else ""
    record = paper_record(
        origin="external_record",
        input_type=input_type,
        title=normalize_whitespace(title_match.group(1) if title_match else ""),
        authors=", ".join(normalize_whitespace(match) for match in author_matches),
        year=int(published_match.group(1)) if published_match else None,
        journal="arXiv",
        arxiv_id=arxiv_id,
        url=url,
        abstract=normalize_whitespace(summary_match.group(1) if summary_match else ""),
        publication_type_raw="preprint",
    )
    add_provenance(record, "metadata", "arxiv", method="api", url="https://export.arxiv.org")
    if record.get("abstract"):
        add_provenance(record, "abstract", "arxiv", method="api", url="https://export.arxiv.org")
    if arxiv_id:
        add_full_text_candidate(record, f"https://arxiv.org/pdf/{urllib.parse.quote(arxiv_id)}.pdf", "arxiv", "pdf")
    return update_access_state(record)


def crossref_search(query: str, limit: int) -> list[dict[str, object]]:
    url = f"https://api.crossref.org/works?query.bibliographic={urllib.parse.quote(query)}&rows={limit}"
    items = http_json(url).get("message", {}).get("items", [])
    return [crossref_item_to_record(item) for item in items]


def crossref_by_doi(doi: str) -> dict[str, object] | None:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(normalize_doi(doi), safe='/')}"
    item = http_json(url).get("message")
    return crossref_item_to_record(item, input_type="doi") if item else None


def europepmc_search(query: str, limit: int) -> list[dict[str, object]]:
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
        f"query={urllib.parse.quote(query)}&format=json&pageSize={limit}&resultType=core"
    )
    items = http_json(url).get("resultList", {}).get("result", [])
    return [europepmc_item_to_record(item) for item in items]


def europepmc_by_pmid(pmid: str) -> dict[str, object] | None:
    query = urllib.parse.quote(f"EXT_ID:{normalize_pmid(pmid)} AND SRC:MED")
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&pageSize=1&resultType=core"
    items = http_json(url).get("resultList", {}).get("result", [])
    return europepmc_item_to_record(items[0], input_type="pmid") if items else None


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
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(normalize_arxiv_id(identifier))}"
    xml_text = http_text(url)
    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, flags=re.DOTALL)
    return arxiv_entry_to_record(entries[0], input_type="arxiv") if entries else None


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def convert_csv(path: Path) -> str:
    rows = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        for row in reader:
            rows.append("| " + " | ".join(cell.strip() for cell in row) + " |")
    if not rows:
        return ""
    if len(rows) == 1:
        return rows[0]
    separator = "|" + "|".join([" --- " for _ in rows[0].split("|")[1:-1]]) + "|"
    return "\n".join([rows[0], separator, *rows[1:]])


def text_from_xml(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    texts = []
    for element in root.iter():
        if element.text and element.text.strip():
            texts.append(element.text.strip())
    return texts


def convert_docx(path: Path) -> str:
    paragraphs = []
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        for paragraph in root.findall(".//w:p", namespace):
            parts = [node.text.strip() for node in paragraph.findall(".//w:t", namespace) if node.text and node.text.strip()]
            if parts:
                paragraphs.append("".join(parts))
    return "\n\n".join(paragraphs)


def convert_pptx(path: Path) -> str:
    slides = []
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        for index, slide_name in enumerate(slide_names, start=1):
            texts = text_from_xml(archive.read(slide_name))
            slides.append(f"## Slide {index}\n\n" + "\n".join(texts))
    return "\n\n".join(slides)


def convert_xlsx(path: Path) -> tuple[str, list[str]]:
    sections = []
    warnings = ["formula logic is not reconstructed; visible cell values only"]
    with zipfile.ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = text_from_xml(ET.tostring(shared_root, encoding="utf-8"))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        ns = {
            "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        sheet_names = [sheet.attrib.get("name", f"Sheet{idx}") for idx, sheet in enumerate(workbook.findall(".//x:sheet", ns), start=1)]

        sheet_files = sorted(
            name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        for index, sheet_file in enumerate(sheet_files):
            root = ET.fromstring(archive.read(sheet_file))
            rows = []
            for row in root.findall(".//x:row", ns):
                cells = []
                for cell in row.findall("x:c", ns):
                    value = cell.findtext("x:v", default="", namespaces=ns)
                    if cell.attrib.get("t") == "s" and value.isdigit():
                        numeric_index = int(value)
                        value = shared_strings[numeric_index] if numeric_index < len(shared_strings) else value
                    cells.append(value)
                if any(cell.strip() for cell in cells):
                    rows.append("| " + " | ".join(cells) + " |")
            title = sheet_names[index] if index < len(sheet_names) else f"Sheet{index + 1}"
            if rows:
                separator = "|" + "|".join([" --- " for _ in rows[0].split("|")[1:-1]]) + "|"
                sections.append(f"## {title}\n\n" + "\n".join([rows[0], separator, *rows[1:]]))
    return "\n\n".join(sections), warnings


def acceptable_extracted_text(text: str) -> bool:
    normalized = normalize_whitespace(text)
    alpha_count = sum(1 for char in normalized if char.isalpha())
    return len(normalized) >= 120 and alpha_count >= 80


def extract_pdf_with_pdftotext(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def extract_pdf_with_mutool(path: Path) -> str:
    for command in (
        ["mutool", "draw", "-F", "txt", "-o", "-", str(path)],
        ["mutool", "convert", "-F", "text", "-o", "-", str(path)],
    ):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return result.stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise RuntimeError("mutool text extraction failed")


def extract_pdf_with_pymupdf(path: Path) -> str:
    try:
        import fitz  # type: ignore
    except ImportError:
        try:
            import pymupdf as fitz  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PyMuPDF unavailable") from exc
    document = fitz.open(path)
    pages = []
    for page_number, page in enumerate(document, start=1):
        extracted = page.get_text("text") or ""
        pages.append(f"## Page {page_number}\n\n{extracted.strip()}")
    return "\n\n".join(pages)


def extract_pdf_with_pypdf(path: Path) -> str:
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(module_name)
            reader = module.PdfReader(str(path))
            pages = []
            for page_number, page in enumerate(reader.pages, start=1):
                extracted = page.extract_text() or ""
                pages.append(f"## Page {page_number}\n\n{extracted.strip()}")
            return "\n\n".join(pages)
        except Exception:
            continue
    raise RuntimeError("pypdf unavailable")


def extract_pdf_with_pdfplumber(path: Path) -> str:
    import pdfplumber  # type: ignore

    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            extracted = page.extract_text() or ""
            pages.append(f"## Page {page_number}\n\n{extracted.strip()}")
    return "\n\n".join(pages)


def ocr_tools_available() -> bool:
    return bool(shutil.which("tesseract")) and (
        bool(shutil.which("pdftoppm")) or bool(shutil.which("mutool")) or import_available("fitz") or import_available("pymupdf")
    )


def import_available(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def render_pdf_pages_for_ocr(path: Path, output_dir: Path) -> list[Path]:
    if shutil.which("pdftoppm"):
        prefix = output_dir / "page"
        subprocess.run(["pdftoppm", "-png", str(path), str(prefix)], check=True, capture_output=True, text=True)
        return sorted(output_dir.glob("page-*.png"))

    if shutil.which("mutool"):
        output_pattern = output_dir / "page-%d.png"
        subprocess.run(
            ["mutool", "draw", "-F", "png", "-o", str(output_pattern), str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return sorted(output_dir.glob("page-*.png"))

    try:
        import fitz  # type: ignore
    except ImportError:
        try:
            import pymupdf as fitz  # type: ignore
        except ImportError as exc:
            raise RuntimeError("no PDF renderer available for OCR") from exc
    document = fitz.open(path)
    image_paths = []
    for page_number, page in enumerate(document, start=1):
        pixmap = page.get_pixmap()
        image_path = output_dir / f"page-{page_number}.png"
        pixmap.save(str(image_path))
        image_paths.append(image_path)
    return image_paths


def run_tesseract(image_path: Path) -> str:
    result = subprocess.run(["tesseract", str(image_path), "stdout"], capture_output=True, text=True, check=True)
    return result.stdout


def attempt_pdf_ocr(path: Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not ocr_tools_available():
        return "", ["OCR tooling is unavailable in this environment"]
    with tempfile.TemporaryDirectory(prefix="paper-access-ocr-") as temp_dir:
        output_dir = Path(temp_dir)
        try:
            image_paths = render_pdf_pages_for_ocr(path, output_dir)
        except Exception as exc:
            return "", [f"OCR rendering failed: {exc}"]
        pages = []
        for image_path in image_paths:
            try:
                text = run_tesseract(image_path)
            except Exception as exc:
                warnings.append(f"OCR failed on {image_path.name}: {exc}")
                continue
            pages.append(text)
        return "\n\n".join(pages).strip(), warnings


def extract_pdf_text(path: Path, enable_ocr: bool = False) -> tuple[str, list[str], str]:
    warnings: list[str] = []
    methods = [
        ("pdftotext", extract_pdf_with_pdftotext),
        ("mutool", extract_pdf_with_mutool),
        ("pymupdf", extract_pdf_with_pymupdf),
        ("pypdf", extract_pdf_with_pypdf),
        ("pdfplumber", extract_pdf_with_pdfplumber),
    ]
    for name, extractor in methods:
        try:
            text = extractor(path)
        except Exception as exc:
            warnings.append(f"{name} failed: {exc}")
            continue
        if acceptable_extracted_text(text):
            return text.strip(), warnings, name
        if normalize_whitespace(text):
            warnings.append(f"{name} produced too little usable text")

    if enable_ocr:
        ocr_text, ocr_warnings = attempt_pdf_ocr(path)
        warnings.extend(ocr_warnings)
        if acceptable_extracted_text(ocr_text):
            return ocr_text.strip(), warnings, "ocr"
        if normalize_whitespace(ocr_text):
            warnings.append("OCR produced too little usable text")
        return "", warnings, "ocr_failed"

    if ocr_tools_available():
        warnings.append("normal PDF extraction failed; OCR is available but disabled")
        return "", warnings, "ocr_needed"
    warnings.append("no PDF extractor succeeded")
    return "", warnings, "extraction_failed"


def strip_markup(text: str) -> str:
    return normalize_whitespace(re.sub(r"<[^>]+>", " ", text))


def extract_abstract_from_text(text: str) -> str:
    if not text:
        return ""
    pattern = re.compile(
        r"\babstract\b[:\s]*(.+?)(?:\n\s*\b(?:introduction|background|methods|keywords)\b|\Z)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    return normalize_whitespace(match.group(1))


def convert_file_to_text(path: Path, enable_ocr: bool = False) -> tuple[str, list[str], str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return read_text_file(path), [], "text"
    if suffix == ".csv":
        return convert_csv(path), [], "csv"
    if suffix == ".docx":
        return convert_docx(path), [], "docx"
    if suffix == ".pptx":
        return convert_pptx(path), [], "pptx"
    if suffix == ".xlsx":
        content, warnings = convert_xlsx(path)
        return content, warnings, "xlsx"
    if suffix == ".pdf":
        return extract_pdf_text(path, enable_ocr=enable_ocr)
    return "", [f"unsupported file type: {suffix or '<no suffix>'}"], "unsupported"


def expand_input_paths(paths: list[str]) -> list[Path]:
    expanded: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file() and candidate.suffix.lower() in TEXT_EXTENSIONS:
                    expanded.append(candidate)
        elif path.is_file():
            expanded.append(path)
    return expanded


def infer_year(metadata: dict[str, object]) -> int | None:
    years = metadata.get("year_candidates", [])
    if not years:
        return None
    try:
        return int(years[-1])
    except (ValueError, TypeError):
        return None


def local_file_to_record(path: Path, enable_ocr: bool = False) -> dict[str, object]:
    record = paper_record(origin="local_file", input_type="path", source_path=str(path), title=path.stem)
    try:
        content, warnings, method = convert_file_to_text(path, enable_ocr=enable_ocr)
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        record["metadata_status"] = "failed"
        record["full_text_status"] = "extraction_failed"
        add_warning(record, str(exc))
        return update_access_state(record)

    for warning in warnings:
        add_warning(record, warning)

    if content:
        record["full_text"] = content
        record["full_text_status"] = "retrieved"
        add_provenance(record, "full_text", "local_file", method=method, detail=str(path))
        abstract = extract_abstract_from_text(content)
        if abstract:
            record["abstract"] = abstract
            record["abstract_status"] = "retrieved"
            add_provenance(record, "abstract", "local_file", method="section_parse", detail=str(path))
    else:
        if method == "ocr_needed":
            record["full_text_status"] = "ocr_needed"
        elif method == "ocr_failed":
            record["full_text_status"] = "ocr_failed"
        else:
            record["full_text_status"] = "extraction_failed"

    metadata_input = "\n".join(part for part in [path.stem, record.get("abstract", ""), content[:10000] if content else ""] if part)
    metadata = detect_metadata(metadata_input)
    record["doi"] = normalize_doi((metadata["identifiers"]["doi"] or [""])[0])
    record["pmid"] = normalize_pmid((metadata["identifiers"]["pmid"] or [""])[0])
    record["arxiv_id"] = normalize_arxiv_id((metadata["identifiers"]["arxiv"] or [""])[0])
    record["url"] = normalize_whitespace((metadata["identifiers"]["url"] or [""])[0])
    record["year"] = infer_year(metadata)
    title_candidate = normalize_whitespace(str(metadata.get("title_candidate", "")))
    if title_candidate:
        record["title"] = title_candidate
    add_provenance(record, "metadata", "local_file", method="identifier_parse", detail=str(path))
    return update_access_state(record)


def enrich_record_from_metadata(record: dict[str, object]) -> dict[str, object]:
    candidates: list[dict[str, object]] = [record]
    doi = normalize_doi(str(record.get("doi", "")))
    pmid = normalize_pmid(str(record.get("pmid", "")))
    arxiv_id = normalize_arxiv_id(str(record.get("arxiv_id", "")))
    title = normalize_whitespace(str(record.get("title", "")))
    try:
        if doi:
            resolved = crossref_by_doi(doi)
            if resolved:
                candidates.append(resolved)
    except Exception as exc:
        add_warning(record, f"Crossref enrichment failed: {exc}")
    try:
        if pmid:
            resolved = europepmc_by_pmid(pmid)
            if resolved:
                candidates.append(resolved)
    except Exception as exc:
        add_warning(record, f"Europe PMC enrichment failed: {exc}")
    try:
        if arxiv_id:
            resolved = arxiv_by_id(arxiv_id)
            if resolved:
                candidates.append(resolved)
    except Exception as exc:
        add_warning(record, f"arXiv enrichment failed: {exc}")
    try:
        if title and not doi and not pmid and not arxiv_id:
            search_hits = openalex_search(title, 1)
            if search_hits:
                candidates.append(search_hits[0])
    except Exception as exc:
        add_warning(record, f"Title enrichment failed: {exc}")
    merged = dedupe_records(candidates)[0]
    if record.get("origin") == "local_file":
        merged["origin"] = "local_file"
        if record.get("source_path"):
            merged["source_path"] = record["source_path"]
        if record.get("full_text_status") == "retrieved":
            merged["full_text"] = record.get("full_text", "")
            merged["full_text_status"] = "retrieved"
            add_provenance(merged, "full_text", "local_file", method="local_file", detail=str(record.get("source_path", "")))
    return update_access_state(merged)


def fetch_external_full_text(record: dict[str, object], enable_ocr: bool = False) -> dict[str, object]:
    candidates = list(dict(record.get("provenance", {})).get("full_text_candidates", []))
    if record.get("full_text_status") == "retrieved":
        return record
    if not candidates:
        record["full_text_status"] = "unavailable"
        return update_access_state(record)

    for candidate in candidates:
        url = normalize_whitespace(str(candidate.get("url", "")))
        provider = normalize_whitespace(str(candidate.get("provider", ""))) or "external"
        kind = normalize_whitespace(str(candidate.get("kind", ""))).lower()
        if not url:
            continue
        try:
            if kind in {"xml", "html", "txt"}:
                text = http_text(url)
                cleaned = strip_markup(text)
                if acceptable_extracted_text(cleaned):
                    record["full_text"] = cleaned
                    record["full_text_status"] = "retrieved"
                    add_provenance(record, "full_text", provider, method=kind, url=url)
                    return update_access_state(record)
                add_warning(record, f"{provider} full-text candidate did not yield usable text")
                continue

            payload, content_type = http_bytes(url)
            if kind == "pdf" or url.lower().endswith(".pdf") or "application/pdf" in content_type.lower():
                with tempfile.NamedTemporaryFile(prefix="paper-access-", suffix=".pdf", delete=False) as handle:
                    handle.write(payload)
                    temp_pdf = Path(handle.name)
                try:
                    text, warnings, method = extract_pdf_text(temp_pdf, enable_ocr=enable_ocr)
                finally:
                    temp_pdf.unlink(missing_ok=True)
                for warning in warnings:
                    add_warning(record, warning)
                if text:
                    record["full_text"] = text
                    record["full_text_status"] = "retrieved"
                    add_provenance(record, "full_text", provider, method=method, url=url)
                    return update_access_state(record)
                if method == "ocr_needed":
                    record["full_text_status"] = "ocr_needed"
                elif method == "ocr_failed":
                    record["full_text_status"] = "ocr_failed"
                else:
                    record["full_text_status"] = "extraction_failed"
                continue

            cleaned = strip_markup(payload.decode("utf-8", errors="replace"))
            if acceptable_extracted_text(cleaned):
                record["full_text"] = cleaned
                record["full_text_status"] = "retrieved"
                add_provenance(record, "full_text", provider, method="http_text", url=url)
                return update_access_state(record)
            add_warning(record, f"{provider} candidate returned non-usable text")
        except Exception as exc:
            add_warning(record, f"{provider} full-text retrieval failed: {exc}")
            continue

    if record.get("full_text_status") not in {"ocr_needed", "ocr_failed", "extraction_failed"}:
        record["full_text_status"] = "unavailable"
    return update_access_state(record)


def local_lookup(query: str, paths: list[str], limit: int, enable_ocr: bool = False) -> list[dict[str, object]]:
    needles = [token.lower() for token in re.findall(r"\w+", query) if len(token) > 2]
    results: list[dict[str, object]] = []
    for candidate in expand_input_paths(paths):
        record = enrich_record_from_metadata(local_file_to_record(candidate, enable_ocr=enable_ocr))
        text = " ".join([str(record.get("title", "")), str(record.get("abstract", "")), str(record.get("full_text", ""))]).lower()
        if needles and not any(token in text for token in needles[: min(5, len(needles))]):
            continue
        results.append(record)
        if len(results) >= limit:
            break
    return dedupe_records(results)
