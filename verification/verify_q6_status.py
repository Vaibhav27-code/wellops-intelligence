import os
import json
import glob
from datetime import datetime

DATA_DIR = r"d:\Hactoberfest\data\raw\flytbase-ahc-swe-asset-intelligence-dataset\test-data\dataset"
ASSETS_DIR = os.path.join(DATA_DIR, "assets")

areas_file = os.path.join(DATA_DIR, "fleet", "areas.json")
with open(areas_file, "r") as f:
    areas_data = json.load(f)["areas"]
area_names = {a["area_id"]: a["name"] for a in areas_data}

THRESHOLDS = {
    "T200": 15.0,
    "T350": 20.0,
    "T500": 25.0
}

def parse_iso(ts_str):
    if not ts_str:
        return None
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

def get_well_type(meta, date_str):
    # Check type_history
    history = meta.get("type_history")
    if history:
        for entry in history:
            f = entry.get("from")
            t = entry.get("to")
            if f and f <= date_str:
                if not t or t >= date_str:
                    return entry.get("well_type")
    return meta.get("well_type", "T200")

def main():
    well_dirs = glob.glob(os.path.join(ASSETS_DIR, "WELL-*"))
    disagreements = []
    
    for w_dir in sorted(well_dirs):
        well_id = os.path.basename(w_dir)
        meta_path = os.path.join(w_dir, "metadata.json")
        area_name = "Unknown"
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
                area_id = meta.get("area_id")
                area_name = area_names.get(area_id, area_id)
                
        # Load inspections
        insp_path = os.path.join(w_dir, "inspections.jsonl")
        inspections = []
        if os.path.exists(insp_path):
            with open(insp_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        inspections.append(json.loads(line))
                        
        if not inspections:
            continue
            
        # Check context for data corrections
        ctx_path = os.path.join(w_dir, "context.jsonl")
        notes = []
        corrections = {}
        if os.path.exists(ctx_path):
            with open(ctx_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        n = json.loads(line)
                        notes.append(n)
                        if n.get("note_type") == "data_correction":
                            insp_id = n.get("inspection_id")
                            fld = n.get("field")
                            corrections[(insp_id, fld)] = n.get("corrected_value")
                            
        # Sort inspections by inspected_at
        inspections.sort(key=lambda x: x.get("inspected_at") or "")
        latest_insp = inspections[-1]
        insp_id = latest_insp.get("inspection_id")
        insp_dt_str = latest_insp.get("inspected_at")
        insp_dt = parse_iso(insp_dt_str)
        
        # Determine inspection producing status
        w_type = get_well_type(meta, insp_dt_str[:10])
        thresh = THRESHOLDS.get(w_type, 15.0)
        
        amb = latest_insp.get("ambient_temp_c")
        if (insp_id, "ambient_temp_c") in corrections:
            amb = float(corrections[(insp_id, "ambient_temp_c")])
            
        wh = latest_insp.get("wellhead_temp_c")
        if (insp_id, "wellhead_temp_c") in corrections:
            wh = float(corrections[(insp_id, "wellhead_temp_c")])
            
        delta = (wh - amb) if (wh is not None and amb is not None) else 0.0
        insp_producing = delta >= thresh
        insp_show_str = f"Producing (dT={delta:.1f}°C >= {thresh}°C)" if insp_producing else f"Not producing (dT={delta:.1f}°C < {thresh}°C)"
        
        # Check operator notes about shut-in or restart
        status_notes = []
        for n in notes:
            if n.get("note_type") == "operator_note":
                txt = (n.get("text") or "").lower()
                # Check for shut-in or restart
                is_shut_in = any(k in txt for k in ["shut in", "shut-in", "secured well", "closed wing valve", "stopped prime mover"])
                is_restart = any(k in txt for k in ["restarted", "started well", "resumed production", "placed back online", "back on line", "brought online"])
                if is_shut_in or is_restart:
                    status_notes.append({
                        "note": n,
                        "is_shut_in": is_shut_in,
                        "is_restart": is_restart,
                        "dt": parse_iso(n.get("created_at")),
                        "dt_str": n.get("created_at"),
                        "text": n.get("text")
                    })
                    
        if not status_notes:
            continue
            
        status_notes.sort(key=lambda x: x["dt"])
        latest_note = status_notes[-1]
        note_dt = latest_note["dt"]
        
        # OPS-3: "A well's current status comes from the most recent of these two:
        # its latest inspection reading ... or its latest operator note saying the well was shut in or restarted.
        # If a shut-in note is more recent than the latest inspection, the well is not producing (shut in),
        # even if that inspection reads as producing.
        # If a restart note is more recent than the latest inspection, the well is producing (unconfirmed)..."
        
        # Does the latest inspection and the operator note disagree?
        # Scenario 1: Note is more recent than inspection:
        # - Note says shut-in, but inspection said producing -> Disagree!
        # - Note says restarted, but inspection said not producing -> Disagree!
        # Scenario 2: Inspection is more recent than note, but note said opposite:
        # - Note said shut-in, inspection says producing -> inspection governs, but do they disagree about whether well is producing?
        # Q6 wording: "for which wells do the latest inspection and the operator notes disagree about whether the well is producing oil? For each one, what is its real status right now, and why?"
        
        disagree = False
        status_now = ""
        reason = ""
        
        note_says_producing = latest_note["is_restart"]
        
        # Only consider recent operator notes (test dataset operator notes)
        if note_dt > insp_dt:
            if latest_note["is_shut_in"] and insp_producing:
                disagree = True
                status_now = "Not producing (shut in)"
                reason = "Operator shut-in note is more recent than latest inspection"
            elif latest_note["is_restart"] and not insp_producing:
                disagree = True
                status_now = "Producing (unconfirmed)"
                reason = "Operator restart note is more recent than latest inspection"
        else:
            # Inspection is more recent, but note was written recently (e.g. within 30 days) and disagreed
            # Actually, if inspection is after the note, the inspection confirms/updates the status.
            pass
                
        if disagree:
            disagreements.append({
                "well_id": well_id,
                "area": area_name,
                "insp_id": insp_id,
                "insp_date": insp_dt_str,
                "insp_shows": insp_show_str,
                "insp_producing": insp_producing,
                "note_date": latest_note["dt_str"],
                "note_text": latest_note["text"],
                "note_action": "Shut in" if latest_note["is_shut_in"] else "Restart",
                "more_recent": "Note" if note_dt > insp_dt else "Inspection",
                "status_now": status_now,
                "reason": reason
            })

    print(f"Total disagreement wells found: {len(disagreements)}\n")
    for d in disagreements:
        print(f"Well: {d['well_id']} | Area: {d['area']}")
        print(f"  Inspection: {d['insp_id']} ({d['insp_date']}) -> {d['insp_shows']}")
        print(f"  Note ({d['note_date']}): \"{d['note_text']}\"")
        print(f"  More recent: {d['more_recent']} -> Real status now: {d['status_now']} ({d['reason']})")
        print("-" * 80)

if __name__ == "__main__":
    main()
