from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from backend.app.llm.factory import get_llm
from backend.app.llm.reliability import ReliableLLMClient
from backend.app.llm.rules_fallback import Intent, extract_intent, intent_prompt, parse_intent_response

logger = logging.getLogger(__name__)

_INTENT_SYSTEM = (
    "Extract the user's asset-operations intent and entities. Return only JSON matching the supplied schema. "
    "Do not answer the question or calculate anything."
)
_REPAIR_SYSTEM = (
    "Your previous intent JSON did not match the schema. Return corrected JSON only. "
    "Do not answer the question or calculate anything."
)
_ANSWER_SYSTEM = (
    "Rewrite the supplied deterministic answer for clarity. Keep every number, date, well ID, and factual claim unchanged. "
    "Do not calculate, add facts, invent citations, or include citation IDs. Return only the answer text."
)


def _template_answer(result: dict[str, Any]) -> str:
    answer = result.get("answer")
    if isinstance(answer, str) and answer.strip():
        return answer.strip()
    visualization = result.get("visualization")
    rows = visualization.get("data") if isinstance(visualization, dict) else None
    if isinstance(rows, list):
        return f"The deterministic tools found {len(rows)} matching records. See the attached results and citations."
    return "The deterministic tools did not return an answer. See the available citations for the evidence."


class LLMQuestionService:
    """Coordinates intent extraction, deterministic tools, and optional wording."""

    def __init__(self, client: ReliableLLMClient | None = None) -> None:
        self.client = client or get_llm()

    def answer(
        self,
        question: str,
        tool_runner: Callable[[Intent], dict[str, Any]],
    ) -> dict[str, Any]:
        calls_used = 0
        extraction_succeeded = False

        if self.client.provider == "rules":
            intent = extract_intent(question)
        else:
            prompt = intent_prompt(question)
            intent = extract_intent(question)
            for retry_invalid in range(2):
                try:
                    calls_used += 1
                    raw = self.client.generate(
                        prompt,
                        system=_INTENT_SYSTEM if retry_invalid == 0 else _REPAIR_SYSTEM,
                        json_schema=Intent.model_json_schema(),
                    )
                    intent = parse_intent_response(raw)
                    extraction_succeeded = True
                    break
                except Exception as exc:
                    # Exception details may contain request content or credentials; never log them.
                    logger.warning(
                        "Intent extraction fell back to deterministic rules provider=%s model=%s",
                        self.client.provider,
                        self.client.model,
                    )
                    if retry_invalid == 0 and calls_used < 2 and self._is_validation_error(exc):
                        continue
                    break

        result = tool_runner(intent)
        if not isinstance(result, dict):
            result = {"answer": str(result), "citations": [], "visualization": None}
        result["intent"] = intent.model_dump()
        result["answer"] = _template_answer(result)

        # A normal request uses one extraction call and one wording call. If validation
        # needed its one permitted retry, the remaining budget is used up by extraction.
        if extraction_succeeded and calls_used < 2 and self.client.provider != "rules":
            payload = {
                "answer": result["answer"],
                "citations": result.get("citations", []),
                "visualization": result.get("visualization"),
                "conflict": result.get("conflict", False),
                "intent": intent.model_dump(),
            }
            try:
                calls_used += 1
                rewritten = self.client.generate(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    system=_ANSWER_SYSTEM,
                ).strip()
                if rewritten:
                    result["answer"] = rewritten
            except Exception:
                logger.warning(
                    "Answer wording fell back to deterministic template provider=%s model=%s",
                    self.client.provider,
                    self.client.model,
                )
        return result

    @staticmethod
    def _is_validation_error(error: Exception) -> bool:
        return isinstance(error, (ValueError, TypeError)) or error.__class__.__name__ == "ValidationError"
