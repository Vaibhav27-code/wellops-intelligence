from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint_reports_provider_and_boolean_key_presence(monkeypatch) -> None:
    secret = "AIza-this-value-must-not-be-returned"
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", secret)
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["llm_provider"] == "gemini"
    assert payload["llm_key_present"] is True
    assert secret not in response.text
