"""Direct-citation regex parser (§6.4 `route` step 4a).

Recognises queries that name a section outright — "section 3(p) of the patents act",
"s.3(d)", "rule 5 of the biological diversity rules" — so the router can go straight to
that section instead of running full retrieval. This is regex only, no model, consistent
with "the router must not call a model" (CLAUDE.md, §2).

`ACT_ALIASES` maps informal names to the `short_key` used in `documents.short_key` /
`section_key` prefixes at ingest time (see `ingest/chunk_legal.py`). Extend it as more
documents are ingested.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ACT_ALIASES: dict[str, str] = {
    "patents act": "patents_act_1970",
    "the patents act": "patents_act_1970",
    "patents act, 1970": "patents_act_1970",
    "patents act 1970": "patents_act_1970",
    "patents rules": "patents_rules_2003",
    "biological diversity act": "biological_diversity_act_2002",
    "the biological diversity act": "biological_diversity_act_2002",
    "biological diversity act, 2002": "biological_diversity_act_2002",
    "biological diversity act 2002": "biological_diversity_act_2002",
    "biodiversity act": "biological_diversity_act_2002",
    "drugs and cosmetics act": "drugs_and_cosmetics_act_1940",
}

_CLAUSE = r"\d+[A-Za-z]*(?:\([a-zA-Z0-9]+\))*"

# "section 3(p)" / "s.3(p)" / "sec 3 (p)" / "rule 5" — clause group captures "3(p)". No `\b`
# directly after the clause group: it can end in ")" (a non-word char), and `\b` can't hold
# between that and the following space/`of` — it would force the match to backtrack to a
# shorter clause (dropping the "(p)" part) just to satisfy the boundary.
_SECTION_RE = re.compile(
    rf"\b(?:section|sec\.?|s\.|rule|r\.)\s*({_CLAUSE})\s*(?:of\s+(?:the\s+)?([a-z][a-z ,\.]+?act|"
    rf"[a-z][a-z ,\.]+?rules))?",
    re.IGNORECASE,
)


@dataclass
class ParsedCitation:
    clause: str
    act_alias: str | None
    doc_short_key: str | None
    section_key: str | None


def parse_citations(query_en: str) -> list[ParsedCitation]:
    """Best-effort extraction; returns [] if nothing looks like a direct citation."""
    results: list[ParsedCitation] = []
    for match in _SECTION_RE.finditer(query_en):
        clause_raw = match.group(1)
        clause = re.sub(r"\s+", "", clause_raw).lower()
        act_phrase = (match.group(2) or "").strip().lower()
        act_phrase = re.sub(r"\s+", " ", act_phrase)
        doc_short_key = ACT_ALIASES.get(act_phrase)
        section_key = f"{doc_short_key}#s{clause}" if doc_short_key else None
        results.append(
            ParsedCitation(
                clause=clause,
                act_alias=act_phrase or None,
                doc_short_key=doc_short_key,
                section_key=section_key,
            )
        )
    return results
