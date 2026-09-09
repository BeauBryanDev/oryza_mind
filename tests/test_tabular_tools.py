from __future__ import annotations

import numpy as np
import pytest

from app.agent import agent as agent_mod
from app.core import load_tabular_models as loaders
from app.core.config import get_settings
from app.tools import check_plant_health_status as health_mod
from app.tools import recommend_crop as crop_mod
from app.tools import rice_fertilizer as fert_mod

ML_PRESENT = get_settings().fertilizer_model_path.exists() and get_settings().crop_model_path.exists()
HEALTH_PRESENT = get_settings().plant_health_model_path.exists()

# df.head(5) of the Kaggle rice fertilizer set, phase already recoded 1000 -> 1.
FERTILIZER_HEAD = [
    ((50.6, 2069.0, "reproductive"), "Flushing Air"),
    ((55.4, 1523.0, "reproductive"), "NPK 15-10-12"),
    ((72.3, 1100.0, "reproductive"), "SP-36"),
    ((83.5, 1070.0, "vegetative"), "ZA"),
    ((43.0, 623.0, "vegetative"), "Urea"),
]
RICE_ROW = dict(n=90, p=42, k=43, temperature_c=20.88, humidity_pct=82.0, ph=6.5, rainfall_mm=202.9)

HEALTH_ROW = dict(soil_moisture_pct=31.61, soil_temperature_c=16.14, humidity_pct=58.53,
                  light_intensity_lux=763.54, soil_ph=6.28, nitrogen_mg_kg=39.0,
                  phosphorus_mg_kg=36.37, potassium_mg_kg=44.17, electrochemical_mv=1.88)


class _FakeTree:
    def __init__(self, label):
        self.label = label
        self.rows = []

    def predict(self, row):
        self.rows.append(row)
        return np.array([self.label])


class _FakeForest:
    def __init__(self, proba):
        self.proba = proba

    def predict_proba(self, row):
        return np.array([self.proba])


@pytest.mark.slow
@pytest.mark.skipif(not ML_PRESENT, reason="ml/ artifacts absent")
@pytest.mark.parametrize("inputs,label", FERTILIZER_HEAD)
def test_fertilizer_head_rows_reproduce_the_notebook(inputs, label):
    """Parity net across sklearn versions: the raw tree still says what it said at training."""
    moist, ec, phase = inputs
    row = np.array([[moist, fert_mod.SOIL_T_MEAN, ec, fert_mod.AIR_T_MEAN, fert_mod.AIR_H_MEAN, fert_mod.PHASE_CODE[phase]]])
    assert loaders.quiet_predict(loaders.get_fertilizer_model().predict, row)[0] == label


def test_flushing_air_is_translated_never_passed_through(monkeypatch):
    fake = _FakeTree("Flushing Air")
    monkeypatch.setattr(fert_mod, "get_fertilizer_model", lambda: fake)
    out = fert_mod.recommend_rice_fertilizer(50.0, 2500.0, "reproductive")
    assert "Flushing Air" not in out
    assert "fresh water" in out
    assert fake.rows[0].shape == (1, 6)


def test_fertilizer_output_never_carries_a_rate(monkeypatch):
    monkeypatch.setattr(fert_mod, "get_fertilizer_model", lambda: _FakeTree("Urea"))
    out = fert_mod.recommend_rice_fertilizer(45.0, 600.0, "vegetative")
    assert "Urea" in out and "kg/ha" not in out.split("No application rate")[0]


def test_out_of_range_moisture_is_rejected_without_predicting(monkeypatch):
    fake = _FakeTree("Urea")
    monkeypatch.setattr(fert_mod, "get_fertilizer_model", lambda: fake)
    out = fert_mod.recommend_rice_fertilizer(95.0, 600.0, "vegetative")
    assert "outside" in out
    assert fake.rows == []


@pytest.mark.slow
@pytest.mark.skipif(not ML_PRESENT, reason="ml/ artifacts absent")
def test_crop_rice_row_scores_rice_first():
    out = crop_mod.recommend_crop(**RICE_ROW)
    pct = float(out.split("Rice suitability: ")[1].split("%")[0])
    assert pct > 90


@pytest.mark.skipif(not get_settings().crop_class_path.exists(), reason="crop_class.json absent")
def test_crop_class_map_has_22_entries_with_rice_at_20():
    classes = loaders.get_crop_classes()
    assert len(classes) == 22
    assert classes[loaders.RICE_CLASS] == "rice"


