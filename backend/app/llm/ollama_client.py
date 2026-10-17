from __future__ import annotations

import os
from typing import Any

import httpx

from backend.app.llm.base import LLMClient


class OllamaClient(LLMClient):
    provider = "ollama"

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma4:e4b")
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        if json_schema:
            payload["format"] = json_schema
        response = httpx.post(
            f"{self.host}/api/generate",
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        result = response.json()
        text = result.get("response")
        if not isinstance(text, str):
            raise ValueError("Ollama response did not contain text")
        return text
