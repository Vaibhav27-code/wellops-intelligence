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

# Approvals:
# MOC-2026-031 extended by MOC-2026-044 -> expires 2027-02-28
moc_31_44 = {"WELL-0013", "WELL-0062", "WELL-0118", "WELL-0248", "WELL-0476"}
# MOC-2026-036 -> expires 2026-12-15
moc_36 = {"WELL-0087", "WELL-0158", "WELL-0249", "WELL-0284", "WELL-0356", "WELL-0388", "WELL-0461"}

TODAY = "2027-01-15"

def main():
    well_dirs = glob.glob(os.path.join(ASSETS_DIR, "WELL-*"))
    bypasses = []
    
    for w_dir in sorted(well_dirs):
        well_id = os.path.basename(w_dir)
        meta_path = os.path.join(w_dir, "metadata.json")
        area_name = "Unknown"
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
                area_id = meta.get("area_id")
                area_name = area_names.get(area_id, area_id)
                
        ctx_path = os.path.join(w_dir, "context.jsonl")
        if not os.path.exists(ctx_path):
            continue
            
        notes = []
        with open(ctx_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    notes.append(json.loads(line))
                    
        # Sort notes by created_at
        notes.sort(key=lambda x: x.get("created_at") or "")
        
        # Look for bypass installation and removal notes
        # Keywords: "bypass installed", "temporary bypass installed", "bypass in place", "installed temporary flowline bypass",
        # "bypass removed", "removed bypass", "flowline bypass removed"
        in_events = []
        out_events = []
        
        for n in notes:
            text = (n.get("text") or "").lower()
            dt = n.get("created_at")
            if "bypass" in text:
                if any(k in text for k in ["installed", "routed through temporary bypass", "placed bypass", "hooked up bypass", "bypass in place", "bypass line installed"]):
                    in_events.append(n)
                elif any(k in text for k in ["removed", "disconnected", "taken out", "bypass out"]):
                    out_events.append(n)
                    
        if in_events:
            for in_e in in_events:
                in_dt = in_e.get("created_at")
                in_date = in_dt.split("T")[0]
                
                # find matching out event after in_dt
                matching_out = [o for o in out_events if o.get("created_at") > in_dt]
                if matching_out:
                    out_dt = matching_out[0].get("created_at")
                    out_date = out_dt.split("T")[0]
                    still_in = False
                else:
                    out_date = "still in"
                    still_in = True
                    
                # Determine approval
                if well_id in moc_31_44:
                    approval = "MOC-2026-031 / MOC-2026-044"
                    valid_until = "2027-02-28"
                elif well_id in moc_36:
                    approval = "MOC-2026-036"
                    valid_until = "2026-12-15"
                else:
                    approval = "None"
                    valid_until = "None"
                    
                # Determine status
                if approval == "None":
                    status = "Not approved"
                else:
                    # check if expired
                    end_cmp = TODAY if still_in else out_date
                    if end_cmp > valid_until:
                        status = "Expired"
                    else:
                        status = "Allowed"
                        
                bypasses.append({
                    "well_id": well_id,
                    "area": area_name,
                    "in_date": in_date,
                    "out_date": out_date,
                    "still_in": still_in,
                    "approval": approval,
                    "valid_until": valid_until,
                    "status": status,
                    "in_text": in_e.get("text"),
                    "out_text": matching_out[0].get("text") if matching_out else None
                })

    print(f"Total bypass events found: {len(bypasses)}\n")
    print(f"{'Well':<10} | {'Area':<18} | {'Bypass In':<11} | {'Bypass Out':<11} | {'Approval':<28} | {'Valid Until':<12} | {'Status'}")
    print("-" * 110)
    for b in bypasses:
        print(f"{b['well_id']:<10} | {b['area']:<18} | {b['in_date']:<11} | {b['out_date']:<11} | {b['approval']:<28} | {b['valid_until']:<12} | {b['status']}")

if __name__ == "__main__":
    main()
