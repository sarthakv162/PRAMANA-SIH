"""Receipt-writing for the deterministic rule-engine endpoints (`classify`, `patent-risk`,
`abs-check`, `tk-radar`) — these never enter the LangGraph orchestrator pipeline
(`orchestrator/graph.py`), but §6.9 promises a real, verifiable audit-chain receipt on
*every* response, not only `/query`'s. Without this, these endpoints' `receipt_id` fields
were random strings that `/receipts/{id}` could never resolve.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from app.audit.receipts import build_receipt
from app.core.hashing import canonical_json, sha256_hex
from app.retrieval.evidence_pack import NumberedSpan
from app.schemas.evidence import EvidenceSpan
from app.schemas.receipts import ModelIds

# Narrow reflection of `requests`, matching orchestrator/nodes/intake.py's — every module that
# inserts into this table declares just the columns it needs (core/db.py's docstring explains
# why there's no shared declarative model).
_requests_table = sa.Table(
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

_NO_MODEL = ModelIds(llm="none", embed="none", nli="none")


def record_rule_engine_result(
    session: Session,
    *,
    corpus_version_id: str,
    corpus_version_label: str,
    endpoint: str,
    jurisdiction: str,
    as_of: date,
    request_payload: dict[str, Any],
    evidence: dict[str, EvidenceSpan],
    chunk_id_by_evidence_id: dict[str, str],
    result_payload: dict[str, Any],
) -> str:
    """Creates the `requests` row + one audit-chain entry for a rule-engine response (no LLM
    or NLI involved — `model_ids` records that honestly rather than naming unused models) and
    returns a real, `/receipts/{id}`-resolvable receipt id.

    `request_payload` is the endpoint's structured input (a `Formulation`, `AbsRequest`,
    `ClassifyRequest`, …) — safe to persist because it's a structured form submission, not the
    free-text `/query` question that invariant I4 forbids persisting.
    """
    request_id = str(uuid.uuid4())
    query_hash = sha256_hex(canonical_json(request_payload))

    session.execute(
        sa.insert(_requests_table).values(
            id=uuid.UUID(request_id),
            corpus_version_id=uuid.UUID(corpus_version_id),
            query_hash=query_hash,
            lang="en",
            jurisdiction=jurisdiction,
            as_of=as_of,
            persona=endpoint,
            deadline_at=None,
        )
    )

    cited_spans = [
        NumberedSpan(
            number=i,
            evidence_id=ev_id,
            chunk_id=chunk_id_by_evidence_id.get(ev_id, ""),
            span=span,
        )
        for i, (ev_id, span) in enumerate(evidence.items(), start=1)
    ]

    receipt = build_receipt(
        session,
        request_id=request_id,
        corpus_version_label=corpus_version_label,
        query_hash=query_hash,
        cited_spans=cited_spans,
        model_ids=_NO_MODEL,
        prompt_version=f"rule_engine/{endpoint}",
        result_payload=result_payload,
        request_payload=request_payload,
    )
    return receipt.id