def test_low_top_probability_reports_ambiguity(monkeypatch):
    proba = np.full(22, 0.03)
    proba[20] = 0.30
    proba[11] = 0.34
    monkeypatch.setattr(crop_mod, "get_crop_model", lambda: _FakeForest(proba))
    monkeypatch.setattr(crop_mod, "get_crop_classes", lambda: {i: f"crop{i}" for i in range(20)} | {20: "rice", 21: "crop21"})
    out = crop_mod.recommend_crop(**RICE_ROW)
    assert out.startswith("Rice suitability: 30.0%")
    assert "ambiguous" in out
    assert "crop11" in out
    assert "crop0" not in out


def test_crop_out_of_range_is_rejected():
    out = crop_mod.recommend_crop(**{**RICE_ROW, "ph": 12.0})
    assert "outside" in out


def test_both_tools_are_bound_in_the_agent():
    names = {t.name for t in agent_mod.TOOLS}
    assert {"recommend_rice_fertilizer", "recommend_crop"} <= names
    assert {"recommend_rice_fertilizer", "recommend_crop"} <= agent_mod.STRING_TOOLS
    assert {"recommend_rice_fertilizer", "recommend_crop"} <= set(agent_mod.TOOL_FUNCS)


def test_plant_health_reads_the_label_through_the_class_map(monkeypatch):
    """1 is High Stress and 2 is Moderate: alphabetical, not a severity scale."""
    proba = np.zeros(3)
    proba[1] = 0.8
    monkeypatch.setattr(health_mod, "get_plant_health_model", lambda: _FakeForest(proba))
    out = health_mod.check_plant_health_status(**HEALTH_ROW)
    assert "High stress" in out
    assert "Moderate" not in out


def test_plant_health_fills_eleven_columns_from_nine_inputs(monkeypatch):
    seen = {}

    class _Recorder:
        def predict_proba(self, row):
            seen["row"] = row
            return np.array([[0.9, 0.05, 0.05]])

    monkeypatch.setattr(health_mod, "get_plant_health_model", lambda: _Recorder())
    health_mod.check_plant_health_status(**HEALTH_ROW)
    row = seen["row"]
    assert row.shape == (1, 11)
    assert row[0][1] == health_mod.AMBIENT_T_MEAN
    assert row[0][9] == health_mod.CHLOROPHYLL_MEAN
    assert row[0][0] == HEALTH_ROW["soil_moisture_pct"]
    assert row[0][6] == HEALTH_ROW["nitrogen_mg_kg"]


def test_plant_health_runs_without_the_electrochemical_reading(monkeypatch):
    """A farmer with no probe still gets a status: the mean fills the column."""
    seen = {}

    class _Recorder:
        def predict_proba(self, row):
            seen["row"] = row
            return np.array([[0.9, 0.05, 0.05]])

    monkeypatch.setattr(health_mod, "get_plant_health_model", lambda: _Recorder())
    row_without = {k: v for k, v in HEALTH_ROW.items() if k != "electrochemical_mv"}
    out = health_mod.check_plant_health_status(**row_without)
    assert "Plant health status" in out
    assert seen["row"][0][10] == health_mod.ELECTROCHEM_MEAN

    schema = health_mod.check_plant_health_tool.args_schema
    assert not schema.model_fields["electrochemical_mv"].is_required()
    assert "Plant health status" in health_mod.check_plant_health_tool.invoke(dict(row_without))


def test_plant_health_output_never_carries_a_rate(monkeypatch):
    proba = np.zeros(3)
    proba[1] = 0.9
    monkeypatch.setattr(health_mod, "get_plant_health_model", lambda: _FakeForest(proba))
    out = health_mod.check_plant_health_status(**HEALTH_ROW).lower()
    assert not any(unit in out for unit in ("kg/ha", "l/ha", "ml/l", "fl oz", "per acre", "per hectare"))


def test_plant_health_out_of_range_is_rejected_without_predicting(monkeypatch):
    def boom():
        raise AssertionError("model must not be consulted for an out-of-range row")

    monkeypatch.setattr(health_mod, "get_plant_health_model", boom)
    out = health_mod.check_plant_health_status(**{**HEALTH_ROW, "soil_ph": 9.0})
    assert "outside" in out


@pytest.mark.skipif(not HEALTH_PRESENT, reason="ml/ artifacts absent")
def test_plant_health_class_map_matches_the_known_labels():
    assert loaders.get_plant_health_classes() == {0: "Healthy", 1: "High Stress", 2: "Moderate Stress"}


def test_plant_health_tool_is_bound_in_the_agent():
    assert "check_plant_health_status" in {t.name for t in agent_mod.TOOLS}
    assert "check_plant_health_status" in agent_mod.STRING_TOOLS
    assert "check_plant_health_status" in agent_mod.TOOL_FUNCS
