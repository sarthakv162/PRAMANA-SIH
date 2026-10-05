"""Sarvam Bulbul v3 TTS, called only for user-requested answer read-aloud.

REST contract: https://docs.sarvam.ai/api-reference/text-to-speech/convert
The API key never reaches the browser or provider error messages returned to it.
"""

from __future__ import annotations

import base64
import binascii
import io
import wave

import httpx

from app.config import get_settings
from app.core.errors import ApiError
from app.intake.langid import detect_language
from app.schemas.enums import Language

TTS_URL = "https://api.sarvam.ai/text-to-speech"
LANGUAGE_CODES = {
    Language.EN: "en-IN", Language.HI: "hi-IN", Language.TA: "ta-IN",
    Language.BN: "bn-IN", Language.MR: "mr-IN", Language.TE: "te-IN",
    Language.GU: "gu-IN", Language.KN: "kn-IN", Language.ML: "ml-IN",
    Language.PA: "pa-IN", Language.OR: "od-IN",
}
MAX_AUDIO_BYTES = 32 * 1024 * 1024


def _decode_wav(payload: object) -> bytes:
    try:
        if not isinstance(payload, dict):
            raise ValueError("Expected an audio response")
        audios = payload.get("audios")
        if not isinstance(audios, list) or len(audios) != 1 or not isinstance(audios[0], str):
            raise ValueError("Expected one audio for one input text")
        if len(audios[0]) > ((MAX_AUDIO_BYTES + 2) // 3) * 4:
            raise ValueError("Audio exceeds the response budget")
        audio = base64.b64decode(audios[0], validate=True)
        with wave.open(io.BytesIO(audio), "rb") as wav:
            frames = wav.getnframes()
            if frames <= 0 or wav.getnchannels() not in (1, 2) or wav.getsampwidth() != 2:
                raise ValueError("Empty or unsupported PCM audio")
            expected_bytes = frames * wav.getnchannels() * wav.getsampwidth()
            if len(wav.readframes(frames)) != expected_bytes:
                raise ValueError("Truncated audio")
        return audio
    except (ValueError, TypeError, binascii.Error, wave.Error, EOFError) as exc:
        raise ApiError("sarvam_invalid_audio", "Sarvam returned invalid speech audio. Please retry.", 502) from exc


async def synthesize_speech(text: str, language: Language) -> tuple[bytes, str]:
    settings = get_settings()
    key = settings.sarvam_api_key.get_secret_value().strip()
    if not key:
        raise ApiError("sarvam_not_configured", "Configure SARVAM_API_KEY on the backend to enable read-aloud.", 503)
    language_code = LANGUAGE_CODES[detect_language(text, language)]
    try:
        async with httpx.AsyncClient(timeout=settings.sarvam_tts_timeout_s) as client:
            response = await client.post(
                TTS_URL,
                headers={"api-subscription-key": key},
                json={
                    "text": text,
                    "language_code": language_code,
                    "model": settings.sarvam_tts_model,
                    "speaker": settings.sarvam_tts_speaker,
                    "speech_sample_rate": 24000,
                    "output_audio_codec": "wav",
                },
            )
    except httpx.TimeoutException as exc:
        raise ApiError("sarvam_timeout", "Sarvam speech generation timed out. Please retry.", 504) from exc
    except httpx.RequestError as exc:
        raise ApiError("sarvam_unavailable", "Unable to reach Sarvam speech. Please retry.", 502) from exc

    if response.status_code in (401, 403):
        raise ApiError("sarvam_auth_failed", "Sarvam rejected the speech credentials. Check SARVAM_API_KEY.", 503)
    if response.status_code == 429:
        raise ApiError("sarvam_rate_limited", "Sarvam's speech limit was reached. Please try again later.", 429)
    if not response.is_success:
        raise ApiError("sarvam_request_failed", "Sarvam could not generate speech. Check the voice configuration.", 502)
    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiError("sarvam_invalid_audio", "Sarvam returned invalid speech audio. Please retry.", 502) from exc
    return _decode_wav(payload), language_code
