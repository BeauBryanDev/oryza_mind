from __future__ import annotations

import json
import logging
import re
import unicodedata
from functools import lru_cache
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import REPO_ROOT
"""Agrochemical product lookup over the scraped distributor catalogue."""

logger = logging.getLogger(__name__)

PRODUCTS_PATH = REPO_ROOT / "RAG" / "agrochemical_products.json"
MAX_HITS = 5

Category = Literal["fungicida", "herbicida", "insecticida"]

TOOL_DESCRIPTION = (
    "Looks up commercial products in a catalogue of Colombian agrochemical "
    "distributors (Invesa, Precisagro) by active ingredient or product name. "
    "Call it ONLY after the user has explicitly agreed to see product "
    "information, or explicitly asks which products to buy. Never call it on "
    "your own initiative. Only name products it returns; never invent one."
)


class SearchProductsInput(BaseModel):
    
    query: str = Field(
        description="Active ingredient or product name, e.g. 'propiconazole', 'azoxystrobin', 'Panzer'."
    )
    category: Category | None = Field(
        default=None, 
        description="Restrict to fungicida, herbicida or insecticida."
    )


def _fold(text: str | None) -> str:
    # Accent- and case-insensitive: "azoxistrobin" must meet "Azoxystrobin",
    # "propiconazol" must meet "Propiconazole".
    text = unicodedata.normalize("NFKD", text or "")
    
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


@lru_cache
def load_products() -> list[dict]:
    
    if not PRODUCTS_PATH.exists():
        
        logger.warning("product catalogue missing at %s", PRODUCTS_PATH)
        return []
    
    with PRODUCTS_PATH.open(encoding="utf-8") as fh:
        
        rows = json.load(fh)
        
    logger.info("loaded %d agrochemical products", len(rows))
    
    return rows


def _terms(query: str) -> list[str]:
    # Split on non-letters, keep stems 4+ chars so "propiconazole" and
    # "propiconazol" share "prop…"; drop Spanish/English filler.
    stop = {"para", 
            "with", 
            "that", 
            "este", 
            "esta", 
            "producto", 
            "product", 
            "fungicide", 
            "fungicida"}
    
    words = [w for w in re.split(r"[^a-z0-9]+", _fold(query)) if len(w) >= 4 and w not in stop]
    
    return [w[:8] for w in words]


def search_agrochemical_products(query: str, category: str | None = None) -> list[dict]:
    """
    Rank catalogue rows by how many query stems hit name, ingredient or description.

    Name and active-ingredient hits outrank description hits so a query for one
    molecule does not surface every product whose blurb merely mentions it.
    """
    terms = _terms(query)
    hits: list[tuple[int, dict]] = []
    
    for row in load_products():
        
        if category and row.get("category") != category:
            continue
        
        name, ai, desc = _fold(row.get("name")), _fold(row.get("active_ingredient")), _fold(row.get("description"))
        score = 0
        
        for t in terms:
            
            if t in name or t in ai:
                score += 3
                
            elif t in desc:
                
                score += 1
                
        if score:
            
            hits.append((score, row))
            
    hits.sort(key=lambda h: (-h[0], h[1]["name"]))
    
    return [row for _, row in hits[:MAX_HITS]]


def format_for_model(rows: list[dict]) -> str:
    
    if not rows:
        
        return "No products in the catalogue match. Do not name a commercial product."
    # No prices reach the model: we inform, we do not sell.
    keep = ("name", 
            "source", 
            "category", 
            "active_ingredient", 
            "product_url", 
            "technical_sheet_url"
            )
    
    return json.dumps([{k: r.get(k) for k in keep} for r in rows], ensure_ascii=False)


def _search_for_model(query: str, category: str | None = None) -> str:
    
    rows = search_agrochemical_products(query, category)
    
    logger.info("products_tool: %r / %s -> %d", query, category, len(rows))
    
    return format_for_model(rows)


search_products_tool = StructuredTool.from_function(
    func=_search_for_model,
    name="search_agrochemical_products",
    description=TOOL_DESCRIPTION,
    args_schema=SearchProductsInput,
)
