from __future__ import annotations

import logging
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from backend.app.llm.base import LLMClient
from backend.app.llm.factory import get_llm
from backend.app.llm.gemini_client import GeminiClient
from backend.app.llm.ollama_client import OllamaClient
from backend.app.llm.reliability import LLMCallTimeout, ReliableLLMClient
from backend.app.llm.rules_fallback import Intent, extract_intent
from backend.app.llm.service import LLMQuestionService


class FakeClient(LLMClient):
    provider = "gemini"
    model = "test-model"

    def __init__(self, responses: list[str] | None = None, error: Exception | None = None) -> None:
        self.responses = list(responses or [])
        self.error = error
        self.calls = 0

    def generate(self, prompt: str, system: str | None = None, json_schema=None) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        if not self.responses:
            raise AssertionError("Unexpected fake LLM call")
        return self.responses.pop(0)


def test_factory_selects_client_from_provider_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    gemini = get_llm(cache_path=tmp_path / "gemini.db")
    assert isinstance(gemini.client, GeminiClient)
    assert gemini.model == "gemini-2.5-flash-lite"

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.local:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:e4b")
    ollama = get_llm(cache_path=tmp_path / "ollama.db")
    assert isinstance(ollama.client, OllamaClient)
    assert ollama.client.host == "http://ollama.local:11434"
    assert ollama.model == "gemma4:e4b"

    monkeypatch.setenv("LLM_PROVIDER", "rules")
    rules = get_llm(cache_path=tmp_path / "rules.db")
    assert rules.provider == "rules"
    assert rules.model == "rules-v1"


def test_cache_hit_avoids_second_provider_call(tmp_path: Path) -> None:
    raw = FakeClient(responses=["cached answer"])
    client = ReliableLLMClient(raw, cache_path=tmp_path / "llm.db")

    assert client.generate("same prompt", system="same system") == "cached answer"
    assert client.generate("same prompt", system="same system") == "cached answer"
    assert raw.calls == 1


def test_rate_limit_retries_then_succeeds(tmp_path: Path, monkeypatch) -> None:
    class RateLimited(Exception):
        status_code = 429

    class RetryClient(FakeClient):
        def generate(self, prompt: str, system: str | None = None, json_schema=None) -> str:
            self.calls += 1
            if self.calls == 1:
                raise RateLimited("private request body is not logged")
            return "success"

    monkeypatch.setattr("backend.app.llm.reliability.time.sleep", lambda _delay: None)
    monkeypatch.setattr("backend.app.llm.reliability.random.uniform", lambda low, high: low)
    raw = RetryClient()
    client = ReliableLLMClient(raw, cache_path=tmp_path / "llm.db", base_backoff_seconds=0.001)

    assert client.generate("prompt") == "success"
    assert raw.calls == 2


