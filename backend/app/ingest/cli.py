"""Manifest → fetch → parse → chunk → embed → DB into a staged corpus version.

`make ingest` creates a new version. `make resume-ingest V=<label>` continues a staged
version after an interruption without re-embedding sources already committed to it.
`make promote V=<label>` flips it live once reviewed.

Usage: `python -m app.ingest.cli [--source ID ...] [--version-label LABEL]
       [--resume-version-label LABEL]`
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pymupdf
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.db import IngestSessionLocal
from app.core.hashing import sha256_hex
from app.core.logging import configure_logging, get_logger
from app.ingest import fetch
from app.ingest.bboxes import find_highlights
from app.ingest.chunk_legal import chunk_document
from app.ingest.parse_pdf import OCR_DENSITY_FLOOR, Page, parse_pdf
from app.ingest.versions import create_staged_version
from app.retrieval import embed
from app.retrieval.repo import chunks, corpus_versions, documents, edges, sections
from app.retrieval.repo import document_versions as repo_document_versions

logger = get_logger("ingest")


def _needs_ocr_review(page: Page) -> bool:
    """Avoid treating whitespace-heavy, text-native statute pages as scans."""
    text = re.sub(r"<<\s*previous\b.*?\bnext\s*>>", "", page.text, flags=re.IGNORECASE).strip()
    if not text:
        return not page.raw_text.strip()
    return page.density < OCR_DENSITY_FLOOR and len(text) < 100


def ingest_source(session: Session, source: fetch.ManifestSource, corpus_version_id: str) -> dict[str, Any]:
    pdf_path = fetch.fetch_source(source)
    parsed = parse_pdf(str(pdf_path))
    result = chunk_document(source.id, parsed, source.doc_type)
    for w in result.warnings:
        logger.warning(w)
    low_ocr_pages = [page.printed_number for page in parsed.pages if _needs_ocr_review(page)]
    if low_ocr_pages:
        logger.warning(f"{source.id}: low-text-density pages need OCR/manual review: {low_ocr_pages}")

    file_sha256 = sha256_hex(pdf_path.read_bytes())
    artifact_dir = Path(__file__).resolve().parents[3] / "corpus" / "raw" / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / f"{source.id}-{file_sha256}.pdf"
    if not artifact.exists():
        shutil.copyfile(pdf_path, artifact)
    # `documents` is not versioned (no corpus_version_id column, §6.1) — it's the same row
    # across every corpus_version, so a document already ingested by an earlier run is
    # reused rather than re-inserted (which would violate its unique `short_key`).
    existing = session.execute(sa.select(documents.c.id).where(documents.c.short_key == source.id)).first()
    if existing:
        document_id = existing.id
    else:
        document_id = uuid.uuid4()
        session.execute(
            sa.insert(documents).values(
                id=document_id,
                short_key=source.id,
                title=source.title,
                doc_type=source.doc_type,
                jurisdiction=source.jurisdiction,
                issuer=source.issuer,
                source_url=source.url,
                pdf_path=str(pdf_path.relative_to(fetch.raw_dir().parent)),
                file_sha256=file_sha256,
                language=source.language,
                in_force_from=date.fromisoformat(source.in_force_from),
                in_force_to=(date.fromisoformat(source.in_force_to) if source.in_force_to else None),
            )
        )

    session.execute(
        sa.insert(repo_document_versions).values(
            document_id=str(document_id),
            corpus_version_id=corpus_version_id,
            pdf_path=str(artifact.relative_to(artifact_dir.parents[1])),
            file_sha256=file_sha256,
            source_url=source.url,
        )
    )

    key_to_section_id: dict[str, uuid.UUID] = {}
    # embed_text = heading path + body (§6.2 step 3) — better embeddings than body alone.
    embed_texts = [f"{' > '.join(d.path)}\n{d.text}" if d.path else d.text for d in result.chunks]
    vectors = embed.embed_texts(embed_texts)

    fitz_doc = pymupdf.open(str(pdf_path))  # type: ignore[no-untyped-call]
    unlocated = 0
    try:
        for draft, embed_text, vector in zip(result.chunks, embed_texts, vectors, strict=True):
            section_id = uuid.uuid4()
            key_to_section_id[draft.section_key] = section_id
            parent_id = key_to_section_id.get(draft.parent_key) if draft.parent_key else None
            chunk_sha = sha256_hex(draft.text)

            session.execute(
                sa.insert(sections).values(
                    id=section_id,
                    document_id=document_id,
                    corpus_version_id=corpus_version_id,
                    section_key=draft.section_key,
                    path=draft.path,
                    heading=draft.heading,
                    parent_id=parent_id,
                    effective_from=date.fromisoformat(source.in_force_from),
                    effective_to=(date.fromisoformat(source.in_force_to) if source.in_force_to else None),
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    text=draft.text,
                    sha256=chunk_sha,
                )
            )

            highlights = find_highlights(fitz_doc, draft.page_start, draft.text)
            if not highlights:
                unlocated += 1

            session.execute(
                sa.insert(chunks).values(
                    id=uuid.uuid4(),
                    section_id=section_id,
                    corpus_version_id=corpus_version_id,
                    jurisdiction=source.jurisdiction,
                    doc_type=source.doc_type,
                    effective_from=date.fromisoformat(source.in_force_from),
                    effective_to=(date.fromisoformat(source.in_force_to) if source.in_force_to else None),
                    page=draft.page_start,
                    char_start=draft.char_start,
                    char_end=draft.char_end,
                    text=draft.text,
                    embed_text=embed_text,
                    sha256=chunk_sha,
                    bboxes=highlights,
                    embedding=vector,
                    tsv=sa.func.to_tsvector("english", embed_text),
                )
            )
    finally:
        fitz_doc.close()  # type: ignore[no-untyped-call]

    for edge in result.edges:
        src_id = key_to_section_id.get(edge.src_key)
        dst_id = key_to_section_id.get(edge.dst_key)
        if src_id is None or dst_id is None:
            logger.warning(f"{source.id}: dropping edge {edge.src_key} -> {edge.dst_key} (unresolved key)")
            continue
        session.execute(
            sa.insert(edges).values(
                src_section_id=src_id,
                dst_section_id=dst_id,
                kind=edge.kind,
                corpus_version_id=corpus_version_id,
            )
        )

    proviso_targets = {edge.dst_key for edge in result.edges if edge.kind == "proviso_of"}
    orphan_provisos = [
        chunk.section_key
        for chunk in result.chunks
        if chunk.section_key.endswith(("-proviso", "-explanation")) and chunk.section_key not in proviso_targets
    ]

    session.commit()
    return {
        "source_id": source.id,
        "sections": len(result.chunks),
        "edges": len(result.edges),
        "unlocated_bboxes": unlocated,
        "low_ocr_pages": low_ocr_pages,
        "orphan_provisos": orphan_provisos,
        "warnings": result.warnings,
    }


def _resume_staged_version(session: Session, label: str) -> str:
    row = session.execute(
        sa.select(corpus_versions.c.id, corpus_versions.c.status).where(corpus_versions.c.label == label)
    ).first()
    if row is None:
        raise ValueError(f"no corpus_version with label {label!r}")
    if row.status != "staged":
        raise ValueError(f"corpus_version {label!r} is {row.status!r}, not staged")
    return str(row.id)


def _existing_source_reports(
    session: Session, sources: list[fetch.ManifestSource], corpus_version_id: str
) -> tuple[set[str], list[dict[str, Any]]]:
    """Summarize already-committed sources so interrupted staging can resume safely."""
    existing_ids: set[str] = set(
        session.execute(
            sa.select(documents.c.short_key)
            .select_from(documents.join(sections, documents.c.id == sections.c.document_id))
            .where(sections.c.corpus_version_id == corpus_version_id)
            .distinct()
        ).scalars()
    )
    source_by_id = {source.id: source for source in sources}
    reports: list[dict[str, Any]] = []
    for source_id in sorted(existing_ids):
        source = source_by_id.get(source_id)
        if source is None:
            continue
        pdf_path = fetch.fetch_source(source)
        parsed = parse_pdf(str(pdf_path))
        result = chunk_document(source.id, parsed, source.doc_type)
        document_id: Any = session.execute(
            sa.select(documents.c.id).where(documents.c.short_key == source.id)
        ).scalar_one()
        source_sections: Any = (
            session.execute(
                sa.select(sections.c.id).where(
                    sections.c.document_id == document_id,
                    sections.c.corpus_version_id == corpus_version_id,
                )
            )
            .scalars()
            .all()
        )
        source_chunks: Any = (
            session.execute(
                sa.select(chunks.c.bboxes)
                .where(chunks.c.section_id.in_(source_sections))
                .where(chunks.c.corpus_version_id == corpus_version_id)
            )
            .scalars()
            .all()
        )
        low_ocr_pages = [page.printed_number for page in parsed.pages if _needs_ocr_review(page)]
        proviso_targets = {edge.dst_key for edge in result.edges if edge.kind == "proviso_of"}
        orphan_provisos = [
            chunk.section_key
            for chunk in result.chunks
            if chunk.section_key.endswith(("-proviso", "-explanation")) and chunk.section_key not in proviso_targets
        ]
        reports.append(
            {
                "source_id": source.id,
                "sections": len(source_sections),
                "edges": len(result.edges),
                "unlocated_bboxes": sum(not boxes for boxes in source_chunks),
                "low_ocr_pages": low_ocr_pages,
                "orphan_provisos": orphan_provisos,
                "warnings": result.warnings,
            }
        )
    return existing_ids, reports


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        dest="source_ids",
        action="append",
        help="Ingest only this manifest source id; may be repeated",
    )
    parser.add_argument("--version-label", help="Label for the new staged corpus_version")
    parser.add_argument("--resume-version-label", help="Resume an existing staged corpus_version by label")
    args = parser.parse_args()

    if args.version_label and args.resume_version_label:
        parser.error("--version-label and --resume-version-label cannot be used together")
    sources = fetch.load_manifest()
    if args.source_ids:
        requested_ids = set(args.source_ids)
        sources = [s for s in sources if s.id in requested_ids]
        missing_ids = requested_ids - {source.id for source in sources}
        if missing_ids:
            raise SystemExit(f"no such manifest source(s): {', '.join(sorted(missing_ids))}")

    with IngestSessionLocal() as session:
        if args.resume_version_label:
            staged_version_label = args.resume_version_label
            version_id = _resume_staged_version(session, staged_version_label)
        else:
            staged_version_label = args.version_label or (f"{date.today().isoformat()}-{uuid.uuid4().hex[:6]}")
            version_id = create_staged_version(session, staged_version_label)
        logger.info(f"staged corpus_version {staged_version_label} ({version_id})")

        review_dir = Path(__file__).resolve().parents[3] / "corpus" / "raw"
        review_dir.mkdir(parents=True, exist_ok=True)
        snapshot = review_dir / f"manifest-{staged_version_label}.yaml"
        current_manifest = fetch.manifest_path().read_bytes()
        if snapshot.exists() and snapshot.read_bytes() != current_manifest:
            raise ValueError("The manifest changed during staged ingestion. Create a new staged version.")
        snapshot.write_bytes(current_manifest)

        already_ingested, reports = (
            _existing_source_reports(session, sources, version_id) if args.resume_version_label else (set(), [])
        )
        for source in sources:
            if source.id in already_ingested:
                logger.info(f"skipping already committed source {source.id}")
                continue
            logger.info(f"ingesting {source.id}")
            reports.append(ingest_source(session, source, version_id))

    print("\n--- ingest report ---")
    report_lines = [
        "# PRAMANA ingest report",
        "",
        f"Staged version: `{staged_version_label}` (`{version_id}`)",
        "",
        (
            "Previously committed sources were revalidated and retained while this staged version resumed."
            if args.resume_version_label
            else ""
        ),
        "Low-density pages are flagged for OCR/manual review. This prototype does not run OCR.",
        "",
        "| Source | Sections | Chunks | Unlocated bboxes | Low-density pages | Orphan provisos | Warnings |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in reports:
        report_lines.append(
            f"| `{r['source_id']}` | {r['sections']} | {r['sections']} | "
            f"{r['unlocated_bboxes']} | {len(r['low_ocr_pages'])} "
            f"({', '.join(map(str, r['low_ocr_pages'])) or 'none'}) | "
            f"{len(r['orphan_provisos'])} | {len(r['warnings'])} |"
        )
        print(
            f"{r['source_id']}: {r['sections']} sections/chunks, {r['edges']} edges, "
            f"{r['unlocated_bboxes']} unlocated bboxes, "
            f"{len(r['low_ocr_pages'])} low-density pages, "
            f"{len(r['orphan_provisos'])} orphan provisos, {len(r['warnings'])} warnings"
        )
        for warning in r["warnings"]:
            report_lines.append(f"\nWarning: {warning}")
        for orphan in r["orphan_provisos"]:
            report_lines.append(f"\nOrphan proviso/explanation: `{orphan}`")

    report_path = fetch.raw_dir() / "ingest_report.md"
    (review_dir / f"quality-{staged_version_label}.json").write_text(json.dumps(reports, indent=2))
    report_path.write_text("\n".join(report_lines) + "\n")
    print(f"full report: {report_path}")


if __name__ == "__main__":
    main()
