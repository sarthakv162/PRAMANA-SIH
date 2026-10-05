from datetime import date
from unittest.mock import Mock

import pytest

from app.rules import abs_logic
from app.rules.engine import evaluate, load_tree
from app.schemas.abs import AbsRequest


@pytest.mark.parametrize("applicant", ["indian_citizen", "indian_company", "foreign_entity", "nri"])
@pytest.mark.parametrize(
    "activity",
    ["research", "commercial_utilisation", "ipr_application", "transfer_results", "export", "cultivation_trade"],
)
def test_abs_missing_facts_never_become_an_obligation_or_exemption(monkeypatch, applicant, activity):
    resolve = Mock(return_value=({}, {}))
    monkeypatch.setattr(abs_logic, "resolve_citations", resolve)
    monkeypatch.setattr(abs_logic, "record_rule_engine_result", lambda *args, **kwargs: "test-receipt")
    result = abs_logic.build_abs_result(
        Mock(), AbsRequest(applicant_type=applicant, activity=[activity]), "id", "version", date.today()
    )
    assert result.assessment_status == "unassessed"
    assert result.checklist
    assert all(item.required is None and item.exempt is None for item in result.checklist)
    assert all(not item.evidence_ids for item in result.checklist)
    assert resolve.call_args.kwargs["include_descendants"] is True


def test_clinical_data_presence_does_not_lower_derivative_rule_score():
    tree = load_tree("patent_risk")
    inputs = {"is_derivative_of_known_substance": True}
    assert (
        evaluate(tree, inputs | {"has_clinical_data": True}).total_score
        == evaluate(tree, inputs | {"has_clinical_data": False}).total_score
    )