def test_gemini_client_builds_json_request_without_network(monkeypatch) -> None:
    seen: dict = {}

    class Models:
        def generate_content(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(text='{"intent":"well_status"}')

    client = GeminiClient(api_key="test-only-secret", model="gemini-test")
    client._client = SimpleNamespace(models=Models())
    schema = Intent.model_json_schema()

    response = client.generate('{"question":"Is WELL-0001 producing?"}', system="extract", json_schema=schema)

    assert response == '{"intent":"well_status"}'
    assert seen["model"] == "gemini-test"
    assert seen["config"].response_mime_type == "application/json"
    assert seen["config"].response_schema == schema


def test_ollama_client_posts_to_local_generate_api_without_network(monkeypatch) -> None:
    seen: dict = {}

    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": "local answer"}

    def fake_post(url: str, *, json: dict, timeout: float) -> MockResponse:
        seen.update(url=url, payload=json, timeout=timeout)
        return MockResponse()

    monkeypatch.setattr("backend.app.llm.ollama_client.httpx.post", fake_post)
    client = OllamaClient(host="http://ollama.test:11434/", model="gemma-test", timeout_seconds=7)

    assert client.generate("prompt", system="system", json_schema={"type": "object"}) == "local answer"
    assert seen["url"] == "http://ollama.test:11434/api/generate"
    assert seen["payload"] == {
        "model": "gemma-test",
        "prompt": "prompt",
        "stream": False,
        "system": "system",
        "format": {"type": "object"},
    }
    assert seen["timeout"] == 7


def test_total_failure_uses_rules_and_deterministic_template(
    tmp_path: Path, caplog, monkeypatch
) -> None:
    secret = "AIza-secret-test-value"
    raw = FakeClient(error=ValueError(f"{secret}; private chat contents"))
    client = ReliableLLMClient(raw, cache_path=tmp_path / "llm.db")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    caplog.set_level(logging.WARNING, logger="backend.app.llm.service")
    caplog.set_level(logging.WARNING, logger="backend.app.llm.reliability")
    captured: list[Intent] = []

    def tools(intent: Intent) -> dict:
        captured.append(intent)
        return {
            "answer": "WELL-0001 had 21 downtime days in 2025.",
            "citations": [{"id": "INS-1"}],
            "visualization": None,
        }

    result = LLMQuestionService(client).answer("How long was WELL-0001 down in 2025?", tools)

    assert result["answer"] == "WELL-0001 had 21 downtime days in 2025."
    assert result["citations"] == [{"id": "INS-1"}]
    assert captured[0].intent == "downtime"
    assert raw.calls == 1
    assert secret not in caplog.text
    assert "private chat contents" not in caplog.text


def test_rules_extractor_handles_official_examples_and_rephrasings() -> None:
    # The first phrasing in each pair follows the official Example Questions; the
    # second varies its wording while preserving the task and entities.
    examples = [
        ("Is WELL-0001 producing oil right now? When was it last inspected, and by whom? Show me its status card.", "WELL-0001 status now, including its latest inspection and inspector.", "well_status"),
        ("Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.", "List the non-producing wells in Northeast Block 8 and their reasons.", "area_nonproducing"),
        ("Show a line chart of WELL-0001's wellhead temperature against air temperature for the last 13 weeks.", "Plot WELL-0001 surface temperature versus ambient over the past 13 weekly checks.", "temperature_trend"),
        ("How many oil spills has WELL-0001 had in the last 4 years, and how much oil in total?", "Count the actual oil releases at WELL-0001 during the previous four years and sum the barrels.", "spill_search"),
        ("How many days was WELL-0001 down in 2025?", "For calendar year 2025, how many downtime days did WELL-0001 record?", "downtime"),
        ("Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months?", "Rank the three longest-shut-in wells in Northeast Block 7 over the past four months.", "downtime"),
        ("Show on a map every well in Northeast Block 8 with a real spill in the last 90 days.", "Map all confirmed oil releases in Northeast Block 8 from the previous 90 days.", "spill_search"),
        ("Show a heatmap of 2026 spills by geographic area and month.", "Create an area-by-month heatmap for spill detections during 2026.", "spill_search"),
        ("Which rules has WELL-0001 broken in the last 12 months, and what is still open?", "List WELL-0001's regulatory breaches from the past year and the unresolved actions.", "compliance"),
        ("In Southwest Block 24, which spills in the last 90 days were not contained within the SOP time limit?", "Find recent Southwest Block 24 releases that exceeded the containment deadline.", "containment_breach"),
        ("For the three wells we discussed yesterday, what have repairs cost this year?", "What did maintenance cost this year on the three assets from our previous chat?", "private_memory"),
        ("The 15 Oct reading for WELL-0164 is wrong; the field crew re-measured the wellhead at 41.0 °C.", "Correct WELL-0164's October 15 wellhead value to 41 degrees C after the faulty reading.", "correction"),
    ]
    for official, paraphrase, expected in examples:
        for question in (official, paraphrase):
            assert extract_intent(question).intent == expected, question


def test_rules_extract_entities_and_period_phrases() -> None:
    intent = extract_intent(
        "Compare WELL-0007 in Northeast Block 8 during summer, Q3 2025, and show downtime."
    )
    assert intent.well_ids == ["WELL-0007"]
    assert intent.area_name == "Northeast Block 8"
    assert intent.season == "summer"
    assert intent.quarter == "Q3"
    assert intent.year == 2025
    assert intent.date_phrase == "during summer"
    assert "downtime" in intent.keywords
    assert extract_intent("Compare shutdowns over the past four months.").date_phrase == "past four months"


def test_valid_intent_then_answer_wording_uses_two_generation_calls(tmp_path: Path) -> None:
    intent_json = Intent(intent="well_status", well_ids=["WELL-0001"]).model_dump_json()
    raw = FakeClient(responses=[intent_json, "WELL-0001 is not producing."])
    client = ReliableLLMClient(raw, cache_path=tmp_path / "llm.db")
    result = LLMQuestionService(client).answer(
        "Is WELL-0001 producing?",
        lambda _intent: {
            "answer": "WELL-0001 is not producing (21.0 °C delta).",
            "citations": [{"id": "INS-1"}],
            "visualization": None,
        },
    )
    assert raw.calls == 2
    assert result["answer"] == "WELL-0001 is not producing."
    assert result["citations"] == [{"id": "INS-1"}]


def test_reliability_wrapper_enforces_hard_timeout(tmp_path: Path) -> None:
    class SlowClient(FakeClient):
        def generate(self, prompt: str, system: str | None = None, json_schema=None) -> str:
            time.sleep(0.04)
            return "late"

    client = ReliableLLMClient(
        SlowClient(),
        cache_path=tmp_path / "llm.db",
        timeout_seconds=0.005,
    )
    with pytest.raises(LLMCallTimeout):
        client.generate("prompt")
    time.sleep(0.05)


def test_invalid_intent_retries_once_and_uses_remaining_call_budget(
    tmp_path: Path,
) -> None:
    raw = FakeClient(
        responses=[
            '{"intent":"not-a-real-intent"}',
            Intent(intent="downtime", well_ids=["WELL-0001"], year=2025).model_dump_json(),
        ]
    )
    client = ReliableLLMClient(raw, cache_path=tmp_path / "llm.db")
    result = LLMQuestionService(client).answer(
        "How many days was WELL-0001 down in 2025?",
        lambda _intent: {"answer": "21 downtime days.", "citations": []},
    )
    assert result["intent"]["intent"] == "downtime"
    assert raw.calls == 2
    assert result["answer"] == "21 downtime days."
