"""ABS checklist (§6.8) — hand-coded decision logic rather than the generic weighted-score
engine (`rules/engine.py`): each activity maps to a specific authority/requirement, which
doesn't reduce to a single score the way patent risk does. Every citation is resolved
against the real ingested Biological Diversity Act, 2002 text.

Drafted from the corpus text directly; not reviewed by counsel — treat every `detail` here
as `status: draft` (CLAUDE.md).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.audit.rule_receipts import record_rule_engine_result
from app.rules.engine import resolve_citations
from app.schemas.abs import AbsChecklistItem, AbsRequest, AbsResult
from app.schemas.decision_path import DecisionEdge, DecisionNode, DecisionPath
from app.schemas.enums import AbsActivity, ApplicantType, Authority

BDA = "biological_diversity_act_2002"

_FOREIGN_TYPES = {ApplicantType.FOREIGN_ENTITY, ApplicantType.NRI}


def build_abs_result(
    session: Session,
    request: AbsRequest,
    corpus_version_id: str,
    corpus_version_label: str,
    as_of: date,
) -> AbsResult:
    jurisdictions = ["IN"]
    section_keys: list[str] = []
    checklist: list[AbsChecklistItem] = []
    is_foreign = request.applicant_type in _FOREIGN_TYPES
    any_codified_tk_local = any(
        r.is_codified_tk and r.is_cultivated for r in request.resources
    ) or not request.resources

    if AbsActivity.RESEARCH in request.activity or AbsActivity.COMMERCIAL_UTILISATION in request.activity:
        if is_foreign:
            key = f"{BDA}#s3"
            section_keys.append(key)
            checklist.append(
                AbsChecklistItem(
                    id="nba_prior_approval",
                    title="NBA prior approval before accessing the biological resource",
                    authority=Authority.NBA,
                    form=None,
                    required=True,
                    exempt=False,
                    timing="Before obtaining the biological resource or associated knowledge",
                    detail="s.3: a person who is not a citizen of India, or not a body corporate/association "
                    "registered or incorporated in India (or with non-Indian participation), needs NBA "
                    "approval before obtaining any biological resource occurring in India or knowledge "
                    "associated with it for research, commercial utilisation, or bio-survey/bio-utilisation.",
                    evidence_ids=[],
                )
            )
        else:
            key = f"{BDA}#s7"
            section_keys.append(key)
            exempt = any_codified_tk_local
            checklist.append(
                AbsChecklistItem(
                    id="sbb_prior_intimation",
                    title="Prior intimation to the State Biodiversity Board",
                    authority=Authority.SBB,
                    form=None,
                    required=not exempt,
                    exempt=exempt,
                    exempt_reason=(
                        "s.7's proviso exempts local people and communities, including growers and "
                        "cultivators of biodiversity, and vaids/hakims practising indigenous medicine "
                        "using codified traditional knowledge."
                        if exempt
                        else None
                    ),
                    timing="Before obtaining the biological resource for commercial utilisation or "
                    "bio-survey/bio-utilisation",
                    detail="s.7: an Indian citizen or a body corporate/association/organisation registered "
                    "in India must give prior intimation to the State Biodiversity Board before obtaining "
                    "a biological resource for commercial utilisation or bio-survey/bio-utilisation, unless "
                    "the s.7 proviso's local-people/cultivator/codified-TK exemption applies.",
                    evidence_ids=[],
                )
            )

    if AbsActivity.IPR_APPLICATION in request.activity:
        key = f"{BDA}#s6"
        section_keys.append(key)
        checklist.append(
            AbsChecklistItem(
                id="nba_approval_before_ipr",
                title="NBA approval before applying for IP based on Indian biological resources",
                authority=Authority.NBA,
                required=True,
                exempt=False,
                timing="Before making the IPR application (in or outside India)",
                detail="s.6: no person shall apply for a patent or other IPR, in or outside India, for an "
                "invention based on research on a biological resource obtained from India, without "
                "previous approval of the National Biodiversity Authority before making the application.",
                evidence_ids=[],
            )
        )

    if AbsActivity.TRANSFER_RESULTS in request.activity or AbsActivity.EXPORT in request.activity:
        key = f"{BDA}#s4"
        section_keys.append(key)
        checklist.append(
            AbsChecklistItem(
                id="nba_approval_transfer",
                title="NBA approval before transferring research results to a non-citizen/foreign entity",
                authority=Authority.NBA,
                required=True,
                exempt=False,
                timing="Before transferring the results of research",
                detail="s.4: no person shall, without previous NBA approval, transfer the results of any "
                "research relating to a biological resource obtained from India to a person who is not a "
                "citizen of India, or a non-Indian-registered body corporate/organisation.",
                evidence_ids=[],
            )
        )

    if AbsActivity.CULTIVATION_TRADE in request.activity and not checklist:
        checklist.append(
            AbsChecklistItem(
                id="no_obligation_identified",
                title="No ABS obligation identified for cultivation/trade alone",
                authority=Authority.NONE,
                required=False,
                exempt=True,
                exempt_reason="Normally-traded agricultural commodities are exempt (BD Rules definitions); "
                "verify against the current NBA exempt list.",
                detail="status: draft — TODO(verify): the normally-traded-commodity exemption is set out "
                "in the Biological Diversity Rules, 2004, which isn't ingested yet.",
                evidence_ids=[],
            )
        )

    evidence, chunk_id_by_evidence_id = resolve_citations(
        session, section_keys, corpus_version_id, corpus_version_label, jurisdictions, as_of
    )
    ev_ids_by_section = {span.section_key: eid for eid, span in evidence.items()}
    # attach evidence ids by re-deriving each item's own section key from its id
    _ID_TO_KEY = {
        "nba_prior_approval": f"{BDA}#s3",
        "sbb_prior_intimation": f"{BDA}#s7",
        "nba_approval_before_ipr": f"{BDA}#s6",
        "nba_approval_transfer": f"{BDA}#s4",
    }
    checklist = [
        item.model_copy(
            update={
                "evidence_ids": [
                    eid
                    for key, eid in ev_ids_by_section.items()
                    if key == _ID_TO_KEY.get(item.id)
                ]
            }
        )
        for item in checklist
    ]

    nodes = [
        DecisionNode(id=f"n_{i}", kind="question", label=item.title, value="yes" if item.required else "no")
        for i, item in enumerate(checklist)
    ]
    nodes.append(DecisionNode(id="n_outcome", kind="outcome", label="ABS checklist complete", value=None))
    edges = [
        DecisionEdge(**{"from": f"n_{i}", "to": (f"n_{i + 1}" if i + 1 < len(checklist) else "n_outcome"), "label": ""})
        for i in range(len(checklist))
    ]

    summary = (
        "One or more ABS obligations apply — see the checklist below."
        if any(i.required for i in checklist)
        else "No mandatory ABS obligation identified for the activities selected."
    )

    abs_result = AbsResult(
        summary=summary,
        checklist=checklist,
        decision_path=DecisionPath(nodes=nodes, edges=edges, outcome_id="n_outcome"),
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
        chunk_id_by_evidence_id=chunk_id_by_evidence_id,
        result_payload=abs_result.model_dump(mode="json"),
    )
    return abs_result.model_copy(update={"receipt_id": receipt_id})
