from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProductionRule:
    well_type: str
    minimum_delta_c: float
    citation: str


@dataclass(frozen=True)
class SpillBand:
    name: str
    minimum_bbl: float
    maximum_exclusive_bbl: float | None


@dataclass(frozen=True)
class SpillRules:
    bands: tuple[SpillBand, ...]
    reportable_class_names: tuple[str, ...]
    reportable_deadline_hours: float
    major_class_name: str
    major_deadline_hours: float
    classification_citation: str
    reporting_citation: str


_WORD_NUMBERS = {
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
}


@dataclass(frozen=True)
class RcaRule:
    well_type: str
    minimum_corrective_events: int
    window_months: int
    citation: str


def load_rca_rule(well_type: str, sample_data_root: str | Path) -> RcaRule:
    """Read the corrective-maintenance RCA trigger from the well-type manuals."""
    root = Path(sample_data_root)
    t200_path = root / "fleet" / "well-types" / "T200.md"
    text = t200_path.read_text(encoding="utf-8")
    count_match = re.search(
        r"([A-Za-z]+|\d+)\s+or more\s+\*\*corrective\*\*",
        text,
        flags=re.IGNORECASE,
    )
    nearby = text[count_match.start() : count_match.start() + 400] if count_match else ""
    window_match = re.search(r"(\d+)\s+months", nearby, flags=re.IGNORECASE)
    if not count_match or not window_match:
        raise ValueError(f"Could not read RCA threshold from {t200_path}")
    raw = count_match.group(1).lower()
    count = int(raw) if raw.isdigit() else _WORD_NUMBERS[raw]
    if well_type.upper() == "T350":
        citation = "fleet/well-types/T350.md#section 6 (refers to T200 section 10)"
    else:
        citation = "fleet/well-types/T200.md#section 10"
    return RcaRule(well_type, count, int(window_match.group(1)), citation)


