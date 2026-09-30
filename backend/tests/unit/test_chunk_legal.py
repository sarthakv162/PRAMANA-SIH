"""Unit tests for the legal chunker (app/ingest/chunk_legal.py, app/ingest/parse_pdf.py).

Uses a small synthetic "Act" text rather than the real Patents Act PDF so these run fast and
don't need a PDF fixture — but the synthetic text intentionally reproduces every awkward
real-world shape the chunker has to handle: a front-matter TOC, a chapter heading with no
punctuation before the first section, an omitted clause represented by asterisks, an
amendment-inserted clause in "N[...]" brackets, an omitted *leading* clause (s.2-style), a
lettered clause with an embedded Explanation, and a numbered sub-section with its own nested
lettered clauses.
"""

from __future__ import annotations

from app.ingest.chunk_legal import chunk_document
from app.ingest.parse_pdf import Page, ParsedDocument, clean_page_text

SYNTHETIC_PAGE_1 = """1
THE SAMPLE ACT, 2024
ARRANGEMENT OF SECTIONS
CHAPTER I
PRELIMINARY
1. Short title.
CHAPTER II
EXCLUSIONS
3. What are not inventions.
CHAPTER I
PRELIMINARY
1. Short title.—This Act may be called the Sample Act, 2024.
CHAPTER II
EXCLUSIONS
3. What are not inventions.—The following are not inventions,—
(a) a frivolous invention;
2[(b) an invention contrary to public order or morality;]
1* * * *
(d) the mere discovery of a new form of a known substance.
Explanation.—For this clause, salts and esters are the same substance.
(e) traditional knowledge.

1. Clause (c) omitted by Act 1 of 2020.
2. Subs. by Act 2 of 2021, for clause (b).
4. Persons entitled.—(1) An application may be made by,—
(a) the inventor;
(b) the assignee.
(2) An application may be joint. He may exercise the powers set out in section 9.
(3) The application shall be in the prescribed form.
9. Term.—A patent shall subsist for twenty years.
"""


def _build_parsed_document(raw_page_text: str) -> ParsedDocument:
    page = Page(
        index=0,
        printed_number=1,
        raw_text=raw_page_text,
        text=clean_page_text(raw_page_text),
        density=100.0,
    )
    return ParsedDocument(pages=[page], full_text=page.text, page_offsets=[0])


def test_verbatim_offsets_match_full_text() -> None:
    parsed = _build_parsed_document(SYNTHETIC_PAGE_1)
    result = chunk_document("sample_act_2024", parsed)
    assert not result.warnings
    for chunk in result.chunks:
        assert parsed.full_text[chunk.char_start : chunk.char_end] == chunk.text


def test_skips_toc_front_matter() -> None:
    parsed = _build_parsed_document(SYNTHETIC_PAGE_1)
    result = chunk_document("sample_act_2024", parsed)
    by_key = {c.section_key: c for c in result.chunks}
    # The TOC's "1. Short title." (no em-dash) must not have produced a section.
    assert by_key["sample_act_2024#s1"].text.startswith("1. Short title.—This Act")


def test_lettered_clauses_and_omitted_clause_gap() -> None:
    parsed = _build_parsed_document(SYNTHETIC_PAGE_1)
    result = chunk_document("sample_act_2024", parsed)
    by_key = {c.section_key: c for c in result.chunks}

    assert by_key["sample_act_2024#s3(a)"].text == "(a) a frivolous invention;"
    # amendment-bracket digit+[...] is stripped, clause (b) text is clean
    expected_b = "(b) an invention contrary to public order or morality;"
    assert by_key["sample_act_2024#s3(b)"].text == expected_b
    # clause (c) was omitted by amendment — no chunk for it, (d) follows directly
    assert "sample_act_2024#s3(c)" not in by_key
    assert by_key["sample_act_2024#s3(d)"].text.startswith("(d) the mere discovery")
    assert "Explanation" not in by_key["sample_act_2024#s3(d)"].text


def test_explanation_split_into_own_chunk_with_edge() -> None:
    parsed = _build_parsed_document(SYNTHETIC_PAGE_1)
    result = chunk_document("sample_act_2024", parsed)
    by_key = {c.section_key: c for c in result.chunks}

    explanation = by_key["sample_act_2024#s3(d)-explanation"]
    assert explanation.text.startswith("Explanation.—For this clause")
    assert explanation.parent_key == "sample_act_2024#s3(d)"
    assert any(
        e.src_key == "sample_act_2024#s3(d)" and e.dst_key == "sample_act_2024#s3(d)-explanation"
        and e.kind == "proviso_of"
        for e in result.edges
    )


def test_chapter_heading_not_absorbed_into_section_text() -> None:
    parsed = _build_parsed_document(SYNTHETIC_PAGE_1)
    result = chunk_document("sample_act_2024", parsed)
    by_key = {c.section_key: c for c in result.chunks}

    assert "CHAPTER" not in by_key["sample_act_2024#s3(e)"].text
    assert by_key["sample_act_2024#s4"].path[0] == "Chapter II"  # inherits until s4's own chapter


def test_nested_numbered_then_lettered_clauses() -> None:
    parsed = _build_parsed_document(SYNTHETIC_PAGE_1)
    result = chunk_document("sample_act_2024", parsed)
    by_key = {c.section_key: c for c in result.chunks}

    assert by_key["sample_act_2024#s4(1)"].text.startswith("(1) An application may be made by,—")
    assert by_key["sample_act_2024#s4(1)(a)"].text == "(a) the inventor;"
    assert by_key["sample_act_2024#s4(1)(b)"].text == "(b) the assignee."
    assert by_key["sample_act_2024#s4(2)"].text.startswith("(2) An application may be joint.")
    expected_s4_3 = "(3) The application shall be in the prescribed form."
    assert by_key["sample_act_2024#s4(3)"].text == expected_s4_3


def test_cross_reference_to_a_section_number_is_not_mistaken_for_its_start() -> None:
    """Regression test: "…set out in section 9. (3) The application…" must not be read as
    section 9 starting with subsection (3) — (3) is section 4's own third subsection, and
    the real section 9 (found later, with its own "Term.—" heading) must not collide with a
    phantom one from the cross-reference.
    """
    parsed = _build_parsed_document(SYNTHETIC_PAGE_1)
    result = chunk_document("sample_act_2024", parsed)
    keys = [c.section_key for c in result.chunks]

    assert keys.count("sample_act_2024#s9") == 1
    by_key = {c.section_key: c for c in result.chunks}
    assert by_key["sample_act_2024#s9"].text == "9. Term.—A patent shall subsist for twenty years."
    assert "sample_act_2024#s9(3)" not in by_key
