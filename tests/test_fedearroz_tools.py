from __future__ import annotations

import json

import pytest

from app.tools import fedearroz_tools as fa

# Offline: each test writes its own snapshot and repoints the module, so nothing
# reads RAG/ or the network.

PRICES = {
    "latest_year": 2026,
    "latest_month": 8,
    "series": {
        "2025": {str(m): 1_400_000.0 for m in range(1, 13)},
        "2026": {str(m): 1_300_000.0 + m for m in range(1, 9)},
    },
}
COSTS = {
    "latest_year": 2025,
    "items": [
        {"item": "FERTILIZACIÓN", "by_year": {"2025": 2_077_749.0}},
        {"item": "PROTECCIÓN AL CULTIVO", "by_year": {"2025": 1_541_488.0}},
    ],
    "total": {"item": "TOTAL", "by_year": {"2025": 9_212_450.0}},
}
AREA = {
    "latest_year": 2025,
    "by_year": {"2025": {"BAJO CAUCA": 59989.0, "LLANOS": 321228.0, "TOTAL NACIONAL": 563970.0}},
    "zone_departments": {
        "Bajo Cauca": ["Antioquia", "Córdoba"],
        "Llanos": ["Meta", "Casanare"],
        "Costa Norte": ["Cesar", "el municipio de Yondó en Antioquia"],
    },
}
CONSUMPTION = {
    "latest_year": 2025,
    "by_year": {
        "2024": {"URBANO": 43.08, "RURAL": 52.23, "TOTAL": 45.22},
        "2025": {"URBANO": 39.22, "RURAL": 49.08, "TOTAL": 41.52},
    },
}


@pytest.fixture(autouse=True)
def snapshots(tmp_path):
    original = (fa.PRICES_PATH, fa.COSTS_PATH, fa.AREA_PATH, fa.CONSUMPTION_PATH)
    for attr, payload in (("PRICES_PATH", PRICES), ("COSTS_PATH", COSTS),
                          ("AREA_PATH", AREA), ("CONSUMPTION_PATH", CONSUMPTION)):
        path = tmp_path / f"{attr}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        setattr(fa, attr, path)
    fa._load.cache_clear()
    yield
    fa.PRICES_PATH, fa.COSTS_PATH, fa.AREA_PATH, fa.CONSUMPTION_PATH = original
    fa._load.cache_clear()


def test_price_reports_latest_month_in_cop_and_compares_year_on_year():
    out = fa.get_colombia_rice_price()
    assert "Agosto 2026" in out and "COP per tonne" in out
    assert "1.300.008" in out          # Spanish thousands separator
    assert "than Agosto 2025" in out


def test_missing_year_refuses_to_estimate():
    assert "Do not estimate" in fa.get_colombia_rice_price(2019)
    assert "Do not estimate" in fa.get_rice_consumption(2000)


def test_costs_break_down_with_a_total_and_a_per_item_share():
    assert "9.212.450" in fa.get_rice_production_costs()
    out = fa.get_rice_production_costs("proteccion al cultivo")
    assert "1.541.488" in out and "17% of the total" in out


def test_costs_never_quote_a_dose():
    out = fa.get_rice_production_costs().lower()
    for unit in ("kg/ha", "l/ha", "fl oz", "dosis de"):
        assert unit not in out


def test_exact_department_beats_a_municipio_substring():
    # Antioquia is a Bajo Cauca department and also appears inside Costa Norte's
    # "el municipio de Yondó en Antioquia". The exact match must win.
    assert "Bajo Cauca" in fa.get_rice_planted_area("Antioquia")
    assert "Llanos" in fa.get_rice_planted_area("meta")
    assert "not one of the departments" in fa.get_rice_planted_area("Amazonas")


def test_every_answer_carries_the_fedearroz_conditions():
    for out in (fa.get_colombia_rice_price(), fa.get_rice_production_costs(),
                fa.get_rice_planted_area()):
        assert "informational only" in out and "no legal or tax standing" in out


def test_missing_dataset_refuses_instead_of_raising(tmp_path):
    fa.PRICES_PATH = tmp_path / "absent.json"
    fa._load.cache_clear()
    assert "unavailable" in fa.get_colombia_rice_price()


def test_tools_are_bound_and_faostat_stays_independent():
    from app.agent.agent import TOOLS, TOOL_FUNCS, STRING_TOOLS
    from app.tools.rice_price_tool import get_rice_price_tool

    for tool, func in [(fa.colombia_rice_price_tool, fa.get_colombia_rice_price),
                       (fa.rice_production_costs_tool, fa.get_rice_production_costs),
                       (fa.rice_planted_area_tool, fa.get_rice_planted_area),
                       (fa.rice_consumption_tool, fa.get_rice_consumption)]:
        assert tool in TOOLS and TOOL_FUNCS[tool.name] is func and tool.name in STRING_TOOLS

    # The two price sources answer separately: different unit, different cadence.
    assert "USD" in get_rice_price_tool.description
    assert "pesos" in fa.colombia_rice_price_tool.description
