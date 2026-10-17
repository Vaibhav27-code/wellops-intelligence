import os
import json
import glob

DATA_DIR = r"d:\Hactoberfest\data\raw\flytbase-ahc-swe-asset-intelligence-dataset\test-data\dataset"
ASSETS_DIR = os.path.join(DATA_DIR, "assets")

areas_file = os.path.join(DATA_DIR, "fleet", "areas.json")
with open(areas_file, "r") as f:
    areas_data = json.load(f)["areas"]
area_names = {a["area_id"]: a["name"] for a in areas_data}

# Target areas: Northeast Block 7 and Northeast Block 8
target_areas = {"Northeast Block 7", "Northeast Block 8"}

def main():
    well_dirs = glob.glob(os.path.join(ASSETS_DIR, "WELL-*"))
    spill_records = []
    
    for w_dir in sorted(well_dirs):
        well_id = os.path.basename(w_dir)
        meta_path = os.path.join(w_dir, "metadata.json")
        area_name = "Unknown"
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
                area_id = meta.get("area_id")
                area_name = area_names.get(area_id, area_id)
                
        if area_name not in target_areas:
            continue
            
        # Check context.jsonl for data corrections to spill volumes
        ctx_path = os.path.join(w_dir, "context.jsonl")
        corrections = {}
        if os.path.exists(ctx_path):
            with open(ctx_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        n = json.loads(line)
                        if n.get("note_type") == "data_correction":
                            insp_id = n.get("inspection_id")
                            field = n.get("field")
                            if field == "spill_est_volume_bbl":
                                corrections[insp_id] = float(n.get("corrected_value"))
                                
        # Check inspections.jsonl
        insp_path = os.path.join(w_dir, "inspections.jsonl")
        if not os.path.exists(insp_path):
            continue
            
        inspections = []
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
                        
        for insp in inspections:
            insp_id = insp.get("inspection_id")
            dt = insp.get("inspected_at")
            if not dt or dt < "2026-06-01":
                continue
                
            orig_vol = insp.get("spill_est_volume_bbl")
            if orig_vol is None:
                continue
            orig_vol = float(orig_vol)
            
            # Effective volume after correction
            eff_vol = corrections.get(insp_id, orig_vol)
            if eff_vol < 5.0:
                continue
                
            # Find clean-up job triggered by this inspection
            cleanup_job = None
            for m in maintenances:
                if m.get("triggered_by_inspection_id") == insp_id:
                    cleanup_job = m
                    break
            if not cleanup_job:
                # check issue text or maintenance type
                for m in maintenances:
                    if m.get("maintenance_type") == "spill_cleanup" and (m.get("started_at") or "") >= dt:
                        cleanup_job = m
                        break
                        
            # Check report file for "Soil samples sent to the lab."
            compliant = False
            reason = ""
            cleanup_str = "None"
            
            if cleanup_job:
                m_id = cleanup_job.get("maintenance_id")
                cleanup_str = m_id
                rep_file = cleanup_job.get("report_file")
                rep_path = os.path.join(w_dir, rep_file) if rep_file else None
                if rep_path and os.path.exists(rep_path):
                    with open(rep_path, "r", encoding="utf-8") as rf:
                        rep_text = rf.read()
                    if "Soil samples sent to the lab." in rep_text:
                        compliant = True
                        reason = "Lab soil samples documented"
                    else:
                        if "soil" in rep_text.lower():
                            reason = "Field readings only, no lab samples sent"
                        else:
                            reason = "No soil sample documentation in report"
                else:
                    reason = "Report file missing"
            else:
                reason = "No clean-up job recorded"
                
            spill_records.append({
                "well_id": well_id,
                "area": area_name,
                "inspection_id": insp_id,
                "date": dt.split("T")[0],
                "volume": eff_vol,
                "cleanup_job": cleanup_str,
                "compliant": "Yes" if compliant else f"No ({reason})"
            })

    print(f"Total regulator-covered spills found: {len(spill_records)}\n")
    print(f"{'Well':<10} | {'Area':<18} | {'Inspection':<15} | {'Date':<11} | {'Vol(bbl)':<9} | {'Clean-up':<14} | {'Compliant?'}")
    print("-" * 115)
    for s in spill_records:
        print(f"{s['well_id']:<10} | {s['area']:<18} | {s['inspection_id']:<15} | {s['date']:<11} | {str(s['volume']):<9} | {s['cleanup_job']:<14} | {s['compliant']}")

if __name__ == "__main__":
    main()
