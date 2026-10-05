"""Package the actual live corpus for an ephemeral HF Space; never promote staging."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import sqlalchemy as sa
from app.core.db import engine
from app.core.portable import populate_snapshot
from app.retrieval import repo
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]


def export(output: Path, from_compose: bool = False) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    seed = output / "corpus.sqlite"
    if seed.exists():
        raise ValueError(
            "Output already has a corpus snapshot; use a new output directory"
        )
    if from_compose:
        code = """import json
from app.core.db import SessionLocal
from app.retrieval import repo
with SessionLocal() as session:
 version = repo.live_corpus_version(session)
 if not version: raise ValueError("No live corpus")
 data = repo.snapshot_rows(session, version[0])
 print(json.dumps(data, default=lambda value: value.tolist() if hasattr(value, "tolist") else str(value)))
"""
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "backend", "python", "-c", code],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        version = (
            data["corpus_versions"][0]["id"],
            data["corpus_versions"][0]["label"],
        )
        for name, rows in data.items():
            for row in rows:
                for column in repo.metadata.tables[name].c:
                    if row.get(column.name) is not None:
                        if isinstance(column.type, sa.DateTime):
                            row[column.name] = datetime.fromisoformat(row[column.name])
                        elif isinstance(column.type, sa.Date):
                            row[column.name] = date.fromisoformat(row[column.name])
    else:
        with Session(engine) as session:
            version = repo.live_corpus_version(session)
            if not version:
                raise ValueError("There is no live corpus to export")
            data = repo.snapshot_rows(session, version[0])
    target = sa.create_engine(f"sqlite:///{seed}")
    try:
        populate_snapshot(target, data)
    finally:
        target.dispose()
    artifacts, unavailable = [], []
    for row in data["document_versions"]:
        relative = Path(row["pdf_path"])
        source = (ROOT / "corpus" / relative).resolve()
        if not source.is_relative_to((ROOT / "corpus").resolve()):
            raise ValueError("PDF path escapes the corpus directory")
        actual = (
            hashlib.sha256(source.read_bytes()).hexdigest()
            if source.is_file()
            else None
        )
        if actual != row["file_sha256"]:
            unavailable.append(
                {
                    "document_id": str(row["document_id"]),
                    "pdf_path": str(relative),
                    "reason": "missing_or_hash_mismatch",
                }
            )
            continue
        destination = output / "corpus" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        artifacts.append({"path": f"corpus/{relative}", "sha256": actual})
    manifest = {
        "format": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "corpus_version": version[1],
        "corpus_status": data["corpus_versions"][0]["status"],
        "embedding_model": data["corpus_versions"][0]["embedding_model"],
        "merkle_root": data["corpus_versions"][0]["merkle_root"],
        "seed_sha256": hashlib.sha256(seed.read_bytes()).hexdigest(),
        "counts": {name: len(rows) for name, rows in data.items()},
        "artifacts": artifacts,
        "unavailable_artifacts": unavailable,
        "includes_user_content": False,
        "includes_staged_versions": False,
    }
    (output / "seed-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--from-compose",
        action="store_true",
        help="Read through the running backend's database connection",
    )
    args = parser.parse_args()
    print(json.dumps(export(args.output.resolve(), args.from_compose), indent=2))
