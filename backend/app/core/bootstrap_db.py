"""Create runtime DB logins from environment secrets and apply Alembic migrations."""

from __future__ import annotations

from pathlib import Path

import psycopg
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url

from alembic import command
from app.config import get_settings


def _ensure_login(connection: psycopg.Connection, role: str, password: str) -> None:
    if not password:
        raise RuntimeError(f"A non-empty password is required to provision database role {role}.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
        exists = cursor.fetchone() is not None
        verb = sql.SQL("ALTER ROLE") if exists else sql.SQL("CREATE ROLE")
        cursor.execute(
            sql.SQL("{} {} LOGIN PASSWORD {}").format(
                verb,
                sql.Identifier(role),
                sql.Literal(password),
            )
        )


def provision_roles() -> None:
    settings = get_settings()
    if not settings.database_url_admin:
        raise RuntimeError("DATABASE_URL_ADMIN is required for database setup.")
    admin = make_url(settings.database_url_admin)
    conninfo = admin.render_as_string(hide_password=False).replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(conninfo) as connection:
        _ensure_login(connection, "pramana_app", settings.app_db_password)
        _ensure_login(connection, "ingest_rw", settings.ingest_db_password)


def migrate() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(config, "head")


def main() -> None:
    provision_roles()
    migrate()


if __name__ == "__main__":
    main()
