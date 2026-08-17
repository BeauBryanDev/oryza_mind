
from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Serializes to camelCase for the TS client, accepts snake_case in Python."""
    # This is a pydantic feature, not a bug. The default is to use snake_case
    # for the JSON, but camelCase for the Python API. This is a convenience for
    # the TS client, which expects camelCase everywhere.
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class SeverityLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PipelineStage(str, enum.Enum):
    IDLE = "IDLE"
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    SEGMENTING = "SEGMENTING"
    ANALYZING = "ANALYZING"
    GENERATING_DIAGNOSIS = "GENERATING_DIAGNOSIS"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


# Lesion pixels over TOTAL IMAGE pixels, calibrated for field photography where
# the plant occupies a fraction of the frame. The earlier 10/25/50 scale assumed
# a leaf filling the image and made HIGH and CRITICAL unreachable outdoors.
SEVERITY_BANDS: tuple[tuple[float, SeverityLevel], ...] = (
    (0.03, SeverityLevel.LOW),
    (0.10, SeverityLevel.MODERATE),
    (0.18, SeverityLevel.HIGH),
)


def severity_from_area(affected_ratio: float) -> SeverityLevel:
    
    for upper, level in SEVERITY_BANDS:
        
        if affected_ratio < upper:
            
            return level
        
    return SeverityLevel.CRITICAL


# Display only. The canonical class string stays the identifier everywhere else.
SCIENTIFIC_NAMES: dict[str, str] = {
    "Bacterial_Leaf_Blight": "Xanthomonas oryzae pv. oryzae",
    "Brown_Spot": "Bipolaris oryzae",
    "Leaf_Blast": "Magnaporthe oryzae",
    "Narrow_Brown": "Cercospora janseana",
    "Rice_Tungro": "Rice tungro bacilliform/spherical virus",
    "Sheath_Blight": "Rhizoctonia solani",
}


class ApiError(CamelModel):
    message: str
    code: str | None = None


class HealthResponse(CamelModel):
    status: str
    version: str
    model_loaded: bool
    weaviate_ready: bool
    # Optional so an older client that does not know about the spike model keeps
    # parsing this payload unchanged.
    spike_model_loaded: bool = False
