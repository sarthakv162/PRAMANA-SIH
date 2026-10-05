"""Export real corpus data and source PDFs for the hosted demo, without user history."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "corpus_versions", "documents", "document_versions", "sections", "chunks", "edges",
    "glossary", "plants", "classical_formulations", "watchlist_cases", "source_reviews",
)


def main() -> None:
    output = ROOT / "backups/demo-seed.tar.gz"
    output.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pramana-seed-") as temporary:
        dump = Path(temporary) / "corpus.dump"
        command = [
            "docker", "compose", "exec", "-T", "db", "sh", "-c",
            'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --data-only '
            + " ".join(f"--table=public.{table}" for table in TABLES),
        ]
        with dump.open("wb") as target:
            subprocess.run(command, cwd=ROOT, stdout=target, check=True)
        with tarfile.open(output, "w:gz") as archive:
            archive.add(dump, arcname="corpus.dump")
            archive.add(ROOT / "corpus", arcname="corpus", filter=lambda entry: None if entry.name.endswith(".DS_Store") else entry)
            evaluation = ROOT / "eval/results/latest.json"
            if evaluation.is_file():
                archive.add(evaluation, arcname="eval/results/latest.json")
    output.chmod(0o600)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(json.dumps({"file": str(output), "bytes": output.stat().st_size, "sha256": digest,
                      "contains": "Existing corpus/statuses/PDFs/reference data and measured evaluation; no conversations or audit payloads"}, indent=2))


if __name__ == "__main__":
    main()
