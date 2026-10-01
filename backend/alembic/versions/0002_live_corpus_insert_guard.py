"""Reject inserts as well as updates/deletes in live corpus versions.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_chunks_immutable ON chunks;")
    op.execute("DROP TRIGGER IF EXISTS trg_sections_immutable ON sections;")
    op.execute("DROP FUNCTION IF EXISTS prevent_live_mutation();")
    op.execute(
        """
        CREATE FUNCTION prevent_live_mutation() RETURNS trigger AS $$
        DECLARE
            v_status text;
        BEGIN
            IF TG_OP IN ('DELETE', 'UPDATE') THEN
                SELECT status INTO v_status
                FROM corpus_versions
                WHERE id = OLD.corpus_version_id;
                IF v_status = 'live' THEN
                    RAISE EXCEPTION
                        'cannot % row in % for a live corpus_version (id=%)',
                        TG_OP, TG_TABLE_NAME, OLD.corpus_version_id;
                END IF;
            END IF;

            IF TG_OP IN ('INSERT', 'UPDATE') THEN
                SELECT status INTO v_status
                FROM corpus_versions
                WHERE id = NEW.corpus_version_id;
            ELSE
                v_status := NULL;
            END IF;

            IF v_status = 'live' THEN
                RAISE EXCEPTION
                    'cannot % row in % for a live corpus_version (id=%)',
                    TG_OP, TG_TABLE_NAME, NEW.corpus_version_id;
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
        BEFORE INSERT OR UPDATE OR DELETE ON chunks
        FOR EACH ROW EXECUTE FUNCTION prevent_live_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_sections_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON sections
        FOR EACH ROW EXECUTE FUNCTION prevent_live_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sections_immutable ON sections;")
    op.execute("DROP TRIGGER IF EXISTS trg_chunks_immutable ON chunks;")
    op.execute("DROP FUNCTION IF EXISTS prevent_live_mutation();")
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
