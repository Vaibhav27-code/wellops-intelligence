from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Literal

from backend.app.calc.rules import assess_spill, load_spill_rules, spill_report_status
from backend.app.tools.db import get_reference_date, get_sample_data_root, query_records
from backend.app.tools.downtime import get_well_downtime
from backend.app.tools.spills import get_all_real_spills
from backend.app.tools.time_ranges import resolve_date_range

Metric = Literal[
    "downtime_days",
    "spill_volume",
    "repair_cost",
    "late_reports",
    "containment_breaches",
]
GroupBy = Literal["well", "area", "month", "well_type"]


def _area_ids(area: str | None, areas: list[dict[str, Any]]) -> tuple[set[str] | None, str | None]:
    if not area:
        return None, None
    match = next(
        (
            row
            for row in areas
            if str(row.get("name", "")).casefold() == area.casefold()
            or str(row.get("area_id", "")).casefold() == area.casefold()
        ),
        None,
    )
    return ({str(match.get("area_id"))}, str(match.get("name"))) if match else (set(), area)


def _month(value: Any) -> str | None:
    text = str(value or "")
    try:
        return date.fromisoformat(text[:10]).strftime("%Y-%m")
    except ValueError:
        return None


def query_metric(
    metric: Metric,
    *,
    area: str | None = None,
    well_type: str | None = None,
    well_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    season: str | None = None,
    quarter: str | None = None,
    year: int | None = None,
    date_phrase: str | None = None,
    group_by: GroupBy = "well",
    reference_date: str | None = None,
) -> dict[str, Any]:
    """Calculate a fleet metric with shared, data-independent filters.

    All metric values are computed from records and deterministic operating rules;
    callers may group the result by well, area, month, or well type.
    """
    if metric not in {"downtime_days", "spill_volume", "repair_cost", "late_reports", "containment_breaches"}:
        raise ValueError(f"Unsupported metric: {metric}")
    if group_by not in {"well", "area", "month", "well_type"}:
        raise ValueError(f"Unsupported group_by: {group_by}")

    reference = (reference_date or get_reference_date())[:10]
    start, end = resolve_date_range(
        reference_date=reference,
        date_from=date_from,
        date_to=date_to,
        season=season,
        quarter=quarter,
        year=year,
        date_phrase=date_phrase,
    )
    start = start or "0001-01-01"
    areas = query_records("area")
    area_ids, canonical_area = _area_ids(area, areas)
    wells = query_records("well")
    selected = [
        row for row in wells
        if (area_ids is None or row.get("area_id") in area_ids)
        and (well_type is None or str(row.get("well_type", "")).casefold() == well_type.casefold())
        and (well_id is None or str(row.get("asset_id", "")).casefold() == well_id.casefold())
    ]
    selected_ids = {str(row.get("asset_id")) for row in selected}
    area_names = {str(row.get("area_id")): str(row.get("name", "Unknown area")) for row in areas}

    evidence: list[dict[str, Any]] = []
    dataset_root = get_sample_data_root()

    if metric == "downtime_days":
        for well in selected:
            asset_id = str(well.get("asset_id"))
            result = get_well_downtime(asset_id, start=start, end=end, as_of=end)
            for reading in result.get("readings", []):
                if reading.get("downtime_days", 0):
                    evidence.append({
                        "well_id": asset_id,
                        "well_type": well.get("well_type"),
                        "area": area_names.get(str(well.get("area_id")), "Unknown area"),
                        "date": str(reading.get("inspected_at", ""))[:10],
                        "value": float(reading.get("downtime_days", 0)),
                        "citation": reading.get("citation"),
                    })

    elif metric in {"spill_volume", "late_reports"}:
        rules = load_spill_rules(dataset_root)
        for asset_id in selected_ids:
            spills = get_all_real_spills(well_id=asset_id, start_date=start, end_date=end, as_of=end)
            metadata = next(row for row in selected if str(row.get("asset_id")) == asset_id)
            if metric == "spill_volume":
                for spill in spills:
                    evidence.append({
                        "well_id": asset_id,
                        "well_type": metadata.get("well_type"),
                        "area": area_names.get(str(metadata.get("area_id")), "Unknown area"),
                        "date": spill.get("date"),
                        "value": float(spill.get("volume_bbl") or 0),
                        "citation": f"assets/{asset_id}/inspections.jsonl#{spill.get('inspection_id')}",
                    })
            else:
                inspections = query_records("inspection", asset_id=asset_id, order_by_event=True)
                contexts = query_records("context", asset_id=asset_id, order_by_event=True)
                events = query_records("regulatory_event", asset_id=asset_id, order_by_event=True)
                events_by_inspection: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for event in events:
                    if event.get("related_inspection_id"):
                        events_by_inspection[str(event["related_inspection_id"])].append(event)
                for inspection in inspections:
                    inspected = str(inspection.get("inspected_at", ""))[:10]
                    if not inspected or not (start <= inspected <= end):
                        continue
                    spill = assess_spill(inspection, contexts, rules, as_of=end)
                    if not spill or not spill.get("external_report_required"):
                        continue
                    related = events_by_inspection.get(str(inspection.get("inspection_id")), [])
                    report_event = next((event for event in related if event.get("event_type") == "spill_report_filed"), None)
                    hours = report_event.get("hours_to_report") if report_event else None
                    status = spill_report_status(hours, {**spill, "hours_to_report": hours})
                    missed = status == "missed"
                    if status == "unknown" and report_event is None and spill.get("report_deadline_hours") is not None:
                        try:
                            discovered = datetime.fromisoformat(str(inspection["inspected_at"]).replace("Z", "+00:00"))
                            if discovered.tzinfo is None:
                                discovered = discovered.replace(tzinfo=timezone.utc)
                            deadline = discovered + timedelta(hours=float(spill["report_deadline_hours"]))
                            cutoff = datetime.combine(date.fromisoformat(end), time.max, tzinfo=timezone.utc)
                            missed = deadline <= cutoff
                        except (KeyError, TypeError, ValueError):
                            missed = False
                    if missed:
                        evidence.append({
                            "well_id": asset_id,
                            "well_type": metadata.get("well_type"),
                            "area": area_names.get(str(metadata.get("area_id")), "Unknown area"),
                            "date": inspected,
                            "value": 1,
                            "citation": f"assets/{asset_id}/inspections.jsonl#{inspection.get('inspection_id')}",
                        })

    elif metric == "repair_cost":
        for well in selected:
            asset_id = str(well.get("asset_id"))
            for repair in query_records("maintenance", asset_id=asset_id, order_by_event=True):
                started = str(repair.get("started_at", ""))[:10]
                if not started or not (start <= started <= end):
                    continue
                costs = repair.get("cost_usd") or {}
                evidence.append({
                    "well_id": asset_id,
                    "well_type": well.get("well_type"),
                    "area": area_names.get(str(well.get("area_id")), "Unknown area"),
                    "date": started,
                    "value": float(costs.get("total") or 0),
                    "citation": f"assets/{asset_id}/maintenance.jsonl#{repair.get('maintenance_id')}",
                })

    elif metric == "containment_breaches":
        from backend.app.tools.repairs import find_containment_breaches

        findings = find_containment_breaches(
            area=canonical_area,
            well_type=well_type,
            well_id=well_id,
            date_from=start,
            date_to=end,
            as_of=end,
        )
        metadata_by_id = {str(row.get("asset_id")): row for row in selected}
        for finding in findings:
            metadata = metadata_by_id.get(str(finding.get("well_id")), {})
            evidence.append({
                "well_id": finding.get("well_id"),
                "well_type": metadata.get("well_type"),
                "area": area_names.get(str(metadata.get("area_id")), "Unknown area"),
                "date": finding.get("started_at"),
                "value": 1,
                "citation": finding.get("citation"),
                "details": finding,
            })

    key_for_group = {
        "well": "well_id",
        "area": "area",
        "well_type": "well_type",
        "month": "month",
    }[group_by]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        group_value = _month(row.get("date")) if group_by == "month" else row.get(key_for_group)
        grouped[str(group_value or "Unknown")].append(row)

    rows = []
    for group_value, values in grouped.items():
        rows.append({
            "group": group_value,
            "value": round(sum(float(item["value"]) for item in values), 2),
            "record_count": len(values),
            "citations": [item["citation"] for item in values if item.get("citation")],
            "records": values,
        })
    rows.sort(key=lambda row: (-row["value"], row["group"]))
    unit = {
        "downtime_days": "days",
        "spill_volume": "bbl",
        "repair_cost": "USD",
        "late_reports": "reports",
        "containment_breaches": "breaches",
    }[metric]
    return {
        "metric": metric,
        "filters": {
            "area": canonical_area,
            "well_type": well_type,
            "well_id": well_id,
            "date_from": start,
            "date_to": end,
            "season": season,
            "quarter": quarter,
        },
        "group_by": group_by,
        "unit": unit,
        "total": round(sum(float(item["value"]) for item in evidence), 2),
        "rows": rows,
        "records": evidence,
    }
