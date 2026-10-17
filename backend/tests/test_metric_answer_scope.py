from backend.app.llm.engine import _parameterized_metric_answer
from backend.app.llm.rules_fallback import Intent


def test_parameterized_metric_answer_names_active_area(monkeypatch):
    monkeypatch.setattr(
        "backend.app.llm.engine.query_metric",
        lambda *args, **kwargs: {
            "filters": {
                "area": "Southwest Block 23",
                "well_type": None,
                "well_id": None,
                "date_from": "2026-01-01",
                "date_to": "2026-10-15",
            },
            "rows": [{"group": "WELL-0001", "value": 125.0, "record_count": 1}],
            "records": [
                {
                    "citation": "assets/WELL-0001/maintenance.jsonl#MNT-0001",
                    "date": "2026-05-01",
                    "well_id": "WELL-0001",
                    "value": 125.0,
                }
            ],
            "unit": "USD",
        },
    )

    result = _parameterized_metric_answer(
        "Which wells in Southwest Block 23 had the highest repair costs in 2026?",
        Intent(
            intent="repair_cost",
            metric="repair_cost",
            area_name="Southwest Block 23",
            year=2026,
        ),
        "2026-10-15",
    )

    assert "for Southwest Block 23" in result["answer"]
    assert "for Southwest Block 23" in result["visualization"]["title"]
