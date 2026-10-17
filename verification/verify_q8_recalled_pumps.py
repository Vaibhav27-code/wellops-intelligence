import os
import json
import glob

DATA_DIR = r"d:\Hactoberfest\data\raw\flytbase-ahc-swe-asset-intelligence-dataset\test-data\dataset"
ASSETS_DIR = os.path.join(DATA_DIR, "assets")

areas_file = os.path.join(DATA_DIR, "fleet", "areas.json")
with open(areas_file, "r") as f:
    areas_data = json.load(f)["areas"]
area_names = {a["area_id"]: a["name"] for a in areas_data}

RECALLED_LOTS = ["LOT-2409-A", "LOT-2409-C", "LOT-2410-B"]

def main():
    well_dirs = glob.glob(os.path.join(ASSETS_DIR, "WELL-*"))
    recalled_pumps = []
    
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
                
        # Load maintenance
        maint_path = os.path.join(w_dir, "maintenance.jsonl")
        if not os.path.exists(maint_path):
            continue
            
        maintenances = []
        with open(maint_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    maintenances.append(json.loads(line))
                    
        # Sort maintenance by started_at
        maintenances.sort(key=lambda x: x.get("started_at") or "")
        
        # Track pump installations over time
        pump_history = []
        for m in maintenances:
            rep_file = m.get("report_file")
            if not rep_file:
                continue
            rep_path = os.path.join(w_dir, rep_file)
            if not os.path.exists(rep_path):
                continue
            with open(rep_path, "r", encoding="utf-8") as rf:
                txt = rf.read()
                
            if "**Parts installed:**" in txt:
                # Extract parts installed lines
                idx = txt.find("**Parts installed:**")
                chunk = txt[idx:idx+250]
                pump_history.append({
                    "maint_id": m.get("maintenance_id"),
                    "started_at": m.get("started_at"),
                    "cost_usd": m.get("cost_usd"),
                    "chunk": chunk
                })
                
        if not pump_history:
            continue
            
        # The pump in the ground right now is the latest one installed!
        latest_install = pump_history[-1]
        chunk = latest_install["chunk"]
        
        # Check if it has a recalled lot
        matched_lot = None
        for lot in RECALLED_LOTS:
            if lot in chunk:
                matched_lot = lot
                break
                
        if matched_lot:
            recalled_pumps.append({
                "well_id": well_id,
                "area": area_name,
                "lot": matched_lot,
                "installed_job": latest_install["maint_id"],
                "installed_at": latest_install["started_at"],
                "cost_usd": latest_install["cost_usd"],
                "details": chunk.split("\n")[0]
            })

    print(f"Total recalled pumps currently in ground: {len(recalled_pumps)}\n")
    print(f"{'Well':<10} | {'Area':<18} | {'Lot':<12} | {'Job ID':<14} | {'Installed At':<12} | {'Cost ($)':<10}")
    print("-" * 85)
    for p in recalled_pumps:
        print(f"{p['well_id']:<10} | {p['area']:<18} | {p['lot']:<12} | {p['installed_job']:<14} | {p['installed_at'][:10]:<12} | {p['cost_usd']}")

if __name__ == "__main__":
    main()
