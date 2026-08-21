
from __future__ import annotations

from pydantic import Field, field_validator

from app.core.config import CLASS_NAMES
from app.schemas.common import CamelModel

#  Even thought this file says vision, it only serves for the seg yolo model,
# the EfficientNetB0  model is handled in spikes module over ./app/schemas/spike.py. 
# The reason is that the EfficientNetB0 model is a binary classifier that predicts whether a rice spike is healthy or unhealthy, while the YOLO segmentation model detects and segments rice leaf diseases. The two models serve different purposes and are used in different parts of the application.
#TODO: FIGURE OUT HOW TO SERVE THIS ON TS IN FRONTEND 
class BoundingBox(CamelModel):
    """Pixel coordinates in the original image, not letterboxed space."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def area(self) -> float:
        
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


class Detection(CamelModel):
    
    class_name: str = Field(description="Canonical class, never a display label")
    confidence: float = Field(ge=0.0, le=1.0)
    box: BoundingBox
    # Pixel count of the instance mask, used for the severity ratio.
    mask_area_px: int = 0

    @field_validator("class_name")
    @classmethod
    def _must_be_canonical(cls, v: str) -> str:
        
        if v not in CLASS_NAMES:
            
            raise ValueError(f"{v!r} is not one of {list(CLASS_NAMES)}")
        
        return v


class VisionResult(CamelModel):
    """One image's detections."""

    image_index: int
    width: int
    height: int
    detections: list[Detection] = Field(default_factory=list)
    # Union of all masks over total image pixels. Feeds severity_from_area().
    affected_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    overlay_data_uri: str | None = None

    @property
    def lesion_count(self) -> int:
        return len(self.detections)

    @property
    def top_detection(self) -> Detection | None:
        return max(self.detections, key=lambda d: d.confidence, default=None)
