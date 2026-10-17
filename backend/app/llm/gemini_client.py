from __future__ import annotations

import os
from typing import Any

from backend.app.llm.base import LLMClient


class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_seconds: float = 30) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.timeout_seconds = timeout_seconds
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        if self._client is None:
            from google import genai
            from google.genai.types import HttpOptions

            self._client = genai.Client(
                api_key=self.api_key,
                http_options=HttpOptions(timeout=int(self.timeout_seconds * 1000)),
            )
        return self._client

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        from google.genai.types import GenerateContentConfig

        config: dict[str, Any] = {}
        if system:
            config["system_instruction"] = system
        if json_schema:
            config["response_mime_type"] = "application/json"
            config["response_json_schema"] = json_schema
        response = self._get_client().models.generate_content(
            model=self.model,
            contents=prompt,
            config=GenerateContentConfig(**config),
        )
        return str(response.text or "")
