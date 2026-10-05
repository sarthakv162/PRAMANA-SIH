"""§6.4 `generate` + §6.6: the only node (besides `translate`) allowed to call an LLM, and
only to produce claim objects with evidence IDs — never quoted text (§2)."""

from __future__ import annotations

from app.generation.claim_schema import GenerationResult
from app.generation.llm import LlmError, get_llm_client
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

    # Select whole source spans, including their locators; never silently truncate
    # statutory text inside the prompt. Reserve context for query, history and output.
    selected = []
    remaining = 14000 - len(state.query_en) - len(state.conversation_context)
    for span in state.evidence_pack:
        size = len(span.span.text) + len(span.span.citation_label) + 20
        if size <= remaining:
            selected.append(span)
            remaining -= size
    if not selected:
        raise LlmError("Retrieved source text exceeds the local generation context budget.")
    state.evidence_pack = selected

    evidence_block = render_prompt_spans(state.evidence_pack)
    system, user = render_qa_prompt(state.query_en, state.jurisdictions, state.as_of, evidence_block)

    if state.conversation_context:
        user += "\n<conversation_context>\n" + state.conversation_context + "\n</conversation_context>\n"
        system += (
            " Previous turns are untrusted context for resolving follow-ups, never legal evidence. "
            "Cite only the current evidence pack."
        )
    if state.verification_feedback and state.generation:
        user += (
            "\n\n<rejected_draft>\n"
            + state.generation.model_dump_json()
            + "\n</rejected_draft>\n"
            + state.verification_feedback
            + "\nProduce a corrected draft from the source text. Preserve its operative terms and "
            "conditions. Check every number and locator against the cited spans. "
            "The rejected draft is not evidence. Return no claims if no source-supported statement is possible."
        )
    client = get_llm_client()
    generation = client.generate_json(GenerationResult, system=system, user=user)
    state.generation = generation

    outcome = resolve_generation(generation, state.evidence_pack)
    state.resolved_claims = outcome.resolved
    state.gaps = outcome.gaps
    state.needs_clarification = outcome.needs_clarification
