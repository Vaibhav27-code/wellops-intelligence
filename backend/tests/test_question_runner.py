from __future__ import annotations

import json

import httpx

from scripts.run_questions import _markdown, _questions, run_questions


def test_question_runner_posts_each_question_and_formats_required_fields() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "answer": f"Answer for {body['question']}",
                "answer_text": f"Answer for {body['question']}",
                "citations": [{"source_file": "assets/example.jsonl"}],
                "visualization": {"type": "table"},
                "provider_path": "rules",
            },
        )

    questions = _questions({
        "questions": [
            "What changed?",
            {"id": "q2", "question": "Show costs."},
            {
                "id": "Q1",
                "label": "Q1: Status Card",
                "question": "Is WELL-0001 producing?",
                "group": "single_well",
                "suggestedUser": "Sample Operator",
            },
        ]
    })
    results = run_questions(
        questions,
        base_url="http://copilot.test",
        user_id="runner-user",
        transport=httpx.MockTransport(handler),
    )
    report = _markdown(results)

    assert requests == [
        {"question": "What changed?", "user_id": "runner-user"},
        {"question": "Show costs.", "user_id": "runner-user"},
        {"question": "Is WELL-0001 producing?", "user_id": "runner-user"},
    ]
    assert "Provider path: `rules`" in report
    assert "Visualization: `table`" in report
    assert "Latency: `" in report and " ms`" in report
    assert "assets/example.jsonl" in report


def test_question_runner_accepts_official_metadata_and_user_session_aliases() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json={"answer_text": "ok", "citations": [], "visualization": None})

    questions = _questions(
        {
            "userId": "default-user",
            "sessionId": "default-session",
            "questions": [
                {
                    "id": "Q1",
                    "label": "Q1: official label",
                    "question": "Question with benchmark metadata?",
                    "group": "single_well",
                    "suggestedUser": "Display-only name",
                    "suggestedUserId": "official-user",
                    "expected": {"visualization": "card"},
                    "setup": [],
                    "followups": [],
                },
                {"id": "Q2", "question": "Use defaults?", "expected": {}},
                {"id": "Q3", "question": "Explicit aliases?", "userId": "item-user", "sessionId": "item-session"},
            ],
        }
    )
    run_questions(
        questions,
        base_url="http://copilot.test",
        user_id="cli-user",
        transport=httpx.MockTransport(handler),
    )

    assert requests == [
        {"question": "Question with benchmark metadata?", "user_id": "official-user", "session_id": "default-session"},
        {"question": "Use defaults?", "user_id": "default-user", "session_id": "default-session"},
        {"question": "Explicit aliases?", "user_id": "item-user", "session_id": "item-session"},
    ]
