# Examples

These examples demonstrate the expected workflow: evidence first, outline second, prose third.

## Example 1: Drafting a results section from notes and data

Prompt:

```text
Use $scientific-writing-workbench to draft the Results section for my microbiome manuscript.
Inputs:
- notes/results_notes.md
- tables/differential_abundance.csv
- figures/figure2.png
- references_clean.bib

First build an evidence map and a section outline.
Then write full-paragraph prose for the Results section.
Every major claim must be linked to a citation, data file, figure, table, or marked as inference.
Include a self-contained legend for Figure 2.
```

## Example 2: Building and cleaning a bibliography

Prompt:

```text
Use $scientific-writing-workbench to clean my bibliography for a review article.
Start from notes/source_links.md and references_raw.bib.
Extract missing DOIs, PMIDs, arXiv IDs, and URLs from the notes.
Resolve what you can into BibTeX without inventing missing fields.
Validate the merged bibliography for malformed entries, duplicate records, DOI issues, and likely preprint-vs-published conflicts.
Return a cleaned bibliography plus an issue list for anything still unresolved.
```

## Example 3: Peer review and response to reviewers

Prompt:

```text
Use $scientific-writing-workbench to review my revised manuscript and help prepare a response letter.
Inputs:
- manuscript_v2.md
- reviewer_comments.md
- references_clean.bib

Run both a qualitative review and the 8-dimension rubric.
Then build a reviewer-response table that maps each comment to a response, the manuscript change made, and the changed location.
Flag any comments that require new analysis rather than wording changes.
```
