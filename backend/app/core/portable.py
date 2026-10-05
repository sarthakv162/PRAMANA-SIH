"""Ephemeral Space schema. PostgreSQL remains the default for durable installations."""

from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session


def create_schema(engine: sa.Engine) -> sa.MetaData:
    from app.audit.chain import audit_log
    from app.escalations import _escalations_table
    from app.history.service import metadata as history
    from app.orchestrator.nodes.intake import requests_table
    from app.retrieval.repo import metadata as corpus

    metadata = sa.MetaData()
    for source in (corpus, history, requests_table.metadata, audit_log.metadata, _escalations_table.metadata):
        for table in source.tables.values():
            if table.name not in metadata.tables:
                table.to_metadata(metadata)
    for name in ("audit_log", "escalations"):
        metadata.tables[name].c.created_at.server_default = sa.DefaultClause(sa.text("CURRENT_TIMESTAMP"))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
            "USING fts5(chunk_id UNINDEXED, text, tokenize='porter unicode61')"
        )
    return metadata


def seal_corpus(engine: sa.Engine) -> None:
    # Hosted snapshots are immutable. Promotion remains the reviewed PostgreSQL workflow.
    with engine.begin() as connection:
        # FTS5 is a derived search index and cannot have table triggers. Evidence
        # always comes from the sealed chunks table, with hashes checked separately.
        for table in ("corpus_versions", "documents", "document_versions", "sections", "chunks", "edges"):
            for operation in ("INSERT", "UPDATE", "DELETE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER IF NOT EXISTS seal_{table}_{operation.lower()} BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'Packaged corpus is immutable; export a reviewed version instead'); END"
                )
        for operation in ("UPDATE", "DELETE"):
            connection.exec_driver_sql(
                f"CREATE TRIGGER IF NOT EXISTS seal_audit_{operation.lower()} BEFORE {operation} ON audit_log "
                "BEGIN SELECT RAISE(ABORT, 'Audit entries are append only'); END"
            )


def populate_snapshot(engine: sa.Engine, data: dict[str, list[dict[str, Any]]]) -> None:
    from app.audit.merkle import merkle_root
    from app.core.hashing import sha256_hex
    from app.retrieval import repo

    metadata = create_schema(engine)
    with engine.begin() as connection:
        for name in ("corpus_versions", "documents", "sections", "chunks", "edges", "document_versions"):
            if data[name]:
                connection.execute(metadata.tables[name].insert(), data[name])
        for row in data["chunks"]:
            if sha256_hex(row["text"]) != row["sha256"]:
                raise ValueError(f"Chunk hash mismatch: {row['id']}")
            connection.execute(
                sa.text("INSERT INTO chunks_fts(chunk_id, text) VALUES (:id, :text)"),
                {"id": str(row["id"]), "text": row["text"]},
            )
    with Session(engine) as session:
        version = data["corpus_versions"][0]
        actual = merkle_root([row.sha256 for row in repo.all_chunks_ordered(session, str(version["id"]))])
        if actual != version["merkle_root"]:
            raise ValueError("Packaged corpus Merkle root differs from its source version")
    seal_corpus(engine)


def restore_snapshot(seed: Path, destination: Path, expected_sha256: str) -> None:
    import shutil

    from app.core.hashing import sha256_hex

    if sha256_hex(seed.read_bytes()) != expected_sha256:
        raise ValueError("Space corpus snapshot checksum failed")
    # Only the entry point calls this, once per server start. Worker processes share the file.
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed, destination)
