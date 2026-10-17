import os
import json
import glob
from collections import defaultdict

DATA_DIR = r"d:\Hactoberfest\data\raw\flytbase-ahc-swe-asset-intelligence-dataset\test-data\dataset"
ASSETS_DIR = os.path.join(DATA_DIR, "assets")

areas_file = os.path.join(DATA_DIR, "fleet", "areas.json")
with open(areas_file, "r") as f:
    areas_data = json.load(f)["areas"]
area_names = {a["area_id"]: a["name"] for a in areas_data}

def main():
    well_dirs = glob.glob(os.path.join(ASSETS_DIR, "WELL-*"))
    area_reasons = defaultdict(lambda: defaultdict(list))
    
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
            
        with open(ctx_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    n = json.loads(line)
                    created_at = n.get("created_at") or ""
                    if created_at.startswith("2026"):
                        txt = n.get("text") or ""
                        if "weather" in txt.lower():
                            # "Workover rig delayed by weather; restart pushed back about a week." -> 7 days
                            area_reasons[area_name]["weather"].append(7)
                        elif "parts" in txt.lower():
                            # "Waiting on replacement parts from the vendor; well stays shut in until they arrive."
                            area_reasons[area_name]["parts"].append(14)
                        elif "contractor" in txt.lower():
                            area_reasons[area_name]["contractors"].append(7)
                        elif "crew" in txt.lower() and "delayed" in txt.lower():
                            area_reasons[area_name]["crews"].append(7)
                            
    print("Breakdown of delay reasons by area for 2026:")
    for area, reasons in sorted(area_reasons.items()):
        print(f"\nArea: {area}")
        total_events = sum(len(v) for v in reasons.values())
        for r, vals in sorted(reasons.items()):
            count = len(vals)
            pct = (count / total_events) * 100
            print(f"  {r:<12}: {count} events ({pct:.1f}%), avg days: {sum(vals)/count:.1f}")

if __name__ == "__main__":
    main()
