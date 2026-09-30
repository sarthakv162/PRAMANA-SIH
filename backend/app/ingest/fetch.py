"""Manifest-driven download (§6.2 step 1). Never ingest a PDF that isn't listed in
`corpus/manifest.yaml` — that file is the one place recording where every source came from
and what it's supposed to hash to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.core.hashing import sha256_hex


def manifest_path() -> Path:
    return Path(__file__).resolve().parents[3] / "corpus" / "manifest.yaml"


def raw_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "corpus" / "raw"


@dataclass
class ManifestSource:
    id: str
    title: str
    jurisdiction: str
    doc_type: str
    issuer: str | None
    tier: str
    language: str
    url: str
    sha256: str | None
    in_force_from: str
    in_force_to: str | None


def load_manifest() -> list[ManifestSource]:
    raw = yaml.safe_load(manifest_path().read_text())
    return [
        ManifestSource(
            id=s["id"],
            title=s["title"],
            jurisdiction=s["jurisdiction"],
            doc_type=s["doc_type"],
            issuer=s.get("issuer"),
            tier=s.get("tier", "A"),
            language=s.get("language", "en"),
            url=s["url"],
            sha256=s.get("sha256"),
            in_force_from=s["in_force_from"],
            in_force_to=s.get("in_force_to"),
        )
        for s in raw["sources"]
    ]


def _update_manifest_sha256(source_id: str, sha256: str) -> None:
    path = manifest_path()
    raw: dict[str, Any] = yaml.safe_load(path.read_text())
    for s in raw["sources"]:
        if s["id"] == source_id:
            s["sha256"] = sha256
            break
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True))


def fetch_source(source: ManifestSource, force: bool = False) -> Path:
    """Download (if needed) and verify one manifest source. Returns the local PDF path.

    First fetch of a source records its sha256 into the manifest (so the source URL and its
    integrity are pinned together from then on); every subsequent fetch checks the file on
    disk still hashes to that value and re-downloads only if `force=True` or the file is
    missing.
    """
    dest = raw_dir() / f"{source.id}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        digest = sha256_hex(dest.read_bytes())
        if source.sha256 is None or digest == source.sha256:
            return dest

    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        response = client.get(source.url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        content = response.content

    digest = sha256_hex(content)
    if source.sha256 is not None and digest != source.sha256:
        raise ValueError(
            f"{source.id}: downloaded file sha256 {digest} does not match manifest "
            f"{source.sha256} — the upstream source changed; verify before re-ingesting."
        )
    dest.write_bytes(content)
    if source.sha256 is None:
        _update_manifest_sha256(source.id, digest)
    return dest
