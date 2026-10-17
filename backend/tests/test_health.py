from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint_reports_provider_and_boolean_key_presence(monkeypatch) -> None:
    secret = "synthetic-test-secret-that-is-not-a-provider-key"
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", secret)
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["llm_provider"] == "gemini"
    assert payload["llm_key_present"] is True
    assert secret not in response.text


def test_demo_health_refuses_non_demo_database(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("ASSET_INTELLIGENCE_DB", "data/asset_intelligence.db")
    monkeypatch.setenv("LLM_CACHE_PATH", "data/demo_llm_cache.db")

    response = TestClient(app).get("/health")
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["demo_mode"] is False
    assert payload["demo_db_safe"] is False
