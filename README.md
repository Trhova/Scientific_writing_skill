# writer_skill

This repository contains the `scientific-writing-workbench` skill for Codex/ChatGPT.

The skill helps with:

- drafting scientific sections from notes, tables, and figures
- organizing and checking references
- adapting a manuscript to a journal
- reviewing drafts and planning revisions
- preparing response-to-reviewers documents

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

## Validation

Quick local validation commands:

```bash
python -m py_compile scientific-writing-workbench/scripts/*.py
python /home/trhova/.codex/skills/.system/skill-creator/scripts/quick_validate.py scientific-writing-workbench
```
