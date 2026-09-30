"""POST /v1/query — the main Q&A endpoint (§5.4, §6.4). MOCK_MODE=1 replays
contracts/fixtures/sse_transcript.txt verbatim as a real SSE stream, so the frontend can
build the stage stepper against a real HTTP response instead of a fake one. Otherwise this
runs the real orchestrator pipeline (`orchestrator/graph.py`).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.core.fixtures import load_fixture_text
from app.orchestrator.graph import run_query
from app.schemas.query import QueryRequest

router = APIRouter(tags=["query"])


async def _replay_sse_transcript(delay_s: float = 0.15) -> AsyncIterator[bytes]:
    transcript = load_fixture_text("sse_transcript.txt")
    events = [chunk for chunk in transcript.split("\n\n") if chunk.strip()]
    for chunk in events:
        yield (chunk + "\n\n").encode("utf-8")
        await asyncio.sleep(delay_s)


def _sse_encode(event: str, data: object) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


async def _stream_real_pipeline(request: QueryRequest) -> AsyncIterator[bytes]:
    async for item in run_query(request):
        yield _sse_encode(item["event"], item["data"])


@router.post("/query")
async def query(request: QueryRequest) -> StreamingResponse:
    settings = get_settings()
    if settings.mock_mode:
        return StreamingResponse(_replay_sse_transcript(), media_type="text/event-stream")
    return StreamingResponse(_stream_real_pipeline(request), media_type="text/event-stream")
