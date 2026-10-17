"""
Independent verification of Q1 (Reservoir pressure) and Q2 (Best producer in 2026).
Checks whether any production-volume or pressure fields exist in the raw dataset.
Reads raw files directly without importing backend code or touching SQLite DB.
"""
import json
from pathlib import Path

DATASET_ROOT = Path("data/raw/flytbase-ahc-swe-asset-intelligence-dataset/test-data/dataset")

def inspect_fields():
    metadata_fields = set()
    inspection_fields = set()
    context_fields = set()
    maintenance_fields = set()
    regulatory_fields = set()

    # Sample across all 600 wells
    for well_dir in (DATASET_ROOT / "assets").glob("WELL-*"):
        # metadata.json
        meta_file = well_dir / "metadata.json"
        if meta_file.exists():
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            metadata_fields.update(data.keys())

        # inspections.jsonl
        insp_file = well_dir / "inspections.jsonl"
        if insp_file.exists():
            for line in insp_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    inspection_fields.update(json.loads(line).keys())

        # context.jsonl
        ctx_file = well_dir / "context.jsonl"
        if ctx_file.exists():
            for line in ctx_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    context_fields.update(json.loads(line).keys())

        # maintenance.jsonl
        mnt_file = well_dir / "maintenance.jsonl"
        if mnt_file.exists():
            for line in mnt_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    maintenance_fields.update(json.loads(line).keys())

        # regulatory-events.jsonl
        reg_file = well_dir / "regulatory-events.jsonl"
        if reg_file.exists():
            for line in reg_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    regulatory_fields.update(json.loads(line).keys())

    print("=== METADATA FIELDS ===")
    print(sorted(metadata_fields))

    print("\n=== INSPECTION FIELDS ===")
    print(sorted(inspection_fields))

    print("\n=== CONTEXT FIELDS ===")
    print(sorted(context_fields))

    print("\n=== MAINTENANCE FIELDS ===")
    print(sorted(maintenance_fields))

    print("\n=== REGULATORY FIELDS ===")
    print(sorted(regulatory_fields))

    # Check for pressure fields
    all_fields = metadata_fields | inspection_fields | context_fields | maintenance_fields | regulatory_fields
    pressure_fields = [f for f in all_fields if "pressure" in f.lower() or "psi" in f.lower() or "bar" in f.lower()]
    production_fields = [f for f in all_fields if "prod" in f.lower() or "volume" in f.lower() or "bbl" in f.lower() or "rate" in f.lower() or "oil" in f.lower()]

    print("\n=== PRESSURE FIELDS FOUND ===")
    print(pressure_fields)

    print("\n=== PRODUCTION / VOLUME FIELDS FOUND ===")
    print(production_fields)

if __name__ == "__main__":
    inspect_fields()
