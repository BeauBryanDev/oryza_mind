
from __future__ import annotations

from typing import Any

from pydantic import Field

from app.schemas.common import CamelModel, SeverityLevel

# My YOLO SEG  model here 
# II will use MongoDB to store the data in v2 
# Hence it is nor ORM nor SQLAlchemy
class DiseaseFinding(CamelModel):
    """One disease found across the submitted photos."""

    name: str = Field(description="Canonical class string, e.g. Brown_Spot")
    scientific_name: str | None = None
    # Highest single-detection confidence for this class. Not a probability
    # over classes: several findings can each be high.
    confidence: float = Field(ge=0.0, le=1.0)
    lesion_count: int = 0
    # Lesion pixels for this class over total image pixels.
    affected_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    severity: SeverityLevel
    # Which uploaded images this disease appears in.
    image_indices: list[int] = Field(default_factory=list)


class SegmentationResult(CamelModel):
    image_index: int
    original_url: str
    # data:image/jpeg;base64,... JPEG, not PNG: lossless overlays ran 1.4-3.1 MB.
    overlay_url: str
    lesion_count: int = 0
    affected_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    # Canonical class names present in this image.
    diseases: list[str] = Field(default_factory=list)


class AnalysisResult(CamelModel):
    # Every disease found, most severe first. Empty means nothing detected, hence healthy. 
    # The first disease is the primary finding, the most severe. The others are less severe.
    # Noted that a healthy result is not an error: it is a valid outcome of the pipeline. 
    # which is a valid healthy result rather than an error. A user can upload good leaf photos
    diseases: list[DiseaseFinding] = Field(default_factory=list) # Or a rotten  beatup leaf image
    # The finding that dominates by affected area. Null when nothing was found.
    # Convenience for chat context, not a claim that others are less real.
    primary_disease: DiseaseFinding | None = None # Be carefull with vision confidence 
    # Union of all lesions over all pixels, across every image.
    overall_affected_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_severity: SeverityLevel = SeverityLevel.LOW
    segmentations: list[SegmentationResult] = Field(default_factory=list)
    recommendations: list[str] | None = None
    metadata: dict[str, Any] | None = None

    @property
    def is_healthy(self) -> bool:
        """True if no disease was detected with sufficient confidence."""
        return not self.diseases
