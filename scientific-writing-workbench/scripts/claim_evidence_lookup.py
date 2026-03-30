#!/usr/bin/env python3
"""Find and rank evidence for a natural-language scientific claim."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from typing import Iterable

from paper_access import DEFAULT_PROVIDERS, collect_paper_records
from scholarly_lookup_common import normalize_title, normalize_whitespace

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "best",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "sentence",
    "source",
    "statement",
    "that",
    "the",
    "this",
    "to",
    "whether",
    "with",
}

STRONG_CLAIM_TERMS = {"cure", "cures", "prevent", "prevents", "eliminate", "eliminates", "prove", "proves"}
SUPPORT_TERMS = {
    "benefit",
    "beneficial",
    "effective",
    "efficacy",
    "enhance",
    "improve",
    "improved",
    "improvement",
    "reduced",
    "reduces",
    "reduction",
    "associated with",
    "ameliorate",
}
LIMITING_TERMS = {
    "adjunct",
    "association",
    "limited",
    "may",
    "mechanistic",
    "pilot",
    "preclinical",
    "trend",
}
CONTRADICT_TERMS = {
    "did not",
    "failed",
    "inconclusive",
    "insufficient",
    "lack of evidence",
    "mixed results",
    "no effect",
    "no significant",
    "not associated",
    "unclear",
}
HUMAN_HINTS = {"patients", "participants", "human", "humans", "adults", "children", "clinical", "trial"}
ANIMAL_HINTS = {"mouse", "mice", "murine", "rat", "rats", "animal", "animals"}
MECHANISTIC_HINTS = {"cell", "cells", "in vitro", "cell line", "mechanistic"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find the strongest evidence supporting or limiting a scientific claim.")
    parser.add_argument("claim", help="Natural-language scientific claim.")
    parser.add_argument("--paths", nargs="*", default=[], help="Local files or directories to search first.")
    parser.add_argument("--limit-per-provider", type=int, default=4, help="Maximum candidates fetched per provider per variant.")
    parser.add_argument("--enable-ocr", action="store_true", help="Enable OCR fallback for local PDFs.")
    parser.add_argument("--json-indent", type=int, default=2, help="Indentation for JSON output.")
    return parser.parse_args()


def strip_prompt_wrappers(claim: str) -> str:
    text = normalize_whitespace(claim)
    patterns = [
        r"^(?:this sentence needs a source:)\s*",
        r"^(?:find the best source for this claim:)\s*",
        r"^(?:what is the best citation for this sentence\??)\s*",
        r"^(?:check whether this statement is actually supported by the literature:)\s*",
        r"^(?:check whether this statement is actually supported:)\s*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    bracket_match = re.search(r"\[(.+)\]", text)
    if bracket_match:
        text = bracket_match.group(1)
    return text.strip(" \"'")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]+", text)]


def keyword_tokens(text: str) -> list[str]:
    return [token for token in tokenize(text) if token not in STOPWORDS and len(token) > 2]


def detect_claim_strength(tokens: Iterable[str]) -> str:
    token_set = set(tokens)
    if token_set & STRONG_CLAIM_TERMS:
        return "strong"
    if {"improves", "improve", "reduces", "reduce", "treats", "treat"} & token_set:
        return "moderate"
    if {"associated", "may", "linked"} & token_set:
        return "cautious"
    return "moderate"


def claim_parts(claim: str) -> tuple[str, str, str]:
    patterns = [
        r"^(?P<subject>.+?)\s+(?P<verb>can cure|cures|can prevent|prevents|improves|improve|reduces|reduce|treats|treat|is associated with|is linked to)\s+(?P<object>.+)$",
        r"^(?P<subject>.+?)\s+(?P<verb>causes|cause|increases|increase|decreases|decrease)\s+(?P<object>.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, claim, flags=re.IGNORECASE)
        if match:
            return (
                normalize_whitespace(match.group("subject")),
                normalize_whitespace(match.group("verb").lower()),
                normalize_whitespace(match.group("object")),
            )
    return claim, "", ""


def action_family(claim: str) -> str:
    _subject, verb, _obj = claim_parts(claim.lower())
    if "cure" in verb:
        return "cure"
    if "prevent" in verb:
        return "prevent"
    if "improve" in verb or "reduce" in verb or "increase" in verb or "decrease" in verb:
        return "improve"
    if "treat" in verb:
        return "treat"
    if "associated with" in verb or "linked to" in verb:
        return "association"
    if "cause" in verb:
        return "cause"
    return "general"


def action_support_terms(family: str) -> set[str]:
    terms = {
        "cure": {"cure", "curative", "remission", "survival", "tumor regression", "anticancer", "anti-cancer"},
        "prevent": {"prevent", "prevention", "reduced risk", "protective"},
        "improve": {"improve", "improves", "improved", "improvement", "enhance", "enhances", "enhanced", "benefit", "beneficial"},
        "treat": {"treat", "treats", "treated", "treatment", "therapeutic", "therapy", "efficacy"},
        "association": {"associated with", "linked to", "correlated with"},
        "cause": {"cause", "causes", "caused", "increase risk", "induces", "promotes"},
        "general": SUPPORT_TERMS,
    }
    return terms[family]


def contains_term(text: str, term: str) -> bool:
    if " " in term or "-" in term:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(contains_term(text, term) for term in terms)


def soften_claim_text(claim: str) -> str:
    softened = claim
    replacements = {
        r"\bcure(s)?\b": "treat",
        r"\bprevent(s)?\b": "reduce risk of",
        r"\bprove(s|d)?\b": "suggest",
        r"\bcauses?\b": "is associated with",
    }
    for pattern, replacement in replacements.items():
        softened = re.sub(pattern, replacement, softened, flags=re.IGNORECASE)
    return normalize_whitespace(softened)


def generate_search_variants(claim: str) -> list[str]:
    normalized = strip_prompt_wrappers(claim)
    subject, _verb, obj = claim_parts(normalized)
    keywords = keyword_tokens(normalized)
    variants = [normalized]
    if keywords:
        variants.append(" ".join(keywords[:8]))
    softened = soften_claim_text(normalized)
    if softened != normalized:
        variants.append(softened)
    if subject and obj:
        variants.append(f"{subject} {obj}")
        variants.append(f"{subject} {obj} systematic review")
        variants.append(f"{subject} {obj} randomized trial")
        variants.append(f"{subject} {obj} human study")
    else:
        variants.append(f"{normalized} systematic review")
        variants.append(f"{normalized} randomized trial")
    unique: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        variant = normalize_whitespace(variant)
        key = variant.lower()
        if variant and key not in seen:
            seen.add(key)
            unique.append(variant)
    return unique[:6]


def classify_evidence_type(record: dict[str, object]) -> str:
    text = " ".join(
        [
            str(record.get("title", "")),
            str(record.get("abstract", "")),
            str(record.get("full_text", ""))[:4000],
            str(record.get("publication_type_raw", "")),
            str(record.get("journal", "")),
        ]
    ).lower()
    if "meta-analysis" in text or "systematic review" in text:
        return "systematic review / meta-analysis"
    if "guideline" in text or "consensus" in text or "position stand" in text:
        return "guideline / consensus"
    if "review-article" in text or re.search(r"\breview\b", text):
        return "review / commentary / editorial"
    if ("placebo" in text or "subjects were" in text or "participants were" in text) and not contains_any(
        text, ANIMAL_HINTS | MECHANISTIC_HINTS
    ):
        return "randomized trial"
    if "randomized" in text or "randomised" in text or "clinical trial" in text or "double-blind" in text:
        return "randomized trial"
    if contains_any(text, HUMAN_HINTS) and not contains_any(text, ANIMAL_HINTS | MECHANISTIC_HINTS):
        return "observational human study"
    if any(term in text for term in ("cohort", "case-control", "cross-sectional", "prospective", "retrospective", "registry")):
        return "observational human study"
    if contains_any(text, ANIMAL_HINTS):
        return "preclinical animal study"
    if contains_any(text, MECHANISTIC_HINTS):
        return "in vitro / mechanistic paper"
    if "review" in text or "commentary" in text or "editorial" in text or "perspective" in text:
        return "review / commentary / editorial"
    if "patients" in text or "participants" in text or "clinical" in text:
        return "observational human study"
    return "unclear"


def directness_score(claim: str, record: dict[str, object]) -> float:
    claim_terms = set(keyword_tokens(claim))
    if not claim_terms:
        return 0.0
    text = " ".join([str(record.get("title", "")), str(record.get("abstract", "")), str(record.get("full_text", ""))[:3000]]).lower()
    text_terms = set(keyword_tokens(text))
    overlap = claim_terms & text_terms
    score = len(overlap) / max(len(claim_terms), 1)
    if normalize_title(claim) and normalize_title(claim) in normalize_title(text):
        score += 0.25
    return min(score, 1.0)


def evidence_weight(evidence_type: str) -> float:
    weights = {
        "systematic review / meta-analysis": 6.0,
        "guideline / consensus": 5.5,
        "randomized trial": 5.0,
        "observational human study": 3.8,
        "preclinical animal study": 2.2,
        "in vitro / mechanistic paper": 1.5,
        "review / commentary / editorial": 2.0,
        "unclear": 1.0,
    }
    return weights.get(evidence_type, 1.0)


def recency_weight(year: int | None) -> float:
    if not year:
        return 0.0
    age = max(0, 2026 - int(year))
    if age <= 2:
        return 1.5
    if age <= 5:
        return 1.0
    if age <= 10:
        return 0.6
    return 0.2


def access_weight(record: dict[str, object]) -> float:
    return {
        "full_text": 2.0,
        "abstract_only": 0.8,
        "metadata_only": -1.0,
    }.get(str(record.get("access_level", "")), 0.0)


def relation_to_claim(claim: str, claim_strength: str, record: dict[str, object], evidence_type: str) -> str:
    text = " ".join([str(record.get("title", "")), str(record.get("abstract", "")), str(record.get("full_text", ""))[:3000]]).lower()
    claim_terms = set(keyword_tokens(claim))
    family = action_family(claim)
    directness = directness_score(claim, record)
    if not claim_terms:
        return "unclear"
    if contains_any(text, CONTRADICT_TERMS):
        if directness >= 0.75:
            return "contradicting"
        if directness >= 0.35:
            return "limiting"
        return "unclear"
    if family == "cure":
        if contains_any(text, {"mucositis", "adjunct", "supportive care", "quality of life", "association"}):
            return "limiting"
        if not contains_any(text, action_support_terms(family)):
            return "limiting"
    if family in {"prevent", "treat"} and not contains_any(text, action_support_terms(family)):
        if contains_any(text, {"associated with", "may", "limited", "pilot", "preclinical"}):
            return "limiting"
    if claim_strength == "strong" and evidence_type in {"preclinical animal study", "in vitro / mechanistic paper"}:
        return "limiting"
    if claim_strength == "strong" and contains_any(text, LIMITING_TERMS):
        return "limiting"
    positive_hit = contains_any(text, action_support_terms(family))
    if positive_hit and directness >= 0.45:
        return "supporting"
    if directness >= 0.35:
        return "limiting"
    return "unclear"


def human_evidence_flag(record: dict[str, object], evidence_type: str) -> bool:
    if evidence_type in {"systematic review / meta-analysis", "guideline / consensus", "randomized trial", "observational human study"}:
        return True
    text = " ".join([str(record.get("title", "")), str(record.get("abstract", "")), str(record.get("full_text", ""))[:2000]]).lower()
    return contains_any(text, HUMAN_HINTS) and not contains_any(text, ANIMAL_HINTS)


def access_note(record: dict[str, object]) -> str:
    level = str(record.get("access_level", "metadata_only"))
    if level == "full_text":
        return "full text available"
    if level == "abstract_only":
        return "abstract available, full text unavailable"
    return "metadata only, paper not read in full"


def rank_record(claim: str, claim_strength: str, record: dict[str, object]) -> dict[str, object]:
    evidence_type = classify_evidence_type(record)
    relation = relation_to_claim(claim, claim_strength, record, evidence_type)
    directness = directness_score(claim, record)
    human_flag = human_evidence_flag(record, evidence_type)
    score = evidence_weight(evidence_type) + (directness * 4.0) + recency_weight(record.get("year"))
    score += access_weight(record)
    if human_flag:
        score += 1.2
    if relation == "supporting":
        score += 1.5
    elif relation == "contradicting":
        score += 1.2
    elif relation == "limiting":
        score += 0.5
    why_selected = (
        f"{evidence_type}; directness {directness:.2f}; "
        f"{'human-relevant' if human_flag else 'not clearly human-clinical'}; "
        f"{access_note(record)}; classified as {relation}"
    )
    enriched = dict(record)
    enriched.update(
        {
            "evidence_type": evidence_type,
            "relation_to_claim": relation,
            "human_relevance": human_flag,
            "ranking_score": round(score, 3),
            "why_selected": why_selected,
        }
    )
    return enriched


def pick_best(records: list[dict[str, object]], relation: str) -> dict[str, object] | None:
    filtered = [record for record in records if record.get("relation_to_claim") == relation]
    if not filtered:
        return None
    return max(filtered, key=lambda item: item["ranking_score"])


def pick_best_review(records: list[dict[str, object]]) -> dict[str, object] | None:
    reviews = [
        record
        for record in records
        if record.get("evidence_type") in {"systematic review / meta-analysis", "guideline / consensus", "review / commentary / editorial"}
    ]
    if not reviews:
        return None
    return max(reviews, key=lambda item: item["ranking_score"])


def verdict_for(claim_strength: str, supporting: dict[str, object] | None, limiting: dict[str, object] | None) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    if not supporting and not limiting:
        return "evidence_unclear", "low", ["No sufficiently relevant records were found."]

    if limiting and (not supporting or float(limiting["ranking_score"]) >= float(supporting["ranking_score"]) + 1.0):
        notes.append("The best matching evidence does not support the claim as written.")
        return "contradicted_or_not_supported", "medium", notes

    if supporting:
        evidence_type = str(supporting.get("evidence_type", ""))
        human_flag = bool(supporting.get("human_relevance"))
        access_level = str(supporting.get("access_level", "metadata_only"))
        if access_level == "metadata_only":
            notes.append("The top match was identified from metadata only and was not read in abstract or full text.")
            return "evidence_unclear", "low", notes
        if claim_strength == "strong" and not human_flag:
            notes.append("Closest support is not human clinical evidence.")
            return "unsupported_as_stated", "high", notes
        if claim_strength == "strong" and evidence_type not in {
            "systematic review / meta-analysis",
            "guideline / consensus",
            "randomized trial",
        }:
            notes.append("The wording is stronger than the current level of evidence.")
            return "unsupported_as_stated", "medium", notes
        if claim_strength == "strong" and limiting:
            notes.append("Some related evidence exists, but the claim is stronger than the literature directly supports.")
            return "unsupported_as_stated", "high", notes
        if limiting:
            notes.append("There is some supporting evidence, but important caveats or narrower interpretations remain.")
            return "partially_supported", "medium", notes
        confidence = "high" if evidence_type in {"systematic review / meta-analysis", "guideline / consensus", "randomized trial"} else "medium"
        if access_level == "abstract_only":
            confidence = "medium" if confidence == "high" else "low"
            notes.append("The strongest support is abstract-based rather than full-text confirmed.")
        return "supported", confidence, notes

    return "evidence_unclear", "low", ["Evidence was too weak or too indirect to classify confidently."]


def compact_source(record: dict[str, object] | None) -> dict[str, object] | None:
    if record is None:
        return None
    return {
        "title": record.get("title", ""),
        "authors": record.get("authors", ""),
        "year": record.get("year"),
        "journal": record.get("journal", ""),
        "doi": record.get("doi", ""),
        "pmid": record.get("pmid", ""),
        "url": record.get("url", ""),
        "evidence_type": record.get("evidence_type", ""),
        "access_level": record.get("access_level", ""),
        "why_selected": record.get("why_selected", ""),
    }


def main() -> int:
    args = parse_args()
    claim = strip_prompt_wrappers(args.claim)
    if not claim:
        print("error: claim is empty after normalization", file=sys.stderr)
        return 1

    variants = generate_search_variants(claim)
    claim_strength = detect_claim_strength(keyword_tokens(claim))
    records = collect_paper_records(
        paths=args.paths,
        queries=variants,
        limit_per_provider=args.limit_per_provider,
        enable_ocr=args.enable_ocr,
        providers=DEFAULT_PROVIDERS,
        full_text_fetch_limit=3,
    )

    ranked = [rank_record(claim, claim_strength, record) for record in records]
    ranked.sort(key=lambda item: item["ranking_score"], reverse=True)

    best_supporting = pick_best(ranked, "supporting")
    best_limiting = pick_best(ranked, "contradicting") or pick_best(ranked, "limiting")
    best_review = pick_best_review(ranked)
    verdict, confidence, notes = verdict_for(claim_strength, best_supporting, best_limiting)

    if best_supporting and best_supporting.get("evidence_type") in {"preclinical animal study", "in vitro / mechanistic paper"}:
        notes.append("Closest support is preclinical or mechanistic rather than human clinical evidence.")
    if best_supporting and not best_supporting.get("human_relevance"):
        notes.append("No clear human clinical evidence was identified among the top supporting records.")
    if best_supporting:
        notes.append(f"Top supporting record access level: {best_supporting.get('access_level', 'metadata_only')}.")
    if best_limiting:
        notes.append(f"Top limiting record access level: {best_limiting.get('access_level', 'metadata_only')}.")
    if verdict in {"unsupported_as_stated", "contradicted_or_not_supported"} and claim_strength == "strong":
        notes.append("Prefer a weaker wording such as 'may be associated with' or 'has limited evidence in humans'.")

    output = {
        "claim": args.claim,
        "normalized_claim": claim,
        "verdict": verdict,
        "confidence": confidence,
        "search_variants": variants,
        "best_supporting_source": compact_source(best_supporting),
        "best_limiting_or_contradicting_source": compact_source(best_limiting),
        "best_review_source": compact_source(best_review),
        "notes": list(dict.fromkeys(note for note in notes if note)),
    }
    print(json.dumps(output, indent=args.json_indent, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
