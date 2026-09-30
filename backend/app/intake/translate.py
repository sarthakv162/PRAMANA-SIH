"""§6.3 translate: English is the retrieval pivot language, so a non-English query is
translated before `route`/`retrieve`, and the answer language's claims are translated back
before rendering. Legal terms of art are masked before translation and restored after (a
term-lock glossary, §6.3, §8) so a translation model can't rephrase "traditional knowledge"
into something a citation search won't recognise.

`TRANSLATE_PROVIDER=llm` (§6.13) is the only provider implemented — Bhashini needs keys this
environment doesn't have; IndicTrans2 is explicitly a stretch goal (§6.3). An English query
never calls out to a model at all.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.generation.llm import get_llm_client
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


def translate_to_english(text: str, source_lang: Language) -> str:
    if source_lang == Language.EN or source_lang == Language.AUTO:
        return text

    masked, restore = _mask_terms(text)
    source_name = _LANGUAGE_NAMES.get(source_lang, source_lang.value)
    client = get_llm_client()
    translated = client.generate_text(
        system=(
            "Translate the user's text to English. Output only the translation, nothing "
            "else. Tokens shaped like __TERM_0__ are placeholders — copy them through "
            "unchanged, do not translate or remove them."
        ),
        user=f"Source language: {source_name}\n\nText:\n{masked}",
    )
    return _unmask(translated.strip(), restore)


def translate_from_english(text: str, target_lang: Language) -> str:
    if target_lang == Language.EN or target_lang == Language.AUTO:
        return text

    masked, restore = _mask_terms(text)
    target_name = _LANGUAGE_NAMES.get(target_lang, target_lang.value)
    client = get_llm_client()
    translated = client.generate_text(
        system=(
            f"Translate the user's text to {target_name}. Output only the translation, "
            "nothing else. Tokens shaped like __TERM_0__ are placeholders — copy them "
            "through unchanged."
        ),
        user=masked,
    )
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
    except Exception:
        return False

    original_tokens = set(original_en.lower().split())
    roundtrip_tokens = set(roundtrip.lower().split())
    if not original_tokens:
        return True
    overlap = len(original_tokens & roundtrip_tokens) / len(original_tokens)
    return overlap >= 0.5
