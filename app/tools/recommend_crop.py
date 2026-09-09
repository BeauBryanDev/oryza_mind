from __future__ import annotations

import logging

import numpy as np
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.load_tabular_models import ( RICE_CLASS, 
                                          get_crop_classes, 
                                          get_crop_model, 
                                          quiet_predict )
"""Rice suitability score from a soil and climate profile, with rotation alternatives."""

logger = logging.getLogger(__name__)

TOP_N = 3

# Training ranges of the Kaggle crop recommendation set.
RANGES = {
    "n": (0.0, 140.0),
    "p": (5.0, 145.0),
    "k": (5.0, 205.0),
    "temperature_c": (8.0, 44.0),
    "humidity_pct": (14.0, 100.0),
    "ph": (3.5, 10.0),
    "rainfall_mm": (20.0, 300.0),
}

TOOL_DESCRIPTION = (
    "Scores how well a field's soil and climate profile suits rice, and names "
    "the crops that fit it best as rotation alternatives. Needs seven values: "
    "soil N, P, K, temperature (C), relative humidity (%), soil pH and annual "
    "rainfall (mm). Ask the farmer for any value they have not given; never "
    "guess. The score is a probability from a statistical model trained on a "
    "public dataset, not an agronomic verdict."
)


class CropInput(BaseModel):
    
    n: float = Field(description="Soil nitrogen content ratio, 0 to 140.")
    p: float = Field(description="Soil phosphorus content ratio, 5 to 145.")
    k: float = Field(description="Soil potassium content ratio, 5 to 205.")
    temperature_c: float = Field(description="Mean temperature in Celsius, 8 to 44.")
    humidity_pct: float = Field(description="Relative humidity in percent, 14 to 100.")
    ph: float = Field(description="Soil pH, 3.5 to 10.")
    rainfall_mm: float = Field(description="Annual rainfall in mm, 20 to 300.")


def recommend_crop(
    n: float, 
    p: float, 
    k: float, 
    temperature_c: float, 
    humidity_pct: float, 
    ph: float, 
    rainfall_mm: float
) -> str:
    values = {
        "n": n, 
        "p": p, 
        "k": k, 
        "temperature_c": temperature_c,
        "humidity_pct": humidity_pct, 
        "ph": ph, 
        "rainfall_mm": rainfall_mm,
    }
    for name, value in values.items():
        lo, hi = RANGES[name]
        if not lo <= value <= hi:
            return f"{name} = {value} is outside the model's range ({lo:g}-{hi:g}). No score."

    row = np.array([list(values.values())], dtype=float)
    proba = quiet_predict(get_crop_model().predict_proba, row)[0]
    classes = get_crop_classes()
    order = np.argsort(proba)[::-1]

    rice_p = float(proba[RICE_CLASS])
    top = [(classes[int(i)], float(proba[i])) for i in order[:TOP_N]]
    logger.info("crop tool: rice=%.3f top=%s", rice_p, top)

    # One decimal so 0.995 does not read as certainty; alternatives under 1 % are noise.
    lines = [f"Rice suitability: {rice_p:.1%}."]
    alternatives = [f"{crop} ({prob:.1%})" for crop, prob in top if crop != "rice" and prob >= 0.01]
    
    if alternatives:
        
        lines.append("Best-fitting crops for rotation: " + ", ".join(alternatives) + ".")
        
    if top[0][1] < get_settings().crop_uncertain_threshold:
        lines.append("The profile is ambiguous: no crop scores above 50 %, treat this as weak evidence.")
    lines.append(
        "Score from a random forest trained on a public Kaggle dataset (0.995 "
        "cross-validated accuracy), not a field trial. Confirm with a local "
        "extension service before changing crops."
    )
    return "\n".join(lines)


recommend_crop_tool = StructuredTool.from_function(
    func=recommend_crop,
    name="recommend_crop",
    description=TOOL_DESCRIPTION,
    args_schema=CropInput,
)
