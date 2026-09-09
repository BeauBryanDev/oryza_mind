from __future__ import annotations

import logging
from typing import Literal

import numpy as np
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.load_tabular_models import get_fertilizer_model, quiet_predict
"""Fertilizer type lookup from soil moisture, EC and growth phase."""

logger = logging.getLogger(__name__)

# Training ranges. A tree extrapolates silently, so refuse instead.
MOISTURE_RANGE = (40.0, 90.0)
EC_RANGE = (102.0, 2998.0)

# Dataset means for the three columns the tree never splits on (importance 0).
# They only keep the input 6-wide; the value is irrelevant to the prediction.
SOIL_T_MEAN = 28.4
AIR_T_MEAN = 29.8
AIR_H_MEAN = 77.5

PHASE_CODE = {"vegetative": 0, "reproductive": 1}

# Generic names so the model can translate. The salinity label is not a
# fertilizer and must never reach the farmer verbatim.
LABEL_TEXT = {
    "Urea": "Urea (nitrogen source)",
    "ZA": "ZA (ammonium sulphate, nitrogen and sulphur source)",
    "NPK 15-10-12": "NPK 15-10-12 (compound fertilizer)",
    "SP-36": "SP-36 (superphosphate, phosphorus source)",
    "KCl": "KCl (potassium chloride, potassium source)",
}
FLUSH_TEXT = (
    "No fertilizer: the soil is saline (EC above 2000 uS/cm). Flush the field "
    "with fresh water and drain before fertilizing."
)

TOOL_DESCRIPTION = (
    "Suggests which fertilizer TYPE fits a rice paddy from three soil readings: "
    "soil moisture (%), soil electrical conductivity EC (uS/cm) and the crop "
    "growth phase. Ask the farmer for all three values if they have not given "
    "them; never guess or assume them. The result is a fertilizer type only, "
    "never a rate: kg/ha comes from the product label or the local extension "
    "service."
)


class FertilizerInput(BaseModel):
    
    soil_moisture_pct: float = Field(description="Soil moisture in percent, 40 to 90.")
    soil_ec: float = Field(description="Soil electrical conductivity in uS/cm, 102 to 2998.")
    growth_phase: Literal["vegetative", "reproductive"] = Field(
        description="vegetative (sowing to tillering) or reproductive (panicle initiation to grain fill)."
    )


def recommend_rice_fertilizer(
    soil_moisture_pct: float, 
    soil_ec: float, 
    growth_phase: str
) -> str:
    lo, hi = MOISTURE_RANGE
    
    if not lo <= soil_moisture_pct <= hi:
        
        return f"Soil moisture {soil_moisture_pct} % is outside the model's range ({lo:.0f}-{hi:.0f} %). No recommendation."
    
    lo, hi = EC_RANGE
    
    if not lo <= soil_ec <= hi:
        
        return f"Soil EC {soil_ec} uS/cm is outside the model's range ({lo:.0f}-{hi:.0f} uS/cm). No recommendation."
    
    phase = PHASE_CODE.get(growth_phase)
    
    if phase is None:
        
        return "growth_phase must be 'vegetative' or 'reproductive'."

    row = np.array(
        [[soil_moisture_pct, 
          SOIL_T_MEAN, 
          soil_ec, 
          AIR_T_MEAN, 
          AIR_H_MEAN, 
          phase]],
        dtype=float,
    )
    label = str(quiet_predict(get_fertilizer_model().predict, row)[0])
    logger.info("fertilizer tool: moist=%s ec=%s phase=%s -> %s", 
                soil_moisture_pct, soil_ec, growth_phase, label)

    advice = FLUSH_TEXT if label == "Flushing Air" else LABEL_TEXT.get(label, label)
    
    return (
        f"Inputs used: soil moisture {soil_moisture_pct} %, EC {soil_ec} uS/cm, "
        f"{growth_phase} phase.\n"
        f"Suggested: {advice}\n"
        "This is a fertilizer type from a decision tree trained on a public "
        "Kaggle rice dataset, not a field trial. No application rate is given: "
        "the dose must come from the product label or a local extension service."
    )


recommend_fertilizer_tool = StructuredTool.from_function(
    
    func=recommend_rice_fertilizer,
    name="recommend_rice_fertilizer",
    description=TOOL_DESCRIPTION,
    args_schema=FertilizerInput,
)
