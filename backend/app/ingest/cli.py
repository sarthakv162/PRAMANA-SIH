"""`make ingest` entrypoint (§6.2): manifest → fetch → parse → chunk → embed → DB, into a
fresh **staged** corpus_version. `make promote V=<label>` flips it live once reviewed.

Usage: `python -m app.ingest.cli [--source ID] [--version-label LABEL]`
"""

from __future__ import annotations

import argparse
import uuid
from datetime import date
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
from app.ingest.parse_pdf import OCR_DENSITY_FLOOR, parse_pdf
from app.ingest.versions import create_staged_version
from app.retrieval import embed
from app.retrieval.repo import chunks, documents, edges, sections

logger = get_logger("ingest")


def ingest_source(
    session: Session, source: fetch.ManifestSource, corpus_version_id: str
) -> dict[str, Any]:
    pdf_path = fetch.fetch_source(source)
    parsed = parse_pdf(str(pdf_path))
    result = chunk_document(source.id, parsed)
    for w in result.warnings:
        logger.warning(w)
    low_ocr_pages = [
        page.printed_number for page in parsed.pages if page.density < OCR_DENSITY_FLOOR
    ]
    if low_ocr_pages:
        logger.warning(
            f"{source.id}: low-text-density pages need OCR/manual review: {low_ocr_pages}"
        )

    file_sha256 = sha256_hex(pdf_path.read_bytes())
    # `documents` is not versioned (no corpus_version_id column, §6.1) — it's the same row
    # across every corpus_version, so a document already ingested by an earlier run is
    # reused rather than re-inserted (which would violate its unique `short_key`).
    existing = session.execute(
        sa.select(documents.c.id).where(documents.c.short_key == source.id)
    ).first()
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
                in_force_to=(
                    date.fromisoformat(source.in_force_to) if source.in_force_to else None
                ),
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
                    effective_to=(
                        date.fromisoformat(source.in_force_to) if source.in_force_to else None
                    ),
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
                    effective_to=(
                        date.fromisoformat(source.in_force_to) if source.in_force_to else None
                    ),
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
            logger.warning(
                f"{source.id}: dropping edge {edge.src_key} -> {edge.dst_key} (unresolved key)"
            )
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
        if chunk.section_key.endswith(("-proviso", "-explanation"))
        and chunk.section_key not in proviso_targets
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


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Ingest only this manifest source id")
    parser.add_argument("--version-label", help="Label for the new staged corpus_version")
    args = parser.parse_args()

    sources = fetch.load_manifest()
    if args.source:
        sources = [s for s in sources if s.id == args.source]
        if not sources:
            raise SystemExit(f"no such manifest source: {args.source}")

    with IngestSessionLocal() as session:
        version_id = create_staged_version(session, args.version_label)
        logger.info(f"staged corpus_version {version_id}")

        reports = []
        for source in sources:
            logger.info(f"ingesting {source.id}")
            reports.append(ingest_source(session, source, version_id))

    print("\n--- ingest report ---")
    report_lines = [
        "# PRAMANA ingest report",
        "",
        f"Staged version: `{version_id}`",
        "",
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
    report_path.write_text("\n".join(report_lines) + "\n")
    print(f"full report: {report_path}")


if __name__ == "__main__":
    main()
