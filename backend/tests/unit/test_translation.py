from app.intake import translate
from app.schemas.enums import Language


def test_translation_uses_local_llm_and_restores_locked_terms(monkeypatch):
    calls = []

    class LocalClient:
        def generate_text(self, system, user):
            calls.append((system, user))
            return user

    monkeypatch.setattr(translate, "get_llm_client", LocalClient)
    assert "traditional knowledge" in translate.translate_to_english("यह traditional knowledge है", Language.HI)
    assert calls and "Translate" in calls[0][0]


def test_translation_chunks_long_text_with_no_loss():
    text = "word " * 900
    chunks = translate._translation_chunks(text)
    assert len(chunks) > 1 and all(len(c) <= 1800 for c in chunks)
    assert " ".join(chunks).split() == text.split()
