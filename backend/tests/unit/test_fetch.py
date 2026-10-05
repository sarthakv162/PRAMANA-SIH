from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.ingest import fetch


def _source() -> fetch.ManifestSource:
    return fetch.ManifestSource(
        id="sample_act",
        title="Sample Act",
        jurisdiction="IN",
        doc_type="statute",
        issuer="Government of India",
        tier="A",
        language="en",
        url="https://example.invalid/sample.pdf",
        sha256=None,
        in_force_from="2000-01-01",
        in_force_to=None,
    )


def test_fetch_retries_transient_connection_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def get(self, url: str, **_: object) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise httpx.ConnectTimeout("temporary timeout")
            return httpx.Response(200, content=b"%PDF-test", request=httpx.Request("GET", url))

    monkeypatch.setattr(fetch.httpx, "Client", Client)
    monkeypatch.setattr(fetch, "raw_dir", lambda: tmp_path)
    monkeypatch.setattr(fetch, "_update_manifest_sha256", lambda *_: None)
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)

    result = fetch.fetch_source(_source())

    assert calls == 3
    assert result.read_bytes() == b"%PDF-test"


def test_fetch_does_not_retry_nontransient_http_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def get(self, url: str, **_: object) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr(fetch.httpx, "Client", Client)
    monkeypatch.setattr(fetch, "raw_dir", lambda: tmp_path)

    with pytest.raises(httpx.HTTPStatusError):
        fetch.fetch_source(_source())

    assert calls == 1


def test_fetch_rejects_success_status_html_instead_of_pinning_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def get(self, url: str, **_: object) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                200,
                content=b"<!doctype html><title>Access denied</title>",
                headers={"content-type": "text/html"},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(fetch.httpx, "Client", Client)
    monkeypatch.setattr(fetch, "raw_dir", lambda: tmp_path)

    with pytest.raises(ValueError, match="did not return a PDF"):
        fetch.fetch_source(_source())

    assert calls == 1
    assert not (tmp_path / "sample_act.pdf").exists()


def test_fetch_does_not_reuse_unpinned_cached_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cached_path = tmp_path / "sample_act.pdf"
    cached_path.write_bytes(b"%PDF-stale cached source")
    calls = 0

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def get(self, url: str, **_: object) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                200,
                content=b"%PDF-current source",
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(fetch.httpx, "Client", Client)
    monkeypatch.setattr(fetch, "raw_dir", lambda: tmp_path)
    monkeypatch.setattr(fetch, "_update_manifest_sha256", lambda *_: None)

    result = fetch.fetch_source(_source())

    assert calls == 1
    assert result.read_bytes() == b"%PDF-current source"


def test_wipo_lex_page_resolves_current_english_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = fetch.ManifestSource(
        id="trade_marks_act_1999",
        title="The Trade Marks Act, 1999",
        jurisdiction="IN",
        doc_type="statute",
        issuer="WIPO Lex (Government of India text)",
        tier="A",
        language="en",
        url="https://www.wipo.int/wipolex/en/legislation/details/22958",
        sha256=None,
        in_force_from="2023-08-11",
        in_force_to=None,
        download_strategy="wipo_lex",
    )
    html = b"""<html><body>
      <a href="https://wipolex-res.wipo.int/edocs/lexdocs/laws/hi/in/in154hi.pdf?token=old">
        The Trade Marks Act, 1999, amended up to Act No. 7 of 2017 is provided for user convenience
      </a>
      <a href="https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/in/in154en_1.pdf?token=fresh">
        The Trade Marks Act, 1999
      </a>
    </body></html>"""
    requested: list[str] = []

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def get(self, url: str, **_: object) -> httpx.Response:
            requested.append(url)
            if url == source.url:
                return httpx.Response(
                    200,
                    content=html,
                    headers={"content-type": "text/html; charset=utf-8"},
                    request=httpx.Request("GET", url),
                )
            return httpx.Response(
                200,
                content=b"%PDF-current consolidated text",
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(fetch.httpx, "Client", Client)
    monkeypatch.setattr(fetch, "raw_dir", lambda: tmp_path)
    monkeypatch.setattr(fetch, "_update_manifest_sha256", lambda *_: None)

    result = fetch.fetch_source(source)

    assert requested == [
        source.url,
        "https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/in/in154en_1.pdf?token=fresh",
    ]
    assert result.read_bytes() == b"%PDF-current consolidated text"
