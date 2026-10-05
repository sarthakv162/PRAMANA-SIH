"""Hash chain (§6.9, invariant I5): one global, append-only, linear chain across every
request. A transaction-scoped advisory lock serializes the tail read and insert, including
the empty-chain case, while preserving the app role's insert-only audit-log privileges.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.core.hashing import chain_entry_hash
from app.core.sql_types import UUID

GENESIS_HASH = "0" * 64

audit_log = sa.Table(
    "audit_log",
    sa.MetaData(),
    sa.Column("seq", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
    sa.Column("request_id", UUID(as_uuid=True)),
    sa.Column("prev_hash", sa.Text),
    sa.Column("entry_hash", sa.Text),
    sa.Column("payload", sa.JSON().with_variant(JSONB(), "postgresql")),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)


@dataclass
class ChainEntry:
    seq: int
    request_id: str
    prev_hash: str
    entry_hash: str
    payload: dict[str, Any]


def append_entry(session: Session, request_id: str, entry: dict[str, Any]) -> ChainEntry:
    """Serializes appends with a transaction-scoped advisory lock, then inserts the new tail.

    A row lock on the current tail is insufficient: concurrent inserts can both observe and
    extend the same predecessor (including when the chain is empty). The advisory lock is
    independent of table contents and remains held until the caller commits.
    """
    if session.get_bind().dialect.name == "postgresql":
        session.execute(sa.text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": 5784116599020218673})
    else:
        # A file-backed SQLite writer lock also works across ZeroGPU worker processes.
        connection = session.connection()
        driver = connection.connection.driver_connection
        if driver is not None and not driver.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    last = session.execute(sa.select(audit_log.c.entry_hash).order_by(audit_log.c.seq.desc()).limit(1)).first()
    prev_hash = last.entry_hash if last else GENESIS_HASH

    entry_hash = chain_entry_hash(prev_hash, entry)
    row = session.execute(
        sa.insert(audit_log)
        .values(request_id=request_id, prev_hash=prev_hash, entry_hash=entry_hash, payload=entry)
        .returning(audit_log.c.seq, audit_log.c.created_at)
    ).one()

    return ChainEntry(
        seq=row.seq,
        request_id=request_id,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        payload=entry,
    )


def verify_chain_segment(session: Session, up_to_seq: int) -> bool:
    """Recomputes every `entry_hash` from `payload`/`prev_hash` up to (and including)
    `up_to_seq` and checks it matches what's stored — invariant I5's tamper check.
    """
    rows = session.execute(sa.select(audit_log).where(audit_log.c.seq <= up_to_seq).order_by(audit_log.c.seq)).all()
    expected_prev = GENESIS_HASH
    for row in rows:
        if row.prev_hash != expected_prev:
            return False
        recomputed = chain_entry_hash(row.prev_hash, row.payload)
        if recomputed != row.entry_hash:
            return False
        expected_prev = row.entry_hash
    return True


def entry_for_request(session: Session, request_id: str) -> ChainEntry | None:
    stmt = sa.select(audit_log).where(audit_log.c.request_id == request_id).order_by(audit_log.c.seq.desc()).limit(1)
    row = session.execute(stmt).first()
    if row is None:
        return None
    return ChainEntry(
        seq=row.seq,
        request_id=str(row.request_id),
        prev_hash=row.prev_hash,
        entry_hash=row.entry_hash,
        payload=row.payload,
    )
