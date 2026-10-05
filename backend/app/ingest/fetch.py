"""Manifest-driven download (§6.2 step 1). Never ingest a PDF that isn't listed in
`corpus/manifest.yaml` — that file is the one place recording where every source came from
and what it's supposed to hash to.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from app.core.hashing import sha256_hex


def manifest_path() -> Path:
    candidate = os.environ.get("PRAMANA_CANDIDATE_MANIFEST")
    return Path(candidate) if candidate else Path(__file__).resolve().parents[3] / "corpus" / "manifest.yaml"


def raw_dir() -> Path:
    candidate = os.environ.get("PRAMANA_CANDIDATE_RAW")
    return Path(candidate) if candidate else Path(__file__).resolve().parents[3] / "corpus" / "raw"


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
    download_strategy: str = "pdf"


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
            download_strategy=s.get("download_strategy", "pdf"),
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


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._active: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            href = dict(attrs).get("href") or ""
            self._active = [href, ""]

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._active[1] += data

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._active is not None:
            self.links.append((self._active[0], self._active[1].strip()))
            self._active = None


def _get_with_retries(client: httpx.Client, url: str, source_id: str) -> httpx.Response:
    """Retry transient transport/status failures, never semantic document errors."""
    for attempt in range(3):
        try:
            response = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except httpx.TimeoutException:
            if attempt == 2:
                raise
        except httpx.TransportError:
            if attempt == 2:
                raise
        time.sleep(2**attempt)
    raise RuntimeError(f"{source_id}: source download exhausted retries")


def _resolve_wipo_lex_pdf(client: httpx.Client, source: ManifestSource) -> str:
    """Resolve a stable WIPO Lex legislation page to its current English PDF.

    WIPO signs its PDF download URLs with short-lived credentials. The manifest stores
    the stable legislation page, then this function extracts only a same-page English
    PDF hosted on WIPO's document service. This prevents expiring download URLs from
    breaking clean setup or future corpus refreshes.
    """
    parsed_source_url = urlparse(source.url)
    if parsed_source_url.hostname not in {"wipo.int", "www.wipo.int"} or not parsed_source_url.path.startswith(
        "/wipolex/en/legislation/details/"
    ):
        raise ValueError(f"{source.id}: wipo_lex download requires a WIPO Lex legislation page")

    page = _get_with_retries(client, source.url, source.id)
    if not page.headers.get("content-type", "").lower().startswith("text/html"):
        raise ValueError(f"{source.id}: WIPO Lex resolver page was not HTML")

    anchors = _AnchorCollector()
    anchors.feed(page.text)
    candidates: dict[str, str] = {}
    for href, label in anchors.links:
        resolved = urljoin(str(page.url), href)
        parsed = urlparse(resolved)
        if (
            parsed.hostname == "wipolex-res.wipo.int"
            and parsed.path.lower().endswith(".pdf")
            and "/laws/en/" in parsed.path.lower()
        ):
            candidates[resolved] = label

    exact_title = [url for url, label in candidates.items() if label.casefold() == source.title.casefold()]
    if len(exact_title) == 1:
        return exact_title[0]
    if len(candidates) == 1:
        return next(iter(candidates))
    raise ValueError(f"{source.id}: could not identify one English PDF on the WIPO Lex page")


def fetch_source(source: ManifestSource, force: bool = False) -> Path:
    """Download (if needed) and verify one manifest source. Returns the local PDF path.

    First fetch of a source records its sha256 into the manifest (so the source URL and its
    integrity are pinned together from then on); every subsequent fetch checks the file on
    disk still hashes to that value and re-downloads only if `force=True` or the file is
    missing.
    """
    dest = raw_dir() / f"{source.id}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force and source.sha256 is not None:
        digest = sha256_hex(dest.read_bytes())
        if digest == source.sha256:
            return dest

    # Public government hosts occasionally stall during TLS setup or return transient 5xx
    # errors. Retry only those failures; authentication/not-found and other 4xx responses
    # should fail immediately. Never write a partial response to the corpus directory.
    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        download_url = _resolve_wipo_lex_pdf(client, source) if source.download_strategy == "wipo_lex" else source.url
        if source.download_strategy not in {"pdf", "wipo_lex"}:
            raise ValueError(f"{source.id}: unsupported download strategy {source.download_strategy}")
        response = _get_with_retries(client, download_url, source.id)
        content = response.content

    digest = sha256_hex(content)
    # Government download endpoints occasionally return an HTML error/challenge page
    # with status 200. Do not pin its hash or let the PDF parser fail later with a
    # misleading error; a PDF header must occur within the first 1024 bytes.
    if b"%PDF-" not in content[:1024]:
        content_type = response.headers.get("content-type", "unknown")
        raise ValueError(f"{source.id}: source did not return a PDF (content-type: {content_type})")
    if source.sha256 is not None and digest != source.sha256:
        raise ValueError(
            f"{source.id}: downloaded file sha256 {digest} does not match manifest "
            f"{source.sha256} — the upstream source changed; verify before re-ingesting."
        )
    dest.write_bytes(content)
    if source.sha256 is None:
        _update_manifest_sha256(source.id, digest)
    return dest
