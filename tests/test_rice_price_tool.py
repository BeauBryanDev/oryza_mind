from __future__ import annotations

import json

import pytest

from app.tools import rice_price_tool as rp

# Offline by design: every test builds its own snapshot and points the module's
# cached loader at it, so nothing here touches RAG/ or the network.


def write_snapshot(tmp_path, countries) -> None:
    payload = {
        "unit": "USD/tonne",
        "fetched_at": "2026-09-09T00:00:00+00:00",
        "countries": countries,
    }
    path = tmp_path / "rice_producer_prices.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    rp.PRICES_PATH = path
    rp.load_prices.cache_clear()


def series(area, first, last, value=400.0, code="1"):
    prices = {str(y): value for y in range(first, last + 1)}
    return {
        "area_code": code,
        "area": area,
        "item": "Rice",
        "item_code": "27",
        "element": "Producer Price (USD/tonne)",
        "unit": "USD/tonne",
        "first_year": first,
        "latest_year": last,
        "latest_price": prices[str(last)],
        "prices": prices,
    }


@pytest.fixture(autouse=True)
def restore_module_state():
    original = rp.PRICES_PATH
    yield
    rp.PRICES_PATH = original
    rp.load_prices.cache_clear()


def test_reliable_country_reports_price_year_and_unit(tmp_path):
    write_snapshot(tmp_path, [series("Peru", 2015, 2024)])
    out = rp.get_rice_price("Peru")
    assert "400 USD/tonne in 2024" in out
    assert "FAOSTAT" in out


def test_stale_country_is_refused_without_quoting_the_old_value(tmp_path):
    write_snapshot(tmp_path, [series("Peru", 2015, 2024),
                              series("India", 2000, 2008, value=385.7, code="2")])
    out = rp.get_rice_price("India")
    assert "not reliable" in out
    assert "2008" in out
    # The refusal must not hand the model a number it can repeat.
    assert "385.7" not in out


def test_country_short_of_the_coverage_floor_is_excluded(tmp_path):
    # Fresh to 2024 but only 4 years reported since 2015.
    write_snapshot(tmp_path, [series("Peru", 2015, 2024),
                              series("Gapland", 2021, 2024, code="3")])
    assert "not reliable" in rp.get_rice_price("Gapland")


def test_country_more_than_one_year_behind_is_excluded(tmp_path):
    write_snapshot(tmp_path, [series("Peru", 2015, 2024),
                              series("Laggard", 2015, 2022, code="4")])
    assert "not reliable" in rp.get_rice_price("Laggard")


def test_unknown_country_asks_for_confirmation_and_lists_options(tmp_path):
    write_snapshot(tmp_path, [series("Peru", 2015, 2024)])
    out = rp.get_rice_price("Narnia")
    assert "confirm the country" in out
    assert "Peru" in out


def test_aliases_and_accents_resolve(tmp_path):
    write_snapshot(tmp_path, [series("Viet Nam", 2015, 2024),
                              series("Türkiye", 2015, 2024, code="5")])
    assert "Viet Nam" in rp.get_rice_price("vietnam")
    assert "Türkiye" in rp.get_rice_price("turquia")
    assert "Türkiye" in rp.get_rice_price("Turkiye")


def test_ambiguous_substring_does_not_silently_pick_one(tmp_path):
    write_snapshot(tmp_path, [series("Guinea", 2015, 2024),
                              series("Guinea-Bissau", 2015, 2024, code="6")])
    assert "confirm the country" in rp.get_rice_price("Guinea-")


def test_trend_is_reported_for_a_smooth_series(tmp_path):
    prices = {str(y): 300.0 + (y - 2015) * 10 for y in range(2015, 2025)}
    row = series("Peru", 2015, 2024)
    row["prices"] = prices
    row["latest_price"] = prices["2024"]
    write_snapshot(tmp_path, [row])
    assert "Trend: up" in rp.get_rice_price("Peru")


def test_reporting_break_suppresses_the_trend(tmp_path):
    # The Colombia shape: an official 2020 value nearly 3x the next year.
    prices = {str(y): 400.0 for y in range(2015, 2025)}
    prices["2020"] = 839.9
    prices["2021"] = 287.6
    row = series("Colombia", 2015, 2024)
    row["prices"] = prices
    row["latest_price"] = prices["2024"]
    write_snapshot(tmp_path, [row])
    out = rp.get_rice_price("Colombia")
    assert "No trend given" in out
    assert "Trend: up" not in out and "Trend: down" not in out


def test_missing_snapshot_refuses_instead_of_raising(tmp_path):
    rp.PRICES_PATH = tmp_path / "absent.json"
    rp.load_prices.cache_clear()
    assert "Do not quote a price" in rp.get_rice_price("Peru")


def test_output_carries_no_unit_conversion(tmp_path):
    write_snapshot(tmp_path, [series("Colombia", 2015, 2024)])
    out = rp.get_rice_price("Colombia").lower()
    # Prices are reported as FAOSTAT reports them; no carga, kg or bag maths.
    for banned in ("carga", "usd/kg", "per kg", "quintal", "bulto"):
        assert banned not in out


def test_tool_is_bound_to_the_agent():
    from app.agent.agent import TOOLS, TOOL_FUNCS, STRING_TOOLS

    assert rp.get_rice_price_tool in TOOLS
    assert TOOL_FUNCS[rp.get_rice_price_tool.name] is rp.get_rice_price
    assert rp.get_rice_price_tool.name in STRING_TOOLS


def test_tool_description_states_it_is_not_a_market_price():
    text = rp.TOOL_DESCRIPTION.lower()
    assert "not" in text and "market" in text
