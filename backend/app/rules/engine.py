"""§6.8 rule engine: ~150 lines of plain Python, no `eval`. Loads a YAML rule tree, evaluates
`when` predicates against a plain dict of facts, sums weighted scores per output section, and
resolves every `cite` (a section_key) to a real `EvidenceSpan` through `retrieval/repo.py` so
citations obey the jurisdiction/as-of gate (§2, §6.8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

import sqlalchemy as sa
import yaml
from sqlalchemy.orm import Session

from app.retrieval import repo
from app.retrieval.evidence_pack import stable_evidence_id
from app.schemas.evidence import EvidenceSpan, Highlight

TREES_DIR = Path(__file__).parent / "trees"


def load_tree(name: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((TREES_DIR / f"{name}.yaml").read_text())
    return data


def _get_field(facts: dict[str, Any], path: str) -> Any:
    value: Any = facts
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
        if value is None:
            return None
    return value


_OPS: dict[str, Any] = {
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
    "gte": lambda a, b: a is not None and a >= b,
    "lte": lambda a, b: a is not None and a <= b,
    "nonempty": lambda a, _b=None: bool(a),
    "empty": lambda a, _b=None: not a,
    "len_gte": lambda a, b: a is not None and len(a) >= b,
    "contains": lambda a, b: a is not None and b in a,
}


def _eval_condition(cond: dict[str, Any], facts: dict[str, Any]) -> bool:
    if "all" in cond:
        return all(_eval_condition(c, facts) for c in cond["all"])
    if "any" in cond:
        return any(_eval_condition(c, facts) for c in cond["any"])
    if "not" in cond:
        return not _eval_condition(cond["not"], facts)
    value = _get_field(facts, cond["field"])
    op = _OPS[cond["op"]]
    return bool(op(value, cond.get("value")))


@dataclass
class RuleHit:
    rule_id: str
    section: str
    weight: float
    reason: str
    cite: list[str]


@dataclass
class RuleEvalResult:
    hits: list[RuleHit] = field(default_factory=list)
    score_by_section: dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0


def evaluate(tree: dict[str, Any], facts: dict[str, Any]) -> RuleEvalResult:
    result = RuleEvalResult()
    for rule in tree.get("rules", []):
        if not _eval_condition(rule["when"], facts):
            continue
        weight = float(rule.get("weight", 0.0))
        section = rule.get("section", "")
        hit = RuleHit(
            rule_id=rule["id"],
            section=section,
            weight=weight,
            reason=rule.get("reason", ""),
            cite=rule.get("cite", []),
        )
        result.hits.append(hit)
        result.score_by_section[section] = result.score_by_section.get(section, 0.0) + weight
        result.total_score += weight
    result.total_score = max(0.0, min(1.0, result.total_score))
    return result


def gauge_from_score(score: float, thresholds: dict[str, float]) -> str:
    if score >= thresholds.get("high", 0.67):
        return "high"
    if score >= thresholds.get("low", 0.34):
        return "medium"
    return "low"


def resolve_citations(
    session: Session,
    section_keys: list[str],
    corpus_version_id: str,
    corpus_version_label: str,
    jurisdictions: list[str],
    as_of: date,
    include_descendants: bool = False,
) -> tuple[dict[str, EvidenceSpan], dict[str, str]]:
    """Resolve rule-tree `cite` section_keys to real `EvidenceSpan`s — through the same
    jurisdiction/as-of gate as any other evidence (§6.4 "cite-resolution" step). A section_key
    that doesn't exist yet (an un-ingested Act) is silently skipped, not fabricated — the
    caller ends up with fewer evidence_ids than cites, which is visible in the response.

    Returns `(evidence_by_id, chunk_id_by_evidence_id)` — the second map lets callers build a
    real audit receipt (`audit/rule_receipts.py`) over these citations, since a receipt needs
    each span's underlying `chunk_id`, not just its rendered `EvidenceSpan`.
    """
    evidence: dict[str, EvidenceSpan] = {}
    chunk_id_by_evidence_id: dict[str, str] = {}
    if include_descendants and section_keys:
        predicates = [
            sa.or_(
                repo.sections.c.section_key == key,
                repo.sections.c.section_key.startswith(key + "("),
                repo.sections.c.section_key.startswith(key + "-"),
            )
            for key in section_keys
        ]
        section_keys = list(
            session.execute(
                sa.select(repo.sections.c.section_key)
                .where(repo.sections.c.corpus_version_id == corpus_version_id, sa.or_(*predicates))
                .order_by(repo.sections.c.section_key)
            ).scalars()
        )
    for key in section_keys:
        section = repo.fetch_section_by_key(session, key, corpus_version_id)
        if section is None:
            continue
        section_chunks = repo.fetch_chunks_for_section(
            session, str(section.id), corpus_version_id, jurisdictions, as_of
        )
        for chunk in section_chunks:
            document = repo.fetch_document(session, str(section.document_id))
            if document is None:
                continue
            artifact = repo.document_artifact(session, document.short_key, corpus_version_label)
            ev_id = stable_evidence_id(str(chunk.id), chunk.char_start, chunk.char_end)
            evidence[ev_id] = EvidenceSpan(
                id=ev_id,
                doc_id=document.short_key,
                doc_title=document.title,
                doc_type=chunk.doc_type,
                jurisdiction=chunk.jurisdiction,
                citation_label=f"{document.title} — {section.section_key.split('#', 1)[-1]}",
                section_key=section.section_key,
                section_path=list(section.path or []),
                page=chunk.page or 0,
                page_end=chunk.page or 0,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                text=chunk.text,
                sha256=chunk.sha256,
                effective_from=chunk.effective_from,
                effective_to=chunk.effective_to,
                corpus_version=corpus_version_label,
                source_url=artifact["source_url"] if artifact else document.source_url,
                pdf_url=f"/v1/documents/{document.short_key}/pdf?corpus_version={quote(corpus_version_label)}",
                highlights=[Highlight(**h) for h in (chunk.bboxes or [])],
            )
            chunk_id_by_evidence_id[ev_id] = str(chunk.id)
    return evidence, chunk_id_by_evidence_id
