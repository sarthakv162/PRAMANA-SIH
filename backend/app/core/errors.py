"""Application errors and FastAPI exception handlers producing the standard ErrorBody (§5)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import ErrorBody, ErrorDetail


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotImplementedYet(ApiError):
    """Raised by endpoints whose real (non-mock) pipeline isn't built yet (post-M0 work)."""

    def __init__(self, feature: str) -> None:
        super().__init__(
            code="not_implemented",
            message=f"{feature} is not implemented outside MOCK_MODE yet.",
            status_code=501,
        )


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id", "req_unknown")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        body = ErrorBody(
            error=ErrorDetail(code=exc.code, message=exc.message, request_id=_request_id(request))
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorBody(
            error=ErrorDetail(
                code="validation_error", message=str(exc.errors()), request_id=_request_id(request)
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        body = ErrorBody(
            error=ErrorDetail(
                code="http_error", message=str(exc.detail), request_id=_request_id(request)
            )
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))
