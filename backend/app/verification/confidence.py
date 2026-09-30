"""§6.7 confidence: one score from four signals, mapped to a level and an abstain/review
decision. The weights and both thresholds (`TAU_ABSTAIN`, `TAU_REVIEW`) are config, meant to
be picked from the dev-set risk-coverage curve (§9) — the defaults here are an even split,
explicitly a placeholder until that tuning happens.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.schemas.enums import Confidence


@dataclass
class ConfidenceOutcome:
    score: float
    level: Confidence
    abstain: bool
    review_recommended: bool


def compute_confidence(
    retrieval_margin: float,
    mean_entailment: float,
    verified_ratio: float,
    back_translation_ok: bool | None,
) -> ConfidenceOutcome:
    settings = get_settings()
    # None means "not applicable" (e.g. the answer language is English) — treated the same
    # as a translation that wasn't checked ok, per §6.7's formula.
    back_translation_term = 1.0 if back_translation_ok else 0.5

    score = (
        settings.confidence_w_retrieval_margin * retrieval_margin
        + settings.confidence_w_mean_entail * mean_entailment
        + settings.confidence_w_verified_ratio * verified_ratio
        + settings.confidence_w_back_translation * back_translation_term
    )
    score = max(0.0, min(1.0, score))

    if score < settings.tau_abstain:
        level = Confidence.LOW
    elif score < settings.tau_review:
        level = Confidence.MEDIUM
    else:
        level = Confidence.HIGH

    return ConfidenceOutcome(
        score=score,
        level=level,
        abstain=score < settings.tau_abstain,
        review_recommended=settings.tau_abstain <= score < settings.tau_review,
    )
