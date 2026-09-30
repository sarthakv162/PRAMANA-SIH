"""Language identification (§6.3). `langdetect` (pure-Python, no model download) rather
than fastText — fastText's compressed model is another few-hundred-MB download this
environment hasn't staged, and `langdetect` covers the target language list (§5.1) well
enough for a prototype; swap it for fastText later if accuracy on short queries demands it.
"""

from __future__ import annotations

from langdetect import DetectorFactory, LangDetectException, detect

from app.schemas.enums import Language

DetectorFactory.seed = 0  # deterministic output — langdetect is otherwise randomised

_SUPPORTED = {lang.value for lang in Language} - {Language.AUTO.value}


def detect_language(text: str, requested: Language = Language.AUTO) -> Language:
    """Honours an explicit `language` request (§6.4 `frame`); only runs detection for
    `auto`. Falls back to English if detection fails (empty/too-short text) or lands on a
    language PRAMANA doesn't support.
    """
    if requested != Language.AUTO:
        return requested
    try:
        detected = detect(text)
    except LangDetectException:
        return Language.EN
    return Language(detected) if detected in _SUPPORTED else Language.EN
