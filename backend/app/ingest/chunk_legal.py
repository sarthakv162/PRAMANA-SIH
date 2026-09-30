"""Legal chunker (§6.2 step 3): split a parsed Act into Chapter → Section → clause chunks.

This is tuned to the layout Indian central Acts actually use (India Code / IP India PDFs):
a front-matter "ARRANGEMENT OF SECTIONS" table of contents that repeats the whole outline
before the operative text starts, `CHAPTER <roman>` headings, sections numbered
`N.` / `NA.` with a title ending "—", and clauses inside a section numbered either `(1)(2)…`
or lettered `(a)(b)…` (never both at the same nesting level in practice — a numbered
sub-section's own lettered sub-clauses, e.g. s.6(1)(a)(b)(c), are kept as one chunk under
the sub-section rather than split further; no text is lost, just less granular citation).

A `Provided that…` proviso or an embedded `Explanation.—…` inside a clause is split into
its own chunk and linked back with a `proviso_of` edge (src = parent, dst = proviso) rather
than folded into the parent's verbatim text, so the resolve step (§6.4) can choose to
co-fetch it via `retrieval/legal_graph.py` instead of always paying for its length.

Output is a plain data structure (`ChunkDraft`/`Edge`) — nothing here touches the database;
`ingest/cli.py` is responsible for writing these to `sections`/`chunks`/`edges`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.hashing import sha256_hex
from app.ingest.parse_pdf import ParsedDocument, page_for_offset

# Body start: Acts open with a full front-matter TOC that repeats every chapter/section
# heading; the operative text repeats "CHAPTER I" once more right before section 1's real
# body. Taking the *last* match skips the TOC without needing to parse it. Some Acts print
# "CHAPTER-I" (hyphen, no space) instead of "CHAPTER I" — `[\s-]+` covers both.
_CHAPTER_I_MARKER = re.compile(r"\bCHAPTER[\s-]+I\b")

_CHAPTER_HEADING = re.compile(r"\bCHAPTER[\s-]+([IVXLCDM]+)\b\s*([A-Z][A-Z ,\-]{2,80})?")

# "3. What are not inventions.—" / "11A. Publication of applications.—" — a section number
# (with an optional trailing amendment letter) followed by a Title Case heading and an
# em-dash/hyphen introducing the body. The em-dash requirement (a heading-only convention,
# never used mid-sentence) is what actually rejects cross-references like "sections 29, 30
# and 31" — those never happen to be followed by ".<capitalised phrase>.—"; the monotonic
# section-number check in `chunk_document` catches anything that still slips through.
_SECTION_START = re.compile(r"(?<!\d)(\d{1,3}[A-Z]{0,2})\.\s+([A-Z][^.]{2,160}?)[,.]\s*[—-]")

# A repealed section reads "5. [<original heading>.] Omitted by <amending Act>…" instead of
# the usual "Title.—" shape.
_SECTION_START_OMITTED = re.compile(r"(?<!\d)(\d{1,3}[A-Z]{0,2})\.\s+(\[[^\]]*\])\s*(?=Omitted\b)")

# Some Acts (e.g. the Biological Diversity Act, 2002) give a section no heading at all —
# straight from the number into its first numbered sub-section, "4. (1) No person shall…".
# Guard against "…exercise the powers set out in section 88. (6) In considering…" — a
# cross-reference to another section's number, immediately followed by an unrelated
# section's own genuine subsection marker. Real section starts are never preceded by the
# word "section(s)".
_NOT_A_CROSS_REFERENCE = r"(?<!section )(?<!Section )(?<!sections )(?<!Sections )"
_SECTION_START_NO_HEADING = re.compile(
    _NOT_A_CROSS_REFERENCE + r"(?<!\d)(\d{1,3}[A-Z]{0,2})\.\s+(?=\(\d+\))"
)

_NUMBERED_CLAUSE = re.compile(r"(?<!\S)\((\d{1,3})\)\s")
_LETTERED_CLAUSE = re.compile(r"(?<!\S)\(([a-z]{1,3})\)\s")

_EXPLANATION_SPLIT = re.compile(r"(?<=\s)(Explanation(?:\s?\d)?\.[—-])")
_PROVISO_SPLIT = re.compile(r"(?<=\s)(Provided (?:that|further|also)[,:]?)\s")

# See the last-matched-section guard in chunk_document — this is generous (the longest
# legitimate section body seen across both real Acts ingested so far is ~2KB) but not
# unbounded.
MAX_UNBOUNDED_TAIL_CHARS = 4000


@dataclass
class ChunkDraft:
    section_key: str
    parent_key: str | None
    path: list[str]
    heading: str | None
    text: str
    char_start: int
    char_end: int
    page_start: int
    page_end: int


@dataclass
class EdgeDraft:
    src_key: str
    dst_key: str
    kind: str  # 'proviso_of' | 'refers_to' | 'defined_in' | 'amends' | 'exception_to'


@dataclass
class ChunkingResult:
    chunks: list[ChunkDraft] = field(default_factory=list)
    edges: list[EdgeDraft] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _find_body_start(full_text: str) -> int:
    matches = list(_CHAPTER_I_MARKER.finditer(full_text))
    return matches[-1].start() if matches else 0


def _split_proviso_and_explanation(
    section_key: str, text: str, char_start: int
) -> tuple[str, list[ChunkDraft], list[EdgeDraft]]:
    """Peel a trailing `Explanation.—`/`Provided that…` off a clause's text.

    Only the first such marker is split out (the common case is one proviso or one
    explanation per clause); anything after a second marker stays attached to the first
    child rather than recursing, which is a deliberate simplification, not a parsing bug.
    """
    for pattern, suffix, kind in (
        (_EXPLANATION_SPLIT, "explanation", "proviso_of"),
        (_PROVISO_SPLIT, "proviso", "proviso_of"),
    ):
        match = pattern.search(text)
        if match:
            main_text = text[: match.start()].rstrip()
            child_text = text[match.start() :].strip()
            child_key = f"{section_key}-{suffix}"
            child_start = char_start + match.start()
            child = ChunkDraft(
                section_key=child_key,
                parent_key=section_key,
                path=[],  # filled in by the caller once it knows the parent's path
                heading=suffix.capitalize(),
                text=child_text,
                char_start=child_start,
                char_end=char_start + len(text),
                page_start=0,
                page_end=0,
            )
            edge = EdgeDraft(src_key=section_key, dst_key=child_key, kind=kind)
            return main_text, [child], [edge]
    return text, [], []


def _valid_numbered_run(body: str, matches: list[re.Match[str]]) -> list[re.Match[str]]:
    """Subsection lists "(1)(2)(3)…" always start immediately after the heading's em-dash —
    a bare "(1)" deep in a sentence is a cross-reference (e.g. "sub-section (1) of section
    20 of the Atomic Energy Act"), not a list. Require the first match near the very start
    of the body, then keep only a strictly-sequential 1, 2, 3, … run (no gaps: unlike
    lettered clauses, sub-sections are never omitted by amendment in a way that skips a
    number outright).
    """
    if not matches or matches[0].start() > 5:
        return []
    accepted = []
    expected = 1
    for m in matches:
        if int(m.group(1)) != expected:
            break
        accepted.append(m)
        expected += 1
    return accepted


def _valid_lettered_run(matches: list[re.Match[str]]) -> list[re.Match[str]]:
    """Lettered clause lists strictly increase through the alphabet (gaps are fine — a
    clause can be omitted by amendment, e.g. s.3(g), and the *first* clause(s) can be
    omitted too, e.g. s.2(1)(a)/(aa) in the Patents Act, so the list doesn't have to start
    at "(a)"). A lone match with nothing after it, or letters that go backwards/repeat,
    means this wasn't a list at all.
    """
    if len(matches) < 2:
        return []
    accepted = [matches[0]]
    last_label = matches[0].group(1)
    for m in matches[1:]:
        if m.group(1) <= last_label:
            break
        accepted.append(m)
        last_label = m.group(1)
    return accepted


def _split_clauses(
    section_key: str,
    body: str,
    body_start: int,
    parent_path: list[str],
    allow_numbered: bool = True,
) -> list[tuple[str, str, int, int]]:
    """Return `(clause_key, clause_text, char_start, char_end)` for one nesting level.

    Marker type (numbered vs lettered) is decided from whichever appears first in the
    section's body — sections use one or the other as their outermost list, never both.
    `allow_numbered=False` is used for the one level of recursion `chunk_document` does into
    a numbered sub-section's own text (§6.2: "(1) …(a)(b)(c)…"), where a fresh `(1)`-shaped
    match inside the clause text would almost always be an internal cross-reference, not
    another nesting level.
    """
    numbered = (
        _valid_numbered_run(body, list(_NUMBERED_CLAUSE.finditer(body))) if allow_numbered else []
    )
    lettered = _valid_lettered_run(list(_LETTERED_CLAUSE.finditer(body)))

    if numbered and (not lettered or numbered[0].start() <= lettered[0].start()):
        markers, fmt = numbered, "({})"
    elif lettered:
        markers, fmt = lettered, "({})"
    else:
        return []

    results: list[tuple[str, str, int, int]] = []
    for i, m in enumerate(markers):
        start = m.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(body)
        label = m.group(1)
        clause_key = f"{section_key}{fmt.format(label)}"
        clause_text = body[start:end].strip()
        results.append(
            (clause_key, clause_text, body_start + start, body_start + start + len(clause_text))
        )
    return results


def _sort_key(num_raw: str) -> float:
    num_value = float(re.sub(r"[A-Z]+$", "", num_raw) or 0)
    letter_suffix = re.sub(r"^\d+", "", num_raw)
    return num_value + (0.1 * (ord(letter_suffix[:1]) - 64) if letter_suffix else 0)


def _fill_numeric_gaps(full_text: str, matches: list[re.Match[str]]) -> list[re.Match[str]]:
    """Some sections are plain prose with no title, no em-dash, and no immediate clause
    marker — nothing distinguishes their *start* from ordinary text (e.g. Biological
    Diversity Act s.4: "4. No person shall, without…"). Those can only be found once we
    already trust the section *before* and *after* them: having confirmed section 3 and
    section 5 are real, a plain "4. <Capital…>" in the gap between them is safe to accept
    on position alone, without any of the shape requirements the primary patterns need.

    Only fills single-integer gaps (3 → 5 tries "4"); a numbered Act section skipping more
    than one number in a row without a lettered/bracket marker chunk_legal already handles
    would be unusual enough to warrant a warning instead of a guess (see caller).
    """
    confirmed: list[re.Match[str]] = []
    last_number = 0.0
    for m in matches:
        key = _sort_key(m.group(1))
        if key < last_number:
            continue
        last_number = key
        confirmed.append(m)

    filled: list[re.Match[str]] = list(confirmed)
    for prev, nxt in zip(confirmed, confirmed[1:], strict=False):
        try:
            prev_num, next_num = int(prev.group(1)), int(nxt.group(1))
        except ValueError:
            continue  # one of them has a letter suffix (e.g. "11A") — skip, too ambiguous
        if next_num - prev_num == 2:
            missing = prev_num + 1
            gap_pattern = re.compile(_NOT_A_CROSS_REFERENCE + rf"(?<!\d)({missing})\.\s+(?=[A-Z])")
            gap_match = gap_pattern.search(full_text, prev.end(), nxt.start())
            if gap_match:
                filled.append(gap_match)

    return sorted(filled, key=lambda m: m.start())


def chunk_document(doc_short_key: str, parsed: ParsedDocument) -> ChunkingResult:
    result = ChunkingResult()
    full_text = parsed.full_text
    body_start = _find_body_start(full_text)

    section_matches = sorted(
        [
            *_SECTION_START.finditer(full_text, body_start),
            *_SECTION_START_OMITTED.finditer(full_text, body_start),
            *_SECTION_START_NO_HEADING.finditer(full_text, body_start),
        ],
        key=lambda m: m.start(),
    )
    if not section_matches:
        result.warnings.append(f"{doc_short_key}: no section headings found after body start")
        return result

    last_number = 0.0

    seen_starts: set[int] = set()
    deduped = []
    for m in section_matches:
        if m.start() not in seen_starts:
            seen_starts.add(m.start())
            deduped.append(m)
    section_matches = _fill_numeric_gaps(full_text, deduped)

    # Chapter heading text sits *between* two sections (or before the first one) and must
    # never be absorbed into either section's stored text. `_last_chapter_heading` finds the
    # last chapter heading in a span (a chapter heading is occasionally followed by a repeated
    # "SECTIONS" sub-header in the TOC-style layout, but never inside operative text) and
    # returns `(path, truncate_at)` so the caller can both update the path going forward and
    # cut the preceding section's body off before the heading starts.
    def _last_chapter_heading(span: str) -> tuple[list[str] | None, int | None]:
        last_match = None
        for chapter_match in _CHAPTER_HEADING.finditer(span):
            last_match = chapter_match
        if last_match is None:
            return None, None
        roman, title = last_match.group(1), (last_match.group(2) or "").strip()
        path = [f"Chapter {roman}"] + ([title.title()] if title else [])
        return path, last_match.start()

    chapter_path, _ = _last_chapter_heading(full_text[body_start : section_matches[0].start()])
    chapter_path = chapter_path or []

    for i, m in enumerate(section_matches):
        num_raw = m.group(1)
        heading = m.group(2).strip().strip("[]") if len(m.groups()) > 1 else None
        sort_key = _sort_key(num_raw)
        if sort_key < last_number:
            # Almost certainly a cross-reference ("section 3, 4 and 5") that slipped past
            # the anchor, not a real heading — skip it rather than emit a bogus section.
            continue
        last_number = sort_key

        section_key = f"{doc_short_key}#s{num_raw}"
        is_last_match = i + 1 >= len(section_matches)
        next_start = section_matches[i + 1].start() if not is_last_match else len(full_text)

        # The last matched section has nothing bounding its tail — if the source PDF has
        # trailing content this chunker was never meant to parse (a second document bound
        # into the same PDF, e.g. Rules appended after an Act, notification signatories,
        # schedules), that whole tail would otherwise get glued onto the last section's
        # text. Cap it and warn instead of silently absorbing an arbitrary amount of
        # unrelated content.
        if is_last_match and next_start - m.end() > MAX_UNBOUNDED_TAIL_CHARS:
            next_start = m.end() + MAX_UNBOUNDED_TAIL_CHARS
            result.warnings.append(
                f"{doc_short_key}: last section {section_key} had an unbounded tail "
                f"(no following section found) — truncated at {MAX_UNBOUNDED_TAIL_CHARS} "
                "chars; check for trailing content (rules/schedules/notifications) this "
                "chunker wasn't meant to ingest."
            )

        trailing_span = full_text[m.end() : next_start]
        next_chapter_path, truncate_at = _last_chapter_heading(trailing_span)
        body_end = m.end() + truncate_at if truncate_at is not None else next_start

        # Trim precisely (not `.strip()`) so char offsets stay exact — required for the
        # verbatim invariant (I3): `EvidenceSpan.text` must equal `full_text[start:end]`.
        raw_body = full_text[m.end() : body_end]
        left_trim = len(raw_body) - len(raw_body.lstrip())
        section_body = raw_body.strip()
        body_char_start = m.end() + left_trim

        section_char_start = m.start()
        path = [*chapter_path, f"Section {num_raw}", *([heading] if heading else [])]

        if next_chapter_path is not None:
            chapter_path = next_chapter_path

        clauses = _split_clauses(section_key, section_body, body_char_start, path)
        if not clauses:
            full_section_text = full_text[m.start() : body_end].rstrip()
            section_char_end = m.start() + len(full_section_text)
            result.chunks.append(
                ChunkDraft(
                    section_key=section_key,
                    parent_key=None,
                    path=path,
                    heading=heading,
                    text=full_section_text,
                    char_start=section_char_start,
                    char_end=section_char_end,
                    page_start=page_for_offset(parsed, section_char_start),
                    page_end=page_for_offset(parsed, max(section_char_end - 1, section_char_start)),
                )
            )
            continue

        # The heading chunk also carries any intro prose before the first clause marker
        # (e.g. s.3's "The following are not inventions … Act,—") — that text is part of
        # the section, not filler to discard.
        section_head_end = clauses[0][2] if clauses else m.end()
        heading_text = full_text[m.start() : section_head_end].rstrip()
        heading_char_end = m.start() + len(heading_text)
        result.chunks.append(
            ChunkDraft(
                section_key=section_key,
                parent_key=None,
                path=path,
                heading=heading,
                text=heading_text,
                char_start=section_char_start,
                char_end=heading_char_end,
                page_start=page_for_offset(parsed, section_char_start),
                page_end=page_for_offset(parsed, heading_char_end - 1),
            )
        )
        for clause_key, clause_text, c_start, _c_end in clauses:
            label = clause_key[len(section_key) :]
            clause_path = [*path, f"clause {label}"]
            main_text, children, edges = _split_proviso_and_explanation(
                clause_key, clause_text, c_start
            )

            # One level of recursion: a numbered sub-section ("(1) … (a)(b)(c)") often has
            # its own lettered list — split that out too instead of storing it as one chunk.
            sub_clauses = (
                _split_clauses(clause_key, main_text, c_start, clause_path, allow_numbered=False)
                if re.fullmatch(r"\(\d{1,3}\)", label)
                else []
            )
            head_text = main_text[: sub_clauses[0][2] - c_start] if sub_clauses else main_text
            head_text = head_text.rstrip()
            result.chunks.append(
                ChunkDraft(
                    section_key=clause_key,
                    parent_key=section_key,
                    path=clause_path,
                    heading=None,
                    text=head_text,
                    char_start=c_start,
                    char_end=c_start + len(head_text),
                    page_start=page_for_offset(parsed, c_start),
                    page_end=page_for_offset(parsed, max(c_start + len(head_text) - 1, c_start)),
                )
            )
            for sub_key, sub_text, s_start, _s_end in sub_clauses:
                sub_label = sub_key[len(clause_key) :]
                sub_main, sub_children, sub_edges = _split_proviso_and_explanation(
                    sub_key, sub_text, s_start
                )
                result.chunks.append(
                    ChunkDraft(
                        section_key=sub_key,
                        parent_key=clause_key,
                        path=[*clause_path, f"clause {sub_label}"],
                        heading=None,
                        text=sub_main,
                        char_start=s_start,
                        char_end=s_start + len(sub_main),
                        page_start=page_for_offset(parsed, s_start),
                        page_end=page_for_offset(parsed, max(s_start + len(sub_main) - 1, s_start)),
                    )
                )
                for sub_child in sub_children:
                    sub_child.path = [*clause_path, f"clause {sub_label}", sub_child.heading or ""]
                    sub_child.page_start = page_for_offset(parsed, sub_child.char_start)
                    sub_child.page_end = page_for_offset(
                        parsed, max(sub_child.char_end - 1, sub_child.char_start)
                    )
                    result.chunks.append(sub_child)
                result.edges.extend(sub_edges)

            for child in children:
                child.path = [*clause_path, child.heading or ""]
                child.page_start = page_for_offset(parsed, child.char_start)
                child.page_end = page_for_offset(parsed, max(child.char_end - 1, child.char_start))
                result.chunks.append(child)
            result.edges.extend(edges)

    return result


def chunk_sha256(text: str) -> str:
    return sha256_hex(text)
