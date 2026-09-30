"""The LLM's raw output schema (§6.6) — deliberately separate from `schemas.claims.Claim`.

This is what the model is allowed to say: a paraphrase plus which evidence IDs support it.
It never contains a `status` or `checks` — those are computed by `verification/` from the
*server's* copy of the cited text, never asserted by the model. `generation/resolve.py` is
the only bridge from this schema to the contract's `Claim`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RawClaim(BaseModel):
    statement: str = Field(description="A paraphrase, <=2 sentences, no quotation marks.")
    evidence_ids: list[str] = Field(
        min_length=1, description="IDs from the numbered evidence pack, e.g. ['E1', 'E3']."
    )
    kind: str = Field(
        default="statement", description="e.g. 'statement', 'exception', 'definition'."
    )


class GenerationResult(BaseModel):
    claims: list[RawClaim] = Field(default_factory=list)
    gaps: list[str] = Field(
        default_factory=list, description="Parts of the question the evidence pack doesn't cover."
    )
    needs_clarification: str | None = Field(
        default=None, description="Set only if the question is genuinely ambiguous."
    )
