from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from backend.app.memory.store import open_memory, rca_threshold_override, retrieve_shared_memory
from backend.app.calc.compliance import load_compliance_rules
from backend.app.calc.rules import load_rca_rule
from backend.app.tools.db import get_connection, get_db_path, get_reference_date, get_sample_data_root, query_records
from backend.app.tools.time_ranges import _subtract_months


def get_well_repairs_cost(well_id: str, year: int | None = None) -> dict[str, Any]:
    year = year or int(get_reference_date()[:4])
    repairs = query_records("maintenance", asset_id=well_id)
    year_str = str(year)
    matching = [
        m for m in repairs
        if str(m.get("started_at", ""))[:4] == year_str
    ]
    total_cost = sum(m.get("cost_usd", {}).get("total", 0) for m in matching)
    labor_cost = sum(m.get("cost_usd", {}).get("labor", 0) for m in matching)
    parts_cost = sum(m.get("cost_usd", {}).get("parts", 0) for m in matching)

    return {
        "well_id": well_id,
        "year": year,
        "repair_count": len(matching),
        "total_cost_usd": total_cost,
        "labor_cost_usd": labor_cost,
        "parts_cost_usd": parts_cost,
        "repairs": matching,
    }


def find_maintenance_patterns(
    *,
    area: str | None = None,
    well_type: str | None = None,
    well_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    equipment_kind: str = "pump_jack",
    maintenance_type: str = "corrective",
    as_of: str | None = None,
) -> list[dict[str, Any]]:
    as_of = as_of or get_reference_date()
    date_to = date_to or as_of
    areas = query_records("area")
    target_area = next((a for a in areas if area and area.casefold() in {str(a.get("name", "")).casefold(), str(a.get("area_id", "")).casefold()}), None)
    if area and not target_area:
        return []
    area_id = target_area.get("area_id") if target_area else None
    wells = query_records("well")
    area_wells = [
        w for w in wells
        if (area_id is None or w.get("area_id") == area_id)
        and (well_type is None or str(w.get("well_type", "")).casefold() == well_type.casefold())
        and (well_id is None or str(w.get("asset_id", "")).casefold() == well_id.casefold())
    ]

    as_of_date = date.fromisoformat(as_of)

    # Load active shared memory / corrections
    mem_conn = open_memory(get_db_path())
    try:
        shared = retrieve_shared_memory(mem_conn)
        corrections = shared.get("corrections", [])
    finally:
        mem_conn.close()

    qualifying_wells = []
    for w in area_wells:
        wid = w.get("asset_id")
        wtype = w.get("well_type", "T200")
        rule = load_rca_rule(str(wtype), get_sample_data_root())
        window_start = date_from or _subtract_months(as_of_date, rule.window_months).isoformat()

        # Check for threshold override
        override = rca_threshold_override(w, equipment_kind, corrections)
        if override:
            threshold = int(float(override.get("corrected_value", 3)))
            is_custom = True
            rule_desc = f"{override.get('author')}'s rule: {override.get('reason')}"
        else:
            threshold = rule.minimum_corrective_events
            is_custom = False
            rule_desc = f"Manual threshold: {rule.minimum_corrective_events} corrective events in {rule.window_months} months"

        repairs = query_records("maintenance", asset_id=wid)
        corrective_pj_repairs = [
            m for m in repairs
            if m.get("equipment_kind") == equipment_kind
            and m.get("maintenance_type") == maintenance_type
            and window_start <= str(m.get("started_at", ""))[:10] <= date_to
        ]

        if len(corrective_pj_repairs) >= threshold:
            qualifying_wells.append(
                {
                    "well_id": wid,
                    "well_name": w.get("name"),
                    "well_type": wtype,
                    "repair_count": len(corrective_pj_repairs),
                    "threshold_applied": threshold,
                    "is_custom_rule": is_custom,
                    "rule_description": rule_desc,
                    "repairs": corrective_pj_repairs,
                    "citations": [
                        f"assets/{wid}/maintenance.jsonl#{m.get('maintenance_id')}"
                        for m in corrective_pj_repairs
                    ],
                }
            )

    qualifying_wells.sort(key=lambda x: x["well_id"])
    return qualifying_wells


def find_containment_breaches(
    *,
    area: str | None = None,
    well_type: str | None = None,
    well_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    as_of: str | None = None,
    sop_limit_hours: float | None = None,
) -> list[dict[str, Any]]:
    as_of = as_of or get_reference_date()
    date_to = date_to or as_of
    if sop_limit_hours is None:
        sop_limit_hours = float(load_compliance_rules(str(get_sample_data_root())).spill_containment_hours)
    areas = query_records("area")
    target_area = next((a for a in areas if area and area.casefold() in {str(a.get("name", "")).casefold(), str(a.get("area_id", "")).casefold()}), None)
    if area and not target_area:
        return []
    area_id = target_area.get("area_id") if target_area else None
    wells = query_records("well")
    area_wells = {
        w.get("asset_id"): w for w in wells
        if area_id is None or w.get("area_id") == area_id
        if well_type is None or str(w.get("well_type", "")).casefold() == well_type.casefold()
        if well_id is None or str(w.get("asset_id", "")).casefold() == well_id.casefold()
    }

    cutoff_date = date_from or (date.fromisoformat(date_to) - timedelta(days=90)).isoformat()

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT d.asset_id, d.source_path, d.content
            FROM documents d
            WHERE d.document_type = 'maintenance_report'
            """
        ).fetchall()
    finally:
        conn.close()

    breaches = []
    containment_pattern = re.compile(
        r"\bcontained\s+(?:(?:about|approximately)\s+)?(\d+(?:\.\d+)?)\s+hours? after (?:the )?inspection(?:\s+flight)?\b",
        re.IGNORECASE,
    )

    for r in rows:
        wid = r["asset_id"]
        if wid not in area_wells:
            continue
        content = r["content"]
        match = containment_pattern.search(content)
        if not match:
            continue
        hours = float(match.group(1))
        if hours > sop_limit_hours:
            source_path = r["source_path"]
            filename = source_path.split("/")[-1]
            repairs = query_records("maintenance", asset_id=wid)
            rel_m = next((m for m in repairs if m.get("report_file") and filename in m.get("report_file")), None)
            if not rel_m:
                continue
            started_at = str(rel_m.get("started_at", ""))[:10]
            if not (cutoff_date <= started_at <= date_to):
                continue

            iid = rel_m.get("triggered_by_inspection_id")
            well_meta = area_wells[wid]
            breaches.append(
                {
                    "well_id": wid,
                    "well_name": well_meta.get("name"),
                    "area_id": area_id,
                    "containment_hours": hours,
                    "sop_limit_hours": sop_limit_hours,
                    "maintenance_id": rel_m.get("maintenance_id"),
                    "inspection_id": iid,
                    "report_file": rel_m.get("report_file"),
                    "started_at": started_at,
                    "citation": f"assets/{wid}/{rel_m.get('report_file')}#{rel_m.get('maintenance_id')}",
                }
            )

    breaches.sort(key=lambda b: b["well_id"])
    return breaches
