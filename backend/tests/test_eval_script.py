from __future__ import annotations

import json
from pathlib import Path

from scripts.evaluate_questions import _check_response
from scripts.run_questions import _questions


def test_official_question_file_is_accepted_by_runner_and_has_18_cases() -> None:
    path = Path(__file__).parent / "fixtures" / "official_eval.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    normalized = _questions(payload)

    assert len(normalized) == 18
    assert normalized[0]["id"] == "Q1"
    assert normalized[0]["question"].startswith("Is WELL-0001")


def test_evaluation_checks_answer_visualization_citations_and_conflict() -> None:
    response = {
        "answer": "WELL-0001 had 21 days down.",
        "visualization": {"type": "table", "data": [{"Well": "WELL-0001"}]},
        "citations": [{"source_file": "assets/WELL-0001/inspections.jsonl", "record_id": "INS-1"}],
        "conflict": True,
    }

    errors = _check_response(
        response,
        {
            "contains": ["21 days"],
            "visualization": "table",
            "exact_values": {"field": "Well", "values": ["WELL-0001"]},
            "citations_contain": ["INS-1"],
            "min_citations": 1,
            "conflict": True,
        },
    )

    assert errors == []
