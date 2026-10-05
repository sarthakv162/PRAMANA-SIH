"""Retrieval-stage evaluation shared by `make eval` and the corpus promotion gate."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.orchestrator.nodes import retrieve
from app.orchestrator.router import route
from app.orchestrator.state import RequestState
from app.retrieval import repo
from app.schemas.query import QueryRequest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = PROJECT_ROOT / "eval" / "golden" / "golden.jsonl"
RESULTS_PATH = PROJECT_ROOT / "eval" / "results" / "latest.json"


def _golden_questions() -> list[dict[str, Any]]:
    with GOLDEN_PATH.open() as golden_file:
        return [json.loads(line) for line in golden_file if line.strip()]


def evaluate_version(session: Session, corpus_version_id: str, label: str) -> dict[str, Any]:
    """Measure retrieval against the small golden set for exactly one pinned version."""
    golden = _golden_questions()
    hits = 0
    gold_total = 0
    retrieved_total = 0
    jurisdiction_leaks = 0
    abstain_correct = 0
    abstain_total = 0

    for item in golden:
        as_of = datetime.fromisoformat(item["as_of"]).date()
        jurisdictions = [item["jurisdiction"]] if item["jurisdiction"] != "BOTH" else ["IN", "INTL"]
        intent, direct_key = route(item["question"])
        state = RequestState(
            request_id="evaluation",
            raw_query="",
            request=QueryRequest(query=item["question"]),
            corpus_version_id=corpus_version_id,
            corpus_version_label=label,
            query_en=item["question"],
            jurisdictions=jurisdictions,
            as_of=as_of,
            intent=intent,
            direct_section_key=direct_key,
        )
        rows = [] if intent in {"out_of_scope", "legal_advice", "dossier"} else retrieve.run(session, state)
        retrieved_keys: set[str] = set()
        for row in rows:
            if row.jurisdiction not in jurisdictions:
                jurisdiction_leaks += 1
            sections = repo.fetch_sections_by_ids(session, [str(row.section_id)])
            retrieved_keys.update(section.section_key for section in sections)

        gold_keys = set(item["gold_evidence_keys"])
        if item["should_abstain"]:
            abstain_total += 1
            if not rows:
                abstain_correct += 1
        elif gold_keys:
            gold_total += len(gold_keys)
            hits += len(gold_keys & retrieved_keys)
            retrieved_total += len(retrieved_keys)

    precision = hits / retrieved_total if retrieved_total else 0.0
    recall = hits / gold_total if gold_total else 0.0
    abstention_accuracy = abstain_correct / abstain_total if abstain_total else 0.0
    return {
        "run_id": f"eval_{uuid.uuid4().hex[:16]}",
        "corpus_version": label,
        "n_questions": len(golden),
        "method": (
            "Actual production routing and retrieval nodes against the pinned version; generation is not evaluated."
        ),
        "conditions": [
            {
                "name": "PRAMANA production routing + retrieval + legal graph; synthesis not measured",
                "citation_precision": round(precision, 2),
                "citation_recall": round(recall, 2),
                "faithfulness": None,
                "abstention_accuracy": round(abstention_accuracy, 2),
                "jurisdiction_leaks": jurisdiction_leaks,
            }
        ],
        "risk_coverage": [],
        "generated_at": datetime.now(UTC).isoformat(),
    }


def save_results(results: dict[str, Any]) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))


def evaluate_live_version(session: Session) -> dict[str, Any]:
    live_version = repo.live_corpus_version(session)
    if live_version is None:
        raise RuntimeError("no live corpus_version — run `make ingest && make promote` first")
    results = evaluate_version(session, *live_version)
    save_results(results)
    return results


def smoke_test_staged_version(session: Session, label: str) -> dict[str, Any]:
    """Run the golden retrieval smoke check before a staged corpus can become live.

    The plan defines no numeric promotion thresholds. This gate requires a staged version,
    a non-empty golden set, and zero jurisdiction leaks; the measured quality figures are
    written to `eval/results/latest.json` for review but are not presented as guarantees.
    """
    from app.retrieval.repo import corpus_versions

    version = session.execute(
        sa.select(corpus_versions.c.id, corpus_versions.c.status).where(corpus_versions.c.label == label)
    ).first()
    if version is None:
        raise ValueError(f"no corpus_version with label {label!r}")
    if version.status != "staged":
        raise ValueError(f"corpus_version {label!r} is {version.status!r}, not staged")

    results = evaluate_version(session, str(version.id), label)
    if results["n_questions"] == 0:
        raise RuntimeError("the golden evaluation set is empty; refusing corpus promotion")
    leaks = sum(row["jurisdiction_leaks"] for row in results["conditions"])
    if leaks:
        raise RuntimeError(f"retrieval smoke test found {leaks} jurisdiction leak(s)")
    save_results(results)
    return results
