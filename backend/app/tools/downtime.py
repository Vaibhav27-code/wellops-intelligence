from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.app.calc.downtime import calculate_downtime
from backend.app.memory.store import apply_corrections_to_inspection, open_memory, retrieve_shared_memory
from backend.app.tools.db import get_db_path, get_sample_data_root, query_records


def _parse_relative_period(period_desc: str, as_of: str = "2026-10-16") -> tuple[str, str]:
    as_of_date = date.fromisoformat(as_of)
    desc = period_desc.lower()
    if "last 4 months" in desc or "past 4 months" in desc or "4 months" in desc:
        # 16 Jun 2026 to 16 Oct 2026
        return "2026-06-16", as_of
    if "last 13 weeks" in desc or "past 13 weeks" in desc or "13 weeks" in desc:
        return "2026-07-23", as_of
    if "last 12 months" in desc or "past 12 months" in desc or "12 months" in desc or "last year" in desc:
        return "2025-10-16", as_of
    if "last 90 days" in desc or "past 90 days" in desc or "90 days" in desc:
        start = (as_of_date - timedelta(days=90)).isoformat()
        return start, as_of
    if "2025" in desc:
        return "2025-01-01", "2025-12-31"
    if "2026" in desc:
        return "2026-01-01", as_of
    return "2026-01-01", as_of


def get_well_downtime(
    well_id: str,
    *,
    start: str | None = None,
    end: str | None = None,
    as_of: str = "2026-10-16",
) -> dict[str, Any]:
    wells = query_records("well", record_id=well_id)
    if not wells:
        wells = query_records("well", asset_id=well_id)
    if not wells:
        raise ValueError(f"Well not found: {well_id}")

    well = wells[0]
    well_type = well.get("well_type", "T200")
    inspections = query_records("inspection", asset_id=well_id, order_by_event=True)
    contexts = query_records("context", asset_id=well_id, order_by_event=True)

    # Apply any active corrections
    mem_conn = open_memory(get_db_path())
    try:
        shared = retrieve_shared_memory(mem_conn, well_id=well_id, well_type=well_type)
        corrections = shared.get("corrections", [])
    finally:
        mem_conn.close()

    corrected_inspections = [
        apply_corrections_to_inspection(insp, well, corrections)
        for insp in inspections
    ]

    sample_root = get_sample_data_root()
    result = calculate_downtime(
        corrected_inspections,
        well_type,
        sample_root,
        contexts=contexts,
        start=start,
        end=end,
        as_of=as_of,
    )
    result["well_id"] = well_id
    result["well_name"] = well.get("name")
    return result


def get_top_downtime_wells_in_area(
    area_name: str,
    top_n: int = 3,
    start: str = "2026-06-16",
    end: str = "2026-10-16",
) -> list[dict[str, Any]]:
    areas = query_records("area")
    target_area = None
    for a in areas:
        if a.get("name", "").lower() == area_name.lower():
            target_area = a
            break
    if not target_area:
        return []

    area_id = target_area.get("area_id")
    wells = query_records("well")
    area_wells = [w for w in wells if w.get("area_id") == area_id]

    ranked = []
    for w in area_wells:
        wid = w.get("asset_id")
        dt_res = get_well_downtime(wid, start=start, end=end, as_of=end)
        ranked.append(
            {
                "well_id": wid,
                "well_name": w.get("name"),
                "well_type": w.get("well_type"),
                "downtime_days": dt_res["downtime_days"],
                "unplanned_downtime_days": dt_res["unplanned_downtime_days"],
                "maximum_consecutive_downtime_days": dt_res["maximum_consecutive_downtime_days"],
                "citation": dt_res["rule_citation"],
            }
        )

    # Sort descending by downtime_days
    ranked.sort(key=lambda x: x["downtime_days"], reverse=True)
    return ranked[:top_n]
