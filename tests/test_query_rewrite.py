from __future__ import annotations

import pytest

from app.agent import agent as agent_mod
from app.agent import query_rewrite as qr
from app.agent.state import AgentState
from app.core.config import get_settings


class _FakeLLM:
    def __init__(self, reply="english query", fail=False):
        self.reply, self.fail, self.calls = reply, fail, []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.fail:
            raise TimeoutError("gemini timed out")
        return type("R", (), {"text": self.reply})()


@pytest.fixture
def llm(monkeypatch):
    fake = _FakeLLM()
    monkeypatch.setattr(qr, "get_rewrite_llm", lambda: fake)
    return fake


@pytest.mark.parametrize("text", [
    "¿Qué fungicida le echo al añublo de la vaina y cuánto por hectárea?",
    "que le echo al arroz que tiene manchas cafes en las hojas",
    "las matas se estan secando desde la punta",
])
def test_spanish_is_detected_with_or_without_accents(text):
    assert qr.is_spanish(text)


@pytest.mark.parametrize("text", [
    "What fungicide do I use for sheath blight and how much per hectare?",
    "The photo shows Sheath_Blight. Severity HIGH, 12.0% of the image shows "
    "lesions. Give practical management steps.",
    "How much Quadris per acre for sheath blight?",
])
def test_english_is_never_detected_as_spanish(text):
    assert not qr.is_spanish(text)


def test_english_message_never_reaches_gemini(llm):
    msg = "What fungicide do I use for sheath blight?"
    assert qr.retrieval_queries(msg, [None]) == [msg]
    assert llm.calls == []


def test_spanish_without_photo_uses_the_literal_prompt(llm):
    out = qr.retrieval_queries("¿Qué le echo a las manchas cafés de la hoja?", [None])
    assert out == ["english query"]
    system = llm.calls[0][0].content
    assert "NEVER name a disease" in system


def test_spanish_with_photo_is_anchored_to_the_vision_class(llm):
    qr.retrieval_queries("¿Qué le echo a las manchas de la hoja?", ["Sheath_Blight"])
    system = llm.calls[0][0].content
    assert "diagnosed the farmer's rice photo as: sheath blight" in system


def test_coinfection_rewrites_once_per_class(llm):
    out = qr.retrieval_queries("¿Qué le echo a las manchas de la hoja?",
                               ["Sheath_Blight", "Brown_Spot"])
    assert len(out) == 2 and len(llm.calls) == 2


def test_failed_rewrite_falls_back_to_the_raw_message(monkeypatch):
    monkeypatch.setattr(qr, "get_rewrite_llm", lambda: _FakeLLM(fail=True))
    msg = "¿Qué le echo a las manchas cafés de la hoja?"
    assert qr.retrieval_queries(msg, [None]) == [msg]


def test_empty_rewrite_falls_back_to_the_raw_message(monkeypatch):
    monkeypatch.setattr(qr, "get_rewrite_llm", lambda: _FakeLLM(reply="  \n "))
    msg = "¿Qué le echo a las manchas cafés de la hoja?"
    assert qr.retrieval_queries(msg, [None]) == [msg]


def test_short_consent_reply_is_not_rewritten(llm):
    assert qr.retrieval_queries("sí, búsquelo", [None]) == ["sí, búsquelo"]
    assert llm.calls == []


def test_switch_off_restores_plain_retrieval(llm, monkeypatch):
    monkeypatch.setenv("QUERY_REWRITE_ENABLED", "false")
    get_settings.cache_clear()
    try:
        msg = "¿Qué le echo a las manchas cafés de la hoja?"
        assert qr.retrieval_queries(msg, [None]) == [msg]
        assert llm.calls == []
    finally:
        get_settings.cache_clear()


def test_retrieval_gets_the_rewrite_and_keeps_the_vision_filter(llm, monkeypatch):
    seen = []

    def fake_retrieve(query, disease_name, intent, top_k):
        seen.append((query, disease_name))
        return type("R", (), {"chunks": []})()

    monkeypatch.setattr(agent_mod, "retrieve", fake_retrieve)
    state = AgentState(session_id="t", disease_name="Leaf_Blast")
    agent_mod._retrieve_for("¿Cuándo fumigo contra la piricularia en la espiga?", state)
    assert seen == [("english query", "Leaf_Blast")]
