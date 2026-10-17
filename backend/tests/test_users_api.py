from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.ingest.loader import load_dataset
from backend.app.main import app
from backend.app.tools.db import get_sample_data_root


def test_users_endpoint_returns_all_ingested_user_fields(
    tmp_path: Path, monkeypatch
) -> None:
    dataset_root = get_sample_data_root()
    database = tmp_path / "users.db"
    load_dataset(dataset_root, database)
    monkeypatch.setenv("ASSET_INTELLIGENCE_DB", str(database))

    source = json.loads((dataset_root / "fleet" / "users.json").read_text(encoding="utf-8"))
    expected = {
        user["user_id"]: {
            "user_id": user["user_id"],
            "name": user.get("name", user["user_id"]),
            "role": user.get("role", "operator"),
            "team_id": user.get("team_id"),
            "area_id": user.get("area_id"),
        }
        for user in source["users"]
    }

    response = TestClient(app).get("/users")

    assert response.status_code == 200
    users = response.json()["users"]
    assert {user["user_id"]: user for user in users} == expected
    assert len(users) == len(expected)
    assert all(set(user) == {"user_id", "name", "role", "team_id", "area_id"} for user in users)
