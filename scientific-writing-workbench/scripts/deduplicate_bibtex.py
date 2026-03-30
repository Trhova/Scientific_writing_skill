#!/usr/bin/env python3
"""Collapse duplicate or near-duplicate BibTeX entries."""

from __future__ import annotations

import argparse
import re
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deduplicate BibTeX entries while keeping the richest record.")
    parser.add_argument("bibtex_file", help="Input BibTeX file.")
    parser.add_argument("--output", help="Write the deduplicated BibTeX to this path.")
    return parser.parse_args()


def split_entries(text: str) -> list[str]:
    entries: list[str] = []
    index = 0
    while True:
        start = text.find("@", index)
        if start < 0:
            break
        brace_start = text.find("{", start)
        if brace_start < 0:
            break
        depth = 0
        end = brace_start
        while end < len(text):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    entries.append(text[start : end + 1].strip())
                    index = end + 1
                    break
            end += 1
        else:
            break
    return entries


def parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pairs = re.finditer(r"(\w+)\s*=\s*({(?:[^{}]|{[^{}]*})*}|\"[^\"]*\"|[^,\n]+)", body, re.DOTALL)
    for match in pairs:
        key = match.group(1).lower()
        value = match.group(2).strip().strip(",").strip()
        if value.startswith("{") and value.endswith("}"):
            value = value[1:-1]
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        fields[key] = value.strip()
    return fields


def parse_entry(raw_entry: str) -> dict[str, object] | None:
    match = re.match(r"@(\w+)\s*{\s*([^,]+)\s*,", raw_entry, re.DOTALL)
    if not match:
        return None
    body = raw_entry[match.end() : -1]
    return {
        "type": match.group(1).lower(),
        "key": match.group(2).strip(),
        "fields": parse_fields(body),
        "raw": raw_entry,
    }


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def score_entry(entry: dict[str, object]) -> tuple[int, int, int]:
    fields = entry["fields"]
    assert isinstance(fields, dict)
    entry_type = entry["type"]
    type_score = {"article": 4, "inproceedings": 3, "book": 2, "misc": 1}.get(entry_type, 0)
    field_score = len([value for value in fields.values() if value])
    published_bonus = 1 if fields.get("doi") and fields.get("journal") else 0
    preprint_penalty = -1 if any(word in " ".join(fields.values()).lower() for word in ("arxiv", "preprint")) else 0
    return (type_score + published_bonus + preprint_penalty, field_score, len(entry["raw"]))


def cluster_key(entry: dict[str, object]) -> str:
    fields = entry["fields"]
    assert isinstance(fields, dict)
    title = normalize_title(fields.get("title", ""))
    year = fields.get("year", "").strip()
    author = fields.get("author", "").split(" and ")[0].lower().strip() if fields.get("author") else ""
    if title and (year or author):
        return f"title:{title}|year:{year}|author:{author}"
    doi = fields.get("doi", "").lower().strip()
    if doi:
        return f"doi:{doi}"
    eprint = fields.get("eprint", "").lower().strip()
    if eprint:
        return f"eprint:{eprint}"
    return f"key:{entry['key']}"


def main() -> int:
    args = parse_args()
    try:
        text = open(args.bibtex_file, "r", encoding="utf-8").read()
    except OSError as exc:
        print(f"error: could not read {args.bibtex_file}: {exc}", file=sys.stderr)
        return 1

    entries = [parse_entry(raw_entry) for raw_entry in split_entries(text)]
    parsed_entries = [entry for entry in entries if entry is not None]
    clusters: dict[str, list[dict[str, object]]] = {}
    for entry in parsed_entries:
        key = cluster_key(entry)
        clusters.setdefault(key, []).append(entry)

    kept: list[dict[str, object]] = []
    dropped_report: list[str] = []
    for key in sorted(clusters):
        group = clusters[key]
        winner = max(group, key=score_entry)
        kept.append(winner)
        losers = [entry["key"] for entry in group if entry["key"] != winner["key"]]
        if losers:
            dropped_report.append(f"{winner['key']} kept for {key}; dropped {', '.join(losers)}")

    output_text = "\n\n".join(entry["raw"] for entry in kept) + ("\n" if kept else "")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output_text)
    else:
        print(output_text, end="")

    if dropped_report:
        print("\nDeduplication report:", file=sys.stderr)
        for line in dropped_report:
            print(f"- {line}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
