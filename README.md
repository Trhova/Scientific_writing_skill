# writer_skill

## Documentation TODO

- [ ] Add `Paperclip` as an optional literature-discovery backend in the skill scripts, not just in the documentation
- [x] Document the full local-first workflow from Word or PDF intake to Markdown conversion to final PDF rendering
- [x] Document what each major part of the skill does
- [x] Add a machine-readable repository summary file for capabilities and installation guidance

This repository contains the `scientific-writing-workbench` skill for Codex.

The skill is built for local-first scientific writing. It helps turn papers, notes, figures, tables, bibliographies, and manuscript drafts into evidence-grounded prose without fabricating citations or overstating claims.

## What the skill does

The skill covers five main jobs:

1. **Literature access and evidence assembly**
   - resolves papers from local PDFs, DOI, PMID, arXiv, titles, citation strings, and topic queries
   - keeps track of whether a source is metadata-only, abstract-only, or full text
   - helps build evidence maps before drafting

2. **Document ingestion and Markdown conversion**
   - converts PDF, DOCX, PPTX, XLSX, CSV, TXT, and Markdown into clean text or Markdown
   - uses `MarkItDown` as the default conversion engine for supported formats
   - falls back to format-specific extractors if needed
   - preserves limitations explicitly instead of pretending extraction succeeded

3. **Scientific drafting and revision**
   - drafts sections from notes, figures, tables, and references
   - checks claim-to-citation alignment
   - supports journal adaptation, reviewer response drafting, and revision planning
   - enforces a second-pass prose cleanup after drafting each section

4. **Citation and bibliography hygiene**
   - extracts DOI, PMID, arXiv, URL, title, and year candidates from raw notes or converted text
   - resolves BibTeX from identifiers when metadata is available
   - validates bibliography fields and DOI quality
   - deduplicates overlapping references

5. **Final Markdown-to-PDF rendering**
   - renders Markdown manuscripts to PDF through the shared local Pandoc/Tectonic pipeline
   - supports headings, superscripts, figures, tables, references, local figure assets, page breaks, and thesis/manuscript-style figure legends
   - prefers vector figure assets when PDF or SVG originals are available

## Core design principles

- local files first
- no fabricated citations or unsupported claims
- explicit uncertainty and access-state tracking
- Markdown as the working manuscript format
- deterministic local rendering for stable PDF output

## Main skill folder

- `scientific-writing-workbench/`

Inside that folder, the main moving parts are:

- `SKILL.md` — skill behavior and routing rules
- `references/` — writing policy, literature lookup, claim support, ingestion, review, and adaptation workflows
- `scripts/` — local entry points for conversion, retrieval, citation checks, and PDF rendering
- `assets/` — templates and shared render assets

## Main scripts

Important entry points in `scientific-writing-workbench/scripts/`:

- `convert_documents.py`
  - converts external files into clean Markdown or text
  - uses MarkItDown first where supported
- `paper_access.py`
  - resolves papers from local files and identifiers
  - normalizes paper records and access state
- `extract_metadata.py`
  - extracts candidate identifiers and metadata from messy text
- `doi_to_bibtex.py`
  - resolves DOI, PMID, arXiv, or URL into BibTeX when available
- `validate_citations.py`
  - checks bibliography quality
- `deduplicate_bibtex.py`
  - removes duplicate or overlapping BibTeX records
- `optional_research_lookup.py`
  - provider-agnostic external literature lookup
- `claim_evidence_lookup.py`
  - finds the strongest source for a specific claim
- `render_pdf.py`
  - official Markdown-to-PDF renderer for final manuscript output

## Installation

### Install the skill into Codex

Project-local install:

```bash
mkdir -p .codex/skills
cp -R scientific-writing-workbench .codex/skills/
```

Global install:

```bash
mkdir -p ~/.codex/skills
cp -R scientific-writing-workbench ~/.codex/skills/
```

Restart Codex or reload the project if the skill does not appear immediately.

## Recommended local environment

This repo includes a repo-local environment for the paper and document tooling used by the skill.

Create or update it:

```bash
bash scripts/setup_writer_env.sh
```

Activate it:

```bash
conda activate /home/trhova/writer_skill/.writer-skill-env
```

Check it:

```bash
bash scripts/check_writer_env.sh
```

The environment is intended to provide:

