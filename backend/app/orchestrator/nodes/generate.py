"""§6.4 `generate` + §6.6: the only node (besides `translate`) allowed to call an LLM, and
only to produce claim objects with evidence IDs — never quoted text (§2)."""

from __future__ import annotations

from app.generation.claim_schema import GenerationResult
from app.generation.llm import get_llm_client
from app.generation.prompts import render_qa_prompt
from app.generation.resolve import resolve_generation
from app.orchestrator.state import RequestState
from app.retrieval.evidence_pack import render_prompt_spans


def run(state: RequestState) -> None:
    if not state.evidence_pack:
        state.resolved_claims = []
        state.gaps = []
        state.needs_clarification = None
        return

    evidence_block = render_prompt_spans(state.evidence_pack)
    system, user = render_qa_prompt(
        state.query_en, state.jurisdictions, state.as_of, evidence_block
    )

    client = get_llm_client()
    generation = client.generate_json(GenerationResult, system=system, user=user)
    state.generation = generation

    outcome = resolve_generation(generation, state.evidence_pack)
    state.resolved_claims = outcome.resolved
    state.gaps = outcome.gaps
    state.needs_clarification = outcome.needs_clarification
