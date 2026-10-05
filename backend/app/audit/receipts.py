"""Receipts (§6.9): build one per response, serve it back via `/receipts/{id}` and
`/receipts/{id}/verify`.

The public `Receipt` schema is deliberately slim (§5.2) — the audit-log payload actually
stored is richer (it also maps each cited `evidence_id` to the chunk it came from), because
`/receipts/{id}/verify` needs that mapping to build a Merkle proof per span and the public
schema has no field for it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit.chain import append_entry, audit_log, verify_chain_segment
from app.audit.merkle import merkle_proof, verify_proof
from app.config import get_settings
from app.core.hashing import canonical_json, sha256_hex
from app.retrieval import repo
from app.retrieval.evidence_pack import NumberedSpan
from app.retrieval.repo import corpus_versions
from app.schemas.receipts import ModelIds, Receipt, SpanVerification, VerifyResult


def _receipt_id(seq: int) -> str:
    settings = get_settings()
    if settings.storage_mode == "ephemeral":
        return f"rcp_{settings.receipt_namespace}_{seq}"
    return f"rcp_{seq}"


def _seq_from_receipt_id(receipt_id: str) -> int | None:
    settings = get_settings()
    prefix = f"rcp_{settings.receipt_namespace}_" if settings.storage_mode == "ephemeral" else "rcp_"
    if not receipt_id.startswith(prefix):
        return None
    try:
        return int(receipt_id[len(prefix) :])
    except ValueError:
        return None


def build_receipt(
    session: Session,
    request_id: str,
    corpus_version_label: str,
    query_hash: str,
    cited_spans: list[NumberedSpan],
    model_ids: ModelIds,
    prompt_version: str,
    result_payload: dict[str, Any],
    request_payload: dict[str, Any] | None = None,
    conversation_id: str | None = None,
) -> Receipt:
    """Appends one hash-chain entry and returns the public `Receipt` for it. `result_payload`
    is the rendered response (AnswerCard/RefusalCard/ClassifyResult/PatentRisk/AbsResult/
    TkRadar, as a dict) — its hash goes in the chain entry so tampering with a stored result,
    not just the corpus, is detectable. The full payload is also stored verbatim (not just its
    hash) so `/dossier` can assemble a document from stored results without re-running the
    pipeline (§6.11). `request_payload`, when given, is the structured (non-free-text) input
    that produced the result — e.g. a `Formulation` — never the raw natural-language query
    text, which invariant I4 forbids persisting.
    """
    from app.history.service import scrub_payload

    # Hash the scrubbed snapshot before its receipt ID is assigned. The audit row
    # keeps this hash after the saved content expires; it never retains message text.
    result_payload = scrub_payload(result_payload)
    request_payload = scrub_payload(request_payload)
    entry: dict[str, Any] = {
        "request_id": request_id,
        "corpus_version": corpus_version_label,
        "query_hash": query_hash,
        "chunk_hashes": [s.span.sha256 for s in cited_spans],
        "spans": [{"evidence_id": s.evidence_id, "chunk_id": s.chunk_id, "sha256": s.span.sha256} for s in cited_spans],
        "model_ids": model_ids.model_dump(),
        "prompt_version": prompt_version,
        "result_hash": sha256_hex(canonical_json(result_payload)),
        "result_receipt_field": result_payload.get("receipt_id"),
        "request_payload_hash": sha256_hex(canonical_json(request_payload)) if request_payload else None,
        "ts": datetime.now(UTC).isoformat(),
    }
    chain_entry = append_entry(session, request_id, entry)
    from app.history.service import save_result

    save_result(
        session,
        request_id,
        result_payload,
        _receipt_id(chain_entry.seq),
        chain_entry.entry_hash,
        request_payload,
        conversation_id,
    )
    session.commit()

    return Receipt(
        id=_receipt_id(chain_entry.seq),
        request_id=request_id,
        corpus_version=corpus_version_label,
        query_hash=query_hash,
        chunk_hashes=entry["chunk_hashes"],
        model_ids=model_ids,
        prompt_version=prompt_version,
        prev_hash=chain_entry.prev_hash,
        entry_hash=chain_entry.entry_hash,
        created_at=datetime.fromisoformat(entry["ts"]),
    )


def get_receipt(session: Session, receipt_id: str) -> Receipt | None:
    seq = _seq_from_receipt_id(receipt_id)
    if seq is None:
        return None
    row = session.execute(sa.select(audit_log).where(audit_log.c.seq == seq)).mappings().first()
    if row is None:
        return None
    payload = row["payload"]
    return Receipt(
        id=receipt_id,
        request_id=str(row["request_id"]),
        corpus_version=payload["corpus_version"],
        query_hash=payload["query_hash"],
        chunk_hashes=payload["chunk_hashes"],
        model_ids=ModelIds.model_validate(payload["model_ids"]),
        prompt_version=payload["prompt_version"],
        prev_hash=row["prev_hash"],
        entry_hash=row["entry_hash"],
        created_at=row["created_at"],
    )


def verify_receipt(session: Session, receipt_id: str) -> VerifyResult | None:
    seq = _seq_from_receipt_id(receipt_id)
    if seq is None:
        return None
    row = session.execute(sa.select(audit_log).where(audit_log.c.seq == seq)).mappings().first()
    if row is None:
        return None

    chain_valid = verify_chain_segment(session, seq)
    payload = row["payload"]

    version = session.execute(
        sa.select(corpus_versions.c.id, corpus_versions.c.merkle_root).where(
            corpus_versions.c.label == payload["corpus_version"]
        )
    ).first()
    corpus_root = (version.merkle_root if version else None) or ""

    span_results: list[SpanVerification] = []
    if version is not None and version.merkle_root:
        ordered = repo.all_chunks_ordered(session, str(version.id))
        index_by_chunk_id = {str(r.id): i for i, r in enumerate(ordered)}
        leaf_hashes = [r.sha256 for r in ordered]

        for span in payload.get("spans", []):
            chunk_row = repo.chunk_current_text_and_id(session, span["chunk_id"])
            if chunk_row is None:
                span_results.append(
                    SpanVerification(
                        evidence_id=span["evidence_id"],
                        sha256=span["sha256"],
                        in_corpus=False,
                        merkle_proof_valid=False,
                    )
                )
                continue
            current_sha256 = sha256_hex(chunk_row.text)
            idx = index_by_chunk_id.get(span["chunk_id"])
            proof_valid = False
            if idx is not None:
                proof = merkle_proof(leaf_hashes, idx)
                proof_valid = verify_proof(current_sha256, proof, version.merkle_root)
            span_results.append(
                SpanVerification(
                    evidence_id=span["evidence_id"],
                    sha256=current_sha256,
                    in_corpus=idx is not None,
                    merkle_proof_valid=proof_valid,
                )
            )

    return VerifyResult(chain_valid=chain_valid, corpus_root=corpus_root, spans=span_results)


@dataclass
class StoredResult:
    """A previously-rendered response, re-fetched by `request_id` for `/dossier` (§6.11) —
    built from what `build_receipt` stored, never by re-running the pipeline.
    """

    request_id: str
    receipt_id: str
    entry_hash: str
    result: dict[str, Any]
    request_payload: dict[str, Any] | None


def latest_result_for_request(session: Session, request_id: str) -> StoredResult | None:
    try:
        uuid.UUID(request_id)
    except ValueError:
        return None
    from app.core.errors import ApiError
    from app.history.service import get_result

    try:
        row = get_result(session, request_id)
    except ApiError:
        return None
    return StoredResult(
        request_id=request_id,
        receipt_id=row["receipt_id"],
        entry_hash=row["entry_hash"],
        result=row["result"],
        request_payload=row["request_payload"],
    )
