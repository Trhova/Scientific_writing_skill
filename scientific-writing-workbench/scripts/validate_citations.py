#!/usr/bin/env python3
"""Validate BibTeX files for common integrity and consistency issues."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
YEAR_RE = re.compile(r"^(19|20)\d{2}$")
PREPRINT_WORDS = ("arxiv", "preprint", "biorxiv", "medrxiv")


@dataclass
class Entry:
    entry_type: str
    key: str
    fields: dict[str, str]
    raw: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BibTeX integrity and common metadata issues.")
    parser.add_argument("bibtex_file", help="BibTeX file to validate.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    parser.add_argument("--check-doi", action="store_true", help="Check whether DOI URLs resolve.")
    return parser.parse_args()


def split_entries(text: str) -> tuple[list[str], list[str]]:
    entries: list[str] = []
    malformed: list[str] = []
    index = 0
    while True:
        start = text.find("@", index)
        if start < 0:
            break
        brace_start = text.find("{", start)
        if brace_start < 0:
            malformed.append(text[start:].strip())
            break
        depth = 0
        end = brace_start
        while end < len(text):
            char = text[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    entries.append(text[start : end + 1].strip())
                    index = end + 1
                    break
            end += 1
        else:
            malformed.append(text[start:].strip())
            break
    return entries, malformed


def parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    length = len(body)
    while i < length:
        while i < length and body[i] in " \t\r\n,":
            i += 1
        if i >= length:
            break
        name_start = i
        while i < length and body[i] not in "=":
            i += 1
        field_name = body[name_start:i].strip().lower()
        if not field_name or i >= length:
            break
        i += 1
        while i < length and body[i].isspace():
            i += 1
        if i >= length:
            break
        if body[i] == "{":
            depth = 0
            value_start = i + 1
            while i < length:
                if body[i] == "{":
                    depth += 1
                elif body[i] == "}":
                    depth -= 1
                    if depth == 0:
                        fields[field_name] = body[value_start:i].strip()
                        i += 1
                        break
                i += 1
        elif body[i] == '"':
            value_start = i + 1
            i += 1
            while i < length and body[i] != '"':
                i += 1
            fields[field_name] = body[value_start:i].strip()
            i += 1
        else:
            value_start = i
            while i < length and body[i] not in ",\n":
                i += 1
            fields[field_name] = body[value_start:i].strip()
    return fields


def parse_entry(raw_entry: str) -> Entry | None:
    match = re.match(r"@(\w+)\s*{\s*([^,]+)\s*,", raw_entry, re.DOTALL)
    if not match:
        return None
    entry_type = match.group(1).lower()
    key = match.group(2).strip()
    body = raw_entry[match.end() : -1]
    return Entry(entry_type=entry_type, key=key, fields=parse_fields(body), raw=raw_entry)


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def first_author(value: str) -> str:
    return value.split(" and ")[0].strip().lower()


def required_fields(entry: Entry) -> list[str]:
    requirements = {
        "article": ["author", "title", "journal", "year"],
        "inproceedings": ["author", "title", "booktitle", "year"],
        "book": ["title", "year"],
        "misc": ["title"],
    }
    return requirements.get(entry.entry_type, ["title"])


def check_doi_resolution(doi: str) -> str | None:
    request = urllib.request.Request(
        f"https://doi.org/{urllib.parse.quote(doi, safe='/')}",
        method="HEAD",
        headers={"User-Agent": "scientific-writing-workbench/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                return f"DOI returned HTTP {response.status}"
            return None
    except urllib.error.URLError as exc:
        return str(exc)


def main() -> int:
    args = parse_args()
    try:
        text = open(args.bibtex_file, "r", encoding="utf-8").read()
    except OSError as exc:
        print(f"error: could not read {args.bibtex_file}: {exc}", file=sys.stderr)
        return 1

    raw_entries, malformed_blocks = split_entries(text)
    entries: list[Entry] = []
    issues: list[dict[str, object]] = []

    for raw_entry in raw_entries:
        entry = parse_entry(raw_entry)
        if entry is None:
            malformed_blocks.append(raw_entry)
            continue
        entries.append(entry)

        for field_name in required_fields(entry):
            if not entry.fields.get(field_name, "").strip():
                issues.append({"severity": "error", "key": entry.key, "issue": f"missing required field '{field_name}'"})

        year = entry.fields.get("year")
        if year and not YEAR_RE.match(year):
            issues.append({"severity": "warning", "key": entry.key, "issue": f"suspicious year '{year}'"})

        doi = entry.fields.get("doi", "").strip()
        if doi:
            if not DOI_RE.match(doi):
                issues.append({"severity": "error", "key": entry.key, "issue": f"invalid DOI format '{doi}'"})
            elif args.check_doi:
                resolution_problem = check_doi_resolution(doi)
                if resolution_problem:
                    issues.append(
                        {"severity": "warning", "key": entry.key, "issue": f"DOI resolution check failed: {resolution_problem}"}
                    )

    for block in malformed_blocks:
        issues.append({"severity": "error", "key": None, "issue": "malformed BibTeX block", "snippet": block[:160]})

    doi_index: dict[str, list[Entry]] = {}
    cluster_index: dict[str, list[Entry]] = {}
    for entry in entries:
        doi = entry.fields.get("doi", "").lower().strip()
        if doi:
            doi_index.setdefault(doi, []).append(entry)
        title = normalize_title(entry.fields.get("title", ""))
        year = entry.fields.get("year", "").strip()
        author = first_author(entry.fields.get("author", "")) if entry.fields.get("author") else ""
        if title and (year or author):
            cluster_key = "|".join([title, year, author])
            cluster_index.setdefault(cluster_key, []).append(entry)

    for doi, group in doi_index.items():
        if len(group) > 1:
            issues.append(
                {
                    "severity": "warning",
                    "key": ",".join(entry.key for entry in group),
                    "issue": f"duplicate DOI cluster '{doi}'",
                }
            )

    for cluster_key, group in cluster_index.items():
        if len(group) > 1:
            years = {entry.fields.get("year", "").strip() for entry in group}
            titles = {entry.fields.get("title", "").strip() for entry in group}
            issues.append(
                {
                    "severity": "warning",
                    "key": ",".join(entry.key for entry in group),
                    "issue": f"possible duplicate title/author/year cluster '{cluster_key}'",
                }
            )
            if len(years) > 1 or len(titles) > 1:
                issues.append(
                    {
                        "severity": "warning",
                        "key": ",".join(entry.key for entry in group),
                        "issue": "title or year mismatch inside duplicate-like cluster",
                    }
                )

            has_preprint = any(
                any(word in " ".join(entry.fields.values()).lower() for word in PREPRINT_WORDS) for entry in group
            )
            has_published = any(entry.entry_type == "article" and entry.fields.get("journal") for entry in group)
            if has_preprint and has_published:
                issues.append(
                    {
                        "severity": "warning",
                        "key": ",".join(entry.key for entry in group),
                        "issue": "likely preprint versus published-version conflict",
                    }
                )

    report = {
        "file": args.bibtex_file,
        "entry_count": len(entries),
        "issue_count": len(issues),
        "issues": issues,
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print(f"Validated {len(entries)} entries from {args.bibtex_file}")
        if not issues:
            print("No issues found.")
        for issue in issues:
            key = issue["key"] or "<unknown>"
            print(f"[{issue['severity']}] {key}: {issue['issue']}")
            if "snippet" in issue:
                print(f"  snippet: {issue['snippet']}")

    return 1 if any(issue["severity"] == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
