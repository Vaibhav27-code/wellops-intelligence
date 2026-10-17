from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any

from backend.app.llm.base import LLMClient

logger = logging.getLogger(__name__)


class LLMCallTimeout(TimeoutError):
    pass


def _status_code(error: BaseException) -> int | None:
    candidates = [getattr(error, "status_code", None), getattr(error, "code", None)]
    response = getattr(error, "response", None)
    candidates.append(getattr(response, "status_code", None))
    for value in candidates:
        try:
            code = int(value)
        except (TypeError, ValueError):
            continue
        if 100 <= code <= 599:
            return code
    return None


class SQLiteResponseCache:
    """Small persistent cache. Only digests and generated answers are stored."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @staticmethod
    def cache_key(provider: str, model: str, system: str | None, prompt: str) -> str:
        material = json.dumps(
            [provider, model, system, prompt],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def get(self, key: str) -> str | None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=5) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS llm_response_cache (cache_key TEXT PRIMARY KEY, answer TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            row = connection.execute(
                "SELECT answer FROM llm_response_cache WHERE cache_key = ?", (key,)
            ).fetchone()
        return str(row[0]) if row else None

    def put(self, key: str, answer: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=5) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS llm_response_cache (cache_key TEXT PRIMARY KEY, answer TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "INSERT INTO llm_response_cache(cache_key, answer) VALUES(?, ?) ON CONFLICT(cache_key) DO UPDATE SET answer=excluded.answer",
                (key, answer),
            )


class ReliableLLMClient(LLMClient):
    def __init__(
        self,
        client: LLMClient,
        *,
        cache_path: str | Path | None = None,
        timeout_seconds: float | None = None,
        max_attempts: int = 4,
        base_backoff_seconds: float = 0.25,
    ) -> None:
        self.client = client
        self.provider = client.provider
        self.model = client.model
        self.timeout_seconds = timeout_seconds or float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        self.max_attempts = max(1, max_attempts)
        self.base_backoff_seconds = max(0.0, base_backoff_seconds)
        self.cache = SQLiteResponseCache(
            cache_path or os.getenv("LLM_CACHE_PATH", "data/llm_cache.db")
        )

    def _call_with_timeout(
        self,
        prompt: str,
        system: str | None,
        json_schema: dict[str, Any] | None,
    ) -> str:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-call")
        future = executor.submit(self.client.generate, prompt, system, json_schema)
        try:
            return future.result(timeout=self.timeout_seconds)
        except FutureTimeout as exc:
            future.cancel()
            logger.warning("LLM call timed out provider=%s model=%s", self.provider, self.model)
            raise LLMCallTimeout("LLM call exceeded its configured timeout") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        key = self.cache.cache_key(self.provider, self.model, system, prompt)
        try:
            cached = self.cache.get(key)
        except sqlite3.Error:
            cached = None
            logger.warning("LLM cache read failed provider=%s model=%s", self.provider, self.model)
        if cached is not None:
            return cached

        for attempt in range(1, self.max_attempts + 1):
            try:
                answer = self._call_with_timeout(prompt, system, json_schema)
                try:
                    self.cache.put(key, answer)
                except sqlite3.Error:
                    logger.warning("LLM cache write failed provider=%s model=%s", self.provider, self.model)
                return answer
            except Exception as exc:
                code = _status_code(exc)
                retryable = code == 429 or (code is not None and 500 <= code < 600)
                if not retryable or attempt >= self.max_attempts:
                    raise
                cap = self.base_backoff_seconds * (2 ** (attempt - 1))
                delay = random.uniform(cap / 2, cap) if cap else 0
                logger.warning(
                    "Retrying transient LLM failure provider=%s model=%s status=%s attempt=%s/%s",
                    self.provider,
                    self.model,
                    code,
                    attempt,
                    self.max_attempts,
                )
                time.sleep(delay)
        raise RuntimeError("LLM attempts exhausted")
