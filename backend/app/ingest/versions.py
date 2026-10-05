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
from app.config import get_settings
from app.eval_runner import smoke_test_staged_version
from app.retrieval.repo import all_chunks_ordered, corpus_versions


def create_staged_version(session: Session, label: str | None = None) -> str:
    label = label or f"{date.today().isoformat()}-{uuid.uuid4().hex[:6]}"
    row = session.execute(
        sa.insert(corpus_versions)
        .values(id=uuid.uuid4(), label=label, status="staged", embedding_model=get_settings().embed_model)
        .returning(corpus_versions.c.id)
    ).one()
    session.commit()
    return str(row.id)


def promote(session: Session, label: str) -> None:
    """Evaluate a staged version, then atomically retire the old and promote the new one."""
    session.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": 5784116599020218674})
    version = session.execute(sa.select(corpus_versions).where(corpus_versions.c.label == label)).first()
    if version is None:
        raise ValueError(f"no corpus_version with label {label!r}")
    if version.status != "staged":
        raise ValueError(f"corpus_version {label!r} is {version.status!r}, not staged")

    from app.ingest.quality import require_approval

    require_approval(session, version)
    evaluation = smoke_test_staged_version(session, label)
    if evaluation["conditions"][0]["citation_recall"] < 0.80:
        raise ValueError("Current golden retrieval recall is below the 0.80 promotion threshold.")
    leaf_hashes = [row.sha256 for row in all_chunks_ordered(session, str(version.id))]
    root = merkle_root(leaf_hashes)

    session.execute(sa.update(corpus_versions).where(corpus_versions.c.status == "live").values(status="retired"))
    session.execute(
        sa.update(corpus_versions).where(corpus_versions.c.id == version.id).values(status="live", merkle_root=root)
    )
    session.commit()


def _main() -> None:
    """`make promote V=<label>` runs the golden retrieval smoke test before promotion."""
    import argparse

    from app.core.db import IngestSessionLocal

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("--label", required=True)
    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--label", required=True)
    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--label", required=True)
    approve_parser.add_argument("--reviewer", required=True)
    approve_parser.add_argument("--report-hash", required=True)
    args = parser.parse_args()

    with IngestSessionLocal() as session:
        if args.command == "review":
            import json

            from app.ingest.quality import review_stage

            print(json.dumps(review_stage(session, args.label), indent=2))
        elif args.command == "approve":
            from app.ingest.quality import approve_stage

            approve_stage(session, args.label, args.reviewer, args.report_hash)
            print(f"Approved quality report for {args.label}")
        else:
            promote(session, args.label)
            print(f"Promoted {args.label} to live")


if __name__ == "__main__":
    _main()