- `pandoc`
- `tectonic`
- `pdftotext`
- `mutool`
- `tesseract` for optional OCR
- Python packages such as `markitdown`, `pymupdf`, `pypdf`, `pdfplumber`, `beautifulsoup4`, `lxml`, `markdown`, and `cairosvg`

## End-to-end workflow: Word to Markdown to PDF

The most important practical workflow in this repo is:

1. **Drop source material into intake**
   - place DOCX, PDF, figures, tables, notes, and bibliography inputs in a clean project folder
   - for repeated writing cycles, use dedicated intake folders instead of overwriting working Markdown directly
2. **Convert external documents into Markdown or text**
   - use `scientific-writing-workbench/scripts/convert_documents.py`
   - for supported formats, the skill uses `MarkItDown` first
   - if conversion is incomplete, the skill falls back and records the limitation
3. **Resolve papers and references**
   - use local PDFs, DOI, PMID, arXiv, title, or citation strings
   - normalize access state before drafting
   - validate and clean BibTeX before relying on it
4. **Draft or revise the working Markdown**
   - edit manuscript content in Markdown, not in the intake DOCX/PDF
   - use the skill to create an evidence map and outline before long-form drafting
   - keep figure assets separate from the manuscript source rather than embedding them into office documents
5. **Render the final PDF locally**
   - use `scientific-writing-workbench/scripts/render_pdf.py` for final manuscript PDFs
   - keep figure paths relative to the manuscript
   - prefer vector figures when available
6. **Repeat the cycle cleanly**
   - if a manuscript changes upstream, drop the new DOCX/PDF into `intake/`
   - regenerate or update Markdown
   - keep `source/` as the editable truth and `output/` as generated artifacts

In short: **intake -> convert -> validate sources -> edit Markdown -> render PDF**.

## How the skill works in practice

The expected operating pattern is:

1. gather local files first
2. resolve or ingest papers and supporting documents
3. build an evidence map or section outline
4. draft in Markdown
5. run citation checks
6. render the manuscript to PDF

The skill is strongest when the working project is organized clearly and the relevant files live in the same repo or folder tree.

## Recommended project structure

A good default structure is the one now used in `thesis_intro/`: explicit intake folders, notes, references, source Markdown, generated outputs, and an archive area.

Suggested layout:

```text
my-writing-project/
  intake/
    chapter_1_intro/
      manuscript_md/
      figures/
    chapter_2_paper/
      manuscript_pdf/
      figure_drop/
    chapter_3_paper/
      manuscript_docx/
      figure_drop/
      tables/
  notes/
    outlines/
    section_notes/
    citation_maps/
  refs/
    references.bib
    source_papers/
  data/
  figures/
  manuscript/
    source/
      frontmatter/
      chapters/
      generated/
    output/
    scripts/
    style/
  archive/
```

What each area is for:

- `intake/`
  - source-of-truth drop zone for new DOCX, PDF, figures, and tables
  - good for repeated manuscript refresh cycles
- `notes/`
  - rough notes, planning files, claim lists, reviewer notes, section maps
- `refs/`
  - BibTeX plus local reference PDFs if you want them separate from intake
- `data/`
  - CSV, TSV, XLSX, processed outputs, and analysis exports used in writing
- `figures/`
  - stable figure assets not tied to one intake cycle
- `manuscript/source/`
  - actual working Markdown that gets edited and rendered
- `manuscript/output/`
  - generated PDFs and merged Markdown outputs
- `manuscript/scripts/`
  - project-specific import/build helpers
- `archive/`
  - old inputs, obsolete exports, temporary planning files, and legacy material you do not want in the active build path

For a thesis-like project, a more concrete chapter intake structure works well:

```text
thesis_intro/
  intake/
    chapter_1_intro/
      figures/
    chapter_2_intratumoral_iaa/
      manuscript_pdf/
    chapter_3_boulardii/
      manuscript_docx/
      figure_drop/
      table_3_MAGs/
    chapter_4_acp/
      manuscript_pdf/
  thesis/
    source/
    output/
    scripts/
    style/
  notes/
  refs/
  archive/
```

This structure makes repeated cycles practical:
- replace the source manuscript or figures in `intake/`
- regenerate Markdown if needed
- edit the Markdown in `source/`
- render PDFs into `output/`
- move obsolete clutter to `archive/`

## MarkItDown integration

Markdown conversion in this skill is now MarkItDown-first.

That means:

