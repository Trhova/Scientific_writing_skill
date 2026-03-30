# Writing Principles

Use this reference when drafting or revising manuscript text.

## Core stance

- Treat the user's files, figures, tables, and bibliography as the primary record.
- Distinguish observed results from interpretation, and interpretation from speculation.
- Prefer precise wording over inflated novelty claims.
- If a statement depends on missing evidence, label it as a hypothesis, expectation, or unresolved point.

## Scientific prose defaults

- Write in complete paragraphs with one main job per paragraph.
- Start paragraphs with context or the key result, then add supporting detail.
- Keep transitions explicit. Readers should not have to infer why one paragraph follows the previous one.
- Use field-appropriate terminology, but avoid avoidable jargon or vague intensifiers such as "very", "dramatically", or "clearly" unless the evidence justifies them.

## Evidence map requirement

Maintain a lightweight evidence map while drafting. For each major claim, track:

- claim id
- claim text
- support type: sourced, inference, or unverified
- supporting references, data files, figures, or tables
- notes on uncertainty or conflicting evidence

This map can be a table, JSON block, or structured notes file. It is a working artifact, not necessarily part of the final manuscript.

## Section writing heuristics

- Title: specific enough to signal scope, but do not overclaim causality or generality.
- Abstract: mirror the paper's actual content; do not introduce claims that are absent from the main text.
- Introduction: narrow from field context to the concrete gap and the manuscript's contribution.
- Methods: favor reproducibility over style; include design choices, software, versions, thresholds, and statistical plans when relevant.
- Results: organize around findings, not around every analysis step.
- Discussion: explain meaning, limitations, alternative explanations, and implications without repeating the full results section.
- Conclusion: short synthesis, not a new discussion.

## Figures and tables

- Use figures or tables when they clarify comparisons, trends, workflows, or quantities that would be awkward in prose alone.
- Legends and captions must be interpretable without forcing the reader to search the main text for basic context.
- Include units, sample sizes, cohort definitions, model names, or statistical tests when those details matter for interpretation.

## Integrity checks before final output

- Every non-trivial claim should point to a citation, figure, table, dataset, or explicit inference label.
- Claims about prior literature should match the cited source category. Do not cite a review as if it were the primary experiment unless that is made explicit.
- Remove placeholder phrasing such as "study X probably shows" or "cite here".
- If the evidence is incomplete, say so instead of smoothing over the gap.

If the user asks for the best source for a claim, or asks whether a sentence is really supported, do not guess. Run the claim through the claim-evidence workflow first and revise the wording if the evidence only supports a weaker statement.
