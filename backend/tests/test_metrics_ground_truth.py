from __future__ import annotations

import json
import os
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from backend.app.ingest.loader import load_dataset
from backend.app.tools.db import get_reference_date, get_sample_data_root
from backend.app.tools.metrics import query_metric


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _source_tables(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    asset_root = root / "assets"
    wells = []
    inspections = []
    contexts = []
    maintenance = []
    for metadata_path in asset_root.glob("*/metadata.json"):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        wells.append(metadata)
        asset_dir = metadata_path.parent
        inspections.extend(_jsonl(asset_dir / "inspections.jsonl"))
        contexts.extend(_jsonl(asset_dir / "context.jsonl"))
        maintenance.extend(_jsonl(asset_dir / "maintenance.jsonl"))
    return tuple(pd.DataFrame(rows) for rows in (wells, inspections, contexts, maintenance))  # type: ignore[return-value]


def _truth_totals(root: Path, reference: str) -> dict[str, float]:
    wells, inspections, contexts, maintenance = _source_tables(root)
    inspections["date"] = pd.to_datetime(inspections["inspected_at"], utc=True).dt.date.astype(str)
    inspections = inspections.loc[inspections["date"] <= reference].copy()

    # Read thresholds directly from the manuals, separately from the production calculator.
    thresholds = {}
    for well_type in wells["well_type"].dropna().unique():
        text = (root / "fleet" / "well-types" / f"{well_type}.md").read_text(encoding="utf-8")
        match = re.search(r"at least\s+\*\*(\d+(?:\.\d+)?)\s*°?\s*C\s+above\s+ambient", text, re.IGNORECASE)
        if not match:
            match = re.search(r"at least\s+\*\*(\d+(?:\.\d+)?)\s*°?\s*C\s+above\s*\n?\s*ambient", text, re.IGNORECASE)
        if not match:
            match = re.search(
                r"exceeds?\s+ambient(?:\s+temperature)?\s+by\s+a\s+minimum\s+of\s+\*\*(\d+(?:\.\d+)?)\s*°?\s*C",
                text,
                re.IGNORECASE,
            )
        assert match, f"No manual threshold parsed for {well_type}"
        thresholds[well_type] = float(match.group(1))
    joined = inspections.merge(wells[["asset_id", "well_type"]], on="asset_id", how="left")
    joined["wellhead_temp_c"] = pd.to_numeric(joined["wellhead_temp_c"], errors="coerce")
    joined["ambient_temp_c"] = pd.to_numeric(joined["ambient_temp_c"], errors="coerce")
    joined["threshold"] = joined["well_type"].map(thresholds)
    downtime_truth = float(((joined["wellhead_temp_c"] - joined["ambient_temp_c"] < joined["threshold"]) * 7).sum())

    # Apply explicit source corrections by inspection, mirroring the documented meaning
    # of correction notes without calling the application's spill assessment code.
    context_rows = contexts.to_dict("records")
    spill_truth = 0.0
    for row in joined.to_dict("records"):
        detected = bool(row.get("spill_detected"))
        event_date = str(row.get("inspected_at", ""))[:10]
        corrections = []
        for note in context_rows:
            if note.get("note_type") != "correction" or note.get("inspection_id") != row.get("inspection_id"):
                continue
            created = str(note.get("created_at", ""))[:10]
            valid_from = str(note.get("valid_from", ""))[:10]
            valid_to = str(note.get("valid_to", ""))[:10]
            note_text = str(note.get("text", "")).casefold()
            if created and created < event_date or created and created > reference:
                continue
            if valid_from and valid_from > event_date or valid_to and valid_to < event_date:
                continue
            if re.search(r"\bnot\s+(?:a\s+)?(?:crude\s+)?spill\b|\bnot crude\b|\bfalse positive\b", note_text):
                corrections.append((created, False))
            elif re.search(r"\bconfirmed\s+(?:as\s+)?(?:a\s+)?spill\b|\bactual crude spill\b", note_text):
                corrections.append((created, True))
        if corrections:
            corrections.sort(key=lambda item: item[0])
            detected = corrections[-1][1]
        if detected:
            volume = pd.to_numeric(pd.Series([row.get("spill_est_volume_bbl")]), errors="coerce").iloc[0]
            spill_truth += 0.0 if pd.isna(volume) else float(volume)

    maintenance["date"] = pd.to_datetime(maintenance["started_at"], utc=True).dt.date.astype(str)
    maintenance = maintenance.loc[maintenance["date"] <= reference]
    repair_costs = maintenance["cost_usd"].apply(
        lambda value: (value or {}).get("total", 0) if isinstance(value, dict) else 0
    )
    return {
        "downtime_days": downtime_truth,
        "spill_volume": round(spill_truth, 2),
        "repair_cost": round(float(pd.to_numeric(repair_costs, errors="coerce").fillna(0).sum()), 2),
    }


def _assert_metric_totals_match(root: Path, reference: str) -> None:
    truth = _truth_totals(root, reference)
    for metric in ("downtime_days", "spill_volume", "repair_cost"):
        result = query_metric(
            metric,  # type: ignore[arg-type]
            date_from="0001-01-01",
            date_to=reference,
            group_by="well",
            reference_date=reference,
        )
        assert result["total"] == truth[metric], metric


def test_fleet_metric_totals_match_independent_pandas_ground_truth(
    tmp_path: Path, monkeypatch
) -> None:
    source_root = get_sample_data_root()
    test_day_database = os.getenv("TEST_DAY_DATABASE")
    database = Path(test_day_database) if test_day_database else tmp_path / "ground-truth.db"
    if not test_day_database:
        load_dataset(source_root, database)
    assert database.is_file(), f"Test database does not exist: {database}"
    monkeypatch.setenv("ASSET_INTELLIGENCE_DB", str(database))
    monkeypatch.setenv("ASSET_INTELLIGENCE_DATASET", str(source_root))
    monkeypatch.delenv("REFERENCE_DATE", raising=False)
    reference = get_reference_date()
    _assert_metric_totals_match(source_root, reference)


def _mutate_dataset(source_root: Path, destination: Path) -> Path:
    shutil.copytree(source_root, destination)
    renames = {"WELL-0001": "ASSET-X201", "WELL-0002": "ASSET-X202"}
    for path in destination.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for old, new in renames.items():
            text = text.replace(old, new)
        text = re.sub(
            r"(?<!\d)20\d{2}-\d{2}-\d{2}(?!\d)",
            lambda match: (date.fromisoformat(match.group(0)) + timedelta(days=180)).isoformat(),
            text,
        )
        path.write_text(text, encoding="utf-8")

    for old, new in renames.items():
        old_path = destination / "assets" / old
        old_path.rename(destination / "assets" / new)

    # Remove several unreferenced inspections so both the row set and timeline change.
    reference_ids: set[str] = set()
    for path in destination.glob("*/**/*.jsonl"):
        if path.name == "inspections.jsonl":
            continue
        for row in _jsonl(path):
            for field in ("inspection_id", "triggered_by_inspection_id", "related_inspection_id"):
                value = row.get(field)
                if value:
                    reference_ids.add(str(value))
    removed = 0
    for path in sorted((destination / "assets").glob("*/inspections.jsonl")):
        rows = _jsonl(path)
        kept = []
        for row in rows:
            if removed < 5 and str(row.get("inspection_id")) not in reference_ids:
                removed += 1
                continue
            kept.append(row)
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in kept), encoding="utf-8")
        if removed >= 5:
            break
    assert removed == 5

    areas_path = destination / "fleet" / "areas.json"
    areas_payload = json.loads(areas_path.read_text(encoding="utf-8"))
    area = areas_payload["areas"][0]
    new_asset_id = "SIM-ASSET-NEW-1"
    area.setdefault("asset_ids", []).append(new_asset_id)
    areas_path.write_text(json.dumps(areas_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    template_path = next((destination / "assets").glob("*/metadata.json"))
    metadata = json.loads(template_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "asset_id": new_asset_id,
            "name": "New simulation well",
            "well_type": "T500",
            "area_id": area["area_id"],
            "team_id": area["team_id"],
        }
    )
    new_asset = destination / "assets" / new_asset_id
    new_asset.mkdir(parents=True)
    (new_asset / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_inspection_date = max(
        str(row["inspected_at"])[:10]
        for path in (destination / "assets").glob("*/inspections.jsonl")
        for row in _jsonl(path)
    )
    simulated_inspection = {
        "inspection_id": "SIM-INS-NEW-1",
        "asset_id": new_asset_id,
        "inspected_at": f"{latest_inspection_date}T07:00:00Z",
        "ambient_temp_c": 18,
        "wellhead_temp_c": 35,
        "spill_detected": False,
        "spill_est_volume_bbl": None,
    }
    (new_asset / "inspections.jsonl").write_text(
        json.dumps(simulated_inspection, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for filename in ("maintenance.jsonl", "regulatory-events.jsonl", "context.jsonl"):
        (new_asset / filename).write_text("", encoding="utf-8")

    (destination / "fleet" / "well-types" / "T500.md").write_text(
        "# T500 Simulation Well Manual\n\n## 1. Production threshold\n\n"
        "A T500 unit is producing when its wellhead exceeds ambient temperature by a minimum of **18°C**.\n",
        encoding="utf-8",
    )
    return destination


def test_mutated_unseen_dataset_matches_independent_ground_truth(
    tmp_path: Path, monkeypatch
) -> None:
    source_root = get_sample_data_root()
    # The mutation oracle is based on source timestamps, independent of any
    # REFERENCE_DATE override used by the calling environment.
    monkeypatch.delenv("REFERENCE_DATE", raising=False)
    source_reference = get_reference_date()
    simulated_root = _mutate_dataset(source_root, tmp_path / "unseen-sample-data")
    database = tmp_path / "unseen-asset-intelligence.db"
    load_dataset(simulated_root, database)
    monkeypatch.setenv("ASSET_INTELLIGENCE_DB", str(database))
    monkeypatch.setenv("ASSET_INTELLIGENCE_DATASET", str(simulated_root))
    monkeypatch.delenv("REFERENCE_DATE", raising=False)

    simulated_reference = get_reference_date(database)
    assert simulated_reference == (date.fromisoformat(source_reference) + timedelta(days=180)).isoformat()
    from backend.app.calc.rules import load_production_rule

    assert load_production_rule("T500", simulated_root).minimum_delta_c == 18
    _assert_metric_totals_match(simulated_root, simulated_reference)
