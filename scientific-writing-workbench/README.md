# Scientific Writing Workbench

`scientific-writing-workbench` is a reusable Codex skill for literature-grounded scientific drafting, citation quality control, journal adaptation, manuscript review, document ingestion, and response-to-reviewers workflows.

## What it does

- local-first: start from the user's own notes, drafts, data, and PDFs before external lookup
- provider-agnostic: optional research lookup is abstracted by provider, not tied to one commercial service
- integrity-first: no fabricated citations, clear uncertainty labels, and explicit claim-to-evidence tracking
- maintainable: compact `SKILL.md`, detailed references, and lightweight scripts
- claim-aware: can search for the strongest citation for a specific sentence and judge whether the claim is supported as written
- paper-aware: can resolve papers from local files, DOI, PMID, arXiv, title, citation strings, and topic queries while tracking metadata, abstract, and full-text access separately
- PDF-ready: can render Markdown manuscripts to PDF through one supported Pandoc + Tectonic pipeline with local figure resolution and vector-first figure handling

## Basic use

Mention the skill directly in your prompt:

```text
Use $scientific-writing-workbench to help with my manuscript.
```

This is the most reliable way to activate it.

## Where to put your files

Put the materials you want the skill to use inside your current project folder. A simple layout is:

```text
project/
  papers/
  notes/
  refs/
  data/
  figures/
  drafts/
```

Typical contents:

- `papers/`: PDFs you want read for context or references
- `notes/`: summaries, pasted excerpts, or claim lists
- `refs/`: BibTeX files
- `data/`: CSV or XLSX tables
- `figures/`: plots and images
- `drafts/`: manuscript drafts or revision files

## Recommended workflow

1. Place your files in the project.
2. Ask the skill to inspect those files first.
3. For drafting, ask for:
   - an evidence map
   - an outline
   - then a section-by-section draft with a mandatory prose edit pass after each section
4. For references, ask it to validate citations before finalizing.
5. For revisions, ask for a reviewer comment to manuscript change table.

When the skill drafts a section, it now uses two internal layers:

1. Scientific drafting:
   - gathers literature
   - organizes claims
   - writes the section for correctness, completeness, and evidence grounding
2. Prose editing:
   - rewrites that section only for flow, tone, and sentence rhythm
   - preserves meaning, citations, paragraph structure, and level of detail

The text shown back to you should already be the post-edited version of that section, not the raw first draft.

Example drafting prompt:

```text
Use $scientific-writing-workbench with papers/, notes/study_notes.md, data/results.csv, figure1.png, and refs/references.bib. First build an evidence map and outline for the Introduction and Results. Then write full paragraphs and flag any unsupported claims.
After drafting each section, run the mandatory prose-editing pass before showing it to me.
```

Example bibliography prompt:

```text
Use $scientific-writing-workbench to clean refs/references_raw.bib and extract missing metadata from notes/source_links.md. Validate duplicates, DOI problems, and likely preprint-versus-published conflicts.
```

Example review prompt:

```text
Use $scientific-writing-workbench to review drafts/manuscript_v2.md with reviewer_comments.md and refs/references.bib. Score it with the rubric and prepare a response-to-reviewers table.
```

Example claim-sourcing prompt:

```text
Use $scientific-writing-workbench to check this statement: "Creatine improves cognitive performance in sleep deprivation." Find the strongest supporting source, strongest limiting source, and give me a verdict on whether it is supported as written.
```

Example paper-access prompt:

```text
Use $scientific-writing-workbench to retrieve the papers behind papers/, DOI 10.1038/exampledoi, and the title "Aryl hydrocarbon receptor and intestinal immunity". Deduplicate them by DOI, PMID, or title-year and tell me which ones are metadata-only, abstract-only, or full-text.
```

## Folder map

- `SKILL.md`: compact workflow router and guardrails
- `agents/openai.yaml`: Codex UI metadata
- `references/`: reusable guidance for drafting, literature review, citation QA, journal adaptation, review, and ingestion
- `scripts/`: small command-line tools for paper access, document conversion, claim evidence lookup, and bibliography handling
- `assets/`: manuscript, rebuttal, checklist, and optional LaTeX templates

