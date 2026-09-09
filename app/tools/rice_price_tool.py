from __future__ import annotations

import json
import logging
import unicodedata
from functools import lru_cache

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import get_settings
"""Rice producer prices over the FAOSTAT bulk snapshot."""

logger = logging.getLogger(__name__)

PRICES_PATH = get_settings().faostat_prices_path

FIRST_YEAR = 2015
MIN_YEARS_REPORTED = 8
MAX_YEARS_BEHIND = 1

# Trend window, and the cap on how many alternatives a refusal lists.
TREND_SPAN = 5
MAX_SUGGESTIONS = 8

# A year-on-year move this large is a reporting break, not a market swing.
# Colombia is the live example: 839.9 USD/tonne in 2020 against 287.6 in 2021,
# both flagged "official" by FAOSTAT, which makes any trend across that boundary
# meaningless. Say so rather than let the model narrate a 42% crash.
BREAK_RATIO = 0.5

TOOL_DESCRIPTION = (
    "Looks up the rice producer price for a country from FAOSTAT, in USD per "
    "tonne of paddy. These are annual national averages that lag by about a "
    "year - they are a reference and a trend, NOT today's market or mill-gate "
    "price, and the farmer must not be told otherwise. Call it only when the "
    "user asks about rice prices, and never to justify a treatment decision. "
    "Always report the year the figure belongs to."
)


class RicePriceInput(BaseModel):

    country: str = Field(
        description="Country name in English or Spanish, e.g. 'Colombia', 'Peru', 'Viet Nam'."
    )


# FAOSTAT area names a farmer will not type. Folded on both sides at lookup.
ALIASES = {
    "usa": "United States of America",
    "us": "United States of America",
    "eeuu": "United States of America",
    "estados unidos": "United States of America",
    "united states": "United States of America",
    "vietnam": "Viet Nam",
    "china": "China, mainland",
    "korea": "Republic of Korea",
    "south korea": "Republic of Korea",
    "corea del sur": "Republic of Korea",
    "turkey": "Türkiye",
    "turquia": "Türkiye",
    "iran": "Iran (Islamic Republic of)",
    "filipinas": "Philippines",
    "espana": "Spain",
    "brasil": "Brazil",
    "peru": "Peru",
    "mexico": "Mexico",
    "japon": "Japan",
    "italia": "Italy",
    "tailandia": "Thailand",
    "grecia": "Greece",
} # farmer user can be use it outsite the country


def _fold(text: str | None) -> str:
    
    text = unicodedata.normalize("NFKD", text or "")
    
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


@lru_cache
def load_prices() -> dict:
    """The snapshot, already split into reliable and unreliable series."""
    if not PRICES_PATH.exists():
        
        logger.warning("rice price snapshot missing at %s", PRICES_PATH)
        return {"reliable": {}, "excluded": {}, "fetched_at": None, "newest_year": None}

    with PRICES_PATH.open(encoding="utf-8") as fh:
        payload = json.load(fh)

    countries = payload.get("countries", [])
    newest = max((c["latest_year"] for c in countries), default=0)

    reliable: dict[str, dict] = {}
    excluded: dict[str, dict] = {}
    
    for row in countries:
        
        reported = sum(1 for y in row["prices"] if int(y) >= FIRST_YEAR)
        fresh = row["latest_year"] >= newest - MAX_YEARS_BEHIND
        bucket = reliable if (reported >= MIN_YEARS_REPORTED and fresh) else excluded
        bucket[_fold(row["area"])] = row

    logger.info("loaded rice prices: %d reliable, %d excluded", 
                len(reliable), len(excluded)
                )
    
    return {
        "reliable": reliable,
        "excluded": excluded,
        "fetched_at": payload.get("fetched_at"),
        "newest_year": newest,
    }


def _find(country: str, 
          table: dict[str, dict]
          ) -> dict | None:
    
    key = _fold(country)
    key = _fold(ALIASES.get(key, key))
    
    if key in table:
        return table[key]

    # some country name are confusing, so we need to find the right one
    matches = [row for name, row in table.items() if key and (key in name or name in key)]
    
    return matches[0] if len(matches) == 1 else None


def _has_break(prices: dict[str, float], 
               start: int, 
               end: int
               ) -> bool:
    
    years = [y for y in range(start, end + 1) if str(y) in prices]
    
    for prev, curr in zip(years, years[1:]):
        
        a, b = prices[str(prev)], prices[str(curr)]
        
        if a > 0 and abs(b - a) / a >= BREAK_RATIO:
            return True
        
    return False


def _trend(prices: dict[str, float],
           latest_year: int
           ) -> str | None:
    
    base_year = str(latest_year - TREND_SPAN)
    
    if base_year not in prices:
        return None
    
    base, latest = prices[base_year], prices[str(latest_year)]
    
    if base <= 0:
        return None
    
    if _has_break(prices, 
                  latest_year - TREND_SPAN, 
                  latest_year):
        
        return (
            f"No trend given: this country's series jumps by more than "
            f"{BREAK_RATIO:.0%} between consecutive years since {base_year}, which "
            "is a reporting break rather than a real price move. Do not describe "
            "a rise or fall over these years."
        )
        
    change = (latest - base) / base * 100
    
    direction = "up" if change > 0 else "down" if change < 0 else "flat"
    
    return f"Trend: {direction} {abs(change):.0f}% since {base_year} ({base:g} USD/tonne)."


def get_rice_price(country: str) -> str:
    
    data = load_prices()
    
    if not data["reliable"]:
        return "The rice price snapshot is unavailable. Do not quote a price."

    row = _find(country, data["reliable"])
    
    if row is None:
        # Distinguish "FAOSTAT has nothing usable for you" from "no such country",
        # because the first is a real answer and the second is a typo.
        stale = _find(country, data["excluded"])
        
        if stale is not None:
            
            return (
                f"FAOSTAT's rice price series for {stale['area']} is not reliable enough "
                f"to quote: it ends in {stale['latest_year']}. Tell the user no current "
                "figure is available for their country and to ask their national rice "
                "federation or extension service. Do not quote the old value."
            )
            
        names = sorted(r["area"] for r in data["reliable"].values())[:MAX_SUGGESTIONS]
        
        return (
            f"No rice price series for '{country}'. Ask the user to confirm the country. "
            f"Countries available include: {', '.join(names)}."
        )

    year = row["latest_year"]
    prices = row["prices"]
    lines = [
        f"{row['area']} - rice (paddy) producer price: "
        f"{row['latest_price']:g} USD/tonne in {year}.",
    ]

    trend = _trend(prices, year)
    
    if trend:
        
        lines.append(trend)

    recent = [f"{y}: {prices[y]:g}" for y in sorted(prices) if int(y) >= year - 4]
    
    lines.append("Recent years (USD/tonne) - " + ", ".join(recent) + ".")

    if year < data["newest_year"]:
        
        lines.append(f"Note this country's series stops at {year}.")

    lines.append(
        "Source FAOSTAT, domain PP, annual national average producer price for paddy. "
        f"Snapshot taken {(data['fetched_at'] or 'unknown date')[:10]}. This is a reference "
        "figure, not a current market or mill-gate quote: real prices move within the year "
        "and by region, variety and moisture. Point the user at their national rice "
        "federation or local mill for a price to sell on."
    )
    return "\n".join(lines)


get_rice_price_tool = StructuredTool.from_function(
    # call it only when the user asks about rice prices, 
    # and never to justify a treatment decision.
    func=get_rice_price,
    name="get_rice_price",
    description=TOOL_DESCRIPTION,
    args_schema=RicePriceInput,
)
