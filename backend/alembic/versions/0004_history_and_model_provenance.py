"""Shared demo history, expiring results, and corpus embedding provenance."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE corpus_versions ADD COLUMN embedding_model text NOT NULL DEFAULT 'legacy-bge-m3';")
    op.execute("""
        CREATE TABLE conversations (
            id uuid PRIMARY KEY, workspace_id text NOT NULL, title text NOT NULL,
            created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL
        );
        CREATE INDEX ix_conversations_workspace ON conversations(workspace_id, updated_at);
        CREATE TABLE saved_results (
            request_id text PRIMARY KEY, workspace_id text NOT NULL,
            conversation_id uuid REFERENCES conversations(id) ON DELETE CASCADE,
            result jsonb NOT NULL, request_payload jsonb, receipt_id text NOT NULL,
            entry_hash text NOT NULL, created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL
        );
        CREATE TABLE conversation_messages (
            id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role text NOT NULL CHECK(role IN ('user','assistant')), content text NOT NULL,
            request_id text, created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL
        );
        CREATE INDEX ix_messages_conversation ON conversation_messages(conversation_id, created_at);
        CREATE TABLE case_file_refs (
            workspace_id text NOT NULL, request_id text NOT NULL REFERENCES saved_results(request_id) ON DELETE CASCADE,
            summary text NOT NULL, position integer NOT NULL, created_at timestamptz NOT NULL,
            PRIMARY KEY(workspace_id, request_id)
        );
        CREATE TABLE document_versions (
            document_id uuid NOT NULL REFERENCES documents(id),
            corpus_version_id uuid NOT NULL REFERENCES corpus_versions(id),
            pdf_path text NOT NULL, file_sha256 text NOT NULL, PRIMARY KEY(document_id, corpus_version_id)
        );
        INSERT INTO document_versions SELECT DISTINCT d.id, s.corpus_version_id, d.pdf_path, d.file_sha256
            FROM documents d JOIN sections s ON d.id=s.document_id;
        GRANT SELECT ON document_versions TO app_ro;
        GRANT SELECT, INSERT ON document_versions TO ingest_rw;
        CREATE TABLE source_reviews (
            corpus_version_id uuid PRIMARY KEY REFERENCES corpus_versions(id),
            report jsonb NOT NULL, report_hash text NOT NULL, reviewer text,
            approved_report_hash text, approved_at timestamptz
        );
        GRANT SELECT, INSERT, UPDATE, DELETE ON conversations, conversation_messages, saved_results, case_file_refs TO pramana_app;
        GRANT SELECT ON source_reviews TO app_ro;
        GRANT SELECT, INSERT, UPDATE ON source_reviews TO ingest_rw;
    """)


def downgrade() -> None:
    for table in (
        "source_reviews",
        "document_versions",
        "case_file_refs",
        "conversation_messages",
        "saved_results",
        "conversations",
    ):
        op.execute(f"DROP TABLE {table};")
    op.execute("ALTER TABLE corpus_versions DROP COLUMN embedding_model;")
