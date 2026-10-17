from __future__ import annotations

from typing import Any

from backend.app.calc.downtime import calculate_downtime
from backend.app.memory.store import apply_corrections_to_inspection, open_memory, retrieve_shared_memory
from backend.app.tools.db import get_db_path, get_reference_date, get_sample_data_root, query_records
from backend.app.tools.time_ranges import resolve_date_range


def _parse_relative_period(period_desc: str, as_of: str | None = None) -> tuple[str | None, str]:
    reference_date = as_of or get_reference_date()
    return resolve_date_range(reference_date=reference_date, date_phrase=period_desc)


def get_well_downtime(
    well_id: str,
    *,
    start: str | None = None,
    end: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    as_of = as_of or get_reference_date()
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
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    reference_date = end or get_reference_date()
    if start is None:
        start, _ = resolve_date_range(reference_date=reference_date, date_phrase="last 4 months")
    end = reference_date
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
