"""Sarvam TTS for explicit read-aloud; ASR remains unavailable.

Answer generation, translation and embeddings continue to use local Ollama.
"""

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from app.core.errors import ApiError
from app.integrations.sarvam import synthesize_speech
from app.schemas.enums import Language
from app.schemas.misc import SpeechAsrResponse, SpeechTtsRequest

router = APIRouter(tags=["speech"])


@router.post("/speech/asr", response_model=SpeechAsrResponse)
async def speech_asr(
    audio: UploadFile = File(...), language: Language = Form(default=Language.AUTO)
) -> SpeechAsrResponse:
    await audio.close()
    raise ApiError(
        "local_asr_unavailable", "A local speech recognition engine is not configured. Please type your question.", 503
    )


@router.post(
    "/speech/tts",
    response_class=Response,
    responses={200: {"content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}}}},
)
async def speech_tts(request: SpeechTtsRequest) -> Response:
    """Read up to 2,500 characters using Sarvam. Requires a server-side API key."""
    audio, language_code = await synthesize_speech(request.text, request.language)
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Speech-Provider": "sarvam", "X-Speech-Language": language_code},
    )
