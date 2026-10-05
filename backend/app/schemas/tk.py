"""TK radar objects. See §5.2, §6.10."""

from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.enums import Jurisdiction


class RegionalName(ContractModel):
    lang: str
    name: str


class NormalizedIngredient(ContractModel):
    input: str
    canonical_latin: str
    sanskrit: str | None = None
    regional: list[RegionalName] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class TkMatch(ContractModel):
    formulation_id: str
    name: str
    source_text: str
    similarity: float = Field(ge=0.0, le=1.0)
    overlap: list[str] = Field(default_factory=list)
    missing_in_input: list[str] = Field(default_factory=list)
    extra_in_input: list[str] = Field(default_factory=list)
    indication_match: bool
    evidence_ids: list[str] = Field(default_factory=list)


class RadarAxis(ContractModel):
    label: str
    value: float = Field(ge=0.0, le=1.0)


class RadarData(ContractModel):
    axes: list[RadarAxis]


class TkdlQuery(ContractModel):
    terms: list[str]
    ipc: list[str]
    text: str
    note: str = (
        "TKDL access is restricted; this pack is for use by an authorised examiner or via the applicant's counsel."
    )


class WatchlistHit(ContractModel):
    case: str
    jurisdiction: Jurisdiction
    summary: str
    outcome: str
    source_url: str


class TkRadar(ContractModel):
    type: Literal["tk_radar"] = "tk_radar"
    normalized_ingredients: list[NormalizedIngredient]
    matches: list[TkMatch]
    radar: RadarData
    tkdl_query: TkdlQuery
    watchlist_hits: list[WatchlistHit] = Field(default_factory=list)
    receipt_id: str
