from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.app.calc.rules import load_production_rule
from backend.app.memory.store import (
    apply_corrections_to_inspection,
    open_memory,
    retrieve_shared_memory,
)
from backend.app.tools.db import get_db_path, get_sample_data_root, query_records


def search_wells(
    query: str | None = None,
    area_id: str | None = None,
    area_name: str | None = None,
    well_type: str | None = None,
) -> list[dict[str, Any]]:
    wells = query_records("well")
    results = []

    if area_name:
        areas = query_records("area")
        for a in areas:
            if a.get("name", "").lower() == area_name.lower():
                area_id = a.get("area_id")
                break

    for w in wells:
        if area_id and w.get("area_id") != area_id:
            continue
        if well_type and w.get("well_type") != well_type:
            continue
        if query:
            q = query.lower()
            asset_id = str(w.get("asset_id", "")).lower()
            name = str(w.get("name", "")).lower()
            if q not in asset_id and q not in name:
                continue
        results.append(w)
    return results


def get_latest_inspection(well_id: str, well: dict[str, Any] | None = None) -> dict[str, Any] | None:
    inspections = query_records("inspection", asset_id=well_id, order_by_event=True, descending=True, limit=1)
    if not inspections:
        return None
    insp = dict(inspections[0])

    if well is None:
        wells = query_records("well", record_id=well_id) or query_records("well", asset_id=well_id)
        well = wells[0] if wells else {}

    # Load active shared corrections
    mem_conn = open_memory(get_db_path())
    try:
        shared = retrieve_shared_memory(mem_conn, well_id=well_id, well_type=well.get("well_type"))
        corrections = shared.get("corrections", [])
    finally:
        mem_conn.close()

    corrected_insp = apply_corrections_to_inspection(insp, well, corrections)
    return corrected_insp


def get_well_details(well_id: str, as_of: str = "2026-10-16") -> dict[str, Any] | None:
    wells = query_records("well", record_id=well_id)
    if not wells:
        wells = query_records("well", asset_id=well_id)
    if not wells:
        return None

    well = dict(wells[0])
    well_type = well.get("well_type", "T200")
    sample_root = get_sample_data_root()
    rule = load_production_rule(well_type, sample_root)

    latest_insp = get_latest_inspection(well_id, well=well)
    well["latest_inspection"] = latest_insp

    if latest_insp:
        ambient = latest_insp.get("ambient_temp_c")
        wellhead = latest_insp.get("wellhead_temp_c")
        if isinstance(ambient, (int, float)) and isinstance(wellhead, (int, float)):
            delta = round(float(wellhead) - float(ambient), 2)
            well["temperature_delta_c"] = delta
            well["threshold_delta_c"] = rule.minimum_delta_c
            is_producing = delta >= rule.minimum_delta_c
            well["is_producing"] = is_producing
            well["production_status"] = "producing" if is_producing else "not_producing"
        else:
            well["is_producing"] = None
            well["production_status"] = "unknown"
    else:
        well["is_producing"] = None
        well["production_status"] = "unknown"

    # Context notes
    notes = query_records("context", asset_id=well_id, order_by_event=True, descending=True)
    well["notes"] = notes

    # Repairs
    repairs = query_records("maintenance", asset_id=well_id, order_by_event=True, descending=True)
    open_repairs = [r for r in repairs if not r.get("completed_at")]
    well["open_repairs"] = open_repairs
    well["repairs"] = repairs

    # Load active shared memory / notes
    mem_conn = open_memory(get_db_path())
    try:
        shared = retrieve_shared_memory(mem_conn, well_id=well_id, well_type=well_type)
        well["active_corrections"] = shared.get("corrections", [])
        well["shared_notes"] = shared.get("notes", [])
    finally:
        mem_conn.close()

    return well
