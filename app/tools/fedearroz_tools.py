from __future__ import annotations

import json
import logging
import unicodedata
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import get_settings
"""Colombian rice market figures from the FEDEARROZ / FNA sheets."""

logger = logging.getLogger(__name__)

_settings = get_settings()

# these  json documents comes from the FEDEARROZ / FNA sheets.
PRICES_PATH = _settings.fedearroz_prices_path
COSTS_PATH = _settings.fedearroz_costs_path
AREA_PATH = _settings.fedearroz_area_path
CONSUMPTION_PATH = _settings.fedearroz_consumption_path
# Colombian Spanish months for Spanish-speaking farmers.
MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
RECENT_MONTHS = 6

# FEDEARROZ publishes these as informational only: no legal or tax standing,
# and responsibility for any decision sits with the reader. Every answer says
# so, the same way the FAOSTAT tool refuses to pass as a market quote.
DISCLAIMER = (
    "Source FEDEARROZ - Fondo Nacional del Arroz. FEDEARROZ publishes these "
    "figures as informational only: they have no legal or tax standing and are "
    "not an official price. They are a national reference, so the price at a "
    "specific mill and the cost on a specific farm both differ. Confirm locally "
    "before making a financial decision."
)
# THANK YOU FEDEARROZ FOR THIS DATA, I WILL CITE YOU IN FRONTEND
# TODO :  add a link to the FEDEARROZ website, They deserved credit.

PRICE_TOOL_DESCRIPTION = (
    "Gives the Colombian paddy rice price (arroz paddy verde) in Colombian "
    "pesos per tonne, from FEDEARROZ, by month. Use this for Colombia; it is "
    "monthly and current, unlike the FAOSTAT tool which is an annual figure in "
    "US dollars for many countries. Call it only when the user asks about "
    "prices or what their harvest is worth. Always state the month and year, "
    "and that it is a national reference, not an official or mill-gate price."
)

COST_TOOL_DESCRIPTION = (
    "Gives the cost of producing one hectare of irrigated rice in Colombia, in "
    "Colombian pesos, broken down by item (land rent, fertilisation, crop "
    "protection, harvest and so on), from FEDEARROZ. Use it when the user asks "
    "what rice costs to grow, whether a treatment is worth it, or how their "
    "spending compares. It gives no dose and recommends no product. Optionally "
    "pass an item to get just that line."
)


AREA_TOOL_DESCRIPTION = (
    "Gives the hectares of mechanised rice planted in Colombia by rice zone "
    "(Bajo Cauca, Centro, Costa Norte, Llanos, Santanderes) and nationally, per "
    "year, from FEDEARROZ and DANE. Pass a department name (Meta, Tolima, "
    "Casanare...) to get that farmer's zone and how much rice it plants. Use it "
    "for questions about where rice is grown or how big the crop is. It is "
    "planted area only - it is not a yield, a price or a disease figure."
)

CONSUMPTION_TOOL_DESCRIPTION = (
    "Gives Colombian rice consumption in kilograms per person per year, split "
    "urban and rural, from FEDEARROZ calculations on the DANE quality-of-life "
    "survey. Use it for questions about rice demand or how much rice Colombians "
    "eat. It says nothing about prices or crop health."
)


class RicePriceCOInput(BaseModel):

    year: int | None = Field(
        default=None,
        description="Year to report, e.g. 2026. Omit for the most recent month available.",
    )


class AreaInput(BaseModel):

    department: str | None = Field(
        default=None,
        description=(
            "Optional Colombian department, e.g. 'Meta', 'Tolima', 'Casanare'. "
            "Returns the rice zone it belongs to. Omit for all zones."
        ),
    )


class ConsumptionInput(BaseModel):

    year: int | None = Field(
        default=None, description="Year to report. Omit for the most recent."
    )


class CostInput(BaseModel):

    item: str | None = Field(
        default=None,
        description=(
            "Optional cost line in Spanish, e.g. 'fertilizacion', 'proteccion al "
            "cultivo', 'arriendo', 'riego'. Omit for the full breakdown."
        ),
    )


def _fold(text: str | None) -> str:
    
    text = unicodedata.normalize("NFKD", text or "")
    
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


@lru_cache
def _load(path: Path) -> dict:
    
    if not path.exists():
        
        logger.warning("fedearroz dataset missing at %s", path)
        return {}
    
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _cop(value: float) -> str:
    # Thousands separators: these are seven-digit numbers and a wall of digits
    # is misread. Spanish we use '.', which is what the farmer expects.
    return f"{value:,.0f}".replace(",", ".")


