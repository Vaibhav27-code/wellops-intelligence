from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from backend.app.calc.compliance import assess_well_compliance
from backend.app.calc.rules import assess_spill, load_production_rule, load_rca_rule, load_spill_rules
from backend.app.ingest.loader import _resolve_report_file
from backend.app.memory.store import apply_corrections_to_inspection, open_memory, retrieve_shared_memory
from backend.app.tools import data_tools
from backend.app.tools.db import get_db_path, get_reference_date, get_sample_data_root, query_records
from backend.app.tools.time_ranges import resolve_date_range
from backend.app.llm.rules_fallback import extract_intent

_WELL_ID = re.compile(r"\bWELL-\d{4}\b", re.IGNORECASE)


class PipelineError(RuntimeError):
    pass


def _well_id(question: str) -> str | None:
    match = _WELL_ID.search(question)
    return match.group(0).upper() if match else None


def _area(question: str) -> dict[str, Any] | None:
    lowered = question.casefold()
    for item in query_records("area"):
        if str(item.get("name", "")).casefold() in lowered:
            return item
    return None


def _reference_date() -> str:
    return get_reference_date()


def _period(question: str, as_of: str) -> tuple[str | None, str]:
    intent = extract_intent(question)
    return resolve_date_range(
        reference_date=as_of,
        date_phrase=intent.date_phrase or question,
        season=intent.season,
        quarter=intent.quarter,
        year=intent.year,
    )


def _date_in_range(value: Any, start: str | None, end: str | None) -> bool:
    if not isinstance(value, str) or len(value) < 10:
        return False
    day = value[:10]
    return (start is None or day >= start) and (end is None or day <= end)


def _users() -> dict[str, str]:
    return {str(row.get("user_id")): str(row.get("name", row.get("user_id"))) for row in query_records("user")}


def _shared_memory(well_id: str | None = None, well_type: str | None = None) -> dict[str, list[dict[str, Any]]]:
    connection = open_memory(get_db_path())
    try:
        return retrieve_shared_memory(connection, well_id=well_id, well_type=well_type)
    finally:
        connection.close()


def _apply_user_corrections(
    inspection: dict[str, Any], well: dict[str, Any], corrections: list[dict[str, Any]]
) -> dict[str, Any]:
    return apply_corrections_to_inspection(inspection, well, corrections)


def _source_citation(path: str, excerpt: str | None = None) -> dict[str, Any]:
    record_id = None
    source_file = path
    if "#" in path:
        source_file, record_id = path.split("#", 1)
    lower = source_file.lower()
    source_type = "manual" if "well-types" in lower else "sop" if "/sops/" in lower else "source"
    if "inspections.jsonl" in lower:
        source_type = "inspection"
    elif "maintenance.jsonl" in lower:
        source_type = "repair"
    elif "regulatory-events.jsonl" in lower:
        source_type = "regulatory"
    elif "context.jsonl" in lower:
        source_type = "note"
    elif "maintenance-reports" in lower:
        source_type = "repair"
    if record_id and record_id.lower().startswith(("ctx-", "reg-", "mnt-", "ins-")):
        record_id = record_id
    return {
        "id": path,
        "source_type": source_type,
        "source_file": source_file,
        "record_id": record_id,
        "excerpt": excerpt,
        "date": None,
    }


