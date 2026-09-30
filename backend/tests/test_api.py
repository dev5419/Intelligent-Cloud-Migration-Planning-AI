import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_applications_endpoint() -> None:
    response = client.get("/applications")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) > 0


def test_application_by_id() -> None:
    response = client.get("/applications/APP001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "APP001" or payload["application_id"] == "APP001"


def test_missing_application_by_id() -> None:
    response = client.get("/applications/APP2000")
    assert response.status_code == 404


@pytest.mark.parametrize("application_id", ["APP001", "APP002", "APP003", "APP004", "APP005"])
def test_recommendation_endpoint(application_id: str) -> None:
    response = client.post("/recommendation", json={"application_id": application_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["app_id"] == application_id or payload["application_id"] == application_id
    assert payload["recommendation"] in {
        "Rehost",
        "Replatform",
        "Repurchase",
        "Refactor",
        "Retire",
        "Retain",
    }
    assert 0 <= float(payload["confidence"]) <= 1
    explanation = payload["explanation"]
    assert sum(explanation["probabilities"].values()) == pytest.approx(1.0, abs=0.02)
    assert explanation["shap"]["available"] is True
    assert explanation["shap"]["top_contributors"]
    assert "SHAP contribution" in explanation["shap"]["summary"]


@pytest.mark.parametrize("application_id", ["APP001", "APP002", "APP004"])
def test_cost_risk_endpoint_runs_simulation(application_id: str) -> None:
    response = client.post("/cost-risk", json={"application_id": application_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["application_id"] == application_id
    assert payload["monthly_aws_cost"] > 0
    assert payload["cost_range"]["lower"] <= payload["monthly_aws_cost"]
    assert payload["monthly_aws_cost"] <= payload["cost_range"]["upper"]
    assert 0 <= payload["risk_score"] <= 100


def test_migration_waves_process_dependencies() -> None:
    response = client.post(
        "/migration-waves",
        json={"application_ids": ["APP001", "APP089"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["application_count"] == 2
    assert payload["summary"]["dependency_count"] == 1
    planned_ids = [app_id for wave in payload["waves"] for app_id in wave["applications"]]
    assert set(planned_ids) == {"APP001", "APP089"}
    assert all("risk_score" in wave and "clusters" in wave for wave in payload["waves"])


def test_migration_waves_reject_unknown_application() -> None:
    response = client.post("/migration-waves", json={"application_ids": ["APP2000"]})
    assert response.status_code == 404


def test_copilot_uses_retrieved_context(monkeypatch) -> None:
    from app import copilot_service

    monkeypatch.setattr(
        copilot_service,
        "_get_pipeline",
        lambda: (
            lambda question, top_k: [{"text": "SOURCE: migration-guide.pdf\nRetrieved evidence."}],
            lambda question, docs: "Answer grounded in retrieved evidence.",
        ),
    )
    response = client.post("/copilot", json={"question": "How do I sequence a migration?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Answer grounded in retrieved evidence."
    assert payload["sources"] == ["migration-guide.pdf"]


def test_copilot_reports_missing_hugging_face_token(monkeypatch) -> None:
    from app import copilot_service

    monkeypatch.setattr(
        copilot_service,
        "_get_pipeline",
        lambda: (
            lambda question, top_k: [{"text": "SOURCE: migration-guide.pdf\nEvidence."}],
            lambda question, docs: (_ for _ in ()).throw(RuntimeError("HF_TOKEN is not configured.")),
        ),
    )
    response = client.post("/copilot", json={"question": "How do I migrate an application?"})
    assert response.status_code == 503
    assert "Verify HF_TOKEN" in response.json()["detail"]


def test_copilot_rejects_placeholder_hugging_face_token(monkeypatch) -> None:
    from copilot.llm import generate_answer

    monkeypatch.setenv("HF_TOKEN", "YOUR_HUGGING_FACE_TOKEN")
    with pytest.raises(RuntimeError, match="HF_TOKEN is not configured"):
        generate_answer("How should waves be sequenced?", [{"text": "Evidence."}])


def test_copilot_sanitizes_inference_errors(monkeypatch, caplog) -> None:
    from app import copilot_service

    error_marker = "DO_NOT_EXPOSE_THIS_VALUE"

    def fail_generation(question, documents):
        raise RuntimeError(f"Invalid Hugging Face credential: {error_marker}")

    monkeypatch.setattr(
        copilot_service,
        "_get_pipeline",
        lambda: (lambda question, top_k: [{"text": "Evidence."}], fail_generation),
    )
    response = client.post("/copilot", json={"question": "How do I migrate an application?"})

    assert response.status_code == 503
    assert "Verify HF_TOKEN" in response.json()["detail"]
    assert error_marker not in response.text
    assert error_marker not in caplog.text


def test_validation_errors() -> None:
    response = client.post("/recommendation", json={})
    assert response.status_code == 422


def test_missing_application() -> None:
    response = client.post("/recommendation", json={"application_id": "APP2000"})
    assert response.status_code == 404


def test_service_error() -> None:
    response = client.post("/cost-risk", json={"application_id": "APP2000"})
    assert response.status_code == 404


def test_swagger_and_openapi() -> None:
    docs_response = client.get("/docs")
    assert docs_response.status_code == 200
    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    assert "Intelligent Cloud Migration Planning API" in openapi_response.json()["info"]["title"]