def _month_name(index: int) -> str:
    
    return MONTHS_ES[index - 1].capitalize()

# TOOLD FOR COLOMBIAN SPANISH FARMERS GET RICE PRICES/MONTHS
def get_colombia_rice_price(year: int | None = None) -> str:
    
    data = _load(PRICES_PATH)
    
    if not data or not data.get("series"):
        return "The FEDEARROZ price data is unavailable. Do not quote a Colombian price."

    series: dict[str, dict[str, float]] = data["series"]
    target = str(year) if year else str(data["latest_year"])
    
    months = series.get(target)
    
    if not months:
        
        available = ", ".join(sorted(y for y, m in series.items() if m))
        return (
            f"No FEDEARROZ price data for {target}. Years available: {available}. "
            "Do not estimate the missing year."
        )

    numbered = sorted(((int(m), v) for m, v in months.items()), key=lambda x: x[0])
    last_month, last_price = numbered[-1]

    lines = [
        f"Arroz paddy verde, Colombia: {_cop(last_price)} COP per tonne in "
        f"{_month_name(last_month)} {target}."
    ]

    recent = numbered[-RECENT_MONTHS:]
    
    if len(recent) > 1:
        listed = ", ".join(f"{_month_name(m)} {_cop(v)}" for m, v in recent)
        lines.append(f"Recent months (COP/tonne) - {listed}.")

    # Same month a year earlier is the comparison a farmer actually makes;
    # month-on-month inside one year is noise at this granularity.
    previous = series.get(str(int(target) - 1), {})
    year_ago = previous.get(str(last_month))
    
    if year_ago:
        
        change = (last_price - year_ago) / year_ago * 100
        direction = "higher" if change > 0 else "lower" if change < 0 else "unchanged"
        lines.append(
            f"That is {abs(change):.0f}% {direction} than {_month_name(last_month)} "
            f"{int(target) - 1} ({_cop(year_ago)} COP/tonne)."
        )

    if year and int(target) < data["latest_year"]:
        lines.append(f"Newer data exists: the series runs to {data['latest_year']}.")

    lines.append(DISCLAIMER)
    logger.info("fedearroz price: %s-%s -> %s",
                target, last_month, last_price)
    
    return "\n".join(lines)

# TOOL FOR COLOMBIAN SPANISH FARMERS GET RICE COSTS/PRODUCTS
def get_rice_production_costs(item: str | None = None) -> str:
    
    data = _load(COSTS_PATH)
    
    if not data or not data.get("items"):
        
        return "The FEDEARROZ cost data is unavailable. Do not quote a production cost."

    year = str(data["latest_year"])
    items = [e for e in data["items"] if year in e["by_year"]]
    total = data.get("total", {}).get("by_year", {}).get(year)

    if item:
        key = _fold(item)
        matches = [e for e in items if key in _fold(e["item"]) or _fold(e["item"]) in key]
        
        if not matches:
            
            names = ", ".join(e["item"] for e in items)
            
            return f"No cost line matches '{item}'. Lines available: {names}."
        
        entry = matches[0]
        
        value = entry["by_year"][year]
        
        share = f" ({value / total:.0%} of the total)" if total else ""
        
        return "\n".join([
            
            f"{entry['item']}: {_cop(value)} COP per hectare, irrigated rice, "
            f"first semester {year}{share}.",
            DISCLAIMER,
        ])

    lines = [
        f"Cost of one hectare of irrigated rice in Colombia, first semester {year} "
        "(COP per hectare):"
    ]
    for entry in sorted(items, key=lambda e: -e["by_year"][year]):
        
        lines.append(f"- {entry['item']}: {_cop(entry['by_year'][year])}")
        
    if total:
        
        lines.append(f"TOTAL: {_cop(total)} COP per hectare.")
        
    lines.append(
        "This is a national average for the irrigated system, not a quote for a "
        "specific farm. It names no product and gives no dose."
    )
    lines.append(DISCLAIMER)
    logger.info("fedearroz costs: %s, item=%s", year, item)
    
    return "\n".join(lines)


TOTAL_ZONE = "TOTAL NACIONAL"


def _zone_for(department: str, 
              zone_departments: dict[str, list[str]]
              ) -> str | None:
    key = _fold(department)
    # Some Colombian departments are very big and have many zones.
    # Like Antioquia and Costa Norte, which are both in the same zone.
    for zone, deps in zone_departments.items():
        
        if any(_fold(d) == key for d in deps):
            return zone
        
    for zone, deps in zone_departments.items():
        
        if any(key in _fold(d) for d in deps):
            
            return zone
        
    return None

