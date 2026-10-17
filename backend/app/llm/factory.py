from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from backend.app.llm.base import LLMClient
from backend.app.llm.gemini_client import GeminiClient
from backend.app.llm.ollama_client import OllamaClient
from backend.app.llm.reliability import ReliableLLMClient
from backend.app.llm.rules_fallback import RulesClient


def _provider_client(provider: str, timeout_seconds: float) -> LLMClient:
    if provider == "gemini":
        return GeminiClient(timeout_seconds=timeout_seconds)
    if provider == "ollama":
        return OllamaClient(timeout_seconds=timeout_seconds)
    if provider == "rules":
        return RulesClient()  # type: ignore[return-value]
    raise ValueError("LLM_PROVIDER must be one of: gemini, ollama, rules")


def get_llm(
    provider: str | None = None,
    *,
    timeout_seconds: float | None = None,
    cache_path: str | Path | None = None,
) -> ReliableLLMClient:
    """Build the configured provider with caching, retry, and timeout protection."""
    load_dotenv()
    selected = (provider or os.getenv("LLM_PROVIDER", "gemini")).strip().casefold()
    timeout = timeout_seconds or float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    raw_client = _provider_client(selected, timeout)
    return ReliableLLMClient(
        raw_client,
        cache_path=cache_path,
        timeout_seconds=timeout,
    )
