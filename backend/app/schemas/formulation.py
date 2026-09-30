"""Formulation — domain input shared by classify/patent-risk/tk-radar. See §5.5."""

from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.enums import ApplicantType


class Ingredient(ContractModel):
    name: str
    part: str | None = None
    role: Literal["active", "excipient"] | None = None
    amount: str | None = None


class ResourceOrigin(ContractModel):
    state: str | None = None
    wild_or_cultivated: Literal["wild", "cultivated"] | None = None
    codified_tk: bool | None = None


class Formulation(ContractModel):
    name: str
    intended_use: str
    product_form: str
    ingredients: list[Ingredient]
    process_summary: str | None = None
    classical_sources_cited: list[str] = Field(default_factory=list)
    claims_novel_effect: bool = False
    novel_effect_evidence: str | None = None
    has_clinical_data: bool = False
    is_derivative_of_known_substance: bool = False
    resource_origin: ResourceOrigin | None = None
    applicant_type: ApplicantType | None = None
    planned_actions: list[str] = Field(default_factory=list)
