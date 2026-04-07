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
   - Resolve and ingest papers from local files, uploaded documents, DOI, PMID, arXiv, title, citation strings, or topic queries. See `references/paper_access_workflow.md`.
   - Ingest PDFs, DOCX, PPTX, XLSX, CSV, TXT, or Markdown when needed. See `references/document_ingestion.md`.
   - Build an evidence map that links each planned claim to one or more references, data sources, or an explicit inference label.
   - Produce a section-by-section outline before drafting prose.
2. Stage 2, scientific drafting:
   - Load both `references/writing_principles.md` and `references/style_preferences.md` before drafting.
   - Convert the evidence-backed outline into connected paragraphs with clear transitions.
   - Preserve uncertainty labels where the evidence is partial or indirect.
   - Run a claim-citation alignment pass before moving to prose refinement.
3. Stage 3, mandatory prose editing:
   - After each drafted section or subsection, run a second-pass language edit before showing any text to the user.
   - Rewrite only for style, flow, tone, and sentence rhythm.
   - Preserve scientific meaning, citations, DOI placement, paragraph structure, and level of detail.
   - Remove awkward LLM-style phrasing, choppy transitions, dramatic standalone transition sentences, and meta-commentary that only announces a point.
   - Return only the post-edited version of that section or subsection.

## Section drafting loop

When writing any manuscript section or subsection, use this loop and do not skip steps:

1. Gather section-specific evidence.
2. Map each planned claim to a citation, figure, data source, or explicit inference label.
3. Draft the section for scientific correctness, mechanistic clarity, and completeness.
4. Run the mandatory prose-editing pass on that drafted section.
5. Return only the edited section to the user.
6. Repeat for the next section or subsection.

The prose-editing pass is required after each section or subsection draft. Do not wait until the full document is finished.

## Task routing

- Core drafting and scientific style: `references/writing_principles.md`
- User-specific drafting and phrasing defaults: `references/style_preferences.md`
- IMRaD and alternative manuscript shapes: `references/imrad_structure.md`
- Reporting checklists and declarations: `references/reporting_guidelines.md`
- Literature discovery and evidence mapping: `references/literature_review_workflow.md`
- Paper retrieval, full-text access, and access-state rules: `references/paper_access_workflow.md`
- Claim-specific sourcing and claim support checks: `references/claim_evidence_workflow.md`
- Citation collection, enrichment, validation, and deduplication: `references/citation_pipeline.md`
- Peer review and scored evaluation: `references/peer_review_rubric.md`
- Journal or conference adaptation: `references/journal_adaptation.md`
- Response-to-reviewers and revision tracking: `references/revision_response.md`
- File ingestion and conversion behavior: `references/document_ingestion.md`
- Prompt patterns and reusable examples: `references/examples.md`

## Script entry points

- `scripts/convert_documents.py`
  Use to turn PDF, DOCX, PPTX, XLSX, CSV, TXT, or Markdown files into clean text or Markdown for downstream reasoning.
- `scripts/paper_access.py`
  Use as the main entry point for resolving papers from local files, DOI, PMID, arXiv, title, citation strings, queries, or claims. It returns normalized paper records with explicit metadata, abstract, and full-text access states.
- `scripts/extract_metadata.py`
  Use to pull DOI, PMID, arXiv, URL, title, and year candidates from notes, plain text, or converted documents.
- `scripts/doi_to_bibtex.py`
  Use to resolve DOI, PMID, arXiv, or URL inputs into BibTeX when online metadata lookup is available.
- `scripts/validate_citations.py`
  Use to catch malformed BibTeX, missing required fields, duplicate records, DOI issues, and likely preprint versus published conflicts.
- `scripts/deduplicate_bibtex.py`
  Use to collapse overlapping bibliography entries while preserving the richest trustworthy record.
- `scripts/optional_research_lookup.py`
  Use for provider-agnostic literature lookup. Start with local notes and existing bibliography, then add optional external providers only if needed. It now returns normalized paper records rather than loose metadata hits.
- `scripts/claim_evidence_lookup.py`
  Use when the user wants the strongest citation for a specific claim, wants a sentence sourced, or asks whether a statement is actually supported by the literature. It ranks paper records while respecting whether the evidence is metadata-only, abstract-only, or full-text.
