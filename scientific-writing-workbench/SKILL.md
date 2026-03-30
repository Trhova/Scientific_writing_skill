---
name: scientific-writing-workbench
description: End-to-end scientific writing skill for evidence-grounded drafting, citation hygiene, journal adaptation, peer review, document ingestion, and reviewer-response support. Use when turning notes, figures, data, PDFs, office files, or manuscript drafts into traceable scientific prose without fabricating citations or overstating evidence.
---

# Scientific Writing Workbench

Use this skill when the task involves planning, drafting, revising, reviewing, or adapting scientific documents. It is designed for a local-first workflow that starts from the user's files and notes, then optionally extends to external evidence lookup through interchangeable providers.

## Non-negotiable rules

- Never fabricate citations, metadata, study results, or journal requirements.
- Mark every major claim as either sourced, inferred, or currently unverified.
- Prefer traceability over smooth prose when the evidence is incomplete.
- Do not default to graphical abstracts, generated figures, or provider-specific services.
- Write final manuscript text in full paragraphs unless the target venue explicitly requires lists or forms.

## Default workflow

1. Stage 1, evidence assembly:
   - Gather local notes, manuscript fragments, figures, tables, and bibliography files first.
   - Ingest PDFs, DOCX, PPTX, XLSX, CSV, TXT, or Markdown when needed. See `references/document_ingestion.md`.
   - Build an evidence map that links each planned claim to one or more references, data sources, or an explicit inference label.
   - Produce a section-by-section outline before drafting prose.
2. Stage 2, prose drafting:
   - Convert the evidence-backed outline into connected paragraphs with clear transitions.
   - Preserve uncertainty labels where the evidence is partial or indirect.
   - Run a claim-citation alignment pass before presenting the manuscript as ready.

## Task routing

- Core drafting and scientific style: `references/writing_principles.md`
- IMRaD and alternative manuscript shapes: `references/imrad_structure.md`
- Reporting checklists and declarations: `references/reporting_guidelines.md`
- Literature discovery and evidence mapping: `references/literature_review_workflow.md`
- Citation collection, enrichment, validation, and deduplication: `references/citation_pipeline.md`
- Peer review and scored evaluation: `references/peer_review_rubric.md`
- Journal or conference adaptation: `references/journal_adaptation.md`
- Response-to-reviewers and revision tracking: `references/revision_response.md`
- File ingestion and conversion behavior: `references/document_ingestion.md`
- Prompt patterns and reusable examples: `references/examples.md`

## Script entry points

- `scripts/convert_documents.py`
  Use to turn PDF, DOCX, PPTX, XLSX, CSV, TXT, or Markdown files into clean text or Markdown for downstream reasoning.
- `scripts/extract_metadata.py`
  Use to pull DOI, PMID, arXiv, URL, title, and year candidates from notes, plain text, or converted documents.
- `scripts/doi_to_bibtex.py`
  Use to resolve DOI, PMID, arXiv, or URL inputs into BibTeX when online metadata lookup is available.
- `scripts/validate_citations.py`
  Use to catch malformed BibTeX, missing required fields, duplicate records, DOI issues, and likely preprint versus published conflicts.
- `scripts/deduplicate_bibtex.py`
  Use to collapse overlapping bibliography entries while preserving the richest trustworthy record.
- `scripts/optional_research_lookup.py`
  Use for provider-agnostic literature lookup. Start with local notes and existing bibliography, then add optional external providers only if needed.

## Operating pattern

When responding to a scientific writing request:

1. Confirm the document type, target audience, and stage of the work.
2. Inspect available files and existing references before searching externally.
3. Build or update an evidence map.
4. Draft an outline before long-form prose.
5. Write paragraphs, not bullets, for the manuscript itself.
6. Validate citations and required declarations before finalizing.
7. If reviewing or revising, produce a comment-to-change mapping instead of vague advice.

## Deliverable defaults

- Manuscripts should include the relevant sections among title, abstract, introduction, methods, results, discussion, conclusion, limitations, cover letter, data availability, ethics, conflicts, acknowledgements, and reviewer response.
- For figures and tables, generate self-contained legends and captions that include units plus sample sizes when available.
- For venue adaptation, explicitly call out changed structure, word-limit pressure points, structured abstract rules, citation style expectations, and missing submission items.

## Quick start

- Start a new manuscript from notes and references using `assets/manuscript_template.md`.
- Start a reviewer rebuttal using `assets/reviewer_response_template.md`.
- Start a journal-fit or submission audit using `assets/journal_checklist_template.md`.
- If LaTeX output is needed, adapt the optional files in `assets/optional_latex/`.
