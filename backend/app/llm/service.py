from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from backend.app.llm.factory import get_llm
from backend.app.llm.reliability import ReliableLLMClient
from backend.app.llm.rules_fallback import Intent, extract_intent, intent_prompt, parse_intent_response
from backend.app.tools.db import get_reference_date

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
                except Exception:
                    # Exception details may contain request content or credentials; never log them.
                    logger.warning(
                        "Intent extraction fell back to deterministic rules provider=%s model=%s",
                        self.client.provider,
                        self.client.model,
                    )
                    break
                try:
                    intent = parse_intent_response(raw)
                    extraction_succeeded = True
                    break
                except Exception as exc:
                    logger.warning(
                        "Intent response failed schema validation provider=%s model=%s",
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
        result["provider_path"] = "llm" if extraction_succeeded else "rules"

        # A normal request uses one extraction call and one wording call. If validation
        # needed its one permitted retry, the remaining budget is used up by extraction.
        if extraction_succeeded and calls_used < 2 and self.client.provider != "rules":
            payload = {
                "answer": result["answer"],
                "citations": result.get("citations", []),
                "visualization": result.get("visualization"),
                "conflict": result.get("conflict", False),
                "conflicts": result.get("conflicts", []),
                "calculation_explanation": result.get("calculation_explanation", ""),
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

        # Standardize return dictionary fields
        answer_text = str(result.get("answer", ""))
        result["answer_text"] = answer_text
        result["answer"] = answer_text

        # Ensure conflicts is always a list
        if "conflicts" not in result or not isinstance(result["conflicts"], list):
            conflict_msg = result.get("conflict_message")
            if conflict_msg:
                result["conflicts"] = [str(conflict_msg)]
            else:
                result["conflicts"] = []
        result["conflict"] = bool(result["conflicts"]) or bool(result.get("conflict", False))

        # Ensure calculation_explanation is populated
        if not result.get("calculation_explanation"):
            result["calculation_explanation"] = self._derive_calculation_explanation(intent, result)

        # Keep citations exactly as returned by tools
        raw_citations = result.get("citations", [])
        result["citations"] = list(raw_citations) if isinstance(raw_citations, list) else []
        result["data_as_of"] = result.get("data_as_of") or get_reference_date()

        return result

    @staticmethod
    def _derive_calculation_explanation(intent: Intent, result: dict[str, Any]) -> str:
        name = intent.intent
        if name == "downtime":
            return (
                "Downtime is calculated deterministically per operating rules: each weekly non-producing inspection "
                "accounts for exactly 7 days. Consecutive qualifying inspections accumulate. Missed inspections count "
                "as 0 days. Repair durations are not counted as downtime, and planned shut-ins are excluded from unplanned downtime."
            )
        if name in ("spill_search", "containment_breach"):
            return (
                "Spill metrics and reporting compliance are evaluated against SOP-SR-01 and regulatory limits: releases "
                ">= 5.0 bbl require 24-hour formal notification, containment within 4 hours, and 60-day agency verification. "
                "Non-crude and false-positive detections documented in context notes are excluded from spill totals."
            )
        if name in ("well_status", "area_nonproducing", "temperature_trend"):
            return (
                "Production status is evaluated deterministically by comparing wellhead temperature against ambient temperature "
                "using the minimum delta threshold parsed directly from the well's operating manual (e.g. 15.0 °C for T200, 20.0 °C for T350)."
            )
        if name == "compliance":
            return (
                "Compliance is evaluated deterministically against operating SOPs (SR-01 spill reporting, SR-02 containment, "
                "SR-03 verification, RC-04 notice of violation responses) and agency enforcement records."
            )
        if name == "repair_cost":
            return (
                "Maintenance expenditures are calculated deterministically by summing labor and parts costs from closed and ongoing work order records."
            )
        if name == "rca":
            return (
                "Root-cause analysis (RCA) eligibility is calculated by counting pump jack repair events within the fleet area "
                "and comparing against standard manual thresholds or user-scoped rule overrides."
            )
        if name == "correction":
            return (
                "Audited correction preserves original sensor record in immutable storage while applying the re-measured value "
                "to dynamic calculations and re-evaluating downstream compliance classifications."
            )
        return "Deterministic rule-based calculation grounded in fleet manuals and database records."

    @staticmethod
    def _is_validation_error(error: Exception) -> bool:
        return isinstance(error, (ValueError, TypeError)) or error.__class__.__name__ == "ValidationError"
