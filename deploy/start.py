"""Start the real web app and local Ollama in one hosted Docker service."""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

WORKSPACE = Path("/workspace")
DATA = Path("/data")
MODELS = ("qwen3:4b", "qwen3-embedding:0.6b")


def configure_database() -> None:
    """Accept a normal PostgreSQL URL and provision the app's runtime logins."""
    raw = os.environ.get("DATABASE_URL_ADMIN") or os.environ.get("DATABASE_URL", "")
    if not raw:
        raise RuntimeError("Set DATABASE_URL to the PostgreSQL service connection.")
    admin = make_url(raw).set(drivername="postgresql+psycopg")
    if not admin.password:
        raise RuntimeError("The PostgreSQL connection must include its generated password.")
    os.environ["DATABASE_URL_ADMIN"] = admin.render_as_string(hide_password=False)
    for role, password_var, url_var in (
        ("pramana_app", "APP_DB_PASSWORD", "DATABASE_URL"),
        ("ingest_rw", "INGEST_DB_PASSWORD", "INGEST_DATABASE_URL"),
    ):
        # Stable per-role credentials derived from the database secret, never printed.
        password = os.environ.get(password_var) or hmac.new(
            admin.password.encode(), f"pramana/{role}".encode(), "sha256"
        ).hexdigest()
        os.environ[password_var] = password
        os.environ[url_var] = admin.set(username=role, password=password).render_as_string(hide_password=False)


def prepare_storage() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    corpus = DATA / "corpus"
    corpus.mkdir(exist_ok=True)
    (corpus / "raw").mkdir(exist_ok=True)
    for seed in (WORKSPACE / "corpus-seed").iterdir():
        destination = corpus / seed.name
        if not destination.exists():
            shutil.copy2(seed, destination)
    for target, destination in ((WORKSPACE / "corpus", corpus), (WORKSPACE / "eval/results", DATA / "eval/results")):
        destination.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.symlink_to(destination, target_is_directory=True)


def postgres_environment() -> dict[str, str]:
    url = make_url(os.environ["DATABASE_URL_ADMIN"])
    return {
        **os.environ,
        "PGHOST": url.host or "localhost",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "postgres",
        "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database or "postgres",
        **({"PGSSLMODE": url.query["sslmode"]} if "sslmode" in url.query else {}),
    }


def import_demo_seed() -> None:
    """Restore real corpus rows only into an empty corpus; never promote staged data."""
    archive = DATA / "demo-seed.tar.gz"
    if not archive.exists():
        print("No demo seed uploaded. Corpus is empty until real sources are imported.", flush=True)
        return
    admin = os.environ["DATABASE_URL_ADMIN"].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(admin) as connection:
        if connection.execute("SELECT count(*) FROM corpus_versions").fetchone()[0]:
            return
    with tarfile.open(archive) as bundle:
        bundle.extractall(DATA, filter="data")
    subprocess.run(
        ["pg_restore", "--data-only", "--disable-triggers", "--single-transaction", "--no-owner", "--no-privileges",
         "--dbname", postgres_environment()["PGDATABASE"], str(DATA / "corpus.dump")],
        env=postgres_environment(), check=True,
    )
    (DATA / "corpus.dump").unlink()
    print("Imported the existing corpus. History starts empty.", flush=True)


def verify_artifacts() -> None:
    # Recheck on every start, including after an interrupted import.
    admin = os.environ["DATABASE_URL_ADMIN"].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(admin) as connection:
        artifacts = connection.execute("SELECT pdf_path, file_sha256 FROM document_versions").fetchall()
        unavailable = 0
        for relative, digest in artifacts:
            path = (DATA / "corpus" / relative).resolve()
            if not path.is_relative_to((DATA / "corpus").resolve()) or not path.is_file():
                unavailable += 1
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                unavailable += 1
    print(f"Corpus PDFs checked: {len(artifacts) - unavailable} valid, {unavailable} unavailable. Invalid PDFs cannot be viewed.", flush=True)


def wait_http(url: str, child: subprocess.Popen, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("A service exited before becoming ready.")
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError("A service did not become ready before the startup deadline.")


def main() -> None:
    children: list[subprocess.Popen] = []

    def stop(_signal: int, _frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        configure_database()
        prepare_storage()
        port = int(os.environ.get("PORT", "8080"))
        if not 1 <= port <= 65535 or port in {8000, 11434}:
            raise RuntimeError("PORT must be a valid public port, different from the internal service ports.")
        template = (WORKSPACE / "deploy/nginx.conf.template").read_text()
        Path("/etc/nginx/conf.d/pramana.conf").write_text(template.replace("__PORT__", str(port)))
        subprocess.run([sys.executable, "-m", "app.core.bootstrap_db"], check=True)
        import_demo_seed()
        verify_artifacts()
        ollama = subprocess.Popen(["ollama", "serve"])
        children.append(ollama)
        wait_http("http://127.0.0.1:11434/api/tags", ollama, 60)
        for model in MODELS:
            subprocess.run(["ollama", "pull", model], check=True)
        backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
        children.append(backend)
        wait_http("http://127.0.0.1:8000/v1/health", backend, 900)
        children.append(subprocess.Popen(["nginx", "-g", "daemon off;"]))
        children.append(subprocess.Popen([sys.executable, "-m", "app.ingest.monitor", "--loop"]))
        print(f"PRAMANA is listening on port {port}; Ollama runs inside this server.", flush=True)
        while True:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("An application service exited; restarting the deployment is required.")
            time.sleep(1)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 10
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError, psycopg.Error, SQLAlchemyError, tarfile.TarError) as error:
        # Connection URLs and passwords must not appear in deployment logs.
        print(f"Deployment startup failed ({type(error).__name__}). Check database access, seed files, model downloads and service logs.", file=sys.stderr)
        raise SystemExit(1) from None
