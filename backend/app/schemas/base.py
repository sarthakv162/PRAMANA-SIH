"""Shared base model. All contract objects inherit this so validation is uniform."""

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Base for every object in THE CONTRACT (docs/IMPLEMENTATION_PLAN.md §5).

    extra="forbid" so a fixture drifting from the schema fails loudly (invariant I7)
    instead of silently passing with an unrecognised field.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
