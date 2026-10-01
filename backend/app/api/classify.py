"""POST /v1/classify — classification wizard. Stateless: client resends all answers (§6.8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.fixtures import load_fixture
from app.retrieval.repo import live_corpus_version
from app.rules.classify_logic import next_step
from app.schemas.classify import ClassifyQuestion, ClassifyRequest, ClassifyResult

router = APIRouter(tags=["classify"])


@router.post("/classify", response_model=ClassifyQuestion | ClassifyResult)
async def classify(
    request: ClassifyRequest, session: Session = Depends(get_session)
) -> ClassifyQuestion | ClassifyResult:
    settings = get_settings()
    if settings.mock_mode:
        if not request.answers:
            return ClassifyQuestion.model_validate(load_fixture("classify_question.json"))
        return ClassifyResult.model_validate(load_fixture("classify_result_classical.json"))

    version = live_corpus_version(session)
    if version is None:
        raise ApiError(code="no_corpus", message="No live corpus version is available.", status_code=503)
    corpus_version_id, corpus_version_label = version
    return next_step(session, request, corpus_version_id, corpus_version_label)
