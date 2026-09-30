"""GET /v1/eval/latest — feeds the Eval screen (§7.3 screen 13, §9). `make eval` writes
eval/results/latest.json; this just serves whatever's there — never hard-coded numbers.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from app.config import get_settings
from app.core.errors import ApiError
from app.core.fixtures import load_fixture
from app.schemas.eval import EvalResults

router = APIRouter(tags=["eval"])

RESULTS_PATH = Path(__file__).resolve().parents[3] / "eval" / "results" / "latest.json"


@router.get("/eval/latest", response_model=EvalResults)
async def eval_latest() -> EvalResults:
    settings = get_settings()
    if settings.mock_mode:
        return EvalResults.model_validate(load_fixture("eval_results.json"))
    if not RESULTS_PATH.exists():
        raise ApiError(
            code="no_eval_run", message="Run `make eval` first.", status_code=404
        )
    return EvalResults.model_validate(json.loads(RESULTS_PATH.read_text()))
