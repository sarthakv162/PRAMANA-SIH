"""Keep official source URLs with each immutable corpus PDF artifact."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE document_versions ADD COLUMN source_url text;")
    op.execute("UPDATE document_versions v SET source_url=d.source_url FROM documents d WHERE v.document_id=d.id;")
    op.execute("ALTER TABLE document_versions ALTER COLUMN source_url SET NOT NULL;")


def downgrade() -> None:
    op.execute("ALTER TABLE document_versions DROP COLUMN source_url;")
