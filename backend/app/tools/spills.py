from __future__ import annotations

from datetime import date
from typing import Any

from backend.app.calc.rules import assess_spill, load_spill_rules
from backend.app.tools.db import get_reference_date, get_sample_data_root, query_records


def get_all_real_spills(
    *,
    well_id: str | None = None,
    area_id: str | None = None,
    area_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    as_of: str | None = None,
) -> list[dict[str, Any]]:
    as_of = as_of or get_reference_date()
    sample_root = get_sample_data_root()
    rules = load_spill_rules(sample_root)

    # Resolve area if needed
    if area_name and not area_id:
        areas = query_records("area")
        for a in areas:
            if a.get("name", "").lower() == area_name.lower():
                area_id = a.get("area_id")
                break

    wells = query_records("well")
    wells_by_id = {w.get("asset_id"): w for w in wells}

    # Filter wells if area_id or well_id provided
    target_wells = wells
    if well_id:
        target_wells = [w for w in wells if w.get("asset_id") == well_id]
    elif area_id:
        target_wells = [w for w in wells if w.get("area_id") == area_id]

    start_d = date.fromisoformat(start_date) if start_date else None
    end_d = date.fromisoformat(end_date) if end_date else date.fromisoformat(as_of)

    # Load active user corrections for spills
    from backend.app.memory.store import open_memory, retrieve_shared_memory
    from backend.app.tools.db import get_db_path
    mem_conn = open_memory(get_db_path())
    try:
        shared = retrieve_shared_memory(mem_conn)
        active_corrs = shared.get("corrections", [])
    finally:
        mem_conn.close()
    corr_by_target = {c.get("inspection_id"): c for c in active_corrs if c.get("inspection_id")}
    corr_by_well = {c.get("well_id"): c for c in active_corrs if c.get("well_id") and c.get("field") == "spill_volume_bbl"}

    real_spills = []

    for w in target_wells:
        wid = w.get("asset_id")
        inspections = query_records("inspection", asset_id=wid, order_by_event=True)
        contexts = query_records("context", asset_id=wid, order_by_event=True)

        for insp in inspections:
            iid = insp.get("inspection_id")
            insp_copy = dict(insp)

            # Apply volume correction if exists
            if iid in corr_by_target and corr_by_target[iid].get("field") == "spill_volume_bbl":
                c = corr_by_target[iid]
                insp_copy["spill_volume_bbl"] = float(c["corrected_value"])
                insp_copy["_corrected_by"] = c.get("author")
            elif wid in corr_by_well:
                # Well-level correction
                c = corr_by_well[wid]
                insp_copy["spill_volume_bbl"] = float(c["corrected_value"])
                insp_copy["_corrected_by"] = c.get("author")

            spill = assess_spill(insp_copy, contexts, rules, as_of=as_of)
            if not spill or not spill.get("spill_detected"):
                continue

            insp_date_str = str(insp.get("inspected_at", ""))[:10]
            if not insp_date_str:
                continue
            insp_d = date.fromisoformat(insp_date_str)
            if start_d and insp_d < start_d:
                continue
            if end_d and insp_d > end_d:
                continue

            vol = spill.get("volume_bbl", 0.0)
            well_meta = wells_by_id.get(wid, {})

            real_spills.append(
                {
                    "well_id": wid,
                    "well_name": well_meta.get("name"),
                    "area_id": well_meta.get("area_id"),
                    "inspection_id": iid,
                    "date": insp_date_str,
                    "inspected_at": insp.get("inspected_at"),
                    "volume_bbl": round(float(vol), 2) if vol is not None else 0.0,
                    "classification": spill.get("classification"),
                    "external_report_required": spill.get("external_report_required"),
                    "report_deadline_hours": spill.get("report_deadline_hours"),
                    "latitude": well_meta.get("latitude"),
                    "longitude": well_meta.get("longitude"),
                    "citations": spill.get("citations", []),
                    "corrected_by": insp_copy.get("_corrected_by"),
                }
            )

    real_spills.sort(key=lambda s: s["date"])
    return real_spills
