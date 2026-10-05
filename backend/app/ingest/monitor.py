"""Weekly official-source checks. Changed bytes are staged, never promoted automatically."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.core.hashing import sha256_hex
from app.ingest import fetch
from app.ingest.quality import authoritative_url

CHECK_PATH = fetch.raw_dir() / "source-check-latest.json"


def check_sources() -> dict[str, Any]:
    now = datetime.now(UTC)
    directory = fetch.raw_dir() / "source-updates" / now.strftime("%Y%m%dT%H%M%SZ")
    directory.mkdir(parents=True, exist_ok=True)
    candidate = yaml.safe_load(fetch.manifest_path().read_text())
    entries = {s["id"]: s for s in candidate["sources"]}
    checks = []
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for source in fetch.load_manifest():
            try:
                if not authoritative_url(source.url):
                    raise ValueError("Source has no authoritative origin")
                url = (
                    fetch._resolve_wipo_lex_pdf(client, source)
                    if source.download_strategy == "wipo_lex"
                    else source.url
                )
                response = fetch._get_with_retries(client, url, source.id)
                if not authoritative_url(str(response.url)) or b"%PDF-" not in response.content[:1024]:
                    raise ValueError("Source did not return an authoritative PDF")
                digest = sha256_hex(response.content)
                changed = digest != source.sha256
                checks.append(
                    {"source_id": source.id, "status": "changed" if changed else "unchanged", "sha256": digest}
                )
                (directory / f"{source.id}.pdf").write_bytes(response.content)
                entries[source.id]["sha256"] = digest
            except Exception as exc:
                checks.append({"source_id": source.id, "status": "check_failed", "error": type(exc).__name__})
                # A failed check cannot silently supply content for staged ingestion.
    changed = any(row["status"] == "changed" for row in checks)
    failed = any(row["status"] == "check_failed" for row in checks)
    candidate_path = directory / "manifest.yaml"
    if changed and not failed:
        candidate_path.write_text(yaml.safe_dump(candidate, sort_keys=False, allow_unicode=True))
    report = {
        "checked_at": now.isoformat(),
        "next_check_at": (now + timedelta(days=7)).isoformat(),
        "checks": checks,
        "candidate_manifest": str(candidate_path) if changed and not failed else None,
        "promotion": "requires staged ingestion, quality evaluation and named reviewer approval",
    }
    CHECK_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECK_PATH.write_text(json.dumps(report, indent=2))
    if not changed:
        shutil.rmtree(directory)
    return report


def stage_candidate(path: str) -> None:
    """Ingest a complete snapshot without changing the canonical manifest or active PDFs."""
    import os
    import sys

    from app.ingest.cli import main as ingest_main

    candidate = Path(path).resolve()
    if not candidate.is_relative_to(fetch.raw_dir().resolve() / "source-updates"):
        raise ValueError("Candidate must come from the source-update staging directory")
    os.environ["PRAMANA_CANDIDATE_MANIFEST"] = str(candidate)
    os.environ["PRAMANA_CANDIDATE_RAW"] = str(candidate.parent)
    sys.argv = ["ingest", "--version-label", "source-update-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")]
    ingest_main()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--stage-candidate")
    args = parser.parse_args()
    if args.stage_candidate:
        stage_candidate(args.stage_candidate)
        return
    while True:
        due = True
        if args.loop and CHECK_PATH.exists():
            try:
                due = datetime.fromisoformat(json.loads(CHECK_PATH.read_text())["next_check_at"]) <= datetime.now(UTC)
            except (ValueError, KeyError):
                pass
        if due:
            print(json.dumps(check_sources()), flush=True)
        if not args.loop:
            return
        time.sleep(60)


if __name__ == "__main__":
    main()
