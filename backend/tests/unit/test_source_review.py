from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.ingest.quality import _covered_chars, approve_stage, authoritative_url, require_approval


def test_extraction_coverage_counts_overlapping_clauses_once_and_clips_offsets():
    assert _covered_chars([(0, 10), (5, 20), (30, 200), (-10, 2)], 100) == 90
    assert _covered_chars([], 100) == 0


@pytest.mark.parametrize(
    "url",
    [
        "https://ipindia.gov.in/legal.pdf",
        "https://www.wipo.int/treaty.pdf",
        "https://fssai.gov.in/file.pdf",
    ],
)
def test_review_accepts_authoritative_https_origins(url):
    assert authoritative_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://ipindia.gov.in/legal.pdf",
        "https://gov.in.attacker.test/file.pdf",
        "https://blog.test/file.pdf",
    ],
)
def test_review_rejects_untrusted_origins(url):
    assert not authoritative_url(url)


@pytest.mark.parametrize(
    "review",
    [
        None,
        SimpleNamespace(
            report={"issues": ["OCR missing"]}, reviewer="Reviewer", approved_report_hash="same", report_hash="same"
        ),
        SimpleNamespace(report={"issues": []}, reviewer=None, approved_report_hash="same", report_hash="same"),
        SimpleNamespace(report={"issues": []}, reviewer="Reviewer", approved_report_hash="stale", report_hash="new"),
    ],
)
def test_promotion_rejects_missing_failed_or_stale_approval(review):
    session = Mock()
    session.execute.return_value.first.return_value = review
    with pytest.raises(ValueError, match="Promotion requires"):
        require_approval(session, SimpleNamespace(id="version"))


@pytest.mark.parametrize(
    "status,hash,issues",
    [
        ("live", "exact", []),
        ("staged", "wrong", []),
        ("staged", "exact", ["extraction warning"]),
    ],
)
def test_approval_requires_exact_passing_staged_report(status, hash, issues):
    session = Mock()
    session.execute.side_effect = [
        SimpleNamespace(one=lambda: SimpleNamespace(id="version", status=status)),
        SimpleNamespace(one=lambda: SimpleNamespace(report_hash="exact", report={"issues": issues})),
    ]
    with pytest.raises(ValueError, match="exact, passing"):
        approve_stage(session, "label", "Human reviewer", hash)
    session.commit.assert_not_called()
