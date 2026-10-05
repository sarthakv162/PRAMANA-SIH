from types import SimpleNamespace

import pytest

from app.rules.classify_logic import _CITE_KEYS, _GROUPS, assess, defining_provision_present
from app.schemas.classify import ClassifyQuestion
from app.schemas.enums import ClassifyCategory

BASE = dict(
    intended_use="medicine",
    therapeutic_claims="yes",
    claims_text="Treat a specified disorder",
    route="oral",
    dosage_form="Tablet, 250 mg twice daily in adults",
    classical_match="exact",
    classical_reference="Authoritative book, chapter and recipe",
    ingredients="Plant A root, Plant B leaves; decoction",
    authoritative_ingredients="yes",
    novelty="no",
    novelty_details="none",
    purified_fraction="no",
    four_markers="no",
)


@pytest.mark.parametrize(
    ("changes", "category"),
    [
        ({}, "classical"),
        ({"classical_match": "none", "classical_reference": "none"}, "proprietary"),
        ({"classical_match": "modified", "novelty": "yes"}, "new_drug"),
        ({"purified_fraction": "yes", "four_markers": "yes"}, "phytopharmaceutical"),
        ({"intended_use": "food", "therapeutic_claims": "no"}, "aahar_nutraceutical"),
        ({"intended_use": "cosmetic", "therapeutic_claims": "no", "route": "topical"}, "cosmetic"),
        ({"purified_fraction": "yes", "four_markers": "no"}, "new_drug"),
        ({"purified_fraction": "yes", "four_markers": "yes", "route": "parenteral"}, "new_drug"),
        ({"classical_match": "none", "authoritative_ingredients": "no"}, "new_drug"),
    ],
)
def test_each_category_and_extract_branch(changes, category):
    assert assess(BASE | changes) == ClassifyCategory(category)


@pytest.mark.parametrize("field", [f.id for _, _, fields in _GROUPS for f in fields])
@pytest.mark.parametrize("value", ["", "unknown"])
def test_every_missing_or_unknown_field_requires_clarification(field, value):
    assert isinstance(assess(BASE | {field: value}), ClassifyQuestion)


@pytest.mark.parametrize(
    "changes",
    [
        {"intended_use": "ambiguous"},
        {"intended_use": "food", "therapeutic_claims": "yes"},
        {"intended_use": "cosmetic", "therapeutic_claims": "yes"},
        {"classical_reference": "none"},
        {"novelty": "yes"},
        {"authoritative_ingredients": "no"},
        {"four_markers": "yes"},
        {"route": "unknown"},
        {"intended_use": "cosmetic", "therapeutic_claims": "no", "route": "oral"},
        {"intended_use": "food", "therapeutic_claims": "no", "route": "topical"},
    ],
)
def test_ambiguous_and_conflicting_inputs_never_force_a_category(changes):
    assert isinstance(assess(BASE | changes), ClassifyQuestion)


def test_intake_requires_at_most_four_distinct_prompts():
    answers = {}
    seen = []
    while isinstance(result := assess(answers), ClassifyQuestion):
        seen.append(result.question_id)
        for f in result.input.fields:
            answers[f.id] = BASE[f.id]
    assert len(seen) == 4 and len(set(seen)) == 4


@pytest.mark.parametrize("category", list(ClassifyCategory))
def test_category_requires_defining_clause_instead_of_a_heading(category):
    key = _CITE_KEYS[category][0]
    heading = key.split("(", 1)[0]
    assert not defining_provision_present(category, {"header": SimpleNamespace(section_key=heading)})
    assert not defining_provision_present(category, {})
    assert defining_provision_present(category, {"clause": SimpleNamespace(section_key=key)})