- supported office and document formats are converted through `MarkItDown` before legacy extractors are used
- this is a local package/tool workflow, not an MCP server workflow
- if MarkItDown cannot convert something cleanly, the skill falls back and records the limitation

Typical conversion command:

```bash
python scientific-writing-workbench/scripts/convert_documents.py path/to/file.docx
```

## Optional external literature discovery backends

The skill is local-first, but broad literature discovery can be improved with external tools.

### Paperclip

`Paperclip` is useful for exploratory literature search when you need to search broadly, grep across large paper sets, or iteratively narrow a corpus before reading papers in detail.

Based on GXL's current documentation, the basic setup is:

```bash
curl -fsSL https://paperclip.gxl.ai/install.sh | bash
paperclip login
paperclip config
```

Useful capabilities described by GXL include:

- `paperclip search`
- `paperclip grep`
- `paperclip map`
- `paperclip ask-image`
- `paperclip sql`
- stateful result reuse via `--from`

Recommended role of Paperclip in this skill:

- use it for broad discovery and narrowing candidate papers
- then pull the relevant papers back into the skill's normal evidence workflow
- still treat `paper_access.py`, local PDFs, and citation validation as the grounded source-of-truth layer for actual drafting

In other words, Paperclip is best treated as an optional search/discovery backend, not as a replacement for the skill's evidence tracking and citation hygiene.

### MarkItDown is not an MCP

There has been some confusion around this in the project history. In this repo:

- `MarkItDown` is used as a local conversion library/CLI
- it is not treated as an MCP server
- the skill uses it through local scripts

## Prompting Codex to use the skill

The most reliable way is to name the skill explicitly.

Examples:

```text
Use $scientific-writing-workbench to draft the introduction from notes/background.md, refs/references.bib, and the PDFs in refs/source_papers/.
```

```text
Use $scientific-writing-workbench to convert the DOCX in intake/chapter_3_paper/manuscript_docx/, extract the figures, and prepare a Markdown chapter draft without inventing citations.
```

```text
Use $scientific-writing-workbench to check whether this claim is actually supported and find the strongest citation.
```

```text
Use $scientific-writing-workbench and Paperclip for broad literature discovery, then validate the final sources locally before drafting.
```

## Typical workflows

### 1. Draft from notes and references

```text
Use $scientific-writing-workbench to draft the introduction from notes/intro_notes.md, refs/references.bib, and the PDFs in refs/source_papers/. First build an evidence map and outline. Then write full paragraphs. Do not invent citations.
```

### 2. Reconvert a manuscript from DOCX to Markdown

```text
Use $scientific-writing-workbench to convert intake/chapter_3_paper/manuscript_docx/paper.docx into Markdown, keep figures separate, and prepare it for PDF rendering.
```

### 3. Check claim support

```text
Use $scientific-writing-workbench to check this claim and find the best supporting and limiting sources.
```

### 4. Render final PDF

```bash
./.writer-skill-env/bin/python scientific-writing-workbench/scripts/render_pdf.py path/to/draft.md
```

## PDF rendering behavior

The renderer:

- supports headings, tables, references, and figure captions
- keeps figure paths relative to the manuscript
- prefers same-basename `.pdf` or `.svg` figure assets over raster inputs
- uses local raster images when vector versions are unavailable
- supports manual page breaks with `\newpage`
- uses the shared Pandoc header in `scientific-writing-workbench/assets/pandoc_header.tex`

Figure handling rules include:

- figures are recognized as an image followed by a bold `Figure X.` legend paragraph and immediate continuation text
- figures default to full text width unless overridden
- long figure blocks may move to dedicated figure pages
- legend styling follows the shared manuscript/thesis rules

## Validation

Quick validation commands:

```bash
python -m py_compile scientific-writing-workbench/scripts/*.py
python /home/trhova/.codex/skills/.system/skill-creator/scripts/quick_validate.py scientific-writing-workbench
```

## Scope of this repository

This repository is the skill plus a live working environment used to develop and test it. That means it includes:

- the reusable `scientific-writing-workbench` skill
- local helper scripts and environment setup
- example writing projects such as the `thesis_intro/` workflow

The README is intentionally broader than a bare skill README because the repository is used both as:

- the source repo for the skill itself
- a reference implementation of how to organize a scientific writing project around intake, Markdown conversion, evidence mapping, and stable PDF rendering
