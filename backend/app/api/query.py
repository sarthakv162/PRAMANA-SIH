"""POST /v1/query — the main Q&A endpoint (§5.4, §6.4). MOCK_MODE=1 replays
contracts/fixtures/sse_transcript.txt verbatim as a real SSE stream, so the frontend can
build the stage stepper against a real HTTP response instead of a fake one. Otherwise this
runs the real orchestrator pipeline (`orchestrator/graph.py`).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.api.conversations import authorize_workspace
from app.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import ApiError
from app.core.fixtures import load_fixture, load_fixture_text
from app.history.service import require_conversation
from app.orchestrator.graph import run_query
from app.schemas.query import QueryRequest

router = APIRouter(tags=["query"])
_QUERY_SLOT = asyncio.Semaphore(1)


def _mock_result_name(request: QueryRequest) -> str:
    query_text = request.query.casefold()
    if any(pattern in query_text for pattern in ("should i file", "will i win", "is this legal for me")):
        return "refusal_legal_advice.json"
    if any(pattern in query_text for pattern in ("fees", "unindexed", "unknown topic")):
        return "refusal_no_evidence.json"
    if request.jurisdiction.value == "BOTH":
        return "answer_card_both_hi.json"
    return "answer_card_in.json"


async def _replay_sse_transcript(result_fixture: str, delay_s: float = 0.15) -> AsyncIterator[bytes]:
    transcript = load_fixture_text("sse_transcript.txt")
    events = [chunk for chunk in transcript.split("\n\n") if chunk.strip()]
    result = load_fixture(result_fixture)
    for chunk in events:
        if chunk.startswith("event: result\n"):
            chunk = f"event: result\ndata: {json.dumps(result, separators=(',', ':'))}"
        yield (chunk + "\n\n").encode("utf-8")
        await asyncio.sleep(delay_s)


def _sse_encode(event: str, data: object) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


async def _stream_real_pipeline(request: QueryRequest) -> AsyncIterator[bytes]:
    async with _QUERY_SLOT:
        async for item in run_query(request):
            yield _sse_encode(item["event"], item["data"])


@router.post(
    "/query",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-sent events: stage, result or error, then done.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def query(request: QueryRequest, x_demo_key: str = Header(default="")) -> StreamingResponse:
    settings = get_settings()
    if settings.query_transport == "gradio":
        raise ApiError("queue_required", "Use the Gradio query endpoint for ZeroGPU allocation and queueing.", 409)
    if request.conversation_id:
        authorize_workspace(x_demo_key)
        with SessionLocal() as session:
            require_conversation(session, request.conversation_id)
    if settings.mock_mode:
        return StreamingResponse(
            _replay_sse_transcript(_mock_result_name(request)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return StreamingResponse(_stream_real_pipeline(request), media_type="text/event-stream")
