from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.llm.base import LLMClient
from backend.app.tools.db import get_sample_data_root


IntentName = Literal[
    "well_status",
    "area_nonproducing",
    "temperature_trend",
    "spill_search",
    "containment_breach",
    "downtime",
    "repair_cost",
    "compliance",
    "rca",
    "sop_search",
    "correction",
    "shared_memory",
    "private_memory",
    "general",
]


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: IntentName = "general"
    well_ids: list[str] = Field(default_factory=list)
    area_name: str | None = None
    well_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    season: Literal["spring", "summer", "autumn", "fall", "winter"] | None = None
    quarter: Literal["Q1", "Q2", "Q3", "Q4"] | None = None
    year: int | None = None
    date_phrase: str | None = None
    metric: Literal[
        "downtime_days",
        "spill_volume",
        "repair_cost",
        "late_reports",
        "containment_breaches",
    ] | None = None
    group_by: Literal["well", "area", "month", "well_type"] = "well"
    limit: int | None = Field(default=None, ge=1, le=100)
    keywords: list[str] = Field(default_factory=list)


_WELL_RE = re.compile(r"\bWELL-\d{4}\b", re.IGNORECASE)
_WELL_TYPE_RE = re.compile(r"\bT\d{3}\b", re.IGNORECASE)
_EXPLICIT_RANGE_RE = re.compile(
    r"\b(?:from|between)\s+(\d{4}-\d{2}-\d{2})\s+(?:to|and)\s+(\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(?:last|past|previous|this|during|in|since|from)\s+(?:the\s+)?(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen)\s+(?:days?|weeks?|months?|years?)\b|"
    r"\b(?:last|past|previous|this|during|in|since|from)\s+(?:the\s+)?(?:\d{4}|year|spring|summer|autumn|fall|winter|(?:first|second|third|fourth|[1-4](?:st|nd|rd|th)?)\s+quarter|(?:last|previous|this|current)\s+quarter|quarter)\b",
    re.IGNORECASE,
)


def _areas() -> tuple[tuple[str, str], ...]:
    path = Path(get_sample_data_root()) / "fleet" / "areas.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return ()
    rows = data.get("areas", []) if isinstance(data, dict) else []
    return tuple(
        (str(row.get("name", "")), str(row.get("area_id", "")))
        for row in rows
        if isinstance(row, dict) and row.get("name")
    )


def _find_area(text: str) -> str | None:
    lowered = text.casefold()
    for name, area_id in _areas():
        if name and name.casefold() in lowered:
            return name
        if area_id and re.search(rf"(?<!\w){re.escape(area_id.casefold())}(?!\w)", lowered):
            return name
    return None


def _extract_quarter(text: str) -> str | None:
    match = re.search(r"\bq\s*([1-4])\b", text, re.IGNORECASE)
    if not match:
        match = re.search(r"\b(first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter\b", text, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).casefold()
    digits = {"first": "1", "second": "2", "third": "3", "fourth": "4", "1st": "1", "2nd": "2", "3rd": "3", "4th": "4"}
    return f"Q{digits.get(value, value)}"