- `scripts/render_pdf.py`
  Use as the official manuscript PDF renderer for Markdown drafts. It supports headings, inline HTML superscripts such as `<sup>1</sup>`, tables, figure captions, local figures, references, and manual `\newpage` breaks, while compiling through Pandoc plus Tectonic and preferring vector figure assets when PDF or SVG originals are available. The supported figure path is an image followed by a bold `Figure X.` legend line plus immediate continuation paragraphs; those legend blocks are rendered through the shared LaTeX header with large figure sizing, full bold legend text, and a horizontal separator after the legend block.

## Operating pattern

When responding to a scientific writing request:

1. Confirm the document type, target audience, and stage of the work.
2. Inspect available files and existing references before searching externally.
3. Use `scripts/paper_access.py` whenever paper retrieval or ingestion quality matters.
4. Build or update an evidence map.
5. Draft an outline before long-form prose.
6. Load any user-specific style defaults from `references/style_preferences.md`, then write paragraphs, not bullets, for the manuscript itself.
7. Immediately after drafting each section or subsection, run the mandatory prose-editing pass and return only the edited version.
8. Validate citations and required declarations before finalizing.
9. If reviewing or revising, produce a comment-to-change mapping instead of vague advice.
10. When the user needs a final manuscript PDF, use `scripts/render_pdf.py` from the repo-local skill environment rather than ad hoc conversion commands or temporary scripts.

When `references/style_preferences.md` is present:

- treat it as the default style layer for phrasing, transitions, figure references, and rhetorical habits
- do not let it override scientific accuracy, evidence standards, or access-state rules
- let direct user instructions in chat override the style file for that turn
- let venue or journal requirements override the style file when they conflict

During the mandatory prose-editing pass:

- improve sentence flow and transition quality without changing scientific meaning
- merge short, disconnected sentences when a smoother structure preserves the same detail
- remove dramatic or fragment-like transition sentences
- remove meta-writing phrases such as `The important point is...`, `Together, these studies...`, or `At first glance...` when they do not add biological content
- keep a formal PhD-thesis tone
- preserve citations, DOI placement, claim strength, factual nuance, and paragraph logic
- do not add or remove literature
- do not compress the writing aggressively
- do not replace precise biological content with smoother but vaguer wording

Bad language patterns that the prose-editing pass should catch and rewrite:

- short standalone transition sentences such as `Time adds another layer to that variation.`
- meta-writing phrases such as `This matters because...`, `Another factor is...`, `The important point is...`, `Together, these studies...`, or `At first glance...`
- empty academic filler such as `plays a key role`, `is increasingly recognized`, `well characterized`, `provides a useful framework`, or `tractable set of molecules`

For requests such as:

- "find a source for this claim"
- "what is the best citation for this sentence?"
- "check whether this statement is actually supported"
- "source this paragraph"
- "find the strongest paper supporting or contradicting this"

start with `scripts/claim_evidence_lookup.py`, then use the returned verdict to decide whether to cite, soften, or reject the claim as written.

For requests such as:

- "find this DOI and read the paper"
- "use these uploaded PDFs when drafting"
- "search the literature for papers on this topic"
- "tell me whether you actually had full text or only an abstract"

start with `scripts/paper_access.py` so the workflow has an explicit access state before drafting or claim evaluation.

## Deliverable defaults

- Manuscripts should include the relevant sections among title, abstract, introduction, methods, results, discussion, conclusion, limitations, cover letter, data availability, ethics, conflicts, acknowledgements, and reviewer response.
- For figures and tables, generate self-contained legends and captions that include units plus sample sizes when available.
- For venue adaptation, explicitly call out changed structure, word-limit pressure points, structured abstract rules, citation style expectations, and missing submission items.

## Quick start

- Start a new manuscript from notes and references using `assets/manuscript_template.md`.
- Start a reviewer rebuttal using `assets/reviewer_response_template.md`.
- Start a journal-fit or submission audit using `assets/journal_checklist_template.md`.
- If LaTeX output is needed, adapt the optional files in `assets/optional_latex/`.
- For a final manuscript PDF, run `python scientific-writing-workbench/scripts/render_pdf.py path/to/draft.md`.
- For reproducible rerenders that match the established thesis/manuscript output, prefer the repo-local environment, for example `./.writer-skill-env/bin/python scientific-writing-workbench/scripts/render_pdf.py path/to/draft.md`.
