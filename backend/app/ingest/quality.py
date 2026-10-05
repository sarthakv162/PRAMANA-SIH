"""Evidence-bound source review and explicit reviewer approval before promotion."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.hashing import canonical_json, sha256_hex
from app.eval_runner import smoke_test_staged_version
from app.ingest import fetch
from app.ingest.parse_pdf import parse_pdf
from app.retrieval import repo

REVIEW_DIR = Path(__file__).resolve().parents[3] / "corpus" / "raw"


def _chunks_for_review(session: Session, version_id: str) -> list[Any]:
    return list(
        session.execute(
            sa.select(
                repo.chunks.c.id,
                repo.chunks.c.sha256,
                repo.chunks.c.text,
                repo.chunks.c.embedding,
                repo.chunks.c.page,
                repo.chunks.c.char_start,
                repo.chunks.c.char_end,
                repo.chunks.c.bboxes,
                repo.sections.c.path,
                repo.sections.c.section_key,
                repo.sections.c.heading,
                repo.sections.c.parent_id,
                repo.sections.c.document_id,
                repo.chunks.c.jurisdiction,
                repo.chunks.c.doc_type,
                repo.chunks.c.effective_from,
                repo.chunks.c.effective_to,
            )
            .select_from(repo.chunks.join(repo.sections, repo.chunks.c.section_id == repo.sections.c.id))
            .where(repo.chunks.c.corpus_version_id == version_id)
            .order_by(repo.chunks.c.id)
        ).all()
    )


def _review_root(rows: list[Any]) -> str:
    # Bind approval to retrieval vectors and citation locators as well as text.
    fingerprints = [
        (
            str(r.id),
            r.sha256,
            sha256_hex(
                canonical_json(
                    {
                        "vector": [float(v) for v in r.embedding] if r.embedding is not None else None,
                        "page": r.page,
                        "start": r.char_start,
                        "end": r.char_end,
                        "boxes": r.bboxes,
                        "path": r.path,
                        "key": r.section_key,
                        "heading": r.heading,
                        "parent": r.parent_id,
                        "document": r.document_id,
                        "jurisdiction": r.jurisdiction,
                        "doc_type": r.doc_type,
                        "effective_from": r.effective_from,
                        "effective_to": r.effective_to,
                    }
                )
            ),
        )
        for r in rows
    ]
    return sha256_hex(canonical_json(fingerprints))


def _covered_chars(intervals: list[tuple[int, int]], total: int) -> int:
    """Measure the union of stored source offsets; overlapping clauses count once."""
    covered, cursor = 0, 0
    for start, end in sorted(intervals):
        start, end = max(0, start), min(total, end)
        if end > max(cursor, start):
            covered += end - max(cursor, start)
        cursor = max(cursor, end)
    return covered


reviews = sa.Table(
    "source_reviews",
    sa.MetaData(),
    sa.Column("corpus_version_id", sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column("report", sa.JSON),
    sa.Column("report_hash", sa.Text),
    sa.Column("reviewer", sa.Text),
    sa.Column("approved_report_hash", sa.Text),
    sa.Column("approved_at", sa.DateTime(timezone=True)),
)


def authoritative_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == domain or host.endswith("." + domain)
        for domain in ("gov.in", "nic.in", "wipo.int", "wto.org", "cbd.int", "who.int")
    )


def review_stage(session: Session, label: str) -> dict[str, Any]:
    version = session.execute(sa.select(repo.corpus_versions).where(repo.corpus_versions.c.label == label)).one()
    if version.status != "staged":
        raise ValueError("Quality review requires a staged corpus.")
    evaluation = smoke_test_staged_version(session, label)
    rows = _chunks_for_review(session, str(version.id))
    issues = []
    if not rows:
        issues.append("Empty corpus")
    if any(sha256_hex(r.text) != r.sha256 or not r.text.strip() for r in rows):
        issues.append("Chunk extraction/hash check failed")
    import yaml

    snapshot = REVIEW_DIR / f"manifest-{label}.yaml"
    if not snapshot.exists():
        issues.append("Missing pinned ingestion manifest snapshot")
    manifest = yaml.safe_load((snapshot if snapshot.exists() else fetch.manifest_path()).read_text())
    source_map = {s["id"]: s for s in manifest["sources"]}
    docs = repo.documents_for_version(session, str(version.id))
    provenance = []
    source_extraction = []
    for doc in docs:
        source = source_map.get(doc.short_key)
        artifact = repo.document_artifact(session, doc.short_key, label)
        source_url = artifact["source_url"] if artifact else doc.source_url
        if source is None or not authoritative_url(source_url):
            issues.append(f"{doc.short_key}: missing authoritative provenance")
        pdf_path = Path(__file__).resolve().parents[3] / "corpus" / (artifact["pdf_path"] if artifact else doc.pdf_path)
        expected = artifact["file_sha256"] if artifact else doc.file_sha256
        if not expected or not pdf_path.is_file() or sha256_hex(pdf_path.read_bytes()) != expected:
            issues.append(f"{doc.short_key}: source file integrity failed")
        if source and (expected != source["sha256"] or source_url != source["url"]):
            issues.append(f"{doc.short_key}: source does not match the pinned ingestion manifest")
        if pdf_path.is_file():
            parsed = parse_pdf(str(pdf_path))
            source_rows = [r for r in rows if str(r.document_id) == str(doc.id)]
            total = len(parsed.full_text)
            covered = _covered_chars([(r.char_start, r.char_end) for r in source_rows], total)
            ratio = covered / total if total else 0.0
            invalid = sum(
                r.char_start < 0 or r.char_end > total or parsed.full_text[r.char_start : r.char_end] != r.text
                for r in source_rows
            )
            missing_boxes = sum(not r.bboxes for r in source_rows)
            source_extraction.append(
                {
                    "source_id": doc.short_key,
                    "source_text_chars": total,
                    "covered_chars": covered,
                    "coverage": round(ratio, 3),
                    "invalid_source_offsets": invalid,
                    "missing_highlights": missing_boxes,
                }
            )
            if ratio < 0.70:
                issues.append(f"{doc.short_key}: less than 70% of extracted source text is indexed; review omissions")
            if invalid or missing_boxes:
                issues.append(f"{doc.short_key}: invalid source offsets or missing citation highlights")
        provenance.append({"source_id": doc.short_key, "url": source_url, "sha256": expected})
    quality_path = REVIEW_DIR / f"quality-{label}.json"
    if not quality_path.exists():
        issues.append("Missing extraction review report")
        extraction = []
    else:
        import json

        extraction = json.loads(quality_path.read_text())
        for source in extraction:
            if source["low_ocr_pages"] or source["orphan_provisos"] or source["warnings"]:
                issues.append(f"{source['source_id']}: unresolved extraction/OCR/proviso warnings")
    metrics = evaluation["conditions"][0]
    if metrics["citation_recall"] < 0.80:
        issues.append("Golden retrieval recall below the 0.80 promotion threshold")
    report = {
        "version": label,
        "embedding_model": version.embedding_model,
        "provenance": provenance,
        "manifest_hash": sha256_hex(snapshot.read_bytes()) if snapshot.exists() else None,
        "chunk_root": _review_root(rows),
        "extraction": extraction,
        "source_extraction": source_extraction,
        "extraction_hash": sha256_hex(quality_path.read_bytes()) if quality_path.exists() else None,
        "golden_hash": sha256_hex(
            Path(__file__).resolve().parents[3].joinpath("eval/golden/golden.jsonl").read_bytes()
        ),
        "evaluation": evaluation,
        "issues": issues,
    }
    digest = sha256_hex(canonical_json(report))
    existing = session.execute(sa.select(reviews).where(reviews.c.corpus_version_id == str(version.id))).first()
    if existing:
        session.execute(
            sa.update(reviews)
            .where(reviews.c.corpus_version_id == str(version.id))
            .values(report=report, report_hash=digest, reviewer=None, approved_report_hash=None, approved_at=None)
        )
    else:
        session.execute(sa.insert(reviews).values(corpus_version_id=str(version.id), report=report, report_hash=digest))
    session.commit()
    return {**report, "report_hash": digest}


def approve_stage(session: Session, label: str, reviewer: str, report_hash: str) -> None:
    if not reviewer.strip():
        raise ValueError("A named reviewer is required.")
    version = session.execute(sa.select(repo.corpus_versions).where(repo.corpus_versions.c.label == label)).one()
    row = session.execute(sa.select(reviews).where(reviews.c.corpus_version_id == str(version.id))).one()
    if version.status != "staged" or row.report_hash != report_hash or row.report["issues"]:
        raise ValueError("Approval requires this exact, passing staged quality report.")
    session.execute(
        sa.update(reviews)
        .where(reviews.c.corpus_version_id == str(version.id))
        .values(reviewer=reviewer.strip(), approved_report_hash=report_hash, approved_at=datetime.now(UTC))
    )
    session.commit()


def require_approval(session: Session, version: Any) -> None:
    row = session.execute(sa.select(reviews).where(reviews.c.corpus_version_id == str(version.id))).first()
    if row is None or row.report["issues"] or not row.reviewer or row.approved_report_hash != row.report_hash:
        raise ValueError("Promotion requires a passing source/extraction/golden report and named reviewer approval.")
    rows = _chunks_for_review(session, str(version.id))
    root = _review_root(rows)
    golden_hash = sha256_hex(Path(__file__).resolve().parents[3].joinpath("eval/golden/golden.jsonl").read_bytes())
    if (
        root != row.report["chunk_root"]
        or any(sha256_hex(r.text) != r.sha256 for r in rows)
        or golden_hash != row.report["golden_hash"]
        or version.embedding_model != row.report["embedding_model"]
    ):
        raise ValueError("The staged corpus or golden set changed after approval. Run quality review again.")
    quality_path = REVIEW_DIR / f"quality-{version.label}.json"
    if not quality_path.exists() or sha256_hex(quality_path.read_bytes()) != row.report.get("extraction_hash"):
        raise ValueError("Extraction report changed after approval. Run quality review again.")
    snapshot = REVIEW_DIR / f"manifest-{version.label}.yaml"
    if not snapshot.exists() or sha256_hex(snapshot.read_bytes()) != row.report.get("manifest_hash"):
        raise ValueError("Pinned manifest changed after approval. Run quality review again.")
    for source in row.report["provenance"]:
        artifact = repo.document_artifact(session, source["source_id"], version.label)
        if artifact is None:
            raise ValueError("Approved source artifact is missing.")
        path = Path(__file__).resolve().parents[3] / "corpus" / artifact["pdf_path"]
        if (
            not path.is_file()
            or sha256_hex(path.read_bytes()) != source["sha256"]
            or artifact["source_url"] != source["url"]
        ):
            raise ValueError("Source PDF changed after approval. Run quality review again.")
