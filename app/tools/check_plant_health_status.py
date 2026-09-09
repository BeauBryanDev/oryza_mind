from __future__ import annotations

import logging

import numpy as np
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.load_tabular_models import ( get_plant_health_classes,
                                          get_plant_health_model,
                                          quiet_predict )
"""Plant stress status from soil and canopy sensor readings."""

logger = logging.getLogger(__name__)

# Training ranges of the Kaggle plant health set, rounded inward so a value on
# the boundary is not rejected. A forest extrapolates silently, so refuse.
RANGES = {
    "soil_moisture_pct": (10.0, 40.0),
    "soil_temperature_c": (15.0, 25.0),
    "humidity_pct": (40.0, 70.0),
    "light_intensity_lux": (200.0, 1000.0),
    "soil_ph": (5.5, 7.5),
    "nitrogen_mg_kg": (10.0, 50.0),
    "phosphorus_mg_kg": (10.0, 50.0),
    "potassium_mg_kg": (10.0, 50.0),
    "electrochemical_mv": (0.0, 2.0),
}

# The two weakest features, 0.017 importance each. Asking a farmer for ambient
# temperature and a chlorophyll meter reading buys nothing, so they are filled
# with the dataset mean and the tool asks for nine values instead of eleven.
AMBIENT_T_MEAN = 24.0
CHLOROPHYLL_MEAN = 34.75
# Importance 0.018. Optional at the tool boundary: a farmer without a probe
# still gets a status. Substituting the mean changes 0 of 1200 predictions.
ELECTROCHEM_MEAN = 0.99

# Only the top two features carry real signal, so the caveat is not boilerplate.
DRIVERS = ("Soil_Moisture", "Nitrogen_Level")

STATUS_TEXT = {
    "Healthy": "Healthy: the readings match well-watered, well-fed plants.",
    "Moderate Stress": "Moderate stress: the plants are under strain but not critically.",
    "High Stress": "High stress: the readings match plants in serious difficulty.",
}

TOOL_DESCRIPTION = (
    "Reads a plant stress status - healthy, moderate stress or high stress - "
    "from eight sensor values: soil moisture (%), soil temperature (C), air "
    "humidity (%), light intensity (lux), soil pH, and soil nitrogen, "
    "phosphorus and potassium (mg/kg). The electrochemical stress signal (mV) "
    "is optional - call the tool without it if the farmer has no probe, never "
    "refuse or ask for it twice. The model is trained on a "
    "public Kaggle sensor dataset, not a field trial. Soil moisture and "
    "nitrogen carry most of the signal. Confirm with a local extension service "
    "before acting."
)


class PlantHealthInput(BaseModel):

    soil_moisture_pct: float = Field(description="Soil moisture in percent, 10 to 40.")
    soil_temperature_c: float = Field(description="Soil temperature in Celsius, 15 to 25.")
    humidity_pct: float = Field(description="Air relative humidity in percent, 40 to 70.")
    light_intensity_lux: float = Field(description="Light intensity in lux, 200 to 1000.")
    soil_ph: float = Field(description="Soil pH, 5.5 to 7.5.")
    nitrogen_mg_kg: float = Field(description="Soil nitrogen in mg/kg, 10 to 50.")
    phosphorus_mg_kg: float = Field(description="Soil phosphorus in mg/kg, 10 to 50.")
    potassium_mg_kg: float = Field(description="Soil potassium in mg/kg, 10 to 50.")
    electrochemical_mv: float | None = Field(
        default=None,
        description="Optional. Electrochemical stress signal in mV, 0 to 2. Omit if unmeasured.",
    )


def check_plant_health_status(
    soil_moisture_pct: float,
    soil_temperature_c: float,
    humidity_pct: float,
    light_intensity_lux: float,
    soil_ph: float,
    nitrogen_mg_kg: float,
    phosphorus_mg_kg: float,
    potassium_mg_kg: float,
    electrochemical_mv: float | None = None,
) -> str:
    values = {
        "soil_moisture_pct": soil_moisture_pct,
        "soil_temperature_c": soil_temperature_c,
        "humidity_pct": humidity_pct,
        "light_intensity_lux": light_intensity_lux,
        "soil_ph": soil_ph,
        "nitrogen_mg_kg": nitrogen_mg_kg,
        "phosphorus_mg_kg": phosphorus_mg_kg,
        "potassium_mg_kg": potassium_mg_kg,
        "electrochemical_mv": electrochemical_mv,
    }
    for name, value in values.items():
        if value is None:
            continue
        lo, hi = RANGES[name]
        if not lo <= value <= hi:
            return f"{name} = {value} is outside the model's range ({lo:g}-{hi:g}). No status."

    electrochem = ELECTROCHEM_MEAN if electrochemical_mv is None else electrochemical_mv

    # PLANT_HEALTH_FEATURES order. The means only keep the row 11-wide.
    row = np.array(
        [[soil_moisture_pct,
          AMBIENT_T_MEAN,
          soil_temperature_c,
          humidity_pct,
          light_intensity_lux,
          soil_ph,
          nitrogen_mg_kg,
          phosphorus_mg_kg,
          potassium_mg_kg,
          CHLOROPHYLL_MEAN,
          electrochem]],
        dtype=float,
    )
    proba = quiet_predict(get_plant_health_model().predict_proba, row)[0]
    classes = get_plant_health_classes()
    index = int(np.argmax(proba))
    # Index order is alphabetical, not ordinal: never compare these integers.
    label = classes[index]
    logger.info("plant health tool: moist=%s n=%s -> %s (%.2f)",
                soil_moisture_pct, nitrogen_mg_kg, label, proba[index])

    lines = [
        f"Plant health status: {STATUS_TEXT.get(label, label)}",
        f"Model confidence: {float(proba[index]):.0%}.",
    ]
    if label != "Healthy":
        lines.append(
            "Check irrigation and nitrogen first: those two readings drive this "
            "result far more than the others. This is a stress signal, not a "
            "diagnosis - it names no disease and prescribes no dose."
        )
    lines.append(
        "Status from a random forest trained on a public Kaggle sensor dataset, "
        "not a field trial. Soil moisture and nitrogen carry most of the signal. "
        "Confirm with a local extension service before acting."
    )
    return "\n".join(lines)


check_plant_health_tool = StructuredTool.from_function(
    func=check_plant_health_status,
    name="check_plant_health_status",
    description=TOOL_DESCRIPTION,
    args_schema=PlantHealthInput,
)
