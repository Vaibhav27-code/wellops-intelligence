from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


def test_feedback_is_persisted_per_user_and_can_be_updated(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    monkeypatch.setenv("ASSET_INTELLIGENCE_DB", str(tmp_path / "feedback.db"))
    client = TestClient(app)

    payload = {
        "user_id": "operator-a",
        "message_id": "assistant-message-42",
        "rating": "negative",
        "comment": "The cited inspection did not support the conclusion.",
    }
    first = client.post("/feedback", json=payload)

    assert first.status_code == 200
    assert first.json()["status"] == "recorded"
    assert first.json()["rating"] == "negative"
    stored = client.get("/feedback/operator-a").json()["feedback"]
    assert len(stored) == 1
    assert stored[0]["feedback_id"] == first.json()["feedback_id"]
    assert stored[0]["user_id"] == "operator-a"
    assert stored[0]["message_id"] == "assistant-message-42"
    assert stored[0]["rating"] == "negative"
    assert stored[0]["comment"] == "The cited inspection did not support the conclusion."
    assert client.get("/feedback/operator-b").json() == {"feedback": []}

    update = client.post(
        "/feedback",
        json={**payload, "rating": "positive", "comment": "The follow-up clarified it."},
    )
    assert update.status_code == 200
    assert update.json()["feedback_id"] == first.json()["feedback_id"]
    rows = client.get("/feedback/operator-a").json()["feedback"]
    assert len(rows) == 1
    assert rows[0]["rating"] == "positive"
    assert rows[0]["comment"] == "The follow-up clarified it."

    same_message_other_user = client.post(
        "/feedback",
        json={"user_id": "operator-b", "message_id": "assistant-message-42", "rating": "positive"},
    )
    assert same_message_other_user.status_code == 200
    assert len(client.get("/feedback/operator-b").json()["feedback"]) == 1
    assert "The cited inspection did not support the conclusion." not in caplog.text


def test_feedback_rejects_blank_ids_invalid_rating_and_long_comment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ASSET_INTELLIGENCE_DB", str(tmp_path / "feedback.db"))
    client = TestClient(app)

    base = {"user_id": "operator-a", "message_id": "assistant-message-42", "rating": "positive"}
    assert client.post("/feedback", json={**base, "user_id": " "}).status_code == 422
    assert client.post("/feedback", json={**base, "rating": "maybe"}).status_code == 422
    assert client.post("/feedback", json={**base, "comment": "x" * 2001}).status_code == 422