def load_production_rule(well_type: str, sample_data_root: str | Path) -> ProductionRule:
    manual_path = Path(sample_data_root) / "fleet" / "well-types" / f"{well_type}.md"
    text = manual_path.read_text(encoding="utf-8")
    match = re.search(
        r"at least\s+\*\*(?P<value>\d+(?:\.\d+)?)\s*°C above ambient",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Could not read production temperature threshold from {manual_path}")
    section = "3" if well_type.upper() == "T350" else "9.3"
    return ProductionRule(
        well_type=well_type,
        minimum_delta_c=float(match.group("value")),
        citation=f"fleet/well-types/{manual_path.name}#section {section}",
    )


def load_spill_rules(sample_data_root: str | Path) -> SpillRules:
    sop_path = Path(sample_data_root) / "fleet" / "sops" / "spill-response-sop.md"
    text = sop_path.read_text(encoding="utf-8")
    bands: list[SpillBand] = []
    for line in text.splitlines():
        cells = [cell.strip().strip("*").lower() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] not in {"minor", "moderate", "reportable", "major"}:
            continue
        range_text = cells[1]
        numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", range_text)]
        if "below" in range_text and len(numbers) == 1:
            bands.append(SpillBand(cells[0], 0.0, numbers[0]))
        elif "to below" in range_text and len(numbers) == 2:
            bands.append(SpillBand(cells[0], numbers[0], numbers[1]))
        elif "or more" in range_text and len(numbers) == 1:
            bands.append(SpillBand(cells[0], numbers[0], None))
    bands.sort(key=lambda band: band.minimum_bbl)
    if not bands or not any(band.name == "reportable" for band in bands) or not any(band.name == "major" for band in bands):
        raise ValueError(f"Could not read spill classes from {sop_path}")

    report_deadline = re.search(
        r"within\s+\*\*(\d+(?:\.\d+)?)\s+hours\*\*[^.]*?within\s+\*\*(\d+(?:\.\d+)?)\s+hours\*\*\s+for a major spill",
        text,
        flags=re.IGNORECASE,
    )
    if not report_deadline:
        raise ValueError(f"Could not read SR-01 report deadlines from {sop_path}")
    return SpillRules(
        bands=tuple(bands),
        reportable_class_names=("reportable",),
        reportable_deadline_hours=float(report_deadline.group(1)),
        major_class_name="major",
        major_deadline_hours=float(report_deadline.group(2)),
        classification_citation="fleet/sops/spill-response-sop.md#section 3",
        reporting_citation="fleet/sops/spill-response-sop.md#section 4 (SR-01)",
    )


def classify_spill(volume_bbl: float, rules: SpillRules) -> SpillBand:
    if volume_bbl < 0:
        raise ValueError("Spill volume cannot be negative")
    for band in rules.bands:
        if volume_bbl >= band.minimum_bbl and (
            band.maximum_exclusive_bbl is None or volume_bbl < band.maximum_exclusive_bbl
        ):
            return band
    raise ValueError(f"No spill class covers {volume_bbl} bbl; check the SOP table")


def _correction_value(note: dict[str, Any]) -> bool | None:
    text = str(note.get("text", "")).lower()
    if re.search(r"\bnot\s+(?:a\s+)?(?:crude\s+)?spill\b|\bnot crude\b|\bfalse positive\b", text):
        return False
    if re.search(r"\bconfirmed\s+(?:as\s+)?(?:a\s+)?spill\b|\bactual crude spill\b", text):
        return True
    return None


def _date(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[:10]


def matching_spill_correction(
    inspection: dict[str, Any],
    contexts: list[dict[str, Any]],
    as_of: str | None = None,
) -> tuple[bool | None, dict[str, Any] | None]:
    """Return an explicit spill correction scoped to this inspection, if one exists."""
    inspection_id = inspection.get("inspection_id")
    inspection_date = _date(inspection.get("inspected_at"))
    candidates: list[dict[str, Any]] = []
    for note in contexts:
        if note.get("note_type") != "correction" or note.get("inspection_id") != inspection_id:
            continue
        created = _date(note.get("created_at"))
        valid_from = _date(note.get("valid_from"))
        valid_to = _date(note.get("valid_to"))
        if created and inspection_date and created < inspection_date:
            continue
        if as_of and created and created > as_of[:10]:
            continue
        if valid_from and inspection_date and valid_from > inspection_date:
            # A correction note may be created later; valid_from describes its
            # application interval, so it must include the corrected reading.
            continue
        if valid_to and inspection_date and valid_to < inspection_date:
            continue
        if _correction_value(note) is not None:
            candidates.append(note)
    if not candidates:
        return None, None
    candidates.sort(key=lambda note: str(note.get("created_at", "")))
    # The latest explicit correction governs; callers can surface disagreement
    # between multiple notes as a conflict rather than rewriting source data.
    latest = candidates[-1]
    return _correction_value(latest), latest


def assess_spill(
    inspection: dict[str, Any],
    contexts: list[dict[str, Any]],
    rules: SpillRules,
    as_of: str | None = None,
) -> dict[str, Any] | None:
    corrected, correction = matching_spill_correction(inspection, contexts, as_of)
    detected = bool(inspection.get("spill_detected"))
    effective_detected = corrected if corrected is not None else detected
    if not effective_detected:
        return {
            "inspection_id": inspection.get("inspection_id"),
            "spill_detected": False,
            "classification": None,
            "external_report_required": False,
            "correction_applied": correction is not None,
            "citations": _spill_citations(inspection, correction, rules, include_classification=False),
        }

    volume = inspection.get("spill_est_volume_bbl")
    if not isinstance(volume, (int, float)):
        return {
            "inspection_id": inspection.get("inspection_id"),
            "spill_detected": True,
            "classification": "unknown",
            "volume_bbl": None,
            "external_report_required": None,
            "correction_applied": correction is not None,
            "citations": _spill_citations(inspection, correction, rules, include_classification=True),
        }
    band = classify_spill(float(volume), rules)
    required = band.name in (*rules.reportable_class_names, rules.major_class_name)
    deadline = (
        rules.major_deadline_hours
        if band.name == rules.major_class_name
        else rules.reportable_deadline_hours if band.name in rules.reportable_class_names else None
    )
    return {
        "inspection_id": inspection.get("inspection_id"),
        "spill_detected": True,
        "volume_bbl": float(volume),
        "classification": band.name,
        "external_report_required": required,
        "report_deadline_hours": deadline,
        "hours_to_report": inspection.get("hours_to_report"),
        "correction_applied": correction is not None,
        "citations": _spill_citations(inspection, correction, rules, include_classification=True),
    }


def _spill_citations(
    inspection: dict[str, Any],
    correction: dict[str, Any] | None,
    rules: SpillRules,
    include_classification: bool,
) -> list[str]:
    citations = [f"assets/{inspection.get('asset_id', 'unknown')}/inspections.jsonl#{inspection.get('inspection_id', 'unknown')}"]
    if correction is not None:
        citations.append(f"assets/{correction.get('asset_id', inspection.get('asset_id', 'unknown'))}/context.jsonl#{correction.get('note_id', 'unknown')}")
    if include_classification:
        citations.extend((rules.classification_citation, rules.reporting_citation))
    return citations


def spill_report_status(hours_to_report: float | None, spill: dict[str, Any]) -> str:
    if not spill.get("external_report_required"):
        return "not_required" if spill.get("spill_detected") else "not_applicable"
    if hours_to_report is None or spill.get("report_deadline_hours") is None:
        return "unknown"
    return "met" if float(hours_to_report) <= float(spill["report_deadline_hours"]) else "missed"
