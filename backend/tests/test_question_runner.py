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
