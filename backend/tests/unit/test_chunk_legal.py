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


def test_duplicate_section_number_preserves_later_text_with_unique_page_key() -> None:
    parsed = _build_parsed_document(
        SYNTHETIC_PAGE_1 + "\n9. Term.—A duplicated schedule entry.\n"
    )

    result = chunk_document("sample_act_2024", parsed)

    sections_nine = [c for c in result.chunks if c.section_key.startswith("sample_act_2024#s9")]
    assert len(sections_nine) == 2
    assert sections_nine[0].section_key == "sample_act_2024#s9"
    assert sections_nine[0].text == "9. Term.—A patent shall subsist for twenty years."
    assert sections_nine[1].section_key == "sample_act_2024#s9-p1"
    assert sections_nine[1].text == "9. Term.—A duplicated schedule entry."
    assert any(
        "repeated heading sample_act_2024#s9 on page 1 was retained as sample_act_2024#s9-p1"
        in warning
        for warning in result.warnings
    )


def test_treaty_articles_skip_contents_and_preserve_verbatim_offsets() -> None:
    treaty_text = """CONVENTION
CONTENTS
Article 1 Objectives
Article 2 Use of terms
Article 3 Objective
PREAMBLE
The Parties to this Convention,
Article 1. Objective
The objective of this Convention is to ensure conservation.
Article 2. Use of terms
For the purposes of this Convention, the terms apply.
Article 3. Relationship with other agreements
The provisions do not affect rights and obligations.
"""
    parsed = _build_parsed_document(treaty_text)

    result = chunk_document("sample_treaty", parsed)

    by_key = {chunk.section_key: chunk for chunk in result.chunks}
    assert set(by_key) == {
        "sample_treaty#art1",
        "sample_treaty#art2",
        "sample_treaty#art3",
    }
    assert by_key["sample_treaty#art1"].text.startswith("Article 1. Objective")
    assert "CONTENTS" not in by_key["sample_treaty#art1"].text
    for chunk in result.chunks:
        assert parsed.full_text[chunk.char_start : chunk.char_end] == chunk.text


def test_rules_use_standalone_ordered_headings_and_skip_inline_references() -> None:
    rules_text = """THE SAMPLE RULES, 2024
TABLE OF CONTENTS
Rule 1. Short title
Rule 2. Definitions
CHAPTER I
PRELIMINARY
Rule 1
Short title and commencement

These rules may be called the Sample Rules, 2024. Rule 99 is referenced here.
CHAPTER II
APPLICATIONS
Rule 2
Definitions

In these rules, terms in Rule 1 have the meanings assigned to them.
"""
    parsed = _build_parsed_document(rules_text)

    result = chunk_document("sample_rules", parsed, doc_type="rule")

    by_key = {chunk.section_key: chunk for chunk in result.chunks}
    assert set(by_key) == {"sample_rules#r1", "sample_rules#r2"}
    assert by_key["sample_rules#r1"].heading == "Short title and commencement"
    assert "Rule 99 is referenced here." in by_key["sample_rules#r1"].text
    assert "CHAPTER II" not in by_key["sample_rules#r1"].text
    for chunk in result.chunks:
        assert parsed.full_text[chunk.char_start : chunk.char_end] == chunk.text


def test_wrapped_treaty_headings_ignore_wrapped_references_and_map_their_own_offsets() -> None:
    parsed = _build_parsed_document(
        "Article\n1\nObjectives\nThe measures under Article 2 apply.\n"
        "The obligations in\nArticle 16 thereof remain applicable.\n"
        "Article\n2\nDefinitions\nTerms used in this agreement have these meanings.\n"
        "Article 3\nScope\nThis agreement covers the stated measures.\n"
    )

    result = chunk_document("wrapped_treaty", parsed)
    by_key = {chunk.section_key: chunk for chunk in result.chunks}

    assert set(by_key) == {"wrapped_treaty#art1", "wrapped_treaty#art2", "wrapped_treaty#art3"}
    assert "Article 16 thereof" in by_key["wrapped_treaty#art1"].text
    assert by_key["wrapped_treaty#art2"].text.startswith("Article 2 Definitions")
    assert by_key["wrapped_treaty#art2"].heading == "Definitions"
    for chunk in result.chunks:
        assert parsed.full_text[chunk.char_start : chunk.char_end] == chunk.text


def test_booklet_article_order_preserves_pages_instead_of_citing_incomplete_article_run() -> None:
    parsed = _build_parsed_document(
        "Article 3\nScope\nScope text.\nArticle 4\nCooperation\nCooperation text.\n"
        "Article 1\nObjectives\nObjectives text.\nArticle 2\nDefinitions\nDefinitions text.\n"
        "Article 5\nImplementation\nImplementation text.\n"
    )

    result = chunk_document("booklet", parsed)

    assert all("#p" in chunk.section_key for chunk in result.chunks)
    assert any("out of reading order" in warning for warning in result.warnings)
    assert "Implementation text." in result.chunks[-1].text


def test_unstructured_notice_falls_back_to_verbatim_page_chunks() -> None:
    parsed = _build_parsed_document(
        "GOVERNMENT OF INDIA\nNotification S.O. 123(E)\n"
        "The amendment comes into force on 1 April 2024.\n"
    )

    result = chunk_document("commencement_notice", parsed, doc_type="notification")

    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.section_key == "commencement_notice#p1"
    assert "1 April 2024" in chunk.text
    assert parsed.full_text[chunk.char_start : chunk.char_end] == chunk.text
    assert any("page-level chunks" in warning for warning in result.warnings)
