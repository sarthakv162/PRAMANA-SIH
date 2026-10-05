"""Extractive ABS research checklist, without unverified applicability determinations.

Activities select statutory provisions. Applicant ownership/control, origin, exceptions,
notifications and timing need further assessment; absent facts never imply an exemption.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.audit.rule_receipts import record_rule_engine_result
from app.rules.engine import resolve_citations
from app.schemas.abs import AbsChecklistItem, AbsRequest, AbsResult
from app.schemas.decision_path import DecisionEdge, DecisionNode, DecisionPath
from app.schemas.enums import AbsActivity, Authority

BDA = "biological_diversity_act_2002"


def build_abs_result(
    session: Session,
    request: AbsRequest,
    corpus_version_id: str,
    corpus_version_label: str,
    as_of: date,
) -> AbsResult:
    # Routing identifiers point into the actual Act, not prewritten legal answers.
    topics: dict[str, tuple[str, list[str]]] = {}
    if {AbsActivity.RESEARCH, AbsActivity.COMMERCIAL_UTILISATION} & set(request.activity):
        topics["access"] = ("Access and commercial utilisation: review applicant and exceptions", ["3", "7"])
    if AbsActivity.IPR_APPLICATION in request.activity:
        topics["ipr"] = ("Intellectual property: review approval, registration and timing", ["6"])
    if {AbsActivity.TRANSFER_RESULTS, AbsActivity.EXPORT} & set(request.activity):
        topics["transfer"] = ("Transfers and export: distinguish research results from resource transfers", ["4", "20"])
    if AbsActivity.CULTIVATION_TRADE in request.activity:
        topics["trade"] = ("Cultivation and trade: review exceptions and applicable notifications", ["7", "40"])
    keys = [f"{BDA}#s{number}" for _, numbers in topics.values() for number in numbers]
    evidence, chunk_ids = resolve_citations(
        session, keys, corpus_version_id, corpus_version_label, ["IN"], as_of, include_descendants=True
    )
    checklist = []
    for topic_id, (title, numbers) in topics.items():
        prefixes = [f"{BDA}#s{number}" for number in numbers]
        ids = [
            eid
            for eid, span in evidence.items()
            if any(span.section_key == key or span.section_key.startswith((key + "(", key + "-")) for key in prefixes)
        ]
        checklist.append(
            AbsChecklistItem(
                id=topic_id,
                title=title,
                authority=Authority.NONE,
                required=None,
                exempt=None,
                detail=(
                    "Applicability is unassessed. Read the cited statutory provisions, including their conditions and "
                    "exceptions. The selected inputs alone do not establish an obligation or exemption."
                    if ids
                    else "Relevant provisions are unavailable for this corpus/date; applicability is unassessed."
                ),
                evidence_ids=ids,
            )
        )
    nodes = [
        DecisionNode(id=f"n_{i}", kind="question", label=item.title, value="unassessed", evidence_ids=item.evidence_ids)
        for i, item in enumerate(checklist)
    ]
    nodes.append(DecisionNode(id="outcome", kind="outcome", label="ABS applicability requires assessment"))
    edges = [
        DecisionEdge(
            **{"from": f"n_{i}", "to": f"n_{i + 1}" if i + 1 < len(checklist) else "outcome", "label": "review"}
        )
        for i in range(len(checklist))
    ]
    result = AbsResult(
        summary="Source-backed research checklist; ABS applicability has not been determined.",
        assessment_status="unassessed",
        checklist=checklist,
        decision_path=DecisionPath(nodes=nodes, edges=edges, outcome_id="outcome"),
        evidence=evidence,
        receipt_id="",
    )
    receipt_id = record_rule_engine_result(
        session,
        corpus_version_id=corpus_version_id,
        corpus_version_label=corpus_version_label,
        endpoint="abs_check",
        jurisdiction="IN",
        as_of=as_of,
        request_payload=request.model_dump(mode="json"),
        evidence=evidence,
        chunk_id_by_evidence_id=chunk_ids,
        result_payload=result.model_dump(mode="json"),
    )
    return result.model_copy(update={"receipt_id": receipt_id})
