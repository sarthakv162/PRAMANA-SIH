"""POST /v1/abs-check — ABS obligations checklist (§6.8)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.fixtures import load_fixture
from app.retrieval.repo import live_corpus_version
from app.rules.abs_logic import build_abs_result
from app.schemas.abs import AbsRequest, AbsResult

router = APIRouter(tags=["abs"])


@router.post("/abs-check", response_model=AbsResult)
async def abs_check(request: AbsRequest, session: Session = Depends(get_session)) -> AbsResult:
    settings = get_settings()
    if settings.mock_mode:
        return AbsResult.model_validate(load_fixture("abs_result.json"))

    version = live_corpus_version(session)
    if version is None:
        raise ApiError(code="no_corpus", message="No live corpus version is available.", status_code=503)
    corpus_version_id, corpus_version_label = version
    as_of = date.fromisoformat(request.as_of) if request.as_of else date.today()
    return build_abs_result(session, request, corpus_version_id, corpus_version_label, as_of)
