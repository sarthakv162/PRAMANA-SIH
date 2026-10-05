"""Serve the existing React app and API through Gradio's ZeroGPU queue."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from pathlib import Path
from typing import Any, cast

from fastapi import Request, Response
from fastapi.responses import FileResponse
from gradio import Server


def query_events(request_json: str) -> Generator[dict[str, Any], None, None]:
    from app.core.db import engine, ingest_engine
    from app.orchestrator.graph import run_query
    from app.schemas.query import QueryRequest

    # ZeroGPU forks its worker. Never reuse the parent's pooled DB connections.
    engine.dispose(close=False)
    ingest_engine.dispose(close=False)
    request = QueryRequest.model_validate_json(request_json)
    result = None
    with asyncio.Runner() as runner:
        stream = cast(AsyncGenerator[dict[str, Any], None], run_query(request))

        async def advance() -> dict[str, Any]:
            return await anext(stream)

        async def close() -> None:
            await stream.aclose()

        try:
            while True:
                try:
                    item = runner.run(advance())
                    if item["event"] == "result":
                        result = item["data"]
                    # Queue transports may coalesce fast updates. Carry the audited
                    # card through the final update so it cannot disappear with `done`.
                    yield {**item, "result": result}
                except StopAsyncIteration:
                    break
        finally:
            runner.run(close())


def create_server(frontend: Path, worker: Callable[[str], Generator[dict[str, Any], None, None]]) -> Server:
    from app.main import API_ROUTERS, lifespan
    from app.main import app as api_app

    server = Server(title="PRAMANA", lifespan=lifespan)
    for router in API_ROUTERS:
        server.include_router(router, prefix="/v1")
    server.exception_handlers.update(api_app.exception_handlers)

    def queued_query(request_json: str) -> Generator[dict[str, Any], None, None]:
        yield from worker(request_json)

    server.api(name="query", concurrency_limit=1, time_limit=180, stream_every=0.1)(queued_query)

    @server.middleware("http")
    async def website(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path.lstrip("/")
        root = frontend.resolve()
        target = (root / path).resolve()
        if request.method == "GET" and target.is_relative_to(root) and target.is_file():
            return FileResponse(target, headers={"Cache-Control": "no-cache"})
        # BrowserRouter routes need the application shell on direct navigation.
        pages = {
            "",
            "classify",
            "patent-risk",
            "abs",
            "tk",
            "case",
            "corpus",
            "eval",
            "admin/escalations",
            "dev/components",
        }
        if request.method == "GET" and (path in pages or (path.startswith("receipt/") and path.count("/") == 1)):
            return FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})
        return await call_next(request)

    return server
