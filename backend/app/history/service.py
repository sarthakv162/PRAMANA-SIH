from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import ApiError
from app.core.hashing import canonical_json, sha256_hex
from app.intake.pii import scrub_pii

metadata = sa.MetaData()
conversations = sa.Table(
    "conversations",
    metadata,
    sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column("workspace_id", sa.Text),
    sa.Column("title", sa.Text),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("expires_at", sa.DateTime(timezone=True)),
)
messages = sa.Table(
    "conversation_messages",
    metadata,
    sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column("conversation_id", sa.Uuid(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="CASCADE")),
    sa.Column("role", sa.Text),
    sa.Column("content", sa.Text),
    sa.Column("request_id", sa.Text),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("expires_at", sa.DateTime(timezone=True)),
)
results = sa.Table(
    "saved_results",
    metadata,
    sa.Column("request_id", sa.Text, primary_key=True),
    sa.Column("workspace_id", sa.Text),
    sa.Column("conversation_id", sa.Uuid(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="CASCADE")),
    sa.Column("result", sa.JSON),
    sa.Column("request_payload", sa.JSON),
    sa.Column("receipt_id", sa.Text),
    sa.Column("entry_hash", sa.Text),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("expires_at", sa.DateTime(timezone=True)),
)
case_refs = sa.Table(
    "case_file_refs",
    metadata,
    sa.Column("workspace_id", sa.Text, primary_key=True),
    sa.Column("request_id", sa.Text, sa.ForeignKey("saved_results.request_id", ondelete="CASCADE"), primary_key=True),
    sa.Column("summary", sa.Text),
    sa.Column("position", sa.Integer),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)


def _now() -> datetime:
    return datetime.now(UTC)


def workspace() -> str:
    return get_settings().workspace_id


