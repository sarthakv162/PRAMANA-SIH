"""POST /v1/patent-risk — 3(p)/3(e)/3(d) risk indicator (§6.8)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.fixtures import load_fixture
from app.retrieval.repo import live_corpus_version
from app.rules.patent_risk_logic import build_patent_risk
from app.schemas.patent_risk import PatentRisk, PatentRiskRequest

router = APIRouter(tags=["patent-risk"])


@router.post("/patent-risk", response_model=PatentRisk)
async def patent_risk(
    request: PatentRiskRequest, session: Session = Depends(get_session)
) -> PatentRisk:
    settings = get_settings()
    if settings.mock_mode:
        fixture_name = (
            "patent_risk_high.json" if request.classical_sources_cited else "patent_risk_low.json"
        )
        return PatentRisk.model_validate(load_fixture(fixture_name))

    version = live_corpus_version(session)
    if version is None:
        raise ApiError(code="no_corpus", message="No live corpus version is available.", status_code=503)
    corpus_version_id, corpus_version_label = version
    jurisdictions = ["IN"]  # patent risk is an India-law question
    return build_patent_risk(
        session,
        request,
        corpus_version_id,
        corpus_version_label,
        jurisdictions,
        request.as_of or date.today(),
    )