def _citations(paths: list[str], excerpts: dict[str, str] | None = None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for path in paths:
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(_source_citation(path, (excerpts or {}).get(path)))
    return result


def _well_records() -> list[dict[str, Any]]:
    return query_records("well")


def _all_inspections() -> list[dict[str, Any]]:
    return query_records("inspection")


def _all_contexts() -> list[dict[str, Any]]:
    return query_records("context")


def _status_for(well: dict[str, Any], inspection: dict[str, Any], corrections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    row = _apply_user_corrections(inspection, well, corrections or [])
    ambient = row.get("ambient_temp_c")
    wellhead = row.get("wellhead_temp_c")
    if not isinstance(ambient, (int, float)) or not isinstance(wellhead, (int, float)):
        return {"status": "unknown", "inspection": row, "delta_c": None}
    rule = load_production_rule(str(well.get("well_type", "")), get_sample_data_root())
    delta = round(float(wellhead) - float(ambient), 3)
    return {
        "status": "producing" if delta >= rule.minimum_delta_c else "not_producing",
        "inspection": row,
        "delta_c": delta,
        "threshold_delta_c": rule.minimum_delta_c,
        "rule_citation": rule.citation,
    }


def _find_well(well_id: str) -> dict[str, Any] | None:
    return next((well for well in _well_records() if well.get("asset_id") == well_id), None)


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [row for row in rows if isinstance(row.get("inspected_at"), str)]
    return max(valid, key=lambda row: row.get("inspected_at", "")) if valid else None


def _get_spills(
    *,
    well_id: str | None = None,
    area_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    as_of: str | None = None,
) -> list[dict[str, Any]]:
    as_of = as_of or _reference_date()
    wells = _well_records()
    if well_id:
        wells = [well for well in wells if well.get("asset_id") == well_id]
    if area_id:
        wells = [well for well in wells if well.get("area_id") == area_id]
    wells_by_id = {str(well.get("asset_id")): well for well in wells}
    contexts_by_well: dict[str, list[dict[str, Any]]] = {}
    inspections_by_well: dict[str, list[dict[str, Any]]] = {}
    for row in _all_contexts():
        contexts_by_well.setdefault(str(row.get("asset_id")), []).append(row)
    for row in _all_inspections():
        inspections_by_well.setdefault(str(row.get("asset_id")), []).append(row)
    rules = load_spill_rules(get_sample_data_root())
    spills: list[dict[str, Any]] = []
    for wid, well in wells_by_id.items():
        contexts = contexts_by_well.get(wid, [])
        memory = _shared_memory(wid, str(well.get("well_type", "")))
        corrections = memory["corrections"]
        for original in inspections_by_well.get(wid, []):
            inspected_at = original.get("inspected_at")
            if not _date_in_range(inspected_at, start, min(end or as_of, as_of)):
                continue
            row = _apply_user_corrections(original, well, corrections)
            spill = assess_spill(row, contexts, rules, as_of=as_of)
            if not spill or not spill.get("spill_detected"):
                continue
            spills.append(
                {
                    "well_id": wid,
                    "well_name": well.get("name"),
                    "area_id": well.get("area_id"),
                    "inspection_id": original.get("inspection_id"),
                    "date": str(inspected_at)[:10],
                    "inspected_at": inspected_at,
                    "volume_bbl": spill.get("volume_bbl"),
                    "classification": spill.get("classification"),
                    "external_report_required": spill.get("external_report_required"),
                    "report_deadline_hours": spill.get("report_deadline_hours"),
                    "latitude": well.get("latitude"),
                    "longitude": well.get("longitude"),
                    "citations": spill.get("citations", []),
                    "corrections": row.get("_applied_corrections", []),
                }
            )
    spills.sort(key=lambda row: (row["date"], row["well_id"], row["inspection_id"]))
    return spills


def _area_wells(area_id: str) -> list[dict[str, Any]]:
    return [well for well in _well_records() if well.get("area_id") == area_id]


def _status_answer(well_id: str) -> dict[str, Any]:
    details = data_tools.get_well_details(well_id)
    derived = details["derived_status"]
    inspection = derived.get("latest_inspection")
    if not inspection:
        raise PipelineError(f"No inspection record is available for {well_id}.")
    people = _users()
    inspected = str(inspection.get("inspected_at", ""))
    inspected_by = people.get(str(inspection.get("inspector_user_id")), "Unknown inspector")
    delta = derived.get("temperature_delta_c")
    status = derived.get("status", "unknown")
    correction = (derived.get("corrections") or [{}])[-1]
    conflict_notes = derived.get("conflicts", [])
    lines = [
        f"{well_id} is {'producing oil' if status == 'producing' else 'not producing oil' if status == 'not_producing' else 'of unknown production status'}.",
        f"Latest inspection: {inspection.get('inspection_id')} on {inspected[:10]}, by {inspected_by} using {inspection.get('method', 'an unrecorded method')}.",
    ]
    if delta is not None:
        lines.append(
            f"The wellhead was {delta:g} °C above ambient; the {details.get('well_type')} manual threshold is {derived.get('threshold_delta_c'):g} °C."
        )
    notes = query_records("context", asset_id=well_id, order_by_event=True, descending=True)
    relevant_notes = [
        note for note in notes
        if note.get("note_type") in {"operator_note", "operator_feedback"}
        and (not note.get("valid_from") or str(note.get("valid_from")) <= inspected[:10])
        and (not note.get("valid_to") or str(note.get("valid_to")) >= inspected[:10])
    ]
    relevant_notes = [note for note in relevant_notes if note.get("text")]
    relevant_notes.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
    if relevant_notes:
        lines.append(f"Relevant field note: {relevant_notes[0]['text']}")
    if derived.get("recorded_status") and derived.get("recorded_status") != status:
        lines.append(f"The source's recorded status is `{derived['recorded_status']}`, which differs from the inspection-derived status.")
    conflicts = bool(conflict_notes)
    if correction:
        lines.append(f"The reading has an audited correction by {people.get(str(correction.get('author')), correction.get('author'))}: {correction.get('reason')}")
    if conflicts:
        lines.append("The correction conflicts with an operator note; I am showing both pieces of evidence.")
    citations = derived.get("citations", [])
    if relevant_notes:
        citations.extend(_citation_path(note) for note in relevant_notes[:1])
    if derived.get("rule_citation"):
        citations.append(derived["rule_citation"])
    card = {
        "well_id": well_id,
        "well_name": details.get("name"),
        "production_status": status,
        "temperature_delta_c": delta,
        "threshold_delta_c": derived.get("threshold_delta_c"),
        "last_inspected_at": inspected,
        "inspected_by": inspected_by,
        "inspection_method": inspection.get("method"),
        "recorded_status": derived.get("recorded_status"),
        "reason": relevant_notes[0].get("text") if relevant_notes else inspection.get("notes"),
        "open_maintenance": derived.get("open_maintenance", []),
    }
    return {
        "answer": "\n".join(lines),
        "citations": _citations(citations),
        "visualization": {"type": "card", "title": f"{well_id} status", "data": [card]},
        "conflict": conflicts,
        "mentioned_wells": [well_id],
    }


def _citation_path(record: dict[str, Any]) -> str:
    return f"{record.get('_source_path', '')}#{record.get('note_id') or record.get('inspection_id') or record.get('maintenance_id') or ''}"


def _nonproducing_in_area(area: dict[str, Any]) -> dict[str, Any]:
    users = _users()
    rows: list[dict[str, Any]] = []
    cites: list[str] = []
    for well in _area_wells(str(area.get("area_id"))):
        wid = str(well.get("asset_id"))
        try:
            details = data_tools.get_well_details(wid)
        except data_tools.RecordNotFound:
            continue
        derived = details["derived_status"]
        if derived.get("status") != "not_producing":
            continue
        inspection = derived.get("latest_inspection") or {}
        delta = derived.get("temperature_delta_c")
        contexts = query_records("context", asset_id=wid)
        note = next(
            (
                context for context in contexts
                if context.get("inspection_id") == inspection.get("inspection_id")
                and context.get("note_type") in {"operator_note", "operator_feedback"}
            ),
            None,
        )
        repairs = derived.get("open_maintenance", [])
        repair = repairs[0] if repairs else None
        reason = (
            f"{repair.get('maintenance_id')}: {repair.get('issue')} (started {str(repair.get('started_at', ''))[:10]}, still open)"
            if repair else str(note.get("text")) if note else f"No recorded reason. Inspector noted: {inspection.get('notes', 'No inspection note.') }"
        )
        rows.append(
            {
                "well_id": wid,
                "well_name": well.get("name"),
                "well_type": well.get("well_type"),
                "wellhead_above_air_c": delta,
                "recorded_status": derived.get("recorded_status"),
                "reason": reason,
            }
        )
        cites.extend(derived.get("citations", []))
        if note:
            cites.append(_citation_path(note))
        if repair:
            cites.append(_citation_path(repair))
        cites.append(_citation_path(inspection))
    rows.sort(key=lambda row: row["well_id"])
    return {
        "answer": f"{len(rows)} wells in {area.get('name')} are not producing. A missing explanation is reported as missing evidence.",
        "citations": _citations(cites),
        "visualization": {"type": "table", "title": f"Non-producing wells — {area.get('name')}", "data": rows, "columns": list(rows[0]) if rows else []},
        "mentioned_wells": [row["well_id"] for row in rows],
    }


def _temperature_trend(well_id: str, question: str, as_of: str) -> dict[str, Any]:
    start, end = _period(question, as_of)
    if not start:
        start = (date.fromisoformat(as_of) - timedelta(days=85)).isoformat()
    details = data_tools.get_well_details(well_id, as_of=as_of)
    well = details
    inspections = query_records("inspection", asset_id=well_id)
    contexts = query_records("context", asset_id=well_id)
    memory = _shared_memory(well_id, str(well.get("well_type", "")))
    production_rule = load_production_rule(str(well.get("well_type", "")), get_sample_data_root())
    rows = []
    citations = [production_rule.citation]
    for original in sorted(inspections, key=lambda row: str(row.get("inspected_at", ""))):
        if not _date_in_range(original.get("inspected_at"), start, end):
            continue
        row = _apply_user_corrections(original, well, memory["corrections"])
        ambient, wellhead = row.get("ambient_temp_c"), row.get("wellhead_temp_c")
        if not isinstance(ambient, (int, float)) or not isinstance(wellhead, (int, float)):
            continue
        delta = float(wellhead) - float(ambient)
        rows.append(
            {
                "date": str(row.get("inspected_at", ""))[:10],
                "inspection_id": row.get("inspection_id"),
                "wellhead_temp_c": wellhead,
                "ambient_temp_c": ambient,
                "production_status": "producing" if delta >= production_rule.minimum_delta_c else "not_producing",
            }
        )
        citations.append(_citation_path(original))
        citations.extend(_citation_path(note) for note in contexts if note.get("inspection_id") == original.get("inspection_id") and note.get("note_type") == "correction")
    down_dates = [row["date"] for row in rows if row["production_status"] == "not_producing"]
    return {
        "answer": f"{len(rows)} inspection readings for {well_id} from {start} through {end}. Not producing on: {', '.join(down_dates) if down_dates else 'none in this period'}.",
        "citations": _citations(citations),
        "visualization": {"type": "line", "title": f"{well_id} wellhead and ambient temperature", "data": rows, "x": "date", "y": ["wellhead_temp_c", "ambient_temp_c"], "units": "°C"},
        "mentioned_wells": [well_id],
    }


def _spill_answer(question: str, as_of: str, area: dict[str, Any] | None, well_id: str | None) -> dict[str, Any]:
    start, end = _period(question, as_of)
    if "last 4 year" in question.casefold() or "past 4 year" in question.casefold():
        cutoff = date.fromisoformat(as_of)
        try:
            start = cutoff.replace(year=cutoff.year - 4).isoformat()
        except ValueError:
            start = cutoff.replace(year=cutoff.year - 4, day=28).isoformat()
        end = as_of
    if "last 90 day" in question.casefold() or "past 90 day" in question.casefold():
        start = (date.fromisoformat(as_of) - timedelta(days=90)).isoformat()
        end = as_of
    spills = _get_spills(
        well_id=well_id,
        area_id=str(area.get("area_id")) if area else None,
        start=start,
        end=end,
        as_of=as_of,
    )
    cites = [citation for spill in spills for citation in spill.get("citations", [])]
    cites.extend(correction.get("correction_id", "") for spill in spills for correction in spill.get("corrections", []))
    mentioned = sorted({str(spill["well_id"]) for spill in spills})
    if "heatmap" in question.casefold():
        months = [date(2000, month, 1).strftime("%b") for month in range(1, date.fromisoformat(as_of).month + 1)]
        month_keys = {f"{date.fromisoformat(as_of).year}-{month:02d}": months[month - 1] for month in range(1, len(months) + 1)}
        counts: dict[tuple[str, str], int] = {}
        areas = query_records("area")
        area_names = {str(row.get("area_id")): str(row.get("name")) for row in areas}
        for spill in spills:
            month = str(spill["date"])[:7]
            if month in month_keys:
                key = (area_names.get(str(spill.get("area_id")), "Unknown area"), month_keys[month])
                counts[key] = counts.get(key, 0) + 1
        grid = [
            {"area": name, "month": month, "value": counts.get((name, month), 0)}
            for name in area_names.values()
            for month in months
        ]
        return {
            "answer": f"{len(spills)} real spill detections were counted through {as_of}; formal source corrections were applied before counting.",
            "citations": _citations(cites),
            "visualization": {"type": "heatmap", "title": f"Spills by area and month — {date.fromisoformat(as_of).year}", "data": grid, "x": "month", "y": "area", "units": "spills"},
            "mentioned_wells": mentioned,
        }
    if "map" in question.casefold():
        map_rows = [
            {key: spill.get(key) for key in ("well_id", "well_name", "date", "volume_bbl", "latitude", "longitude", "classification")}
            for spill in spills
        ]
        return {
            "answer": f"Found {len(spills)} real spills in the requested area and period.",
            "citations": _citations(cites),
            "visualization": {"type": "map", "title": "Real spills", "data": map_rows},
            "mentioned_wells": mentioned,
        }
    total_volume = round(sum(float(spill.get("volume_bbl") or 0) for spill in spills), 2)
    answer = f"{len(spills)} real spills totaling {total_volume:g} bbl were found."
    rows = [
        {key: spill.get(key) for key in ("well_id", "inspection_id", "date", "volume_bbl", "classification")}
        for spill in spills
    ]
    return {
        "answer": answer,
        "citations": _citations(cites),
        "visualization": {"type": "table", "title": "Real spills", "data": rows, "columns": list(rows[0]) if rows else []},
        "mentioned_wells": mentioned,
    }


def _downtime_answer(question: str, well_id: str | None, area: dict[str, Any] | None, as_of: str) -> dict[str, Any]:
    start, end = _period(question, as_of)
    if well_id:
        if start is None:
            year = re.search(r"\b(20\d{2})\b", question)
            if year:
                start, end = f"{year.group(1)}-01-01", f"{year.group(1)}-12-31"
            else:
                start, end = (date.fromisoformat(as_of) - timedelta(days=90)).isoformat(), as_of
        result = data_tools.downtime_for_well(well_id, start=start, end=end, as_of=as_of)
        citations = [result["rule_citation"], *(row["citation"] for row in result["readings"] if row["status"] == "not_producing")]
        return {
            "answer": f"{well_id} had {result['downtime_days']} downtime days in {start} through {end}. Each inspected non-producing reading counts as seven days; missed inspections and repair duration add zero.",
            "citations": _citations(citations),
            "visualization": None,
            "mentioned_wells": [well_id],
        }
    if area:
        if start is None:
            start = (date.fromisoformat(as_of) - timedelta(days=122)).isoformat()
        ranked = []
        for well in _area_wells(str(area.get("area_id"))):
            result = data_tools.downtime_for_well(str(well.get("asset_id")), start=start, end=end, as_of=as_of)
            ranked.append({"well_id": well.get("asset_id"), "well_name": well.get("name"), "well_type": well.get("well_type"), "downtime_days": result["downtime_days"]})
        ranked.sort(key=lambda row: (-int(row["downtime_days"]), str(row["well_id"])))
        top_n = 3 if "3" in question or "three" in question.casefold() else 5
        rows = ranked[:top_n]
        return {
            "answer": f"Top {len(rows)} wells by downtime in {area.get('name')} from {start} through {end}.",
            "citations": _citations([f"assets/{row['well_id']}/inspections.jsonl" for row in rows] + ["fleet/well-types/T200.md#section 9.3", "fleet/well-types/T350.md#section 3"]),
            "visualization": {"type": "bar", "title": "Downtime by well", "data": rows, "x": "well_id", "y": "downtime_days", "units": "days"},
            "mentioned_wells": [str(row["well_id"]) for row in rows],
        }
    raise PipelineError("Name a well or geographic area so I can calculate downtime.")


def _compliance_answer(well_id: str, as_of: str) -> dict[str, Any]:
    well = _find_well(well_id)
    if not well:
        raise PipelineError(f"Unknown well: {well_id}")
    inspections = query_records("inspection", asset_id=well_id)
    maintenance = query_records("maintenance", asset_id=well_id)
    events = query_records("regulatory_event", asset_id=well_id)
    contexts = query_records("context", asset_id=well_id)
    memory = _shared_memory(well_id, str(well.get("well_type", "")))
    inspections = [_apply_user_corrections(row, well, memory["corrections"]) for row in inspections]
    report_texts = data_tools.get_maintenance_report_texts(maintenance, dataset_root=get_sample_data_root())
    findings = assess_well_compliance(
        well, inspections, maintenance, events, contexts, report_texts, str(get_sample_data_root()), as_of
    )
    flagged = [row for row in findings if row["status"] in {"confirmed_violation", "potential_violation"}]
    rows = [
        {"protocol_id": row["protocol_id"], "status": row["status"], "summary": row["summary"]}
        for row in flagged
    ]
    citations = [citation for row in flagged for citation in row.get("citations", [])]
    fine_total = sum(float(event.get("fine_amount_usd") or 0) for event in events if event.get("event_type") == "notice_of_violation")
    if not rows:
        answer = f"No confirmed or potential violations were found for {well_id} as of {as_of} using the available records."
    else:
        answer = f"Found {len(rows)} confirmed or potential compliance issues for {well_id} as of {as_of}."
    if fine_total:
        answer += f" Recorded NOV fine total: USD {fine_total:,.0f}."
    return {
        "answer": answer,
        "citations": _citations(citations),
        "visualization": {"type": "table", "title": f"Compliance findings — {well_id}", "data": rows, "columns": ["protocol_id", "status", "summary"]},
        "mentioned_wells": [well_id],
    }


def answer_question(question: str, user_id: str, *, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not question.strip():
        raise PipelineError("Enter a question about the asset data.")
    if not get_db_path().exists():
        raise PipelineError("The dataset has not been loaded yet. Run `python -m backend.app.ingest` first.")
    as_of = _reference_date()
    well_id = _well_id(question)
    area = _area(question)
    text = question.casefold()

    if "compliance" in text or "rules has" in text or "rules did" in text or "broken" in text:
        if not well_id:
            raise PipelineError("Name a well to check its compliance evidence.")
        return _compliance_answer(well_id, as_of)
    if "spill" in text and any(word in text for word in ("contain", "contained", "heatmap", "map", "how many", "total", "barrel", "real oil", "real spill")):
        return _spill_answer(question, as_of, area, well_id)
    if "downtime" in text or ("down" in text and area):
        return _downtime_answer(question, well_id, area, as_of)
    if "line chart" in text or ("temperature" in text and "week" in text and well_id):
        return _temperature_trend(well_id or "", question, as_of)
    if "not producing" in text or "non-producing" in text or ("which wells" in text and area):
        if area:
            return _nonproducing_in_area(area)
    if well_id:
        return _status_answer(well_id)
    if area:
        wells = _area_wells(str(area.get("area_id")))
        rows = [{"well_id": row.get("asset_id"), "well_name": row.get("name"), "well_type": row.get("well_type")} for row in wells]
        return {
            "answer": f"Found {len(rows)} wells in {area.get('name')}.",
            "citations": _citations([f"assets/{row['well_id']}/metadata.json" for row in rows]),
            "visualization": {"type": "table", "title": f"Wells — {area.get('name')}", "data": rows, "columns": list(rows[0]) if rows else []},
            "mentioned_wells": [str(row["well_id"]) for row in rows],
        }
    documents = data_tools.search_manuals_and_sops(question, limit=5)
    if documents:
        citations = [_source_citation(row["source_path"], row.get("excerpt")) for row in documents]
        return {
            "answer": "I found these source documents relevant to your question. Review the cited passages for the exact procedure.",
            "citations": citations,
            "visualization": None,
            "mentioned_wells": [],
        }
    raise PipelineError("I could not identify a well, area, calculation, or matching manual/SOP evidence in that question.")
