from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """Minimal synchronous interface shared by remote and local providers."""

    provider: str
    model: str

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError
