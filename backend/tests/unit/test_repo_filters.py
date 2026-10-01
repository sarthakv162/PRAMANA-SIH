from datetime import date

from sqlalchemy.dialects import postgresql

from app.retrieval.repo import fetch_chunks_for_section


class _Result:
    def all(self):
        return []


class _CaptureSession:
    statement = None

    def execute(self, statement):
        self.statement = statement
        return _Result()


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
