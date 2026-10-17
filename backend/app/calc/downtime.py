from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .rules import load_production_rule


_PLANNED_SHUT_IN = re.compile(r"\b(?:planned|scheduled)\b.{0,40}\bshut[- ]?in\b|\bshut[- ]?in\b.{0,40}\b(?:planned|scheduled)\b", re.IGNORECASE)
_MAX_WEEKLY_GAP_DAYS = 10


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_date(value: str | date | None, *, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.max.time() if end_of_day else datetime.min.time(), tzinfo=timezone.utc)
    elif len(value) <= 10:
        parsed = datetime.combine(
            date.fromisoformat(value),
            datetime.max.time() if end_of_day else datetime.min.time(),
            tzinfo=timezone.utc,
        )
    else:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.combine(date.fromisoformat(value), datetime.max.time() if end_of_day else datetime.min.time(), tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


_PLANNING_NOTE_TYPES = {"operator_note", "operator_feedback"}


def _planned_note_for(note: dict[str, Any], inspected_at: datetime) -> bool:
    if note.get("note_type") not in _PLANNING_NOTE_TYPES or not _PLANNED_SHUT_IN.search(str(note.get("text", ""))):
        return False
    valid_from = note.get("valid_from")
    valid_to = note.get("valid_to")
    day = inspected_at.date()
    try:
        if valid_from and date.fromisoformat(str(valid_from)) > day:
            return False
        if valid_to and date.fromisoformat(str(valid_to)) < day:
            return False
    except ValueError:
        return False
    return True


def calculate_downtime(
    inspections: list[dict[str, Any]],
    well_type: str,
    sample_data_root: str | Path,
    *,
    contexts: list[dict[str, Any]] | None = None,
    start: str | date | None = None,
    end: str | date | None = None,
    as_of: str | date | None = None,
) -> dict[str, Any]:
    """Count one week for each non-producing inspection; gaps and repairs add zero."""
    rule = load_production_rule(well_type, sample_data_root)
    start_at = _as_date(start)
    end_at = _as_date(end, end_of_day=True)
    as_of_at = _as_date(as_of, end_of_day=True)
    notes = contexts or []
    ordered = sorted(
        ((row, _timestamp(row.get("inspected_at"))) for row in inspections),
        key=lambda item: item[1] or datetime.min.replace(tzinfo=timezone.utc),
    )
    readings: list[dict[str, Any]] = []
    total_days = 0
    unplanned_days = 0
    current_streak = 0
    max_streak = 0
    previous_nonproducing_at: datetime | None = None

    for inspection, inspected_at in ordered:
        if inspected_at is None:
            continue
        if as_of_at and inspected_at > as_of_at:
            continue
        if start_at and inspected_at < start_at:
            continue
        if end_at and inspected_at > end_at:
            continue

        ambient = inspection.get("ambient_temp_c")
        wellhead = inspection.get("wellhead_temp_c")
        if not isinstance(ambient, (int, float)) or not isinstance(wellhead, (int, float)):
            status = "unknown"
            current_streak = 0
            previous_nonproducing_at = None
        else:
            delta = float(wellhead) - float(ambient)
            producing = delta >= rule.minimum_delta_c
            status = "producing" if producing else "not_producing"
            if producing:
                current_streak = 0
                previous_nonproducing_at = None
            else:
                # Normal observations are about seven days apart. A two-week
                # interval contains a missed weekly inspection and breaks the streak.
                if previous_nonproducing_at is not None and (inspected_at - previous_nonproducing_at).total_seconds() <= _MAX_WEEKLY_GAP_DAYS * 24 * 60 * 60:
                    current_streak += 7
                else:
                    current_streak = 7
                previous_nonproducing_at = inspected_at
                max_streak = max(max_streak, current_streak)
                total_days += 7

        planned = status == "not_producing" and any(_planned_note_for(note, inspected_at) for note in notes)
        if status == "not_producing" and not planned:
            unplanned_days += 7
        readings.append(
            {
                "inspection_id": inspection.get("inspection_id"),
                "inspected_at": inspection.get("inspected_at"),
                "status": status,
                "temperature_delta_c": round(float(wellhead) - float(ambient), 3)
                if isinstance(ambient, (int, float)) and isinstance(wellhead, (int, float)) else None,
                "downtime_days": 7 if status == "not_producing" else 0,
                "unplanned_downtime_days": 0 if planned or status != "not_producing" else 7,
                "planned_shut_in": planned,
                "consecutive_downtime_days": current_streak if status == "not_producing" else 0,
                "citation": f"assets/{inspection.get('asset_id', 'unknown')}/inspections.jsonl#{inspection.get('inspection_id', 'unknown')}",
            }
        )

    return {
        "well_type": well_type,
        "threshold_delta_c": rule.minimum_delta_c,
        "period": {"start": str(start) if start else None, "end": str(end) if end else None},
        "downtime_days": total_days,
        "unplanned_downtime_days": unplanned_days,
        "maximum_consecutive_downtime_days": max_streak,
        "inspection_count": len(readings),
        "readings": readings,
        "rule_citation": rule.citation,
    }
