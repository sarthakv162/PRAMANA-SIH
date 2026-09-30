"""Standard error body. See §5. Every error response uses this shape."""

from app.schemas.base import ContractModel


class ErrorDetail(ContractModel):
    code: str
    message: str
    request_id: str


class ErrorBody(ContractModel):
    error: ErrorDetail
