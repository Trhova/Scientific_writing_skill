# Paper Access Workflow

Use this reference when the task starts from a local PDF, uploaded document, DOI, PMID, arXiv ID, title, citation string, topic query, or claim and the skill needs to locate and read scientific papers safely.

## Goal

Treat paper retrieval and paper ingestion as a first-class workflow:

1. resolve the best paper record available
2. retrieve metadata
3. retrieve the abstract when available
4. retrieve full text when available
5. record exactly which level of access was achieved
6. use that access state to decide how confidently the paper can support drafting or claim checking

## Entry points

Start with `scripts/paper_access.py`.

Supported starting points:

- local file paths
- directories containing papers
- DOI
- PMID
- arXiv ID
- title
- citation string
- free-text topic query
- claim text that needs sourcing

## Local-first order

1. inspect local files and uploaded documents first
2. extract identifiers and title candidates from those files
3. enrich local records from external metadata providers if identifiers exist
4. search external sources only when local material is absent, incomplete, or clearly insufficient

Local full text should be preferred over an external abstract-only record for the same paper.

## Access-state rules

Every paper record should carry explicit access status:

- `metadata_only`
  - bibliographic metadata exists
  - no usable abstract or full text was retrieved
- `abstract_only`
  - metadata exists
  - abstract was retrieved
  - full text was unavailable or not extracted
- `full_text`
  - usable full text was retrieved from a local file or open-access external source

Related status fields:

- `metadata_status`: `retrieved`, `missing`, or `failed`
- `abstract_status`: `retrieved`, `unavailable`, or `failed`
- `full_text_status`: `retrieved`, `unavailable`, `extraction_failed`, `ocr_needed`, or `ocr_failed`

Do not describe a paper as "read" unless abstract or full text was actually retrieved.

## Retrieval and ingestion behavior

### Metadata

Use DOI, PMID, arXiv, and title normalization to resolve the best available paper record.

Preferred external metadata sources:

- Europe PMC / PubMed-compatible records for biomedical papers
- OpenAlex for broad scholarly records and open-access hints
- Crossref for DOI metadata enrichment
- arXiv for preprints

### Abstract

If an abstract is available from the provider, store it and label the record as abstract-accessible.

### Full text

External full text is open-access only.

Use direct open-access sources when available. Do not rely on fragile publisher scraping and do not assume access to subscription content.

For local or downloaded PDFs, try layered extraction in this order:

1. `pdftotext`
2. `mutool`
3. `pymupdf`
4. `pypdf`
5. `pdfplumber`

OCR stays off by default. If extraction fails and OCR is not enabled, report `ocr_needed` when OCR would be the next fallback.

## Deduplication

Deduplication is mandatory, not optional.

Primary identity keys:

1. DOI
2. PMID
3. normalized title plus year

When duplicates are merged, preserve the richest trustworthy record:

- prefer local full text over external abstract-only versions
- preserve stronger metadata from external providers when the local title is only a filename
- merge warnings and provenance instead of dropping them

## How the writing workflow should use access state

- `full_text`
  - can support stronger mechanistic, methods, and result wording
- `abstract_only`
  - can support screening and cautious top-level claims
  - should not be treated as if methods and detailed results were fully verified
- `metadata_only`
  - can support bibliography building or literature search orientation
  - should not support statements like "the paper shows" or detailed factual claims

When evidence is only metadata- or abstract-level, the drafting workflow should use cautious language or mark the claim as not fully verified.

## Failure handling

Fail clearly per paper.

Examples:

- metadata retrieved, abstract unavailable, full text unavailable
- metadata retrieved, abstract retrieved, full text extraction failed
- metadata retrieved, abstract unavailable, OCR needed
- metadata lookup failed for this DOI

Do not silently drop a paper just because one provider or extractor failed.
