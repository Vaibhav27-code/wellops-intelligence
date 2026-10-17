from __future__ import annotations

import calendar
import re
from datetime import date, timedelta


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
}
_MONTHS = {
    "spring": (3, 1, 5, 31),
    "summer": (6, 1, 8, 31),
    "autumn": (9, 1, 11, 30),
    "fall": (9, 1, 11, 30),
}


def _subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = 1 + (quarter - 1) * 3
    end_month = start_month + 2
    return date(year, start_month, 1), date(year, end_month, calendar.monthrange(year, end_month)[1])


def _season_bounds(season: str, start_year: int) -> tuple[date, date]:
    normalized = season.casefold()
    if normalized == "winter":
        return date(start_year, 12, 1), date(start_year + 1, 2, calendar.monthrange(start_year + 1, 2)[1])
    if normalized not in _MONTHS:
        raise ValueError(f"Unsupported season: {season}")
    start_month, start_day, end_month, end_day = _MONTHS[normalized]
    return date(start_year, start_month, start_day), date(start_year, end_month, end_day)


def _parse_span(phrase: str) -> tuple[str, int] | None:
    match = re.search(
        r"\b(?:last|past|previous|over the last)\s+(\d+|" + "|".join(_NUMBER_WORDS) + r")\s+(days?|weeks?|months?|years?)\b",
        phrase,
        re.IGNORECASE,
    )
    if not match:
        return None
    amount = _NUMBER_WORDS.get(match.group(1).casefold(), None)
    if amount is None:
        amount = int(match.group(1))
    return match.group(2).casefold(), amount


def _as_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def resolve_date_range(
    *,
    reference_date: str | date,
    date_from: str | date | None = None,
    date_to: str | date | None = None,
    season: str | None = None,
    quarter: str | None = None,
    year: int | None = None,
    date_phrase: str | None = None,
) -> tuple[str | None, str]:
    """Resolve explicit and natural date filters against a dataset reference date."""
    reference = _as_date(reference_date)
    assert reference is not None
    phrase = (date_phrase or "").casefold()

    explicit_start = _as_date(date_from)
    explicit_end = _as_date(date_to)
    if explicit_start or explicit_end:
        start = explicit_start
        end = min(explicit_end or reference, reference)
        if start and start > end:
            raise ValueError("date_from must be on or before date_to/reference date")
        return start.isoformat() if start else None, end.isoformat()

    if re.search(r"\b(?:last|previous)\s+quarter\b", phrase):
        current_quarter = (reference.month - 1) // 3 + 1
        previous_quarter = current_quarter - 1 or 4
        previous_year = reference.year if current_quarter > 1 else reference.year - 1
        start, end = _quarter_bounds(previous_year, previous_quarter)
        return start.isoformat(), min(end, reference).isoformat()

    if quarter:
        quarter_match = re.search(r"([1-4])", str(quarter))
        if quarter_match:
            quarter_number = int(quarter_match.group(1))
            if re.search(r"\bthis\s+quarter\b", phrase):
                quarter_number = (reference.month - 1) // 3 + 1
                target_year = reference.year
            else:
                target_year = year or reference.year
            start, end = _quarter_bounds(target_year, quarter_number)
            return start.isoformat(), min(end, reference).isoformat()

    if season:
        normalized = season.casefold()
        if normalized == "winter":
            candidates = [_season_bounds(normalized, candidate_year) for candidate_year in range(reference.year - 2, reference.year + 2)]
        elif normalized in _MONTHS:
            candidates = [_season_bounds(normalized, candidate_year) for candidate_year in range(reference.year - 2, reference.year + 2)]
        else:
            raise ValueError(f"Unsupported season: {season}")

        if re.search(r"\b(?:last|previous)\s+", phrase):
            completed = [bounds for bounds in candidates if bounds[1] < reference]
            start, end = max(completed, key=lambda bounds: bounds[1]) if completed else min(candidates)
        elif re.search(r"\bthis\s+", phrase):
            containing = [bounds for bounds in candidates if bounds[0] <= reference <= bounds[1]]
            same_start_year = [bounds for bounds in candidates if bounds[0].year == (year or reference.year)]
            start, end = (containing or same_start_year or candidates)[0]
        elif year:
            start, end = _season_bounds(normalized, year)
        else:
            containing = [bounds for bounds in candidates if bounds[0] <= reference <= bounds[1]]
            completed = [bounds for bounds in candidates if bounds[1] < reference]
            start, end = (containing or [max(completed, key=lambda bounds: bounds[1])])[0]
        end = min(end, reference)
        if start > reference:
            return start.isoformat(), start.isoformat()
        return start.isoformat(), end.isoformat()

    if re.search(r"\b(?:last|previous)\s+year\b", phrase):
        target_year = reference.year - 1
        return date(target_year, 1, 1).isoformat(), date(target_year, 12, 31).isoformat()
    if re.search(r"\bthis\s+year\b", phrase):
        return date(reference.year, 1, 1).isoformat(), reference.isoformat()

    span = _parse_span(phrase)
    if span:
        unit, amount = span
        if unit.startswith("day"):
            start = reference - timedelta(days=amount)
        elif unit.startswith("week"):
            start = reference - timedelta(days=amount * 7)
        elif unit.startswith("month"):
            start = _subtract_months(reference, amount)
        else:
            try:
                start = reference.replace(year=reference.year - amount)
            except ValueError:
                start = reference.replace(year=reference.year - amount, day=28)
        return start.isoformat(), reference.isoformat()

    explicit_year = year
    if explicit_year is None:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", phrase)
        if match:
            explicit_year = int(match.group(1))
    if explicit_year is not None:
        start = date(explicit_year, 1, 1)
        end = date(explicit_year, 12, 31)
        if explicit_year == reference.year:
            end = reference
        return start.isoformat(), end.isoformat()

    return None, reference.isoformat()
