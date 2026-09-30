"""corpus_versions lifecycle (§6.2 step 8): staged → live, with the old version kept
queryable (as-of/replay never needs a version that's been deleted, only ones marked
`retired`, which nothing in this prototype does automatically).
"""

from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit.merkle import merkle_root
from app.retrieval.repo import all_chunks_ordered, corpus_versions


def create_staged_version(session: Session, label: str | None = None) -> str:
    label = label or f"{date.today().isoformat()}-{uuid.uuid4().hex[:6]}"
    row = session.execute(
        sa.insert(corpus_versions)
        .values(label=label, status="staged")
        .returning(corpus_versions.c.id)
    ).one()
    session.commit()
    return str(row.id)


def promote(session: Session, label: str) -> None:
    """Flip a staged version to live. §6.2 step 8 also runs an eval smoke test first —
    that lands with the eval harness in M5; this is the mechanical half of the promotion.
    """
    version = session.execute(
        sa.select(corpus_versions).where(corpus_versions.c.label == label)
    ).first()
    if version is None:
        raise ValueError(f"no corpus_version with label {label!r}")
    if version.status != "staged":
        raise ValueError(f"corpus_version {label!r} is {version.status!r}, not staged")

    leaf_hashes = [row.sha256 for row in all_chunks_ordered(session, str(version.id))]
    root = merkle_root(leaf_hashes)

    session.execute(
        sa.update(corpus_versions)
        .where(corpus_versions.c.status == "live")
        .values(status="retired")
    )
    session.execute(
        sa.update(corpus_versions)
        .where(corpus_versions.c.id == version.id)
        .values(status="live", merkle_root=root)
    )
    session.commit()


def _main() -> None:
    """`make promote V=<label>` (§6.2 step 8, Makefile). The eval smoke test this is
    documented to run first lands with the eval harness (M5); today this just flips the
    flag, so run it only after reviewing the staged version's ingest report by hand.
    """
    import argparse

    from app.core.db import SessionLocal

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("--label", required=True)
    args = parser.parse_args()

    with SessionLocal() as session:
        promote(session, args.label)
    print(f"promoted {args.label} to live")


if __name__ == "__main__":
    _main()
