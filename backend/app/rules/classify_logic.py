"""Classification wizard (§6.8) — stateless: client resends all answers each turn. A short
2-question tree; category-defining law lives in the Drugs & Cosmetics Act/Rules, which isn't
ingested yet, so those specific citations are `status: draft`/`TODO(verify)` (CLAUDE.md) —
only the patent (Patents Act s.3(p)) and ABS (Biological Diversity Act s.3) posture citations
are backed by real ingested text.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.audit.rule_receipts import record_rule_engine_result
from app.rules.engine import resolve_citations
from app.schemas.classify import (
    AbsPosture,
    ClassifyQuestion,
    ClassifyRequest,
    ClassifyResult,
    InputOption,
    IpPosture,
    PostureItem,
    Progress,
    QuestionInput,
    Requirement,
)
from app.schemas.decision_path import DecisionEdge, DecisionNode, DecisionPath
from app.schemas.enums import ClassifyCategory, InputKind, Risk

_Q1 = "q_first_schedule"
_Q2 = "q_clinical_data"

CATEGORY_LABELS = {
    ClassifyCategory.CLASSICAL: "Classical / generic Ayurvedic medicine",
    ClassifyCategory.PROPRIETARY: "Proprietary Ayurvedic medicine",
    ClassifyCategory.NEW_DRUG: "New Ayurvedic drug",
}


def _draft_posture(note: str) -> PostureItem:
    return PostureItem(risk=Risk.LOW, note=f"status: draft — TODO(verify): {note}", evidence_ids=[])


def next_step(
    session: Session,
    request: ClassifyRequest,
    corpus_version_id: str,
    corpus_version_label: str,
) -> ClassifyQuestion | ClassifyResult:
    as_of = date.fromisoformat(request.as_of) if request.as_of else date.today()

    if _Q1 not in request.answers:
        return ClassifyQuestion(
            question_id=_Q1,
            text="Is your formulation, including its ingredients and method of preparation, "
            "described in one of the authoritative books listed in the First Schedule to the "
            "Drugs and Cosmetics Rules, 1945?",
            why_asked="This determines whether the product is a classical (generic) Ayurvedic "
            "medicine or a proprietary/new formulation. status: draft — TODO(verify): the "
            "First Schedule text isn't in the ingested corpus yet.",
            input=QuestionInput(
                kind=InputKind.BOOLEAN,
                options=[InputOption(value="yes", label="Yes"), InputOption(value="no", label="No")],
            ),
            evidence_ids=[],
            evidence={},
            progress=Progress(answered=0, estimated_total=2),
        )

    if request.answers[_Q1] == "yes":
        category = ClassifyCategory.CLASSICAL
    elif _Q2 not in request.answers:
        return ClassifyQuestion(
            question_id=_Q2,
            text="Do you have clinical safety/efficacy data for this formulation?",
            why_asked="A proprietary Ayurvedic medicine can rely on documented traditional use; "
            "a new drug claim generally needs its own clinical evidence.",
            input=QuestionInput(
                kind=InputKind.BOOLEAN,
                options=[InputOption(value="yes", label="Yes"), InputOption(value="no", label="No")],
            ),
            evidence_ids=[],
            evidence={},
            progress=Progress(answered=1, estimated_total=2),
        )
    elif request.answers[_Q2] == "yes":
        category = ClassifyCategory.NEW_DRUG
    else:
        category = ClassifyCategory.PROPRIETARY

    jurisdictions = ["IN"]
    cite_keys = []
    if category == ClassifyCategory.CLASSICAL:
        cite_keys = ["patents_act_1970#s3(p)", "biological_diversity_act_2002#s3"]
    evidence, chunk_id_by_evidence_id = resolve_citations(
        session, cite_keys, corpus_version_id, corpus_version_label, jurisdictions, as_of
    )
    ev_by_key = {span.section_key: eid for eid, span in evidence.items()}

    if category == ClassifyCategory.CLASSICAL:
        patent_ev = [ev_by_key[k] for k in ["patents_act_1970#s3(p)"] if k in ev_by_key]
        abs_ev = [ev_by_key[k] for k in ["biological_diversity_act_2002#s3"] if k in ev_by_key]
        ip_posture = IpPosture(
            patent=PostureItem(
                risk=Risk.HIGH,
                note="Classical formulations matching s.3(p) are excluded from patenting.",
                evidence_ids=patent_ev,
            ),
            gi=_draft_posture("GI eligibility depends on region/community ties (GI Act, not ingested)."),
            trademark=_draft_posture("Brand name/logo can be trademarked independent of the formulation."),
            design=_draft_posture("Only packaging/product shape would qualify, not the formulation."),
            copyright=_draft_posture("Not generally applicable to the formulation itself."),
            trade_secret=_draft_posture("A specific process refinement could be kept as a trade secret."),
        )
        abs_posture = AbsPosture(
            summary="If ingredients are sourced from Indian biological resources for commercial "
            "use, NBA/SBB approval may still be required regardless of patent status.",
            evidence_ids=abs_ev,
        )
        requirements = [
            Requirement(
                text="status: draft — TODO(verify): manufacturing licence under the Drugs and "
                "Cosmetics Act/Rules citing the First-Schedule reference text.",
                evidence_ids=[],
            )
        ]
    else:
        ip_posture = IpPosture(
            patent=_draft_posture("Patent posture needs case-by-case s.3(d)/(e) review."),
            gi=_draft_posture("GI Act not ingested yet."),
            trademark=_draft_posture("Brand name/logo can generally be trademarked."),
            design=_draft_posture("Designs Act not ingested yet."),
            copyright=_draft_posture("Not generally applicable to the formulation itself."),
            trade_secret=_draft_posture("Process details could be kept as a trade secret."),
        )
        abs_posture = AbsPosture(
            summary="status: draft — TODO(verify): ABS obligations depend on the resource's "
            "origin; use /abs-check for a full determination.",
            evidence_ids=[],
        )
        requirements = [
            Requirement(
                text=f"status: draft — TODO(verify): {CATEGORY_LABELS[category]} licensing "
                "requirements under the Drugs and Cosmetics Act/Rules (not yet ingested).",
                evidence_ids=[],
            )
        ]

    nodes = [
        DecisionNode(
            id="n1", kind="question", label="First-Schedule classical source?",
            value=request.answers.get(_Q1),
        ),
        DecisionNode(id="n2", kind="outcome", label=CATEGORY_LABELS[category], value=None),
    ]
    edges = [DecisionEdge(**{"from": "n1", "to": "n2", "label": request.answers.get(_Q1, "")})]

    classify_result = ClassifyResult(
        category=category,
        category_label=CATEGORY_LABELS[category],
        requirements=requirements,
        ip_posture=ip_posture,
        abs_posture=abs_posture,
        decision_path=DecisionPath(nodes=nodes, edges=edges, outcome_id="n2"),
        evidence=evidence,
        receipt_id="",
    )
    receipt_id = record_rule_engine_result(
        session,
        corpus_version_id=corpus_version_id,
        corpus_version_label=corpus_version_label,
        endpoint="classify",
        jurisdiction="IN",
        as_of=as_of,
        request_payload=request.model_dump(mode="json"),
        evidence=evidence,
        chunk_id_by_evidence_id=chunk_id_by_evidence_id,
        result_payload=classify_result.model_dump(mode="json"),
    )
    return classify_result.model_copy(update={"receipt_id": receipt_id})