# TOOL FOR COLOMBIAN SPANISH FARMERS GET RICE PLANTED AREA
def get_rice_planted_area(department: str | None = None) -> str:
    
    data = _load(AREA_PATH)
    
    if not data or not data.get("by_year"):
        
        return "The FEDEARROZ planted-area data is unavailable. Do not quote an area."

    year = str(data["latest_year"])
    by_zone: dict[str, float] = data["by_year"][year]
    zone_departments = data.get("zone_departments", {})

    if department:
        
        zone = _zone_for(department, zone_departments)
        
        if zone is None:
            names = ", ".join(sorted({d for deps in zone_departments.values() for d in deps
                                      if "municipio" not in _fold(d)}))
            return (
                f"'{department}' is not one of the departments FEDEARROZ maps to a "
                f"rice zone. Departments covered: {names}."
            )
        # Zone keys in the data are upper case, the footnote uses title case.
        match = next((z for z in by_zone if _fold(z) == _fold(zone)), None)
        hectares = by_zone.get(match) if match else None
        total = by_zone.get(TOTAL_ZONE)
        line = f"{department.title()} is in the {zone} rice zone."
        
        if hectares:
            share = f", {hectares / total:.0%} of the national total" if total else ""
            line += (
                f" That zone planted {_cop(hectares)} hectares of mechanised rice "
                f"in {year}{share}."
            )
        return "\n".join([line, DISCLAIMER])

    lines = [f"Mechanised rice planted in Colombia, {year} (hectares):"]
    
    for zone, hectares in sorted(by_zone.items(), key=lambda z: -z[1]):
        
        if zone == TOTAL_ZONE:
            continue
        
        lines.append(f"- {zone}: {_cop(hectares)}")
        
    if TOTAL_ZONE in by_zone:
        
        lines.append(f"{TOTAL_ZONE}: {_cop(by_zone[TOTAL_ZONE])} hectares.")
        
    lines.append(DISCLAIMER)
    
    logger.info("fedearroz area: %s, department=%s", year, department)
    
    return "\n".join(lines)

# TOOL FOR COLOMBIAN SPANISH PEOPLE WHO LIVE IN THE RICE FARMS 
# # GET RICE CONSUMPTION
def get_rice_consumption(year: int | None = None) -> str:
    
    data = _load(CONSUMPTION_PATH)
    
    if not data or not data.get("by_year"):
        return "The FEDEARROZ consumption data is unavailable. Do not quote a figure."

    by_year: dict[str, dict[str, float]] = data["by_year"]
    target = str(year) if year else str(data["latest_year"])
    row = by_year.get(target)
    
    if not row:
        return (
            f"No consumption data for {target}. Years available: "
            f"{', '.join(sorted(by_year))}. Do not estimate the missing year."
        )

    parts = ", ".join(f"{seg.lower()} {value:g}" for seg, value in row.items())
    lines = [f"Rice consumption in Colombia, {target}: {parts} kg per person per year."]

    previous = by_year.get(str(int(target) - 1), {})
    
    if "TOTAL" in row and "TOTAL" in previous and previous["TOTAL"]:
        
        change = (row["TOTAL"] - previous["TOTAL"]) / previous["TOTAL"] * 100
        direction = "up" if change > 0 else "down" if change < 0 else "flat"
        lines.append(f"Total is {direction} {abs(change):.0f}% on {int(target) - 1}.")

    lines.append(
        "Calculated by FEDEARROZ from the DANE Encuesta Nacional de Calidad de "
        "Vida (ECV). This is national demand, not a price and not a farm figure."
    )
    logger.info("fedearroz consumption: %s", target)
    
    return "\n".join(lines)


# X4 TOOLS CALLS FOR THE ORYZA MIND AGENT GRAPH 

colombia_rice_price_tool = StructuredTool.from_function(
    func=get_colombia_rice_price,
    name="get_colombia_rice_price",
    description=PRICE_TOOL_DESCRIPTION,
    args_schema=RicePriceCOInput,
)

rice_production_costs_tool = StructuredTool.from_function(
    func=get_rice_production_costs,
    name="get_rice_production_costs",
    description=COST_TOOL_DESCRIPTION,
    args_schema=CostInput,
)

rice_planted_area_tool = StructuredTool.from_function(
    func=get_rice_planted_area,
    name="get_rice_planted_area",
    description=AREA_TOOL_DESCRIPTION,
    args_schema=AreaInput,
)

rice_consumption_tool = StructuredTool.from_function(
    func=get_rice_consumption,
    name="get_rice_consumption",
    description=CONSUMPTION_TOOL_DESCRIPTION,
    args_schema=ConsumptionInput,
)
