# Claim Evidence Workflow

Use this reference when the task is to source a sentence, verify a claim, or find the strongest paper supporting or limiting a statement.

## Goal

For a given claim:

1. normalize the wording
2. generate multiple search variants
3. resolve local papers first with `scripts/paper_access.py`
4. search external scholarly sources
5. rank the evidence
6. return a verdict on whether the claim is supported as written

## Claim normalization

Strip prompt wrappers such as:

- "this sentence needs a source"
- "find the best source for this claim"
- "check whether this statement is actually supported"

Then reduce the claim to its scientific core:

- intervention, exposure, or factor
- outcome
- population or context if present
- strength of wording

Examples:

- "Boulardii can cure cancer" contains an intervention, a disease outcome, and an extremely strong verb
- "Creatine improves cognitive performance in sleep deprivation" contains an intervention, outcome, and context

## Search-variant generation

Do not rely on one search string.

Generate a small set of variants that include:

- the original claim
- a keyword-only version
- a softened version if the wording is unusually strong
- targeted variants such as:
  - `systematic review`
  - `randomized trial`
  - `human study`

The point is to find both direct evidence and higher-level evidence summaries.

## Evidence ranking

Rank sources using a combination of:

- evidence type
- directness to the claim
- recency
- whether the paper was available only as metadata, as an abstract, or as full text
- human relevance versus only animal or mechanistic evidence
- whether the paper supports, narrows, or contradicts the claim

Preferred evidence order:

1. systematic review or meta-analysis
2. guideline or consensus statement
3. randomized trial
4. observational human study
5. preclinical animal study
6. in vitro or mechanistic work
7. commentary or editorial

## Verdict rules

Use one of:

- `supported`
- `partially_supported`
- `unsupported_as_stated`
- `contradicted_or_not_supported`
- `evidence_unclear`

### When to use `supported`

- the evidence is directly relevant
- the wording is not stronger than the evidence
- the best source is human-relevant and not obviously contradicted by a stronger source

### When to use `partially_supported`

- there is real support, but the wording needs narrowing
- the best evidence supports only part of the statement
- the evidence applies to a narrower population, context, or endpoint

### When to use `unsupported_as_stated`

- the claim wording is too strong for the evidence
- the closest support is only preclinical, animal, mechanistic, or weakly observational
- the evidence supports an association or limited effect, not the full claim

### When to use `contradicted_or_not_supported`

- the best matching literature directly reports no effect, insufficient evidence, or opposing findings
- the strongest relevant record is more limiting than the best supporting record

### When to use `evidence_unclear`

- too little relevant information was found
- retrieved sources are too indirect or too mixed for a confident judgment

## Handling overstated claims

Prefer rejecting or softening a claim over forcing a weak citation match.

Useful cautious alternatives:

- "may be associated with"
- "has shown effects in preclinical studies"
- "has limited evidence in humans"
- "has been investigated for"
- "has mixed or preliminary evidence"

Avoid upgrading weak evidence into strong causal language such as:

- "cures"
- "prevents"
- "proves"
- "works for"

## Output expectations

The result should identify:

- the best supporting source
- the best limiting or contradicting source if relevant
- the best review source if available
- a verdict on the claim as written
- notes explaining whether the wording should be weakened
- whether the selected sources were metadata-only, abstract-only, or full-text accessible
