# Examples

These examples demonstrate the expected workflow: evidence first, outline second, scientific draft third, prose-edit pass fourth.

If you want the skill to follow persistent global phrasing habits, edit `references/style_preferences.md`. The examples below assume that file is loaded during drafting and revision.

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
After each section or subsection draft, run the mandatory prose-editing pass before showing it to me.
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

## Example 4: Best citation for a specific claim

Prompt:

```text
Use $scientific-writing-workbench to check this claim: "Creatine improves cognitive performance in sleep deprivation."
Generate search variants, search local files first if relevant, then search the literature.
Return the strongest supporting source, the strongest limiting or contradicting source, the best review source, and a verdict on whether the claim is supported as written.
If the wording is too strong, suggest a safer alternative.
```

## Example 5: Retrieving papers from mixed inputs

Prompt:

```text
Use $scientific-writing-workbench to retrieve the papers behind these inputs before drafting:
- papers/
- DOI 10.1038/s41598-024-54249-9
- PMID 12345678
- the title "Aryl hydrocarbon receptor and intestinal immunity"

Resolve duplicates by DOI, PMID, or title-year.
Tell me which records have metadata only, which have abstracts, and which have full text.
Prefer local full text if the same paper exists both locally and online.
```

## Example 6: Rejecting an overstated claim

Prompt:

```text
Use $scientific-writing-workbench to evaluate this sentence: "Boulardii can cure cancer."
Find the strongest evidence for and against it and tell me whether the statement is supported as written.
If not, explain what the literature actually supports and suggest a more defensible phrasing.
```

## Example 7: Drafting with personal style defaults

Prompt:

```text
Use $scientific-writing-workbench to draft the Introduction from notes/intro_outline.md, papers/, and refs/references.bib.
Follow the global style defaults in references/style_preferences.md.
Make the scientific point first, then attach figure references in parentheses, for example `(Fig. 1D)`.
Do not use openers like "Figure 1D shows..." unless I explicitly ask for that style.
Keep the tone restrained and mechanistic.
After drafting each section, run the mandatory prose-editing pass so I only see the edited version.
```
