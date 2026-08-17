
from __future__ import annotations

import enum

from pydantic import Field

from app.schemas.chat import Citation
from app.schemas.common import CamelModel


class SpikeLabel(str, enum.Enum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"


class SpikePrediction(CamelModel):
    """One panicle image's verdict."""
    # My EfficientNetB0 model is a binary classifier that predicts whether a rice spike is healthy or unhealthy. The model outputs a sigmoid score, which is interpreted as the probability of being unhealthy. The label is determined by comparing the score to a threshold (default 0.5). If the score is close to the threshold (within a margin), the prediction is marked as uncertain.
    image_index: int
    filename: str | None = None
    label: SpikeLabel
    # Confidence in the reported label, not the raw sigmoid.
    confidence: float = Field(ge=0.0, le=1.0)
    # Raw sigmoid output, P(unhealthy). Kept so a caller can re-band without
    # re-running inference.
    unhealthy_score: float = Field(ge=0.0, le=1.0)
    # True when the score sits near the threshold. The label is still the best
    # guess; the client should present it as provisional.
    uncertain: bool = False


class SpikeResult(CamelModel):
    predictions: list[SpikePrediction] = Field(default_factory=list)
    # Worst case across the batch, since one bad panicle dooms the whole batch.
    overall_label: SpikeLabel
    unhealthy_count: int = 0
    total_count: int = 0
    model_label: str = "EfficientNetB0 (spike binary classifier)"

    # Agent output. Null when generation was skipped or failed -- a verdict
    # without advice is still useful, a 500 is not.
    assessment: str | None = None
    recommendations: list[str] | None = None
    citations: list[Citation] = Field(default_factory=list)
    # False when the corpus returned nothing and the model answered from its
    # own knowledge. The UI must say so: an ungrounded answer carries no
    # citations and, by prompt rule, no dosages.
    grounded: bool = True