def extract_intent(question: str) -> Intent:
    """Extract entities and a broad task intent without model calls or data answers."""
    text = question.casefold()
    well_ids = list(dict.fromkeys(match.upper() for match in _WELL_RE.findall(question)))
    area_name = _find_area(question)
    season_match = re.search(r"\b(spring|summer|autumn|fall|winter)\b", text)
    year_match = re.search(r"\b(20\d{2})\b", text)
    date_match = _DATE_RE.search(question)
    date_phrase = date_match.group(0) if date_match else None
    quarter = _extract_quarter(question)
    date_range_match = _EXPLICIT_RANGE_RE.search(question)
    well_type_match = _WELL_TYPE_RE.search(question)

    keyword_rules = {
        "downtime": r"\b(down|downtime|offline|shut[- ]*in)\b",
        "spill": r"\b(spills?|crude|releases?|barrels?|bbl)\b",
        "repair_cost": r"\b(repair|repairs|maintenance|work orders?)\b.{0,35}\b(cost|costs|spent|price|expense|expensive|priciest|costly)\b|\b(cost|costs|spent|price|expense|expensive|priciest|costly)\b.{0,35}\b(repair|repairs|maintenance|work orders?)\b",
        "sop": r"\b(sop|procedure|protocol|manual|limit|deadline)\b",
        "late_reports": r"\b(late|overdue|missed|unfiled|after the deadline|past the deadline)\b.{0,25}\b(reports?|filings?|notices?)\b|\b(reports?|filings?|notices?)\b.{0,25}\b(late|overdue|missed|unfiled|after the deadline|past the deadline)\b",
        "correction": r"\b(correct|correction|wrong|faulty|re-measured|remeasured|measured)\b",
        "memory": r"\b(remember|discussed|yesterday|previous (?:conversation|chat)|last (?:conversation|chat)|history)\b",
    }
    keywords = [name for name, pattern in keyword_rules.items() if re.search(pattern, text, re.IGNORECASE)]

    metric = None
    if re.search(r"\b(containment|contained)\b", text) and re.search(r"\b(breach|breaches|limit|sop|time)\b", text):
        metric = "containment_breaches"
    elif "late_reports" in keywords:
        metric = "late_reports"
    elif "repair_cost" in keywords:
        metric = "repair_cost"
    elif "downtime" in keywords:
        metric = "downtime_days"
    elif "spill" in keywords:
        metric = "spill_volume"

    if re.search(r"\b(by|per|each)\s+(?:geographic\s+)?areas?\b|\barea(?:-by-|\s+by\s+)month", text):
        group_by = "area"
    elif re.search(r"\b(by|per|each)\s+months?\b|\bmonthly\b|\bheatmap\b", text):
        group_by = "month"
    elif re.search(r"\b(by|per|each)\s+well[- ]types?\b", text):
        group_by = "well_type"
    else:
        group_by = "well"

    limit_match = re.search(r"\b(?:top|the)\s+(\d{1,2})\b", text)
    limit = int(limit_match.group(1)) if limit_match else None

    private_memory = bool(re.search(r"\b(we discussed|i discussed|remember|yesterday|previous (?:conversation|chat)|last (?:conversation|chat)|our last chat)\b", text))
    shared_memory = bool(re.search(r"\b(for everyone|for all|team now wants|shared notice|shared memory)\b", text))
    if re.search(r"\b(correct|correction|wrong|faulty|re-measured|remeasured|team now wants)\b", text):
        intent: IntentName = "correction"
    elif shared_memory:
        intent = "shared_memory"
    elif private_memory:
        intent = "private_memory"
    elif metric == "late_reports":
        intent = "compliance"
    elif re.search(r"\b(contain|contained|containment)\b", text) and re.search(r"\b(spills?|releases?)\b", text):
        intent = "containment_breach"
    elif re.search(r"\b(compliance|violation|violations|breach|breaches|broken|rules has|rules did|still open)\b", text):
        intent = "compliance"
    elif re.search(r"\b(root[ -]cause|rca|pump jack)\b", text):
        intent = "rca"
    elif "repair_cost" in keywords:
        intent = "repair_cost"
    elif "downtime" in keywords:
        intent = "downtime"
    elif re.search(r"\b(sop|procedure|protocol|manual)\b", text):
        intent = "sop_search"
    elif "spill" in keywords:
        intent = "spill_search"
    elif re.search(r"\b(temperature|wellhead|ambient|line chart|trend)\b", text) and re.search(r"\b(chart|trend|weeks?|months?|temperature|over time)\b", text):
        intent = "temperature_trend"
    elif re.search(r"\b(which|what|list|show)\b.{0,45}\b(wells?|not producing|non[ -]?producing)\b", text) and area_name:
        intent = "area_nonproducing"
    elif well_ids:
        intent = "well_status"
    else:
        intent = "general"

    return Intent(
        intent=intent,
        well_ids=well_ids,
        area_name=area_name,
        well_type=well_type_match.group(0).upper() if well_type_match else None,
        date_from=date_range_match.group(1) if date_range_match else None,
        date_to=date_range_match.group(2) if date_range_match else None,
        season=season_match.group(1).casefold() if season_match else None,
        quarter=quarter,
        year=int(year_match.group(1)) if year_match else None,
        date_phrase=date_phrase,
        metric=metric,
        group_by=group_by,
        limit=limit,
        keywords=keywords,
    )


def intent_prompt(question: str) -> str:
    return json.dumps({"question": question}, ensure_ascii=False)


def parse_intent_response(response: str) -> Intent:
    return Intent.model_validate_json(response)


class RulesClient(LLMClient):
    provider = "rules"
    model = "rules-v1"

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        del system, json_schema
        try:
            request = json.loads(prompt)
            question = request.get("question", "") if isinstance(request, dict) else ""
        except (json.JSONDecodeError, TypeError):
            question = prompt
        return extract_intent(str(question)).model_dump_json()
