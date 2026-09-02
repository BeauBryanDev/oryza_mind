from __future__ import annotations

import numpy as np
import pytest

from app.rag import vectorstore
from app.rag.retriever import RetrievalIntent, _build_filter, retrieve


class _FakeEncoder:
    def __init__(self):
        self.seen: list = []

    def encode(self, texts, **kwargs):
        self.seen.append(texts)
        if isinstance(texts, str):
            return np.zeros(1024, dtype=np.float32)
        return np.zeros((len(texts), 1024), dtype=np.float32)


@pytest.fixture
def encoder(monkeypatch):
    fake = _FakeEncoder()
    monkeypatch.setattr(vectorstore, "get_encoder", lambda: fake)
    return fake


def test_query_prefix_is_applied(encoder):
    """SAFETY RULE 1: e5 is asymmetric, an unprefixed query degrades silently."""
    vectorstore.embed_query("sheath blight fungicide rate")
    assert encoder.seen[0] == "query: sheath blight fungicide rate"


def test_batched_queries_keep_the_prefix_and_order(encoder):
    vectors = vectorstore.embed_queries(["neck blast", "false smut"])
    assert encoder.seen[0] == ["query: neck blast", "query: false smut"]
    assert len(vectors) == 2
    assert len(vectors[0]) == 1024


@pytest.mark.parametrize("blank", ["", "   "])
def test_empty_queries_are_rejected(encoder, blank):
    with pytest.raises(ValueError):
        vectorstore.embed_query(blank)
    with pytest.raises(ValueError):
        vectorstore.embed_queries(["ok", blank])


def test_treatment_intent_applies_both_safety_clauses():
    where, applied = _build_filter(None, RetrievalIntent.TREATMENT)
    assert where is not None
    assert "is_inoculation_protocol == False" in applied
    assert "document_type != screening_manual" in applied


def test_unfiltered_intent_applies_nothing():
    where, applied = _build_filter(None, RetrievalIntent.UNFILTERED)
    assert where is None
    assert applied == []


def test_disease_clause_is_added_only_when_given():
    _, without = _build_filter(None, RetrievalIntent.REFERENCE)
    _, with_class = _build_filter("Leaf_Blast", RetrievalIntent.REFERENCE)
    assert "disease_name == Leaf_Blast" in with_class
    assert not any(c.startswith("disease_name") for c in without)


class _FakeObject:
    def __init__(self, props):
        self.properties = props
        self.metadata = type("M", (), {"distance": 0.2})()


class _FakeCollection:
    def __init__(self, objects):
        self.objects = objects
        self.calls: list[dict] = []
        self.query = self

    def near_vector(self, **kwargs):
        self.calls.append(kwargs)
        return type("R", (), {"objects": self.objects})()


def _chunk(chunk_id: str, inoculation: bool = False) -> _FakeObject:
    return _FakeObject(
        {
            "chunk_id": chunk_id,
            "text": "text",
            "source_document": "doc.pdf",
            "is_inoculation_protocol": inoculation,
        }
    )


@pytest.mark.parametrize("bad", ["leaf_blast", "Narrow Brown", "Blast"])
def test_non_canonical_disease_name_is_rejected(bad):
    """A near-miss matches nothing in Weaviate and would return silently empty."""
    with pytest.raises(ValueError):
        retrieve("treatment", disease_name=bad)


def test_inoculation_chunk_is_dropped_client_side(monkeypatch):
    collection = _FakeCollection([_chunk("safe"), _chunk("xoc-protocol", inoculation=True)])
    monkeypatch.setattr("app.rag.retriever.get_collection", lambda: collection)
    monkeypatch.setattr("app.rag.retriever.embed_query", lambda *a, **k: [0.0] * 1024)

    result = retrieve("treatment for bacterial leaf blight")
    assert [c.chunk_id for c in result.chunks] == ["safe"]


def test_supplied_vector_skips_embedding(monkeypatch):
    collection = _FakeCollection([_chunk("safe")])
    monkeypatch.setattr("app.rag.retriever.get_collection", lambda: collection)

    def _fail(*args, **kwargs):
        raise AssertionError("embed_query must not run when a vector is passed")

    monkeypatch.setattr("app.rag.retriever.embed_query", _fail)
    vector = [0.5] * 1024
    retrieve("neck blast", query_vector=vector)
    assert collection.calls[0]["near_vector"] == vector
