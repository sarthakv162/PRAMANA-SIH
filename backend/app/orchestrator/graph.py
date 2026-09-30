"""§6.4: the orchestrator pipeline. A plain async generator, not the LangGraph library —
the architecture diagram's node sequence is a functional requirement (deterministic router,
one shared state object, each stage able to shrink the deadline), not a mandate to depend on
a specific graph-execution framework; a straight-line generator is easier to read, test, and
step through than a graph library would be for a pipeline that never actually branches back
on itself.

Yields `StageEvent`s as stages complete, then exactly one `AnswerCard | RefusalCard`, matching
the SSE contract in §5.4. Caching (`orchestrator/nodes/cache.py`) is built and unit-tested but
not yet wired into this pipeline — a `cache` stage always reports `skipped` for now; wiring a
hit to jump straight to `render` is a follow-up, not a correctness requirement for M1/M2.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.core.db import SessionLocal
from app.core.deadline import DeadlineExceeded
from app.core.logging import get_logger
from app.generation.llm import LlmError
from app.orchestrator.nodes import audit as audit_node
from app.orchestrator.nodes import frame, generate, intake, resolve, retrieve, route
from app.orchestrator.nodes import verify as verify_node
from app.orchestrator.nodes.intake import NoLiveCorpusError
from app.orchestrator.state import RequestState
from app.render.card import build_answer, build_refusal
from app.schemas.answer import AnswerCard, TimingsMs
from app.schemas.enums import RefusalReason, StageName, StageStatus
from app.schemas.query import QueryRequest
from app.schemas.refusal import RefusalCard

logger = get_logger("orchestrator.graph")

_NON_QA_MESSAGES = {
    "classify": "This sounds like a classification question — try the classification wizard.",
    "patent_risk": "This sounds like a patent-risk question — try the patent risk checker.",
    "abs": "This sounds like an access-and-benefit-sharing question — try the ABS checker.",
    "tk": "This sounds like a traditional-knowledge-match question — try TK radar.",
    "dossier": "Dossier export isn't handled by /query — use /dossier with your case items.",
}

_ALL_STAGES = [
    StageName.INTAKE, StageName.FRAME, StageName.CACHE, StageName.ROUTE, StageName.RETRIEVE,
    StageName.RESOLVE, StageName.GENERATE, StageName.VERIFY, StageName.RENDER, StageName.AUDIT,
]


def _stage_event(name: StageName, status: StageStatus, ms: int | None = None) -> dict[str, Any]:
    return {"name": name.value, "status": status.value, "ms": ms}


class _StageRunner:
    """Small helper so every stage in `run_query` emits its `running`/`done` pair the same
    way, and stages the qa path doesn't reach (e.g. `retrieve` on a refusal-before-retrieval
    path) still get an explicit `skipped` event rather than silently vanishing.
    """

    def __init__(self) -> None:
        self.timings: dict[str, int] = {}
        self.done: set[StageName] = set()

    async def run(self, name: StageName, fn: Any, *args: Any) -> AsyncIterator[dict[str, Any]]:
        t = time.monotonic()
        yield {"event": "stage", "data": _stage_event(name, StageStatus.RUNNING)}
        if _is_coroutine_function(fn):
            await fn(*args)
        else:
            await run_in_threadpool(fn, *args)
        ms = int((time.monotonic() - t) * 1000)
        self.timings[name.value] = ms
        self.done.add(name)
        yield {"event": "stage", "data": _stage_event(name, StageStatus.DONE, ms)}

    def skipped_events(self) -> list[dict[str, Any]]:
        return [
            {"event": "stage", "data": _stage_event(name, StageStatus.SKIPPED)}
            for name in _ALL_STAGES
            if name not in self.done
        ]


def _is_coroutine_function(fn: Any) -> bool:
    import inspect

    return inspect.iscoroutinefunction(fn)


async def run_query(request: QueryRequest) -> AsyncIterator[dict[str, Any]]:
    """Yields dicts shaped `{"event": "stage"|"result"|"error"|"done", "data": {...}}` —
    `api/query.py` is the only place these get turned into actual SSE wire bytes.
    """
    request_id = str(uuid.uuid4())
    state = RequestState(request_id=request_id, raw_query=request.query, request=request)
    runner = _StageRunner()
    t0 = time.monotonic()

    with SessionLocal() as session:
        try:
            async for event in runner.run(StageName.INTAKE, intake.run, state, session):
                yield event
            async for event in runner.run(StageName.FRAME, frame.run, state):
                yield event

            yield {"event": "stage", "data": _stage_event(StageName.CACHE, StageStatus.SKIPPED)}
            runner.done.add(StageName.CACHE)

            async for event in runner.run(StageName.ROUTE, route.run, state):
                yield event

            card: AnswerCard | RefusalCard
            if state.intent == "legal_advice":
                card = build_refusal(
                    state,
                    RefusalReason.LEGAL_ADVICE_REQUEST,
                    "I can share what the relevant sources say, but I can't tell you what to "
                    "do in your specific situation — that needs a qualified professional. "
                    "You can escalate this to an IP facilitator below.",
                    receipt_id="",
                )
            elif state.intent == "out_of_scope":
                card = build_refusal(
                    state,
                    RefusalReason.OUT_OF_SCOPE,
                    "This doesn't look like an Ayurvedic IP/ABS/regulatory question I can "
                    "help with using the indexed documents.",
                    receipt_id="",
                )
            elif state.intent != "qa":
                card = build_refusal(
                    state,
                    RefusalReason.OUT_OF_SCOPE,
                    _NON_QA_MESSAGES.get(state.intent, "Try a different endpoint for this."),
                    receipt_id="",
                )
            else:
                state.deadline.check()
                chunk_rows: list[Any] = []

                async def _retrieve(s: RequestState) -> None:
                    nonlocal chunk_rows
                    chunk_rows = await run_in_threadpool(retrieve.run, session, s)

                async for event in runner.run(StageName.RETRIEVE, _retrieve, state):
                    yield event
                resolve_args = (StageName.RESOLVE, resolve.run, session, state, chunk_rows)
                async for event in runner.run(*resolve_args):
                    yield event

                if not state.evidence_pack:
                    card = build_refusal(
                        state,
                        RefusalReason.NO_EVIDENCE,
                        "The indexed documents don't cover this. I can't answer without a source.",
                        receipt_id="",
                    )
                else:
                    state.deadline.check()
                    try:
                        async for event in runner.run(StageName.GENERATE, generate.run, state):
                            yield event
                    except LlmError as exc:
                        logger.warning(f"request {request_id}: generation unavailable ({exc})")
                        state.resolved_claims = []
                        state.gaps = ["Generation is unavailable — showing sources only."]
                        runner.done.add(StageName.GENERATE)
                        yield {
                            "event": "stage",
                            "data": _stage_event(StageName.GENERATE, StageStatus.FAILED),
                        }

                    confidence_holder: list[Any] = []

                    async def _verify(s: RequestState) -> None:
                        confidence_holder.append(verify_node.run(s))

                    async for event in runner.run(StageName.VERIFY, _verify, state):
                        yield event
                    confidence = confidence_holder[0]

                    if confidence.abstain or not state.verified_claims:
                        card = build_refusal(
                            state,
                            RefusalReason.LOW_CONFIDENCE,
                            "I found related sources but couldn't verify a confident answer "
                            "from them.",
                            receipt_id="",
                        )
                    else:
                        timings_ms = TimingsMs(
                            intake=runner.timings.get("intake", 0),
                            retrieve=runner.timings.get("retrieve", 0),
                            generate=runner.timings.get("generate", 0),
                            verify=runner.timings.get("verify", 0),
                            total=0,
                        )
                        card = build_answer(state, confidence, timings_ms, receipt_id="")

            runner.done.add(StageName.RENDER)
            yield {"event": "stage", "data": _stage_event(StageName.RENDER, StageStatus.DONE)}

            if isinstance(card, AnswerCard):
                total_ms = int((time.monotonic() - t0) * 1000)
                card = card.model_copy(
                    update={"timings_ms": card.timings_ms.model_copy(update={"total": total_ms})}
                )

            async def _audit(s: RequestState) -> None:
                nonlocal card
                receipt_id = await run_in_threadpool(
                    audit_node.run, session, s, card.model_dump(mode="json")
                )
                card = card.model_copy(update={"receipt_id": receipt_id})

            async for event in runner.run(StageName.AUDIT, _audit, state):
                yield event

            for event in runner.skipped_events():
                yield event

            yield {"event": "result", "data": card.model_dump(mode="json")}
            yield {"event": "done", "data": {}}

        except NoLiveCorpusError as exc:
            logger.error(f"request {request_id}: {exc}")
            yield {
                "event": "error",
                "data": {"code": "no_corpus", "message": str(exc), "request_id": request_id},
            }
            yield {"event": "done", "data": {}}
        except DeadlineExceeded:
            fallback = build_refusal(
                state,
                RefusalReason.DEADLINE_EXCEEDED,
                "This took too long to answer — please try again.",
                receipt_id="",
            )
            yield {"event": "result", "data": fallback.model_dump(mode="json")}
            yield {"event": "done", "data": {}}
        except Exception as exc:  # last-resort safety net — never leave the SSE stream hanging
            logger.exception(f"request {request_id}: unhandled error in query pipeline")
            yield {
                "event": "error",
                "data": {
                    "code": "internal_error",
                    "message": f"{type(exc).__name__}: {exc}",
                    "request_id": request_id,
                },
            }
            yield {"event": "done", "data": {}}