def scrub_payload(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_pii(value).scrubbed_text
    if isinstance(value, list):
        return [scrub_payload(v) for v in value]
    if isinstance(value, dict):
        # Legal evidence is server-owned and must remain byte-for-byte identical.
        return {k: v if k in {"evidence", "nearest_sources"} else scrub_payload(v) for k, v in value.items()}
    return value


def purge_expired(session: Session) -> None:
    now = _now()
    session.execute(sa.delete(messages).where(messages.c.expires_at <= now))
    session.execute(sa.delete(results).where(results.c.expires_at <= now))
    session.execute(sa.delete(conversations).where(conversations.c.expires_at <= now))
    session.commit()


def create_conversation(session: Session, title: str) -> dict[str, Any]:
    now = _now()
    values = {
        "id": str(uuid.uuid4()),
        "workspace_id": workspace(),
        "title": scrub_pii(title).scrubbed_text,
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(days=30),
    }
    session.execute(sa.insert(conversations).values(**values))
    session.commit()
    return values


def require_conversation(session: Session, conversation_id: str) -> dict[str, Any]:
    row = (
        session.execute(
            sa.select(conversations).where(
                conversations.c.id == conversation_id,
                conversations.c.workspace_id == workspace(),
                conversations.c.expires_at > _now(),
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError("conversation_not_found", "Conversation not found or expired.", 404)
    return dict(row)


def list_conversations(session: Session) -> list[dict[str, Any]]:
    purge_expired(session)
    return [
        dict(row)
        for row in session.execute(
            sa.select(conversations)
            .where(
                conversations.c.workspace_id == workspace(),
                conversations.c.expires_at > _now(),
            )
            .order_by(conversations.c.updated_at.desc())
            .limit(100)
        ).mappings()
    ]


def get_result(session: Session, request_id: str) -> dict[str, Any]:
    row = (
        session.execute(
            sa.select(results).where(
                results.c.request_id == request_id,
                results.c.workspace_id == workspace(),
                results.c.expires_at > _now(),
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError("result_not_found", "Saved result not found or expired.", 404)
    if (
        session.get_bind().dialect.name == "postgresql"
        or getattr(get_settings(), "storage_mode", "persistent") == "ephemeral"
    ):
        # Bind the expiring copy to the append-only audit row. Receipt IDs are assigned
        # after hashing, so restore the original field for canonical hash validation.
        from app.audit.chain import audit_log

        audit = session.execute(
            sa.select(audit_log.c.payload, audit_log.c.entry_hash)
            .where(audit_log.c.request_id == request_id)
            .order_by(audit_log.c.seq.desc())
            .limit(1)
        ).first()
        if audit is None or audit.entry_hash != row["entry_hash"]:
            raise ApiError("result_integrity_failed", "Saved result integrity check failed.", 409)
        if "result_receipt_field" in audit.payload:
            snapshot = dict(row["result"])
            if audit.payload["result_receipt_field"] is None:
                snapshot.pop("receipt_id", None)
            else:
                snapshot["receipt_id"] = audit.payload["result_receipt_field"]
            if sha256_hex(canonical_json(snapshot)) != audit.payload["result_hash"]:
                raise ApiError("result_integrity_failed", "Saved result integrity check failed.", 409)
    return dict(row)


def conversation_detail(session: Session, conversation_id: str) -> dict[str, Any]:
    purge_expired(session)
    conversation = require_conversation(session, conversation_id)
    rows = session.execute(
        sa.select(messages)
        .where(
            messages.c.conversation_id == conversation_id,
            messages.c.expires_at > _now(),
        )
        .order_by(messages.c.created_at, messages.c.id)
    ).mappings()
    output = []
    for row in rows:
        item = {k: row[k] for k in ("id", "role", "content", "request_id", "created_at")}
        if item["role"] == "assistant" and item["request_id"]:
            try:
                item["result"] = get_result(session, item["request_id"])["result"]
            except ApiError:
                item["result"] = None
        output.append(item)
    return {**conversation, "messages": output}


def recent_context(session: Session, conversation_id: str | None) -> str:
    if conversation_id is None:
        return ""
    require_conversation(session, conversation_id)
    rows = session.execute(
        sa.select(messages.c.role, messages.c.content)
        .where(
            messages.c.conversation_id == conversation_id,
            messages.c.expires_at > _now(),
        )
        .order_by(messages.c.created_at.desc())
        .limit(6)
    ).all()
    # Conversation content is context only, never evidence. Bound its size for 8K generation.
    return "\n".join(f"{r.role}: {r.content[:600]}" for r in reversed(rows))[-2400:]


def add_user_message(session: Session, conversation_id: str, content: str, request_id: str) -> None:
    require_conversation(session, conversation_id)
    now = _now()
    session.execute(
        sa.insert(messages).values(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=scrub_pii(content).scrubbed_text,
            request_id=request_id,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    session.execute(
        sa.update(conversations)
        .where(conversations.c.id == conversation_id)
        .values(
            updated_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    session.commit()


def result_summary(payload: dict[str, Any]) -> str:
    statements = [c["text"] for section in payload.get("sections", []) for c in section.get("claims", [])]
    return (
        "\n".join(statements)
        or payload.get("message")
        or payload.get("category_label")
        or payload.get("summary")
        or payload.get("type", "Result")
    )


def save_result(
    session: Session,
    request_id: str,
    payload: dict[str, Any],
    receipt_id: str,
    entry_hash: str,
    request_payload: dict[str, Any] | None = None,
    conversation_id: str | None = None,
) -> None:
    now = _now()
    clean = scrub_payload(payload)
    clean["receipt_id"] = receipt_id
    values = dict(
        request_id=request_id,
        workspace_id=workspace(),
        conversation_id=conversation_id,
        result=clean,
        request_payload=scrub_payload(request_payload),
        receipt_id=receipt_id,
        entry_hash=entry_hash,
        created_at=now,
        expires_at=now + timedelta(days=30),
    )
    session.execute(sa.insert(results).values(**values))
    if conversation_id:
        require_conversation(session, conversation_id)
        session.execute(
            sa.insert(messages).values(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                role="assistant",
                content=result_summary(clean),
                request_id=request_id,
                created_at=now,
                expires_at=now + timedelta(days=30),
            )
        )
    # Caller commits together with the audit entry.


def list_case_refs(session: Session) -> list[dict[str, Any]]:
    purge_expired(session)
    return [
        dict(r)
        for r in session.execute(
            sa.select(
                case_refs.c.request_id,
                case_refs.c.summary,
                results.c.receipt_id,
            )
            .select_from(case_refs.join(results))
            .where(
                case_refs.c.workspace_id == workspace(),
                results.c.workspace_id == workspace(),
                results.c.expires_at > _now(),
            )
            .order_by(case_refs.c.position, case_refs.c.created_at)
        ).mappings()
    ]


def add_case_ref(session: Session, request_id: str) -> list[dict[str, Any]]:
    result = get_result(session, request_id)
    exists = session.execute(
        sa.select(case_refs.c.request_id).where(
            case_refs.c.workspace_id == workspace(),
            case_refs.c.request_id == request_id,
        )
    ).first()
    if not exists:
        position = (
            session.execute(
                sa.select(sa.func.max(case_refs.c.position)).where(
                    case_refs.c.workspace_id == workspace(),
                )
            ).scalar()
            or 0
        )
        session.execute(
            sa.insert(case_refs).values(
                workspace_id=workspace(),
                request_id=request_id,
                summary=result_summary(result["result"])[:300],
                position=position + 1,
                created_at=_now(),
            )
        )
        session.commit()
    return list_case_refs(session)
