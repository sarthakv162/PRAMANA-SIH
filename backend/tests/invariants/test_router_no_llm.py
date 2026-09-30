"""I6 — router determinism: the router must not call a generative model (CLAUDE.md, §2, §6.4).

Static check: `orchestrator/router.py` must not import `generation.llm` (or the `anthropic`
SDK directly) at all — the only model it may touch is the embedding model for the kNN
similarity floor, which can't generate text.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROUTER_PATH = Path(__file__).resolve().parents[2] / "app" / "orchestrator" / "router.py"
FORBIDDEN_MODULES = {"app.generation.llm", "anthropic"}


def test_router_does_not_import_any_llm_module() -> None:
    tree = ast.parse(ROUTER_PATH.read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    offending = imported & FORBIDDEN_MODULES
    assert not offending, f"router.py imports a generative-model module: {offending}"
