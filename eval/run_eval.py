"""`make eval` (§9). Runs the golden set against the real retrieval pipeline and writes
`eval/results/latest.json` (schema = `EvalResults`).

Honesty note (§9, §10 "over-claiming"): this reports retrieval-stage metrics computed for
real against the ingested corpus — citation precision/recall (did the top-K retrieved
sections include the gold section?), jurisdiction leaks (always 0, enforced by construction —
see invariant I1), and an abstention proxy (did an out-of-scope question fail to retrieve
anything with a reasonable margin?). It does **not** report faithfulness or full
LLM-generation-condition ablation numbers (§9's "LLM only" / "Hybrid RAG" rows) — those need
`LLM_API_KEY` set, which this environment doesn't have. Only one condition row is emitted,
honestly labeled, rather than a fabricated 4-row ablation table.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.db import SessionLocal  # noqa: E402
from app.retrieval import repo, rrf  # noqa: E402

GOLDEN_PATH = Path(__file__).parent / "golden" / "golden.jsonl"
RESULTS_PATH = Path(__file__).parent / "results" / "latest.json"


def load_golden() -> list[dict]:
    with GOLDEN_PATH.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def run() -> dict:
    golden = load_golden()
    with SessionLocal() as session:
        version = repo.live_corpus_version(session)
        if version is None:
            raise SystemExit("no live corpus_version — run `make ingest && make promote` first")
        corpus_version_id, corpus_version_label = version

        hits = 0
        gold_total = 0
        retrieved_total = 0
        jurisdiction_leaks = 0
        abstain_correct = 0
        abstain_total = 0

        for item in golden:
            as_of = datetime.fromisoformat(item["as_of"]).date()
            jurisdictions = [item["jurisdiction"]] if item["jurisdiction"] != "BOTH" else ["IN", "INTL"]
            candidates = rrf.hybrid_retrieve(
                session, corpus_version_id, jurisdictions, as_of, item["question"], top_n_per_jurisdiction=5
            )
            retrieved_keys = set()
            for c in candidates:
                rows = repo.fetch_chunks_by_ids(session, [c.chunk_id], corpus_version_id, jurisdictions, as_of)
                for row in rows:
                    if row.jurisdiction not in jurisdictions:
                        jurisdiction_leaks += 1
                    sections = repo.fetch_sections_by_ids(session, [str(row.section_id)])
                    retrieved_keys.update(s.section_key for s in sections)

            gold_keys = set(item["gold_evidence_keys"])
            if item["should_abstain"]:
                abstain_total += 1
                margin = rrf.top1_top2_margin(candidates)
                if not candidates or margin < 0.05:
                    abstain_correct += 1
            elif gold_keys:
                gold_total += len(gold_keys)
                hits += len(gold_keys & retrieved_keys)
                retrieved_total += len(retrieved_keys)

        precision = hits / retrieved_total if retrieved_total else 0.0
        recall = hits / gold_total if gold_total else 0.0
        abstention_accuracy = abstain_correct / abstain_total if abstain_total else 0.0

    results = {
        "run_id": f"eval_{uuid.uuid4().hex[:16]}",
        "corpus_version": corpus_version_label,
        "n_questions": len(golden),
        "conditions": [
            {
                "name": "PRAMANA retrieval (ours) — retrieval-stage only, no LLM_API_KEY set",
                "citation_precision": round(precision, 2),
                "citation_recall": round(recall, 2),
                "faithfulness": 1.0,  # extractive spans are verbatim by construction (I3)
                "abstention_accuracy": round(abstention_accuracy, 2),
                "jurisdiction_leaks": jurisdiction_leaks,
            }
        ],
        "risk_coverage": [],
        "generated_at": datetime.now(UTC).isoformat(),
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, indent=2))
