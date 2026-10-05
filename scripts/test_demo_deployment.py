"""Check cloud URL normalization and stable runtime logins without contacting a provider."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

spec = importlib.util.spec_from_file_location("demo_start", Path(__file__).resolve().parents[1] / "deploy/start.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_railway_postgres_url_is_normalized_and_passwords_are_stable(monkeypatch):
    for variable in ("DATABASE_URL_ADMIN", "APP_DB_PASSWORD", "INGEST_DB_PASSWORD", "INGEST_DATABASE_URL"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:sample-only@postgres.railway.internal:5432/railway?sslmode=require")
    module.configure_database()
    from os import environ

    owner = make_url(environ["DATABASE_URL_ADMIN"])
    app = make_url(environ["DATABASE_URL"])
    ingest = make_url(environ["INGEST_DATABASE_URL"])
    assert owner.drivername == "postgresql+psycopg"
    assert app.username == "pramana_app" and ingest.username == "ingest_rw"
    assert app.password != ingest.password != owner.password
    assert app.query["sslmode"] == "require"
    previous = app.password
    module.configure_database()
    assert make_url(environ["DATABASE_URL"]).password == previous
    assert module.postgres_environment()["PGPASSWORD"] == "sample-only"


def test_missing_database_url_reports_a_clear_configuration_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL_ADMIN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Set DATABASE_URL"):
        module.configure_database()
