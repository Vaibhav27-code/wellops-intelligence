from __future__ import annotations

import sqlite3

import pytest

from backend.app.llm.engine import _intent_period
from backend.app.llm.rules_fallback import Intent
from backend.app.tools.db import get_reference_date
from backend.app.tools.time_ranges import resolve_date_range


def test_reference_date_uses_latest_inspection_in_database(tmp_path, monkeypatch) -> None:
    database = tmp_path / "asset.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE records (entity_type TEXT, event_at TEXT)")
        connection.executemany(
            "INSERT INTO records VALUES (?, ?)",
            [
                ("inspection", "2026-02-14T07:00:00Z"),
                ("inspection", "2026-10-15T07:00:00Z"),
                ("maintenance", "2026-12-01T07:00:00Z"),
            ],
        )
    monkeypatch.delenv("REFERENCE_DATE", raising=False)
    assert get_reference_date(database) == "2026-10-15"


def test_reference_date_override_is_validated_and_takes_precedence(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REFERENCE_DATE", "2025-03-09")
    assert get_reference_date(tmp_path / "missing.db") == "2025-03-09"

    monkeypatch.setenv("REFERENCE_DATE", "not-a-date")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        get_reference_date(tmp_path / "missing.db")


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"date_phrase": "last 4 months"}, ("2026-06-15", "2026-10-15")),
        ({"date_phrase": "last 90 days"}, ("2026-07-17", "2026-10-15")),
        ({"date_phrase": "last quarter"}, ("2026-07-01", "2026-09-30")),
        ({"date_phrase": "this quarter", "quarter": "Q4"}, ("2026-10-01", "2026-10-15")),
        ({"date_phrase": "this summer", "season": "summer"}, ("2026-06-01", "2026-08-31")),
        ({"date_phrase": "in 2025", "year": 2025}, ("2025-01-01", "2025-12-31")),
        ({"date_from": "2026-02-01", "date_to": "2026-02-15"}, ("2026-02-01", "2026-02-15")),
    ],
)
def test_relative_and_explicit_periods_resolve_against_reference(kwargs, expected) -> None:
    assert resolve_date_range(reference_date="2026-10-15", **kwargs) == expected


def test_explicit_year_does_not_get_overridden_by_engine_default_period() -> None:
    intent = Intent(intent="downtime", year=2025)

    assert _intent_period(intent, "2026-10-15", "this year") == (
        "2025-01-01",
        "2025-12-31",
    )


def test_explicit_date_range_cannot_extend_after_reference_date() -> None:
    assert resolve_date_range(
        reference_date="2026-10-15",
        date_from="2026-10-01",
        date_to="2026-12-31",
    ) == ("2026-10-01", "2026-10-15")


def test_date_range_rejects_reversed_bounds() -> None:
    with pytest.raises(ValueError, match="date_from"):
        resolve_date_range(
            reference_date="2026-10-15",
            date_from="2026-10-16",
            date_to="2026-10-17",
        )
