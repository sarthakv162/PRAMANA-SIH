"""Builds `PatentRisk` from the `patent_risk` rule tree (§6.8) — the one "never cut" rule
engine demo (§10), backed by the real ingested Patents Act s.3(p)/(e)/(d) text.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.audit.rule_receipts import record_rule_engine_result
from app.rules.engine import evaluate as evaluate_tree
from app.rules.engine import gauge_from_score, load_tree, resolve_citations
from app.schemas.decision_path import DecisionEdge, DecisionNode, DecisionPath
from app.schemas.enums import Risk
from app.schemas.formulation import Formulation
from app.schemas.patent_risk import PatentRisk, PatentRiskSection, WhatWouldHelp

_SECTIONS = ["3(p)", "3(e)", "3(d)"]


def build_patent_risk(
    session: Session,
    formulation: Formulation,
    corpus_version_id: str,
    corpus_version_label: str,
    jurisdictions: list[str],
    as_of: date,
) -> PatentRisk:
    tree = load_tree("patent_risk")
    facts = formulation.model_dump()
    result = evaluate_tree(tree, facts)

    all_cites = sorted({c for hit in result.hits for c in hit.cite})
    evidence, chunk_id_by_evidence_id = resolve_citations(
        session, all_cites, corpus_version_id, corpus_version_label, jurisdictions, as_of
    )
    ev_id_by_section_key = {span.section_key: ev_id for ev_id, span in evidence.items()}

    per_section: list[PatentRiskSection] = []
    nodes: list[DecisionNode] = []
    edges: list[DecisionEdge] = []
    prev_node_id: str | None = None

    for section in _SECTIONS:
        hits = [h for h in result.hits if h.section == section]
        score = result.score_by_section.get(section, 0.0)
        risk = Risk(gauge_from_score(score, tree["outputs"]["thresholds"]))
        evidence_ids = sorted({ev_id_by_section_key[c] for h in hits for c in h.cite if c in ev_id_by_section_key})
        per_section.append(
            PatentRiskSection(
                section=section,
                risk=risk,
                triggered_rules=[h.rule_id for h in hits],
                reasons=[h.reason for h in hits],
                evidence_ids=evidence_ids,
            )
        )

        node_id = f"n_{section.replace('(', '').replace(')', '')}"
        label = f"Does the formulation trigger s.{section}?"
        value = "yes" if hits else "no"
        nodes.append(DecisionNode(id=node_id, kind="question", label=label, value=value, evidence_ids=evidence_ids))
        if prev_node_id:
            edges.append(DecisionEdge(**{"from": prev_node_id, "to": node_id, "label": value}))
        prev_node_id = node_id

    overall_score = min(1.0, sum(result.score_by_section.values()))
    gauge = Risk(gauge_from_score(overall_score, tree["outputs"]["thresholds"]))
    outcome_id = "n_outcome"
    nodes.append(
        DecisionNode(id=outcome_id, kind="outcome", label=f"Overall patent risk: {gauge}", value=None)
    )
    if prev_node_id:
        edges.append(DecisionEdge(**{"from": prev_node_id, "to": outcome_id, "label": gauge}))

    what_would_help: list[WhatWouldHelp] = []
    if any(s.section == "3(d)" and s.risk != "low" for s in per_section):
        what_would_help.append(
            WhatWouldHelp(text="Comparative data showing enhanced efficacy over the known substance.")
        )
    if any(s.section == "3(p)" and s.risk != "low" for s in per_section):
        what_would_help.append(
            WhatWouldHelp(text="Evidence of a technical effect not disclosed in the cited classical source.")
        )

    patent_risk = PatentRisk(
        gauge=gauge,
        score=overall_score,
        per_section=per_section,
        what_would_help=what_would_help,
        decision_path=DecisionPath(nodes=nodes, edges=edges, outcome_id=outcome_id),
        evidence=evidence,
        receipt_id="",
    )
    receipt_id = record_rule_engine_result(
        session,
        corpus_version_id=corpus_version_id,
        corpus_version_label=corpus_version_label,
        endpoint="patent_risk",
        jurisdiction="IN",
        as_of=as_of,
        request_payload=formulation.model_dump(mode="json"),
        evidence=evidence,
        chunk_id_by_evidence_id=chunk_id_by_evidence_id,
        result_payload=patent_risk.model_dump(mode="json"),
    )
    return patent_risk.model_copy(update={"receipt_id": receipt_id})
