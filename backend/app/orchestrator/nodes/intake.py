"""§6.4 `intake`: PII scrub, language id, deadline, `requests` row. Invariant I4: only the
scrubbed query's hash may ever be logged or persisted — `state.raw_query` must not leak past
this node.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deadline import Deadline
from app.core.hashing import sha256_hex
from app.core.logging import get_logger
from app.intake.langid import detect_language
from app.intake.pii import scrub_pii
from app.intake.translate import translate_to_english
from app.orchestrator.state import RequestState
from app.retrieval.repo import live_corpus_version

logger = get_logger("orchestrator.intake")

requests_table = sa.Table(
    "requests",
    sa.MetaData(),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("corpus_version_id", UUID(as_uuid=True)),
    sa.Column("query_hash", sa.Text),
    sa.Column("lang", sa.Text),
    sa.Column("jurisdiction", sa.Text),
    sa.Column("as_of", sa.Date),
    sa.Column("persona", sa.Text),
    sa.Column("deadline_at", sa.DateTime(timezone=True)),
)


class NoLiveCorpusError(Exception):
    pass


def run(state: RequestState, session: Session) -> None:
    settings = get_settings()
    state.deadline = Deadline(settings.request_deadline_s)

    scrub = scrub_pii(state.raw_query)
    state.scrubbed_query = scrub.scrubbed_text
    state.query_hash = sha256_hex(scrub.scrubbed_text)
    if scrub.found:
        logger.info(f"pii scrubbed: kinds={sorted(set(scrub.found))} query_hash={state.query_hash}")

    state.lang = detect_language(scrub.scrubbed_text, state.request.language)
    state.query_en = translate_to_english(scrub.scrubbed_text, state.lang)

    version = live_corpus_version(session)
    if version is None:
        raise NoLiveCorpusError("no live corpus_version — run `make ingest && make promote`")
    state.corpus_version_id, state.corpus_version_label = version

    from app.history.service import add_user_message, recent_context

    state.conversation_context = recent_context(session, state.request.conversation_id)
    state.persona = state.request.persona

    session.execute(
        sa.insert(requests_table).values(
            id=uuid.UUID(state.request_id),
            corpus_version_id=state.corpus_version_id,
            query_hash=state.query_hash,
            lang=state.lang.value,
            jurisdiction=state.request.jurisdiction.value,
            as_of=state.request.as_of or date.today(),
            persona=state.persona.value,
            deadline_at=datetime.now(UTC) + timedelta(seconds=settings.request_deadline_s),
        )
    )
    session.commit()
    if state.request.conversation_id:
        add_user_message(session, state.request.conversation_id, state.scrubbed_query, state.request_id)
