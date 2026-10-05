from datetime import date

from sqlalchemy.dialects import postgresql

from app.retrieval.repo import ancestor_section_ids, fetch_chunks_for_section, fetch_section_by_key


class _Result:
    def all(self):
        return []


class _CaptureSession:
    statement = None

    def execute(self, statement):
        self.statement = statement
        return _Result()


class _ParentResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _SectionRow:
    def __init__(self, section_id, parent_id):
        self.id = section_id
        self.parent_id = parent_id


class _AncestorSession:
    def __init__(self):
        self.statements = []
        self.results = [
            [_SectionRow("clause", "section")],
            [_SectionRow("section", "chapter")],
            [_SectionRow("chapter", None)],
        ]

    def execute(self, statement):
        self.statements.append(statement)
        return _ParentResult(self.results.pop(0))


def test_section_fetch_uses_version_jurisdiction_and_as_of_gate() -> None:
    session = _CaptureSession()
    fetch_chunks_for_section(
        session,
        "section-id",
        "corpus-version-id",
        ["IN"],
        date(2024, 1, 1),
    )
    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "corpus_version_id" in sql
    assert "jurisdiction" in sql
    assert "effective_from" in sql
    assert "effective_to" in sql


def test_ancestor_fetch_walks_to_heading_with_corpus_version_gate() -> None:
    session = _AncestorSession()
    ancestors = ancestor_section_ids(session, ["clause"], "corpus-version-id")

    assert ancestors == ["chapter", "section"]
    assert len(session.statements) == 3
    for statement in session.statements:
        sql = str(statement.compile(dialect=postgresql.dialect()))
        assert "corpus_version_id" in sql
        assert "parent_id" in sql


def test_rule_key_fallback_requires_the_pinned_version_and_an_actual_rule_document():
    from types import SimpleNamespace
    from unittest.mock import Mock

    canonical = SimpleNamespace(section_key="rules#r5")
    session = Mock()
    session.execute.side_effect = [SimpleNamespace(first=lambda: None), SimpleNamespace(first=lambda: canonical)]
    assert fetch_section_by_key(session, "rules#s5", "version") is canonical
    alternate = session.execute.call_args.args[0]
    sql = str(alternate.compile(dialect=postgresql.dialect()))
    assert "corpus_version_id" in sql and "documents.doc_type" in sql and "documents.short_key" in sql
