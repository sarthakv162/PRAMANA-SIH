"""Initial schema — corpus, retrieval, graph, audit tables (docs/IMPLEMENTATION_PLAN.md §6.1).

Revision ID: 0001
Revises:
Create Date: 2026-09-30

Design notes:
- Primary keys are `uuid` (via pgcrypto's gen_random_uuid()) everywhere except audit_log,
  which uses `seq bigserial` as specified in §6.1 (it's an append-only hash chain, so a
  monotonic integer sequence is the point, not a UUID).
- Tables are created with raw SQL (`op.execute`) rather than `op.create_table` because the
  interesting parts of this migration — the HNSW/GIN/trgm indexes, the CHECK-constrained
  enum columns, the immutability trigger, and the role grants — are all things SQLAlchemy's
  table-builder DSL expresses awkwardly. Plain DDL is easier to read and to verify against
  the plan.
- Roles are created with a DO-block existence guard so re-running the migration against a
  DB that already has the roles (e.g. a shared dev Postgres) doesn't error. Table/index/
  trigger creation is NOT guarded — this migration assumes a fresh database, consistent
  with every other Alembic migration ever written; re-running it twice against the same DB
  is not a supported operation (use `alembic downgrade` first).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.execute(
        """
        CREATE TABLE corpus_versions (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            label       text NOT NULL UNIQUE,
            status      text NOT NULL CHECK (status IN ('staged', 'live', 'retired')),
            merkle_root text,
            created_at  timestamptz NOT NULL DEFAULT now(),
            notes       text
        );
        """
    )

    op.execute(
        """
        CREATE TABLE documents (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            short_key     text NOT NULL UNIQUE,
            title         text NOT NULL,
            doc_type      text NOT NULL CHECK (doc_type IN (
                              'statute', 'rule', 'regulation', 'treaty',
                              'notification', 'case', 'guideline', 'manual'
                          )),
            jurisdiction  text NOT NULL CHECK (jurisdiction IN ('IN', 'INTL')),
            issuer        text,
            source_url    text NOT NULL,
            pdf_path      text,
            file_sha256   text NOT NULL,
            language      text NOT NULL DEFAULT 'en',
            in_force_from date NOT NULL,
            in_force_to   date
        );
        """
    )

    op.execute(
        """
        CREATE TABLE sections (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id       uuid NOT NULL REFERENCES documents(id),
            corpus_version_id uuid NOT NULL REFERENCES corpus_versions(id),
            section_key       text NOT NULL,
            path              text[] NOT NULL DEFAULT '{}',
            heading           text,
            parent_id         uuid REFERENCES sections(id),
            effective_from    date NOT NULL,
            effective_to      date,
            supersedes_id     uuid REFERENCES sections(id),
            page_start        integer,
            page_end          integer,
            text              text NOT NULL,
            sha256            text NOT NULL,
            UNIQUE (section_key, corpus_version_id)
        );
        """
    )
    op.execute("CREATE INDEX ix_sections_document_id ON sections (document_id);")
    op.execute("CREATE INDEX ix_sections_corpus_version_id ON sections (corpus_version_id);")
    op.execute("CREATE INDEX ix_sections_parent_id ON sections (parent_id);")
    op.execute("CREATE INDEX ix_sections_supersedes_id ON sections (supersedes_id);")
    op.execute(
        "CREATE INDEX ix_sections_section_key_trgm ON sections "
        "USING gin (section_key gin_trgm_ops);"
    )
    op.execute(
        "CREATE INDEX ix_sections_heading_trgm ON sections USING gin (heading gin_trgm_ops);"
    )

    op.execute(
        """
        CREATE TABLE chunks (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            section_id        uuid NOT NULL REFERENCES sections(id),
            corpus_version_id uuid NOT NULL REFERENCES corpus_versions(id),
            jurisdiction      text NOT NULL CHECK (jurisdiction IN ('IN', 'INTL')),
            doc_type          text NOT NULL CHECK (doc_type IN (
                                  'statute', 'rule', 'regulation', 'treaty',
                                  'notification', 'case', 'guideline', 'manual'
                              )),
            effective_from    date NOT NULL,
            effective_to      date,
            page              integer,
            char_start        integer NOT NULL,
            char_end          integer NOT NULL,
            text              text NOT NULL,
            embed_text        text NOT NULL,
            sha256            text NOT NULL,
            bboxes            jsonb,
            embedding         vector(1024),
            tsv               tsvector
        );
        """
    )
    op.execute("CREATE INDEX ix_chunks_section_id ON chunks (section_id);")
    op.execute("CREATE INDEX ix_chunks_corpus_version_id ON chunks (corpus_version_id);")
    op.execute("CREATE INDEX ix_chunks_jurisdiction ON chunks (jurisdiction);")
    op.execute("CREATE INDEX ix_chunks_effective_from ON chunks (effective_from);")
    op.execute("CREATE INDEX ix_chunks_effective_to ON chunks (effective_to);")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops);"
    )
    op.execute("CREATE INDEX ix_chunks_tsv_gin ON chunks USING gin (tsv);")

    op.execute(
        """
        CREATE TABLE edges (
            src_section_id    uuid NOT NULL REFERENCES sections(id),
            dst_section_id    uuid NOT NULL REFERENCES sections(id),
            kind              text NOT NULL CHECK (kind IN (
                                  'amends', 'refers_to', 'defined_in',
                                  'proviso_of', 'exception_to'
                              )),
            corpus_version_id uuid NOT NULL REFERENCES corpus_versions(id),
            PRIMARY KEY (src_section_id, dst_section_id, kind, corpus_version_id)
        );
        """
    )
    op.execute("CREATE INDEX ix_edges_dst_section_id ON edges (dst_section_id);")
    op.execute("CREATE INDEX ix_edges_corpus_version_id ON edges (corpus_version_id);")

    op.execute(
        """
        CREATE TABLE glossary (
            term_en      text PRIMARY KEY,
            translations jsonb NOT NULL DEFAULT '{}',
            locked       boolean NOT NULL DEFAULT false
        );
        """
    )

    op.execute(
        """
        CREATE TABLE plants (
            id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            latin     text NOT NULL,
            sanskrit  text,
            common    jsonb,
            synonyms  text[]
        );
        """
    )

    op.execute(
        """
        CREATE TABLE classical_formulations (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name         text NOT NULL,
            source_text  text,
            ingredients  jsonb NOT NULL DEFAULT '[]',
            indications  text[]
        );
        """
    )

    op.execute(
        """
        CREATE TABLE watchlist_cases (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            title        text NOT NULL,
            jurisdiction text NOT NULL CHECK (jurisdiction IN ('IN', 'INTL')),
            summary      text,
            outcome      text,
            source_url   text
        );
        """
    )

    op.execute(
        """
        CREATE TABLE requests (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            corpus_version_id uuid NOT NULL REFERENCES corpus_versions(id),
            query_hash        text NOT NULL,
            lang              text NOT NULL,
            jurisdiction      text NOT NULL CHECK (jurisdiction IN ('IN', 'INTL', 'BOTH')),
            as_of             date NOT NULL,
            persona           text,
            deadline_at       timestamptz,
            created_at        timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_requests_corpus_version_id ON requests (corpus_version_id);")

    op.execute(
        """
        CREATE TABLE audit_log (
            seq         bigserial PRIMARY KEY,
            request_id  uuid NOT NULL REFERENCES requests(id),
            prev_hash   text,
            entry_hash  text NOT NULL,
            payload     jsonb NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_audit_log_request_id ON audit_log (request_id);")

    op.execute(
        """
        CREATE TABLE escalations (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            request_id  uuid NOT NULL REFERENCES requests(id),
            contact     text,
            note        text,
            status      text NOT NULL DEFAULT 'open',
            created_at  timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_escalations_request_id ON escalations (request_id);")

    op.execute(
        """
        CREATE TABLE eval_runs (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at  timestamptz NOT NULL DEFAULT now(),
            config      jsonb,
            results     jsonb
        );
        """
    )

    # --- Immutability: chunks/sections are frozen once their corpus_version is 'live' ---
    op.execute(
        """
        CREATE FUNCTION prevent_live_mutation() RETURNS trigger AS $$
        DECLARE
            v_status text;
        BEGIN
            SELECT status INTO v_status
            FROM corpus_versions
            WHERE id = OLD.corpus_version_id;

            IF v_status = 'live' THEN
                RAISE EXCEPTION
                    'cannot % row in % for a live corpus_version (id=%)',
                    TG_OP, TG_TABLE_NAME, OLD.id;
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_chunks_immutable
        BEFORE UPDATE OR DELETE ON chunks
        FOR EACH ROW EXECUTE FUNCTION prevent_live_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_sections_immutable
        BEFORE UPDATE OR DELETE ON sections
        FOR EACH ROW EXECUTE FUNCTION prevent_live_mutation();
        """
    )

    # --- Least-privilege roles (§6.1) ---
    # Login roles are provisioned separately from environment secrets at backend startup.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_ro') THEN
                CREATE ROLE app_ro NOLOGIN;
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ingest_rw') THEN
                CREATE ROLE ingest_rw NOLOGIN;
            END IF;
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'audit_append') THEN
                CREATE ROLE audit_append NOLOGIN;
            END IF;
        END
        $$;
        """
    )

    op.execute("GRANT USAGE ON SCHEMA public TO app_ro, ingest_rw, audit_append;")

    # app_ro: read-only at query time, every table (including future ones).
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_ro;")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_ro;"
    )

    # ingest_rw: read/write on corpus + reference tables only. The immutability trigger
    # still blocks UPDATE/DELETE on live-version chunks/sections regardless of this grant —
    # that invariant is enforced at the row level, not the role level.
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE ON
            documents, sections, chunks, edges, corpus_versions,
            plants, classical_formulations, watchlist_cases, glossary
        TO ingest_rw;
        """
    )

    # audit_append: insert-only on the hash chain, nothing else.
    op.execute("GRANT INSERT ON audit_log TO audit_append;")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE audit_log_seq_seq TO audit_append;")


def downgrade() -> None:
    op.execute("REVOKE ALL ON SEQUENCE audit_log_seq_seq FROM audit_append;")
    op.execute("REVOKE ALL ON audit_log FROM audit_append;")
    op.execute(
        "REVOKE ALL ON documents, sections, chunks, edges, corpus_versions, "
        "plants, classical_formulations, watchlist_cases, glossary FROM ingest_rw;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM app_ro;"
    )
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_ro;")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_ro, ingest_rw, audit_append;")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_ro') THEN
                DROP ROLE app_ro;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'ingest_rw') THEN
                DROP ROLE ingest_rw;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'audit_append') THEN
                DROP ROLE audit_append;
            END IF;
        END
        $$;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_sections_immutable ON sections;")
    op.execute("DROP TRIGGER IF EXISTS trg_chunks_immutable ON chunks;")
    op.execute("DROP FUNCTION IF EXISTS prevent_live_mutation();")

    op.execute("DROP TABLE IF EXISTS eval_runs;")
    op.execute("DROP TABLE IF EXISTS escalations;")
    op.execute("DROP TABLE IF EXISTS audit_log;")
    op.execute("DROP TABLE IF EXISTS requests;")
    op.execute("DROP TABLE IF EXISTS watchlist_cases;")
    op.execute("DROP TABLE IF EXISTS classical_formulations;")
    op.execute("DROP TABLE IF EXISTS plants;")
    op.execute("DROP TABLE IF EXISTS glossary;")
    op.execute("DROP TABLE IF EXISTS edges;")
    op.execute("DROP TABLE IF EXISTS chunks;")
    op.execute("DROP TABLE IF EXISTS sections;")
    op.execute("DROP TABLE IF EXISTS documents;")
    op.execute("DROP TABLE IF EXISTS corpus_versions;")
