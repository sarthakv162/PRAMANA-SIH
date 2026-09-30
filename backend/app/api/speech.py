"""POST /v1/speech/asr, POST /v1/speech/tts. Bhashini adapter is M4 work (§6.12).

Until Bhashini keys/adapter exist, the real endpoints return 503 so the frontend falls back to
browser speech, exactly as §7.4 specifies — that fallback contract holds in mock mode too.
"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.core.errors import ApiError
from app.schemas.misc import SpeechAsrResponse, SpeechTtsRequest

router = APIRouter(tags=["speech"])

_UNAVAILABLE = ApiError(
    code="speech_unavailable",
    message="Speech backend not configured; use the browser speech APIs.",
    status_code=503,
)


@router.post("/speech/asr", response_model=SpeechAsrResponse)
async def speech_asr(audio: UploadFile = File(...)) -> SpeechAsrResponse:
    raise _UNAVAILABLE


@router.post("/speech/tts")
async def speech_tts(request: SpeechTtsRequest) -> None:
    raise _UNAVAILABLE
