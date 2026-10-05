"""Scope recognition evaluation, distinct from retrieval and synthesis quality."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.orchestrator.router import route


def evaluate_routing() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    cases = [json.loads(line) for line in (root / "eval/golden/routing.jsonl").read_text().splitlines() if line.strip()]
    totals: Counter[str] = Counter()
    correct: Counter[str] = Counter()
    results = []
    for case in cases:
        intent, _ = route(case["query"])
        expected_in_scope = case["scope"] != "out_of_domain"
        passed = (intent != "out_of_scope") == expected_in_scope
        totals[case["scope"]] += 1
        correct[case["scope"]] += int(passed)
        results.append({**case, "intent": intent, "passed": passed})
    report = {
        "n_cases": len(cases),
        "scope_accuracy": {key: correct[key] / count for key, count in totals.items()},
        "answerable_by_phrasing": {
            kind: sum(r["passed"] for r in results if r["scope"] == "answerable" and r["phrasing"] == kind)
            / sum(1 for r in results if r["scope"] == "answerable" and r["phrasing"] == kind)
            for kind in ["direct", "weak", "indirect"]
        },
        "limitations": (
            "Scope-recognition benchmark only; answerable labels reflect listed topics, "
            "not end-to-end factual answer correctness."
        ),
        "cases": results,
    }
    (root / "eval/results/routing.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    report = evaluate_routing()
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    raise SystemExit(0 if report["scope_accuracy"]["answerable"] >= 0.95 else 1)
