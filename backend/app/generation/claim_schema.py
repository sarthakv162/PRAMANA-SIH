"""The LLM's raw output schema (§6.6) — deliberately separate from `schemas.claims.Claim`.

This is what the model is allowed to say: a paraphrase plus which evidence IDs support it.
It never contains a `status` or `checks` — those are computed by `verification/` from the
*server's* copy of the cited text, never asserted by the model. `generation/resolve.py` is
the only bridge from this schema to the contract's `Claim`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RawClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement: str = Field(
        min_length=1, max_length=1000, description="A paraphrase, <=2 sentences, no quotation marks."
    )
    evidence_ids: list[str] = Field(
        min_length=1, max_length=12, description="IDs from the numbered evidence pack, e.g. ['E1', 'E3']."
    )
    kind: str = Field(default="statement", description="e.g. 'statement', 'exception', 'definition'.")


class GenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[RawClaim] = Field(default_factory=list, max_length=12)
    gaps: list[str] = Field(
        default_factory=list, max_length=16, description="Parts of the question the evidence pack doesn't cover."
    )
    needs_clarification: str | None = Field(
        default=None, description="Set only if the question is genuinely ambiguous."
    )