## Personal style defaults

You can keep your global writing-style preferences inside:

```text
references/style_preferences.md
```

Edit that file to store habits such as:

- how to refer to figures
- whether you prefer `Fig. 1D` rather than `Figure 1D shows...`
- how restrained or interpretive the prose should sound
- how explicit transitions should be

The skill treats this file as a default style layer during drafting and revision.

Important precedence:

- direct instructions you give in chat win for that turn
- journal or venue requirements win if they conflict with your defaults
- style preferences do not override evidence standards or citation integrity rules

## Installation

Project-local installation:

```bash
mkdir -p .codex/skills
cp -R scientific-writing-workbench .codex/skills/
```

Global installation:

```bash
mkdir -p ~/.codex/skills
cp -R scientific-writing-workbench ~/.codex/skills/
```

If the skill does not show up immediately, restart Codex or reopen the project.

## Validation commands

```bash
python -m py_compile scientific-writing-workbench/scripts/*.py
python /home/trhova/.codex/skills/.system/skill-creator/scripts/quick_validate.py scientific-writing-workbench
```

## Official PDF rendering

The supported manuscript rendering path is:

```bash
python scientific-writing-workbench/scripts/render_pdf.py path/to/draft.md
```

Optional explicit output path:

```bash
python scientific-writing-workbench/scripts/render_pdf.py path/to/draft.md --output path/to/draft.pdf
```

This renderer is part of the skill and is intended to replace one-off Markdown-to-PDF fallbacks.

For reproducible output, run it from the repo-local environment rather than the system Python:

```bash
./.writer-skill-env/bin/python scientific-writing-workbench/scripts/render_pdf.py path/to/draft.md
```

It supports:

- Markdown headings
- inline HTML superscripts such as `<sup>1</sup>`
- bold and italics
- Markdown tables
- figure captions written as bold `Figure X.` paragraphs immediately below an image
- figure caption continuation paragraphs immediately following the bold `Figure X.` line, including panel-style legends such as `**(A)** ...`
- local figures referenced relative to the manuscript directory
- references sections in the manuscript body
- explicit manual page breaks with `\newpage`
- escaped literal Markdown characters inside custom legends, for example `\\*p<0.05`

Figure handling is vector-first:

- if the manuscript references `figure.png` and a same-basename `figure.pdf` exists, the PDF figure is preferred
- otherwise a same-basename `figure.svg` is preferred over raster input
- same-basename SVG figures are converted deterministically to cached PDF for LaTeX embedding
- if no vector sibling exists, the original raster image is used

This keeps labels and line art sharp when vector originals are available while still working with PNG or JPG figures.

The renderer uses the repo-local environment defined in `environment.yml`, together with the Pandoc header at `assets/pandoc_header.tex`.

Pagination rules:

- `\newpage` is the supported manual page-break marker in manuscript Markdown
- section headings reserve space for following text to reduce stranded headings
- figure blocks are detected as an image followed by a bold `Figure X.` legend paragraph and any immediate legend continuation paragraphs
- the renderer prioritizes figure readability over aggressive keep-together shrinking
- figures default to full text width when no smaller width is requested
- long figure blocks may be moved to dedicated figure pages rather than shrinking the image heavily
- figure legend blocks are rendered in the shared manuscript style: bold lead line, bold continuation text, and a horizontal separator after the legend block

Figure authoring rules for stable output:

- write figure blocks as:
  - image line
  - blank line
  - bold `Figure X. ...` legend line
  - optional immediate continuation paragraphs for the rest of the legend
- keep the continuation paragraphs directly attached to that figure block; do not insert unrelated headings or tables between the image and the legend
- if you need literal Markdown characters inside a custom legend, escape them in the source, for example `\\*`, `\\_`, or `\\#`

## Examples

See `references/examples.md` for realistic prompts covering drafting, bibliography cleanup, paper retrieval, and review plus revision response.
