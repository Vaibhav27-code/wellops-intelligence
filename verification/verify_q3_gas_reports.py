import os
import json
import glob
from datetime import datetime, timezone

DATA_DIR = r"d:\Hactoberfest\data\raw\flytbase-ahc-swe-asset-intelligence-dataset\test-data\dataset"
ASSETS_DIR = os.path.join(DATA_DIR, "assets")

# Load metadata for well -> area mapping
areas_file = os.path.join(DATA_DIR, "fleet", "areas.json")
with open(areas_file, "r") as f:
    areas_data = json.load(f)["areas"]
area_names = {a["area_id"]: a["name"] for a in areas_data}

def parse_iso(ts_str):
    if not ts_str:
        return None
    # normalize ISO format
    ts_str = ts_str.replace("Z", "+00:00")
    return datetime.fromisoformat(ts_str)

def main():
    # 1. Find all gas reports since 2026-11-01
    gas_keywords = ["smell", "rotten-egg", "gas odor", "h2s monitor alarm", "h2s alarm", "gas smell"]
    
    gas_reports = []
    
    well_dirs = glob.glob(os.path.join(ASSETS_DIR, "WELL-*"))
    print(f"Scanning {len(well_dirs)} wells...")
    
    for w_dir in sorted(well_dirs):
        well_id = os.path.basename(w_dir)
        meta_path = os.path.join(w_dir, "metadata.json")
        area_name = "Unknown"
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
                area_id = meta.get("area_id")
                area_name = area_names.get(area_id, area_id)
        
        # Load context.jsonl
        ctx_path = os.path.join(w_dir, "context.jsonl")
        notes = []
        if os.path.exists(ctx_path):
            with open(ctx_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        notes.append(json.loads(line))
        
        # Load inspections.jsonl
        insp_path = os.path.join(w_dir, "inspections.jsonl")
        inspections = []
        if os.path.exists(insp_path):
            with open(insp_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        inspections.append(json.loads(line))
                        
        # Load maintenance.jsonl
        maint_path = os.path.join(w_dir, "maintenance.jsonl")
        maintenances = []
        if os.path.exists(maint_path):
            with open(maint_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        maintenances.append(json.loads(line))
        
        for n in notes:
            if n.get("note_type") == "operator_note":
                text = (n.get("text") or "").lower()
                created_at = n.get("created_at")
                if not created_at or created_at < "2026-11-01":
                    continue
                
                # Check for gas mentions
                if any(k in text for k in ["smelled gas", "rotten-egg", "gas odor", "h2s monitor alarm", "gas smell", "odor"]):
                    report_dt = parse_iso(created_at)
                    
                    # Find earliest qualifying response after report_dt
                    # Response: maintenance started_at OR inspection method == 'manual'
                    candidates = []
                    
                    for insp in inspections:
                        method = (insp.get("method") or "").lower()
                        if method == "manual":
                            insp_dt = parse_iso(insp.get("inspected_at"))
                            if insp_dt and insp_dt > report_dt:
                                candidates.append({
                                    "type": "inspection",
                                    "id": insp.get("inspection_id"),
                                    "dt": insp_dt,
                                    "dt_str": insp.get("inspected_at")
                                })
                                
                    for m in maintenances:
                        started_dt = parse_iso(m.get("started_at"))
                        if started_dt and started_dt > report_dt:
                            candidates.append({
                                "type": "maintenance",
                                "id": m.get("maintenance_id"),
                                "dt": started_dt,
                                "dt_str": m.get("started_at")
                            })
                            
                    candidates.sort(key=lambda x: x["dt"])
                    
                    # Deadline calculation
                    # 24 hours if before 2027-01-01, 12 hours from 2027-01-01
                    cutoff_2027 = parse_iso("2027-01-01T00:00:00Z")
                    if report_dt < cutoff_2027:
                        deadline_hours = 24.0
                    else:
                        deadline_hours = 12.0
                        
                    if candidates:
                        resp = candidates[0]
                        hours_to_resp = (resp["dt"] - report_dt).total_seconds() / 3600.0
                        met = "Met" if hours_to_resp <= deadline_hours else "Missed"
                        resp_str = f"{resp['id']} ({resp['dt_str']})"
                    else:
                        hours_to_resp = None
                        met = "Missed"
                        resp_str = "None"
                        
                    gas_reports.append({
                        "well_id": well_id,
                        "area": area_name,
                        "reported_at": created_at,
                        "note_text": n.get("text"),
                        "response": resp_str,
                        "hours": round(hours_to_resp, 1) if hours_to_resp is not None else "N/A",
                        "deadline": f"{int(deadline_hours)}h",
                        "status": met
                    })

    print(f"\nFound {len(gas_reports)} gas reports since 2026-11-01:\n")
    print(f"{'Well':<12} | {'Area':<18} | {'Reported At':<20} | {'Hours':<6} | {'Deadline':<8} | {'Status':<6} | {'Response'}")
    print("-" * 100)
    for r in gas_reports:
        print(f"{r['well_id']:<12} | {r['area']:<18} | {r['reported_at']:<20} | {str(r['hours']):<6} | {r['deadline']:<8} | {r['status']:<6} | {r['response']}")

if __name__ == "__main__":
    main()
