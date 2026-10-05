"""Local Ollama English-pivot translation with term locking (§6.3, §8).

Non-English questions are translated before retrieval; verified claim paraphrases and gaps
are translated only after their English text has been checked against source evidence. Statutory
evidence spans remain verbatim in the source language. An English question avoids translation.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.generation.llm import LlmError, get_llm_client
from app.schemas.enums import Language

_LANGUAGE_NAMES = {
    Language.HI: "Hindi",
    Language.TA: "Tamil",
    Language.BN: "Bengali",
    Language.MR: "Marathi",
    Language.TE: "Telugu",
    Language.GU: "Gujarati",
    Language.KN: "Kannada",
    Language.ML: "Malayalam",
    Language.PA: "Punjabi",
    Language.OR: "Odia",
}


@lru_cache
def _glossary_terms() -> list[str]:
    path = Path(__file__).parent / "glossary" / "terms.yaml"
    data = yaml.safe_load(path.read_text())
    return [t["term_en"] for t in data["terms"] if t.get("locked")]


def _mask_terms(text: str) -> tuple[str, dict[str, str]]:
    restore: dict[str, str] = {}
    masked = text
    for i, term in enumerate(_glossary_terms()):
        if term.lower() in masked.lower():
            placeholder = f"__TERM_{i}__"
            masked = re.sub(re.escape(term), placeholder, masked, flags=re.IGNORECASE)
            restore[placeholder] = term
    return masked, restore


def _unmask(text: str, restore: dict[str, str]) -> str:
    for placeholder, term in restore.items():
        text = text.replace(placeholder, term)
    return text


def _translation_chunks(text: str, limit: int = 1800) -> list[str]:
    """Split long text at sentence/word boundaries within the local prompt budget."""
    if len(text) <= limit:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    segments: list[str] = []
    current = ""
    for sentence in sentences:
        words = sentence.split()
        parts: list[str] = []
        part = ""
        for word in words:
            if len(word) > limit:
                if part:
                    parts.append(part)
                parts.extend(word[i : i + limit] for i in range(0, len(word), limit))
                part = ""
            elif not part or len(part) + len(word) + 1 <= limit:
                part = f"{part} {word}".strip()
            else:
                parts.append(part)
                part = word
        if part:
            parts.append(part)
        for item in parts:
            candidate = f"{current} {item}".strip()
            if current and len(candidate) > limit:
                segments.append(current)
                current = item
            else:
                current = candidate
    if current:
        segments.append(current)
    return segments


def _translate(text: str, source: Language, target: Language) -> str:
    translation_chunks = _translation_chunks(text)
    llm_client = get_llm_client()
    target_name = _LANGUAGE_NAMES.get(target, target.value)
    translated_chunks: list[str] = []
    for chunk in translation_chunks:
        translated_chunks.append(
            llm_client.generate_text(
                system=(
                    f"Translate the user's text to {target_name}. Output only the translation. "
                    "Copy tokens shaped like __TERM_0__ through unchanged."
                ),
                user=chunk,
            ).strip()
        )
    return " ".join(translated_chunks)


def translate_to_english(text: str, source_lang: Language) -> str:
    if source_lang == Language.EN or source_lang == Language.AUTO:
        return text

    masked, restore = _mask_terms(text)
    translated = _translate(masked, source_lang, Language.EN)
    return _unmask(translated.strip(), restore)


def translate_from_english(text: str, target_lang: Language) -> str:
    if target_lang == Language.EN or target_lang == Language.AUTO:
        return text

    masked, restore = _mask_terms(text)
    translated = _translate(masked, Language.EN, target_lang)
    return _unmask(translated.strip(), restore)


def back_translation_ok(original_en: str, translated: str, target_lang: Language) -> bool:
    """Translate `translated` back to English and check it's still close to `original_en`
    (§6.3). "Close" here is a cheap token-overlap ratio, not embedding similarity — good
    enough to catch a translation that changed the meaning, not to grade translation quality.
    """
    if target_lang == Language.EN or target_lang == Language.AUTO:
        return True
    try:
        roundtrip = translate_to_english(translated, target_lang)
    except LlmError:
        # Provider failures must reach the caller; treating them as a low confidence score
        # hides broken credentials and produces a misleading answer card.
        raise
    except Exception:
        return False

    original_tokens = set(original_en.lower().split())
    roundtrip_tokens = set(roundtrip.lower().split())
    if not original_tokens:
        return True
    overlap = len(original_tokens & roundtrip_tokens) / len(original_tokens)
    return overlap >= 0.5
