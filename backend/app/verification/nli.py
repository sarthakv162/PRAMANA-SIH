"""NLI entailment (§6.7): mDeBERTa-v3 XNLI. Premise = the claim's cited evidence spans
(joined verbatim); hypothesis = the claim's English statement. Cached process-wide; like
`retrieval/embed.py`, this must not pay model-load cost at import time or reload per request.
Live-mode startup explicitly warms it before accepting requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

from app.config import get_settings

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizerBase


@dataclass
class NliResult:
    entailment: float
    neutral: float
    contradiction: float


@lru_cache
def _model_and_tokenizer() -> tuple[PreTrainedModel, PreTrainedTokenizerBase]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(2)
    settings = get_settings()
    try:
        tokenizer = cast(Any, AutoTokenizer).from_pretrained(settings.nli_model, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(settings.nli_model, local_files_only=True)
    except OSError:
        # The first setup downloads verifier weights; subsequent starts use only
        # the persistent cache, without unnecessary hub metadata requests.
        tokenizer = cast(Any, AutoTokenizer).from_pretrained(settings.nli_model)
        model = AutoModelForSequenceClassification.from_pretrained(settings.nli_model)
    model.to("cpu")  # see retrieval/embed.py — accelerator contention on this machine
    model.eval()
    torch.set_grad_enabled(False)
    return model, tokenizer


def entailment_score(premise: str, hypothesis: str) -> NliResult:
    """Runs the NLI pair through the model and returns softmax probabilities keyed by the
    model's own label order (read from `model.config.id2label`, not assumed — different NLI
    checkpoints order entailment/neutral/contradiction differently).
    """
    import torch

    model, tokenizer = _model_and_tokenizer()
    inputs = tokenizer(premise, hypothesis, truncation=False, return_tensors="pt")
    if inputs["input_ids"].shape[-1] > 512:
        # Discarding a tail can hide legal qualifications. A truncated premise must
        # never certify the full cited text. Keep its sources available for review.
        return NliResult(entailment=0.0, neutral=1.0, contradiction=0.0)
    logits = model(**inputs).logits[0]
    probs = torch.softmax(logits, dim=-1).tolist()

    raw_id2label = model.config.id2label or {}
    id2label = {int(k): str(v).lower() for k, v in raw_id2label.items()}
    by_label = {id2label[i]: probs[i] for i in range(len(probs))}

    return NliResult(
        entailment=by_label.get("entailment", 0.0),
        neutral=by_label.get("neutral", 0.0),
        contradiction=by_label.get("contradiction", 0.0),
    )
