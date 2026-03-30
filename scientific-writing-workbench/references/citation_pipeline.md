# Citation Pipeline

Use this reference for bibliography building, cleaning, and validation.

## Pipeline stages

1. Discovery and intake
   - collect DOIs, PMIDs, arXiv IDs, URLs, note fragments, and existing BibTeX
   - keep a record of where each identifier came from
2. Metadata extraction
   - extract identifiers and candidate titles from local files first
   - use `scripts/extract_metadata.py` for text or converted documents
3. Enrichment
   - fill missing metadata from online sources only when an identifier or trustworthy source is available
   - use `scripts/doi_to_bibtex.py`
   - never invent fields that cannot be confirmed
4. Formatting and normalization
   - normalize entry keys, DOI casing, whitespace, and obvious field formatting issues
5. Validation
   - use `scripts/validate_citations.py`
   - check malformed BibTeX, missing fields, duplicate records, DOI problems, and likely preprint versus published conflicts
6. Deduplication
   - use `scripts/deduplicate_bibtex.py`
   - keep the richest trustworthy published record when entries overlap

## Required caution

- A BibTeX record is not automatically correct because it parsed successfully.
- Do not merge entries that only look similar without a reason.
- If a preprint and published article appear to describe the same work, prefer the published version for ordinary citation unless the preprint is the actual object being discussed.

## Validation targets

Check for:

- missing required fields by entry type
- malformed BibTeX blocks
- DOI syntax problems
- unresolved DOI links when online checks are enabled
- duplicate DOI or title-year-author clusters
- title or year conflicts across duplicate-like entries
- preprint flags on one record and journal publication fields on another record with the same title

## Recommended working files

- `references_raw.bib` for initial intake
- `references_clean.bib` for validated output
- `citation_issues.json` or a similar report for unresolved problems

## Minimal command sequence

```bash
python scientific-writing-workbench/scripts/extract_metadata.py notes.md
python scientific-writing-workbench/scripts/doi_to_bibtex.py 10.1038/exampledoi --append references_raw.bib
python scientific-writing-workbench/scripts/validate_citations.py references_raw.bib --json
python scientific-writing-workbench/scripts/deduplicate_bibtex.py references_raw.bib --output references_clean.bib
```
