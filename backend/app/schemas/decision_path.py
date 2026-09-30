"""DecisionPath — drives the React Flow decision-tree view. See §5.2."""

from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel


class DecisionNode(ContractModel):
    id: str
    kind: Literal["question", "outcome"]
    label: str
    value: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    taken: bool = True


class DecisionEdge(ContractModel):
    from_: str = Field(alias="from")
    to: str
    label: str


class DecisionPath(ContractModel):
    nodes: list[DecisionNode]
    edges: list[DecisionEdge]
    outcome_id: str
