from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from app.agent import agent as agent_mod
from app.agent.state import AgentState
from app.schemas.chat import ChatResponse, ChatTurn, ProductHit, Role
from app.schemas.common import PipelineStage
from app.tools import products_tool


ROWS = [
    {"id": "invesa:ciclope-500-ec", "source": "invesa", "name": "Cíclope 500 EC", "category": "fungicida",
     "active_ingredient": "difenoconazole y propiconazole", "description": "fungicida sistémico",
     "price_min": 43689.0, "price_max": 130839.0, "currency": "COP",
     "product_url": "https://agroinvesa.com/products/ciclope-500-ec", "technical_sheet_url": "t.pdf", "safety_sheet_url": "s.pdf"},
    {"id": "precisagro:foster", "source": "precisagro", "name": "Foster®", "category": "fungicida",
     "active_ingredient": "Propiconazole", "description": "fungicida a base de Propiconazole 250 g/L",
     "price_min": None, "price_max": None, "currency": None,
     "product_url": "https://precisagro.com.co/product/foster/", "technical_sheet_url": "t.pdf", "safety_sheet_url": None},
    {"id": "invesa:panzer-648-sl", "source": "invesa", "name": "Panzer 648 SL", "category": "herbicida",
     "active_ingredient": "glifosato", "description": "herbicida no selectivo. Mezclar con propiconazole no recomendado.",
     "price_min": 28000.0, "price_max": 90000.0, "currency": "COP",
     "product_url": "https://agroinvesa.com/products/panzer-648-sl", "technical_sheet_url": None, "safety_sheet_url": None},
]


@pytest.fixture(autouse=True)
def catalogue(monkeypatch):
    monkeypatch.setattr(products_tool, "load_products", lambda: ROWS)


def test_accent_and_case_insensitive_match():
    hits = products_tool.search_agrochemical_products("Propiconazol")
    assert [h["name"] for h in hits][:2] == ["Cíclope 500 EC", "Foster®"]


def test_ingredient_hit_outranks_description_hit():
    names = [h["name"] for h in products_tool.search_agrochemical_products("propiconazole")]
    assert names[-1] == "Panzer 648 SL"


def test_category_filter():
    hits = products_tool.search_agrochemical_products("propiconazole", category="herbicida")
    assert [h["name"] for h in hits] == ["Panzer 648 SL"]


def test_no_match_tells_the_model_not_to_invent():
    assert "Do not name a commercial product" in products_tool.format_for_model([])


def test_prices_never_reach_the_model_or_the_response():
    payload = products_tool.format_for_model(ROWS)
    assert "price" not in payload and "43689" not in payload and "COP" not in payload
    hit = ProductHit.model_validate(ROWS[0])
    dumped = json.dumps(hit.model_dump(by_alias=True))
    assert "price" not in dumped.lower()
    assert "priceMin" not in ChatResponse.model_json_schema()["$defs"]["ProductHit"]["properties"]


class _FakeLLM:
    """Records whether tools were bound and scripts one tool call then prose."""

    def __init__(self):
        self.bound = False
        self.calls = 0

    def bind_tools(self, tools):
        self.bound = True
        return self

    def invoke(self, messages):
        self.calls += 1
        if self.bound and self.calls == 1:
            return AIMessage(content="", tool_calls=[
                {"name": "search_agrochemical_products", "args": {"query": "propiconazole", "category": "fungicida"}, "id": "c1"}
            ])
        return AIMessage(content="Foster and Cíclope carry propiconazole.")


@pytest.fixture
def fake_llm(monkeypatch):
    fake = _FakeLLM()
    monkeypatch.setattr(agent_mod, "get_llm", lambda: fake)
    monkeypatch.setattr(agent_mod, "_retrieve_for", lambda message, state: [])
    return fake


def test_first_turn_never_binds_the_tool(fake_llm):
    """Consent floor: with no prior assistant turn the model cannot look up products."""
    state = AgentState(session_id="s", stage=PipelineStage.ANALYZING)
    agent_mod.run_agent("what fungicide for sheath blight?", state, history=[])
    assert fake_llm.bound is False
    assert state.products == []


def test_confirmed_follow_up_runs_the_tool_and_collects_products(fake_llm):
    state = AgentState(session_id="s", stage=PipelineStage.ANALYZING)
    history = [
        ChatTurn(role=Role.USER, content="what fungicide for sheath blight?"),
        ChatTurn(role=Role.ASSISTANT, content="Propiconazole... Want me to look up products?"),
    ]
    reply, _ = agent_mod.run_agent("yes please", state, history=history)
    assert fake_llm.bound is True
    assert fake_llm.calls == 2
    assert [p["id"] for p in state.products] == ["invesa:ciclope-500-ec", "precisagro:foster"]
    assert "Foster" in reply


def test_tool_rounds_are_capped(monkeypatch):
    class Loop(_FakeLLM):
        def invoke(self, messages):
            self.calls += 1
            if self.bound and self.calls <= agent_mod.MAX_TOOL_ROUNDS + 1:
                return AIMessage(content="", tool_calls=[
                    {"name": "search_agrochemical_products", "args": {"query": "x"}, "id": f"c{self.calls}"}
                ])
            return AIMessage(content="done")

    fake = Loop()
    monkeypatch.setattr(agent_mod, "get_llm", lambda: fake)
    monkeypatch.setattr(agent_mod, "_retrieve_for", lambda message, state: [])
    state = AgentState(session_id="s", stage=PipelineStage.ANALYZING)
    reply, _ = agent_mod.run_agent("yes", state, history=[ChatTurn(role=Role.ASSISTANT, content="offer?")])
    assert reply == "done"
    assert fake.calls == agent_mod.MAX_TOOL_ROUNDS + 2
