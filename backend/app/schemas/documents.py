"""Corpus browser objects. See §5.3 (GET /documents, GET /corpus/versions)."""

from datetime import date, datetime

from app.schemas.base import ContractModel
from app.schemas.enums import CorpusVersionStatus, DocType, Jurisdiction


class DocumentSummary(ContractModel):
    id: str
    short_key: str
    title: str
    doc_type: DocType
    jurisdiction: Jurisdiction
    issuer: str | None = None
    source_url: str
    language: str
    in_force_from: date
    in_force_to: date | None = None


class CorpusVersionInfo(ContractModel):
    label: str
    status: CorpusVersionStatus
    created_at: datetime
