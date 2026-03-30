# Scientific Writing Workbench

`scientific-writing-workbench` is a reusable Codex skill for literature-grounded scientific drafting, citation quality control, journal adaptation, manuscript review, document ingestion, and response-to-reviewers workflows.

## What it does

- local-first: start from the user's own notes, drafts, data, and PDFs before external lookup
- provider-agnostic: optional research lookup is abstracted by provider, not tied to one commercial service
- integrity-first: no fabricated citations, clear uncertainty labels, and explicit claim-to-evidence tracking
- maintainable: compact `SKILL.md`, detailed references, and lightweight scripts
- claim-aware: can search for the strongest citation for a specific sentence and judge whether the claim is supported as written

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
   - then polished prose
4. For references, ask it to validate citations before finalizing.
5. For revisions, ask for a reviewer comment to manuscript change table.

Example drafting prompt:

```text
Use $scientific-writing-workbench with papers/, notes/study_notes.md, data/results.csv, figure1.png, and refs/references.bib. First build an evidence map and outline for the Introduction and Results. Then write full paragraphs and flag any unsupported claims.
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

## Folder map

- `SKILL.md`: compact workflow router and guardrails
- `agents/openai.yaml`: Codex UI metadata
- `references/`: reusable guidance for drafting, literature review, citation QA, journal adaptation, review, and ingestion
- `scripts/`: small command-line tools for document conversion and bibliography handling
- `assets/`: manuscript, rebuttal, checklist, and optional LaTeX templates

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

## Examples

See `references/examples.md` for realistic prompts covering drafting, bibliography cleanup, and review plus revision response.
