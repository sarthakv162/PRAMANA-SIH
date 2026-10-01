"""Create least-privilege grants for the API runtime role.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT app_ro TO pramana_app;")
    op.execute("GRANT audit_append TO pramana_app;")
    op.execute("GRANT SELECT, INSERT ON requests, escalations TO pramana_app;")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT ON requests, escalations FROM pramana_app;")
    op.execute("REVOKE audit_append FROM pramana_app;")
    op.execute("REVOKE app_ro FROM pramana_app;")
