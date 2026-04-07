# writer_skill

This repository contains the `scientific-writing-workbench` skill for Codex/ChatGPT.

The skill helps with:

- drafting scientific sections from notes, tables, and figures
- organizing and checking references
- checking whether a sentence is actually supported by the literature
- adapting a manuscript to a journal
- reviewing drafts and planning revisions
- preparing response-to-reviewers documents
- retrieving papers from local files, DOI, PMID, arXiv, titles, and literature search queries

Main skill folder:

- `scientific-writing-workbench/`

## How to install it

If you want the skill only in this project:

```bash
mkdir -p .codex/skills
cp -R scientific-writing-workbench .codex/skills/
```

If you want the skill available in all your Codex projects:

```bash
mkdir -p ~/.codex/skills
cp -R scientific-writing-workbench ~/.codex/skills/
```

After copying it, restart Codex or reload the project if the skill does not appear immediately.

## Recommended local environment

This repo now includes a repo-local Conda environment for the paper and document tooling used by the skill.

It is meant to provide:

- `pdftotext` for fast PDF text extraction
- `mutool` as a second PDF extractor
- `tesseract` for optional OCR
- Python libraries such as `pymupdf`, `pypdf`, `pdfplumber`, `pytesseract`, `beautifulsoup4`, `lxml`, `markdown`, and `cairosvg`

Create or update the environment:

```bash
bash scripts/setup_writer_env.sh
```

Activate it:

```bash
conda activate /home/trhova/writer_skill/.writer-skill-env
```

Check that the important tools are available:

```bash
bash scripts/check_writer_env.sh
```

This environment stays inside the repo at `.writer-skill-env/` and is ignored by git.

## How to use it

The simplest way is to mention the skill by name in your prompt:

```text
Use $scientific-writing-workbench to draft the introduction for my paper from my notes and references.
```

You can also ask in normal language, but naming the skill directly is the most reliable way to make Codex use it.

## Where to put your papers and reference material

Put your files anywhere inside your working project folder. The skill is local-first, so it works best when the papers and notes are already in the same project you have open.

A simple layout that works well is:

```text
my-project/
  papers/
  notes/
  refs/
  data/
  figures/
  drafts/
```

What to place there:

- `papers/`: PDFs of papers you want Codex to read or use as reference material
- `notes/`: your rough notes, summaries, copied quotes, or claim lists
- `refs/`: BibTeX files such as `references.bib`
- `data/`: CSV or XLSX files
- `figures/`: figures, plots, or images already made
- `drafts/`: manuscript drafts in Markdown, TXT, DOCX, or PDF

You do not have to use these exact folder names. They are only a clean starting point.

## What a normal workflow looks like

1. Put your source material in the project folder.
2. Ask Codex to use `$scientific-writing-workbench`.
3. Tell it what you want written, reviewed, or cleaned up.
4. Ask it to start with an evidence map and outline before prose if you are drafting.
5. Ask it to validate citations before you treat the output as final.

Example:

```text
Use $scientific-writing-workbench to draft the Results section from notes/results.md, data/main_results.csv, figure1.png, and refs/references.bib. First make an evidence map and outline. Then write full paragraphs. Check that each major claim is supported by a figure, data file, citation, or clearly marked inference.
```

## Common things you can ask it to do

- Draft an abstract, introduction, methods, results, discussion, conclusion, or cover letter
- Turn bullet notes into full scientific prose
- Build or clean a bibliography from DOIs, PMIDs, URLs, and BibTeX
- Find the strongest paper supporting or limiting a specific claim
- Check for duplicate or suspicious references
- Adapt a paper to a target journal
- Review a draft and score it with a rubric
- Build a response-to-reviewers table

## If you want it to use your papers for references

Tell Codex exactly where the papers are.

Example:

```text
Use $scientific-writing-workbench with the PDFs in papers/ and the notes in notes/lit_notes.md. Build an evidence map for the introduction and use those papers when drafting. Do not invent any citations.
```

If you already have a BibTeX file, mention that too:

```text
Use $scientific-writing-workbench with papers/, notes/project_notes.md, and refs/references.bib. Clean the bibliography and use the validated references while drafting the discussion.
```

If you want it to source or verify a specific sentence:

```text
Use $scientific-writing-workbench to check this claim: "Boulardii can cure cancer." Find the strongest supporting and limiting sources and tell me whether the claim is actually supported as written.
```

If you want it to retrieve and inspect papers first:

```text
Use $scientific-writing-workbench to retrieve papers from papers/, DOI 10.1038/exampledoi, PMID 12345678, and the title "Aryl hydrocarbon receptor and intestinal immunity". Tell me which records have only metadata, which have abstracts, and which have full text before you draft anything.
```

## Validation

Quick local validation commands:

```bash
python -m py_compile scientific-writing-workbench/scripts/*.py
python /home/trhova/.codex/skills/.system/skill-creator/scripts/quick_validate.py scientific-writing-workbench
```

If you want to run the skill scripts with the repo-local environment, activate the env first and then run commands such as:

```bash
python scientific-writing-workbench/scripts/paper_access.py --doi 10.1038/s41598-024-54249-9
python scientific-writing-workbench/scripts/claim_evidence_lookup.py "This sentence needs a source: [Creatine improves cognitive performance in sleep deprivation]"
```

## PDF rendering

This repo includes a Markdown-to-PDF renderer for manuscripts:

```bash
python scientific-writing-workbench/scripts/render_pdf.py thesis_intro/intro_draft.md
```

Optional explicit output path:

```bash
python scientific-writing-workbench/scripts/render_pdf.py thesis_intro/intro_draft.md --output thesis_intro/intro_draft.pdf
```

For stable rerenders that match the established thesis/manuscript output, use the repo-local environment explicitly:

```bash
./.writer-skill-env/bin/python scientific-writing-workbench/scripts/render_pdf.py thesis_intro/intro_draft.md
```

It renders Markdown through `pandoc` + `tectonic` using the shared Pandoc header and the current figure-layout rules.

It preserves:

- inline HTML superscripts
- headings
- tables
- local figures
- references sections

It also prefers vector figure assets when PDF or SVG originals are available and uses deterministic local caching for converted SVG figures.

Figure behavior:

- figure paths stay relative to the manuscript directory
- same-basename `.pdf` figures are preferred over raster inputs
- same-basename `.svg` figures are preferred when no PDF figure is present
- raster images are used only when no vector source is available
- figures are recognized as an image followed by a bold `Figure X.` legend paragraph and immediate legend continuation text
- figures default to full text width unless a smaller width is requested
- the renderer prioritizes large readable figures over aggressive downscaling
- long figure blocks are moved to dedicated figure pages when needed
- figure legends use the shared thesis style: bold legend text with a horizontal separator after the legend block
- escaped literal Markdown characters inside custom legends are supported, for example `\\*p<0.05`

Manual pagination:

- use `\newpage` in the Markdown source when a manuscript section must start on a new page
- heading spacing and widow/orphan penalties are configured in the Pandoc header to reduce weak page breaks

The renderer uses the Pandoc header at:

```text
scientific-writing-workbench/assets/pandoc_header.tex
```
