from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import health as health_router


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(health_router, "is_model_available", lambda: True)
    monkeypatch.setattr(health_router, "is_spike_model_available", lambda: True)
    monkeypatch.setattr(health_router, "_weaviate_ready", lambda: True)
    with TestClient(app) as c:
        yield c


def test_everything_loaded_reports_ok(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"


def test_unreachable_weaviate_degrades_without_failing(client, monkeypatch):
    monkeypatch.setattr(health_router, "_weaviate_ready", lambda: False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_spike_model_is_reported_in_camel_case_without_gating_status(client, monkeypatch):
    monkeypatch.setattr(health_router, "is_spike_model_available", lambda: False)
    body = client.get("/health").json()
    assert body["spikeModelLoaded"] is False
    assert body["status"] == "ok"
