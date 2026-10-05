"""TTS transport/validation tests. Generated PCM is a test fixture, not live speech."""

import base64
import io
import json
import wave

import httpx
import pytest

from app.config import Settings
from app.integrations import sarvam
from app.schemas.enums import Language


@pytest.fixture
def wav_bytes() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 240)
    return output.getvalue()


@pytest.fixture
def settings(monkeypatch):
    settings = Settings(_env_file=None, SARVAM_API_KEY="test-only-secret")
    monkeypatch.setattr(sarvam, "get_settings", lambda: settings)
    return settings


@pytest.fixture
def transport(monkeypatch):
    original_client = httpx.AsyncClient

    def install(handler):
        monkeypatch.setattr(
            sarvam.httpx, "AsyncClient",
            lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
        )

    return install


@pytest.mark.parametrize("language", [language for language in Language if language != Language.AUTO])
def test_real_route_contract_maps_languages_and_returns_wav(client, settings, transport, wav_bytes, language):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://api.sarvam.ai/text-to-speech"
        assert request.headers["api-subscription-key"] == "test-only-secret"
        assert "authorization" not in request.headers
        body = json.loads(request.content)
        assert body == {
            "text": "An indexed provision.", "language_code": sarvam.LANGUAGE_CODES[language],
            "model": "bulbul:v3", "speaker": "shubh", "speech_sample_rate": 24000,
            "output_audio_codec": "wav",
        }
        return httpx.Response(200, json={"audios": [base64.b64encode(wav_bytes).decode()]})

    transport(handler)
    response = client.post("/v1/speech/tts", json={"text": "An indexed provision.", "language": language.value})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-speech-provider"] == "sarvam"
    assert response.content == wav_bytes
    assert len(calls) == 1


def test_auto_detects_language(client, settings, transport, wav_bytes, monkeypatch):
    monkeypatch.setattr(sarvam, "detect_language", lambda text, language: Language.HI)

    def handler(request):
        assert json.loads(request.content)["language_code"] == "hi-IN"
        return httpx.Response(200, json={"audios": [base64.b64encode(wav_bytes).decode()]})

    transport(handler)
    assert client.post("/v1/speech/tts", json={"text": "परीक्षण", "language": "auto"}).status_code == 200


def test_missing_key_does_not_contact_provider(client, settings, transport):
    settings.sarvam_api_key = type(settings.sarvam_api_key)("")
    transport(lambda request: pytest.fail("Missing keys must not contact Sarvam"))
    response = client.post("/v1/speech/tts", json={"text": "Answer", "language": "en"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "sarvam_not_configured"


@pytest.mark.parametrize(("status", "expected", "code"), [
    (401, 503, "sarvam_auth_failed"), (403, 503, "sarvam_auth_failed"),
    (429, 429, "sarvam_rate_limited"), (422, 502, "sarvam_request_failed"),
    (500, 502, "sarvam_request_failed"),
])
def test_provider_errors_are_safe_and_not_retried(client, settings, transport, status, expected, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "test-only-secret and private answer text"})

    transport(handler)
    response = client.post("/v1/speech/tts", json={"text": "Answer", "language": "en"})
    assert response.status_code == expected
    assert response.json()["error"]["code"] == code
    assert "test-only-secret" not in response.text and "private answer text" not in response.text
    assert len(calls) == 1


@pytest.mark.parametrize(("error_type", "status", "code"), [
    (httpx.ReadTimeout, 504, "sarvam_timeout"), (httpx.ConnectError, 502, "sarvam_unavailable"),
])
def test_transport_errors(client, settings, transport, error_type, status, code):
    def handler(request):
        raise error_type("test-only-secret", request=request)

    transport(handler)
    response = client.post("/v1/speech/tts", json={"text": "Answer"})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "test-only-secret" not in response.text


@pytest.mark.parametrize("payload", [
    {}, {"audios": []}, {"audios": ["not base64!"]}, {"audios": [""]},
    {"audios": [base64.b64encode(b"not a WAV").decode()]}, {"audios": [1]},
    {"audios": ["one", "two"]}, [],
])
def test_invalid_audio_is_never_served(client, settings, transport, payload):
    transport(lambda request: httpx.Response(200, json=payload))
    response = client.post("/v1/speech/tts", json={"text": "Answer"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "sarvam_invalid_audio"


def test_non_json_and_truncated_wav_are_rejected(client, settings, transport, wav_bytes):
    for response in [
        httpx.Response(200, text="invalid json"),
        httpx.Response(200, json={"audios": [base64.b64encode(wav_bytes[:-4]).decode()]}),
    ]:
        transport(lambda request, response=response: response)
        assert client.post("/v1/speech/tts", json={"text": "Answer"}).status_code == 502


@pytest.mark.parametrize("text", ["", "  \n  ", "x" * 2501])
def test_invalid_text_never_contacts_sarvam(client, settings, transport, text):
    transport(lambda request: pytest.fail("Invalid text must be rejected before the provider call"))
    assert client.post("/v1/speech/tts", json={"text": text}).status_code == 422


def test_key_is_masked_in_settings(settings):
    assert "test-only-secret" not in repr(settings)


def test_asr_remains_explicitly_unavailable(client):
    response = client.post("/v1/speech/asr", files={"audio": ("test.wav", b"fixture", "audio/wav")})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "local_asr_unavailable"
