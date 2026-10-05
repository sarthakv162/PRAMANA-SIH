from datetime import date

from app.generation.prompts import render_qa_prompt


def test_prompt_preserves_parent_context_and_avoids_unstated_patentability_inferences() -> None:
    system, user = render_qa_prompt(
        "Can traditional knowledge be patented in India?",
        ["IN"],
        date(2026, 10, 3),
        "[E1] parent: the following are not inventions; "
        "[E2] section 3(p): an invention that is, in effect, traditional knowledge.",
    )

    assert "cite both" in system
    assert "A user's question is not evidence" in system
    assert "[E1] parent" in user
    assert "Do not infer unstated consequences" in system
    assert "repeat a canned answer" in system
