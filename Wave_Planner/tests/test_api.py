"""Tests for the optional standalone API (api.py)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)
PORTFOLIO_CSV = Path(__file__).resolve().parents[2] / "data" / "processed" / "application_portfolio_1000.csv"


def post(payload):
    return client.post("/migration-waves", json=payload)


def index(body):
    return {a: w["wave"] for w in body["waves"] for a in w["applications"]}


def test_sample_respects_dependency_order():
    body = post({"source": "sample"}).json()
    order = index(body)
    assert order["app-002"] < order["app-001"] < order["app-003"]
    assert body["summary"]["planner"]["unmet_dependencies"] == 0
    assert [w["wave"] for w in body["waves"]] == list(range(1, len(body["waves"]) + 1))


def test_response_shape():
    wave = post({"source": "sample", "max_wave_size": 4}).json()["waves"][0]
    assert wave["risk"] in {"Low", "Medium", "High"}
    assert {"cluster_id", "risk_factors"} <= set(wave["clusters"][0])


def test_subset_and_warning():
    body = post({"source": "sample", "application_ids": ["app-001"]}).json()
    assert set(index(body)) == {"app-001"}
    assert any("outside" in w for w in body["warnings"])


def test_unknown_id_404():
    assert post({"source": "sample", "application_ids": ["x"]}).status_code == 404


@pytest.mark.parametrize("payload", [{"max_wave_size": 0}, {"max_cluster_size": 0}, {"resolution": 0}, {"source": "s3"}])
def test_invalid_422(payload):
    assert post(payload).status_code == 422


@pytest.mark.skipif(not PORTFOLIO_CSV.exists(), reason="portfolio CSV not present")
def test_portfolio_default_source():
    body = post({}).json()
    assert len(index(body)) == 1000
    assert body["summary"]["improvement_vs_random_pct"]["unmet_dependencies"] > 30
