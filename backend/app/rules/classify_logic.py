"""Four adaptive intake prompts. Outcomes are provisional, source-grounded routing.

Clinical data alone never determines a product category. Ambiguity keeps the user on the
relevant prompt. The app's new_drug bucket is an investigation/reviewer workflow, not a
claim that 'new Ayurvedic drug' is a standalone statutory definition.
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
    QuestionField,
    QuestionInput,
    Requirement,
)
from app.schemas.decision_path import DecisionEdge, DecisionNode, DecisionPath
from app.schemas.enums import ClassifyCategory, InputKind, Risk
from app.schemas.evidence import EvidenceSpan

CATEGORY_LABELS = {
    ClassifyCategory.CLASSICAL: "Classical / generic Ayurvedic medicine",
    ClassifyCategory.PROPRIETARY: "Patent or proprietary Ayurvedic medicine",
    ClassifyCategory.NEW_DRUG: "New / investigational medicinal product — regulatory review needed",
    ClassifyCategory.PHYTOPHARMACEUTICAL: "Phytopharmaceutical drug",
    ClassifyCategory.AAHAR_NUTRACEUTICAL: "Ayurveda Aahara / nutraceutical — food pathway",
    ClassifyCategory.COSMETIC: "Cosmetic",
}


def _field(id: str, label: str, choices: list[tuple[str, str]] | None = None) -> QuestionField:
    return QuestionField(
        id=id,
        label=label,
        kind=InputKind.SINGLE if choices else InputKind.TEXT,
        options=[InputOption(value=value, label=label) for value, label in (choices or [])],
    )


YES_NO = [("yes", "Yes"), ("no", "No"), ("unknown", "Not sure")]
_GROUPS = [
    (
        "q_use_claims",
        "What will the product be used for, and what will its label claim?",
        [
            _field(
                "intended_use",
                "Intended use",
                [
                    ("medicine", "Medicinal use"),
                    ("food", "Food / nutrition"),
                    ("cosmetic", "Cleansing / beautifying"),
                    ("ambiguous", "Mixed or undecided"),
                ],
            ),
            _field("therapeutic_claims", "Diagnosis, prevention, mitigation or treatment claims?", YES_NO),
            _field("claims_text", "Describe the intended use and the proposed label claims"),
        ],
    ),
    (
        "q_route_dosage",
        "How is the product administered, and in what dosage form?",
        [
            _field(
                "route",
                "Route",
                [
                    ("oral", "Oral"),
                    ("topical", "Topical / external"),
                    ("parenteral", "Injection / parenteral"),
                    ("other", "Other / uncertain"),
                ],
            ),
            _field("dosage_form", "Dosage form, quantity, frequency and intended population"),
        ],
    ),
    (
        "q_classical_match",
        "Does an authoritative classical source describe this product exactly?",
        [
            _field(
                "classical_match",
                "Formulation, process, dosage and indication match",
                [
                    ("exact", "Exact match"),
                    ("modified", "Changed ingredients, process, dosage or indication"),
                    ("none", "No formulation match"),
                    ("unknown", "Not established"),
                ],
            ),
            _field("classical_reference", "Book, passage and deviations (write 'none' if there is no source match)"),
        ],
    ),
    (
        "q_ingredients_extract",
        "What are the ingredients, novelty and extract characteristics?",
        [
            _field("ingredients", "All ingredients, plant parts, amounts and extraction / preparation process"),
            _field(
                "authoritative_ingredients",
                "Are all medicinal ingredients documented in authoritative classical sources?",
                YES_NO,
            ),
            _field("novelty", "Novel indication, ingredient, process, dosage or isolated substance?", YES_NO),
            _field("novelty_details", "Describe any novelty and supporting data (write 'none' if absent)"),
            _field("purified_fraction", "Purified, standardised medicinal plant extract fraction?", YES_NO),
            _field(
                "four_markers",
                "At least four bioactive / phytochemical compounds assessed qualitatively AND quantitatively?",
                YES_NO,
            ),
        ],
    ),
]


def _invalid(fields: list[QuestionField], answers: dict[str, str]) -> list[str]:
    missing = []
    for f in fields:
        value = answers.get(f.id, "").strip()
        choices = {o.value for o in f.options}
        if not value or value in {"unknown", "ambiguous", "other"} or (choices and value not in choices):
            missing.append(f.label)
    return missing


def _question(index: int, fields: list[QuestionField], missing: list[str] | None = None) -> ClassifyQuestion:
    id, text, _ = _GROUPS[index]
    explanation = (
        "Product purpose, route, classical match and ingredients determine the provisional regulatory pathway."
    )
    if missing:
        explanation += " Clarify: " + "; ".join(missing) + ". No category is assigned while these facts are missing."
    return ClassifyQuestion(
        question_id=id,
        text=text,
        why_asked=explanation,
        input=QuestionInput(kind=InputKind.TEXT, fields=fields),
        progress=Progress(answered=index, estimated_total=4),
    )


def assess(answers: dict[str, str]) -> ClassifyQuestion | ClassifyCategory:
    medicinal = answers.get("intended_use") == "medicine" or answers.get("therapeutic_claims") == "yes"
    for index, (_, _, all_fields) in enumerate(_GROUPS):
        fields = all_fields
        if index == 3 and not medicinal:
            # Food and cosmetics still need ingredient/extract details, without a medicinal-source assertion.
            fields = [f for f in fields if f.id not in {"authoritative_ingredients", "four_markers"}]
        missing = _invalid(fields, answers)
        if missing:
            return _question(index, fields, missing if any(f.id in answers for f in fields) else None)
        if index == 0 and answers["intended_use"] in {"food", "cosmetic"} and answers["therapeutic_claims"] == "yes":
            return _question(
                0, fields, ["Food / cosmetic purpose conflicts with medicinal claims; clarify the intended pathway"]
            )
        if (
            index == 2
            and answers["classical_match"] == "exact"
            and answers["classical_reference"].strip().casefold() in {"none", "n/a", "no"}
        ):
            return _question(2, fields, ["An exact classical match requires the book and passage reference"])
    if answers["intended_use"] == "cosmetic":
        if answers["route"] != "topical":
            return _question(1, _GROUPS[1][2], ["Cosmetic use requires external application; confirm route and use"])
        return ClassifyCategory.COSMETIC
    if answers["intended_use"] == "food":
        if answers["route"] != "oral":
            return _question(1, _GROUPS[1][2], ["Food use requires oral consumption; confirm route and use"])
        return ClassifyCategory.AAHAR_NUTRACEUTICAL
    if answers["purified_fraction"] == "yes":
        if answers["four_markers"] == "yes" and answers["route"] != "parenteral":
            return ClassifyCategory.PHYTOPHARMACEUTICAL
        return ClassifyCategory.NEW_DRUG
    if answers["four_markers"] == "yes":
        return _question(
            3,
            _GROUPS[3][2],
            ["Marker standardisation is inconsistent with an unpurified fraction; clarify extract details"],
        )
    if answers["classical_match"] == "exact":
        if answers["novelty"] == "yes" or answers["authoritative_ingredients"] == "no":
            return _question(
                2,
                _GROUPS[2][2],
                ["An exact match conflicts with novelty or non-classical ingredients; describe deviations"],
            )
        return ClassifyCategory.CLASSICAL
    if answers["novelty"] == "yes" or answers["authoritative_ingredients"] == "no" or answers["route"] == "parenteral":
        return ClassifyCategory.NEW_DRUG
    return ClassifyCategory.PROPRIETARY


_CITE_KEYS = {
    ClassifyCategory.CLASSICAL: ["drugs_cosmetics_act_1940#s3(a)", "drugs_rules_1945_consolidated_2024#s158B"],
    ClassifyCategory.PROPRIETARY: ["drugs_cosmetics_act_1940#s3(h)(i)", "drugs_rules_1945_consolidated_2024#s158B"],
    ClassifyCategory.NEW_DRUG: ["new_drugs_clinical_trials_rules_2019#s2(w)"],
    ClassifyCategory.PHYTOPHARMACEUTICAL: [
        "drugs_rules_1945_consolidated_2024#s2(ec)",
    ],
    ClassifyCategory.COSMETIC: ["drugs_cosmetics_act_1940#s3(aaa)"],
    ClassifyCategory.AAHAR_NUTRACEUTICAL: ["fssai_ayurveda_aahara_regulations_2022#s2(b)"],
}


def defining_provision_present(category: ClassifyCategory, evidence: dict[str, EvidenceSpan]) -> bool:
    # A licensing provision or a generic definitions heading cannot support the category.
    defining_key = _CITE_KEYS[category][0]
    return any(span.section_key == defining_key for span in evidence.values())


def next_step(
    session: Session, request: ClassifyRequest, corpus_version_id: str, corpus_version_label: str
) -> ClassifyQuestion | ClassifyResult:
    assessment = assess(request.answers)
    if isinstance(assessment, ClassifyQuestion):
        return assessment
    category = assessment
    as_of = request.as_of or date.today()
    keys = _CITE_KEYS[category]
    evidence, chunk_ids = resolve_citations(session, keys, corpus_version_id, corpus_version_label, ["IN"], as_of)
    ids = list(evidence)
    supported = defining_provision_present(category, evidence)
    notes = "Provisional pathway based on declared inputs; licensing authority review is required."
    if not supported:
        notes = (
            "status: draft — TODO(verify): category-defining provisions are absent from this corpus version. " + notes
        )
    nodes = [
        DecisionNode(
            id=f"n{i + 1}",
            kind="question",
            label=text,
            value="; ".join(f"{f.label}: {request.answers.get(f.id, 'not supplied')}" for f in fields),
            evidence_ids=ids,
        )
        for i, (_, text, fields) in enumerate(_GROUPS)
    ]
    nodes.append(DecisionNode(id="outcome", kind="outcome", label=CATEGORY_LABELS[category], evidence_ids=ids))
    edges = [DecisionEdge(**{"from": nodes[i].id, "to": nodes[i + 1].id, "label": "next"}) for i in range(4)]
    posture = PostureItem(
        risk=Risk.MEDIUM,
        note="Not assessed by product classification. Use the relevant IP / ABS checker and source review.",
    )
    result = ClassifyResult(
        category=category,
        category_label=CATEGORY_LABELS[category],
        status="provisional" if supported else "draft",
        requirements=[Requirement(text=notes, evidence_ids=ids)],
        ip_posture=IpPosture(**{k: posture for k in IpPosture.model_fields}),
        abs_posture=AbsPosture(summary="Resource origin, applicant and activity are needed for ABS assessment."),
        decision_path=DecisionPath(nodes=nodes, edges=edges, outcome_id="outcome"),
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
        chunk_id_by_evidence_id=chunk_ids,
        result_payload=result.model_dump(mode="json"),
    )
    return result.model_copy(update={"receipt_id": receipt_id})
