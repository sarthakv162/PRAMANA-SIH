"""§6.4 `route`: deterministic intent routing. **Calls no generative model** — CLAUDE.md and
invariant I6 require this; the only model touched here is the embedding model, used purely
for a kNN similarity floor, which cannot itself generate text or be prompt-injected into a
generation loop.

Order: (a) a direct-citation regex fast path, (b) keyword rules, (c) embedding-kNN over a
small exemplar set per intent, with a similarity floor below which the query is `out_of_scope`.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.retrieval import cite_parse, embed

_LEGAL_ADVICE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bshould i\b.*\b(file|patent|apply|sue|litigate)\b",
        r"\bwill i win\b",
        r"\bis (?:this|it) legal for me\b",
        r"\bcan you represent me\b",
        r"\bwhat should i do\b.*\b(court|sue|lawsuit|litigation)\b",
    ]
]

_TRADITIONAL_KNOWLEDGE_PATENT_PATTERN = re.compile(
    r"\btraditional knowledge\b.*\bpatent\w*\b|"
    r"\bpatent\w*\b.*\btraditional knowledge\b",
    re.IGNORECASE,
)

_KEYWORD_RULES: dict[str, list[re.Pattern[str]]] = {
    "classify": [
        re.compile(r"\bclassif(y|ication)\b", re.IGNORECASE),
        re.compile(r"\bwhat category\b", re.IGNORECASE),
        re.compile(r"\bis my (formulation|product) (classical|proprietary|a new drug)\b", re.IGNORECASE),
    ],
    "patent_risk": [
        re.compile(r"\bpatent (risk|eligib)", re.IGNORECASE),
        re.compile(r"\b3\s*\(\s*[pde]\s*\)\b", re.IGNORECASE),
        re.compile(r"\bcan (this|it|my formulation) be patented\b", re.IGNORECASE),
    ],
    "abs": [
        re.compile(r"\baccess and benefit sharing\b", re.IGNORECASE),
        re.compile(r"\b(abs|nba|sbb|bmc)\b approval", re.IGNORECASE),
        re.compile(r"\bbenefit.?shar", re.IGNORECASE),
    ],
    "tk": [
        re.compile(r"\btk radar\b", re.IGNORECASE),
        re.compile(r"\btkdl\b", re.IGNORECASE),
        re.compile(r"\bsimilar (classical )?formulations?\b", re.IGNORECASE),
        re.compile(r"\bwatchlist\b", re.IGNORECASE),
    ],
    "dossier": [
        re.compile(r"\bdossier\b", re.IGNORECASE),
        re.compile(r"\bexport (this|my) (case|results?)\b", re.IGNORECASE),
    ],
}

# ~10 short exemplar phrases per intent, embedded once and cached — the kNN fallback for
# queries the regex rules miss. A tiny, hand-picked set, not a trained classifier.
_EXEMPLARS: dict[str, list[str]] = {
    "qa": [
        "Can traditional knowledge be patented in India?",
        "What does the Biological Diversity Act say about foreign research access?",
        "What is a geographical indication?",
        "What are the requirements for a patent application in India?",
        "Does the Patents Act cover Ayurvedic formulations?",
    ],
    "classify": [
        "What category does my formulation fall under?",
        "Is my product classical, proprietary, or a new drug?",
        "How do I classify an Ayurvedic cosmetic product?",
    ],
    "patent_risk": [
        "What is the patent risk for my formulation?",
        "Does section 3(p) exclude my invention?",
        "Can this admixture be patented?",
    ],
    "abs": [
        "Do I need NBA approval to use this plant commercially?",
        "What are my access and benefit sharing obligations?",
        "Do I need to intimate the State Biodiversity Board?",
    ],
    "tk": [
        "Does my formulation match a classical Ayurvedic recipe?",
        "Show me the TK radar for my ingredients.",
        "Is there a TKDL entry for turmeric wound healing?",
    ],
    "dossier": [
        "Build a compliance dossier for my case.",
        "Export my results as a PDF.",
    ],
    "out_of_scope": [
        "What's the weather today?",
        "Write me a poem about flowers.",
        "What is the capital of France?",
    ],
}

# Coverage is defined by subject matter, independently of what is currently indexed.
_DOMAIN = re.compile(
    r"\b(ayurved\w*|ayush|patent\w*|trademark\w*|copyright|geographical indication|"
    r"traditional knowledge|biodiversity|biological diversity|biopiracy|benefit.?sharing|"
    r"nba|sbb|bmc|tkdl|tk|wipo|trips|pct|nagoya|cbd|budapest treaty|madrid protocol|"
    r"hague agreement|plant variet\w*|ppvfr|fssai|cdsco|phytopharmaceutical\w*|"
    r"nutraceutical\w*|aahara?|drug\w*|cosmetic\w*|licen[cs]\w*|regulat\w*|"
    r"manufactur\w*|formulat\w*|intellectual property|trade secret|design protection|"
    r"herbal|medicinal|botanical|clinical trial\w*|label\w*|export|import)\b",
    re.I,
)
_UNRELATED = re.compile(
    r"\b(weather|rain|sports? score|football|cricket|capital of|write (?:me )?a poem|"
    r"recipe for (?:dinner|cake)|bitcoin price)\b",
    re.I,
)

SIMILARITY_FLOOR = 0.35


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


@lru_cache
def _exemplar_vectors() -> tuple[tuple[str, list[float]], ...]:
    """`(intent, vector)` for every exemplar, embedded once per process."""
    pairs: list[tuple[str, list[float]]] = []
    for intent, exemplars in _EXEMPLARS.items():
        for vec in embed.embed_texts(exemplars):
            pairs.append((intent, vec))
    return tuple(pairs)


def _knn_intent(query_en: str) -> tuple[str, float]:
    query_vec = embed.embed_query(query_en)
    best_intent, best_score = "out_of_scope", -1.0
    for intent, vec in _exemplar_vectors():
        score = _cosine(query_vec, vec)
        if score > best_score:
            best_intent, best_score = intent, score
    return best_intent, best_score


def route(query_en: str) -> tuple[str, str | None]:
    """Returns `(intent, direct_section_key)`. `direct_section_key` is set only when a
    citation regex found an unambiguous section reference (§6.4 step 4a fast path).
    """
    if _UNRELATED.search(query_en):
        return "out_of_scope", None
    if any(p.search(query_en) for p in _LEGAL_ADVICE_PATTERNS):
        return "legal_advice", None

    citations = cite_parse.parse_citations(query_en)
    resolved_citation = next((c for c in citations if c.section_key), None)
    if resolved_citation:
        return "qa", resolved_citation.section_key

    # The plan's primary TK patentability flow maps to Patents Act s.3(p). Broad semantic
    # retrieval can otherwise prefer neighboring opposition sections that merely mention TK.
    if _TRADITIONAL_KNOWLEDGE_PATENT_PATTERN.search(query_en):
        return "qa", "patents_act_1970#s3(p)"

    for intent, patterns in _KEYWORD_RULES.items():
        if any(p.search(query_en) for p in patterns):
            return intent, None

    if _DOMAIN.search(query_en):
        return "qa", None
    try:
        intent, score = _knn_intent(query_en)
    except embed.EmbeddingUnavailable:
        return "out_of_scope", None
    if score < SIMILARITY_FLOOR:
        return "out_of_scope", None
    return intent, None
