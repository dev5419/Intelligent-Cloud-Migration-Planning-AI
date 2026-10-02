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
            lambda question, top_k: [{"text": "SOURCE: demo_migration_knowledge.pdf\nRetrieved evidence."}],
            lambda question, docs: "Answer grounded in retrieved evidence.",
        ),
    )
    response = client.post("/copilot", json={"question": "What is rehosting?"})
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"question", "answer", "sources"}
    assert payload["answer"] == "Answer grounded in retrieved evidence."
    assert payload["sources"] == ["demo_migration_knowledge.pdf"]


def _mock_copilot_core_api(monkeypatch, responses):
    from app import copilot_service

    calls = []

    def request(method, path, payload=None):
        calls.append((method, path, payload))
        result = responses[(method, path)]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(copilot_service, "_request_core_api", request)
    return calls


@pytest.mark.parametrize(
    "question",
    [
        "What is the recommendation for APP001?",
        "What should APP001 use for migration?",
    ],
)
def test_copilot_uses_live_recommendation(monkeypatch, question: str) -> None:
    from app import copilot_service

    calls = _mock_copilot_core_api(
        monkeypatch,
        {
            ("GET", "/applications"): [{"id": "APP001", "application_id": "APP001"}],
            ("POST", "/recommendation"): {"recommendation": "Rehost", "confidence": 0.82},
        },
    )
    response = client.post("/copilot", json={"question": question})
    payload = response.json()

    assert response.status_code == 200
    assert set(payload) == {"question", "answer", "sources"}
    assert "Rehost" in payload["answer"]
    assert "82%" in payload["answer"]
    assert payload["sources"] == ["/applications", "/recommendation"]
    assert calls[-1] == ("POST", "/recommendation", {"application_id": "APP001"})


@pytest.mark.parametrize(
    "question",
    [
        "What is the estimated cost of APP001?",
        "What is the risk for APP001?",
    ],
)
def test_copilot_uses_live_cost_risk(monkeypatch, question: str) -> None:
    _mock_copilot_core_api(
        monkeypatch,
        {
            ("GET", "/applications"): [{"id": "APP001", "application_id": "APP001"}],
            ("POST", "/cost-risk"): {
                "monthly_aws_cost": 100.0,
                "cost_range": {"lower": 80.0, "upper": 120.0},
                "risk_score": 45.0,
            },
        },
    )
    response = client.post("/copilot", json={"question": question})

    assert response.status_code == 200
    assert "$100.00" in response.json()["answer"]
    assert "$80.00 to $120.00" in response.json()["answer"]
    assert "45.0/100" in response.json()["answer"]
    assert response.json()["sources"] == ["/applications", "/cost-risk"]


def test_copilot_uses_live_direct_dependencies(monkeypatch) -> None:
    _mock_copilot_core_api(
        monkeypatch,
        {
            ("GET", "/applications"): [
                {"id": "APP001", "application_id": "APP001", "dependencies": ["APP089", "APP635"]}
            ],
        },
    )
    response = client.post("/copilot", json={"question": "What are APP001's dependencies?"})

    assert response.status_code == 200
    assert "APP089, APP635" in response.json()["answer"]
    assert response.json()["sources"] == ["/applications"]


def test_copilot_uses_live_reverse_dependencies(monkeypatch) -> None:
    _mock_copilot_core_api(
        monkeypatch,
        {
            ("GET", "/applications"): [
                {"id": "APP001", "application_id": "APP001", "dependencies": []},
                {"id": "APP002", "application_id": "APP002", "dependencies": ["APP001"]},
                {"id": "APP003", "application_id": "APP003", "dependencies": []},
            ],
        },
    )
    response = client.post("/copilot", json={"question": "What depends on APP001?"})

    assert response.status_code == 200
    assert "APP002" in response.json()["answer"]
    assert "APP003" not in response.json()["answer"]
    assert response.json()["sources"] == ["/applications"]


@pytest.mark.parametrize(
    "question",
    [
        "Which application should run first?",
        "Which applications should be migrated first?",
    ],
)
def test_copilot_uses_live_migration_order(monkeypatch, question: str) -> None:
    calls = _mock_copilot_core_api(
        monkeypatch,
        {
            ("POST", "/migration-waves"): {
                "waves": [{"wave": 1, "applications": ["APP010", "APP001"]}]
            },
        },
    )
    response = client.post("/copilot", json={"question": question})

    assert response.status_code == 200
    assert "APP010" in response.json()["answer"]
    assert response.json()["sources"] == ["/migration-waves"]
    assert calls == [("POST", "/migration-waves", {"application_ids": None})]


def test_copilot_validates_application_id_before_live_lookup(monkeypatch) -> None:
    calls = _mock_copilot_core_api(
        monkeypatch,
        {("GET", "/applications"): [{"id": "APP001", "application_id": "APP001"}]},
    )
    response = client.post("/copilot", json={"question": "What is the recommendation for APP9999?"})

    assert response.status_code == 200
    assert "could not find APP9999" in response.json()["answer"]
    assert calls == [("GET", "/applications", None)]


def test_copilot_sanitizes_live_data_failures(monkeypatch, caplog) -> None:
    from app import copilot_service

    marker = "DO_NOT_EXPOSE_CORE_RESPONSE"
    _mock_copilot_core_api(
        monkeypatch,
        {
            ("GET", "/applications"): [{"id": "APP001", "application_id": "APP001"}],
            ("POST", "/recommendation"): copilot_service.LiveDataUnavailable(marker),
        },
    )
    response = client.post("/copilot", json={"question": "What is the recommendation for APP001?"})

    assert response.status_code == 200
    assert "live application data is currently unavailable" in response.json()["answer"].lower()
    assert marker not in response.text
    assert marker not in caplog.text


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


def test_copilot_resolves_placeholder_token_from_secrets_manager(monkeypatch) -> None:
    import boto3
    from copilot import llm

    secret_name = "test/copilot-huggingface-token"
    fake_token = "test-only-token-not-a-credential"
    secret_requests = []

    class FakeSecretsManager:
        def get_secret_value(self, SecretId):
            secret_requests.append(SecretId)
            return {"SecretString": fake_token}

    monkeypatch.setattr(llm, "_HF_TOKEN", None)
    monkeypatch.setenv("HF_TOKEN", "YOUR_HUGGING_FACE_TOKEN")
    monkeypatch.setenv("HF_SECRET_NAME", secret_name)
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setattr(boto3, "client", lambda service, region_name: FakeSecretsManager())

    assert llm._get_hf_token() == fake_token
    assert secret_requests == [secret_name]


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
