from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.app.calc.downtime import calculate_downtime
from backend.app.calc.compliance import assess_spill_compliance, load_compliance_rules
from backend.app.calc.rules import assess_spill, classify_spill, load_production_rule, load_spill_rules, spill_report_status
from backend.app.ingest.loader import DatasetValidationError, load_dataset, table_counts
from backend.app.tools.data_tools import get_well_details, search_human_notes, search_wells


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


@pytest.fixture
def sample_data(tmp_path: Path) -> Path:
    root = tmp_path / "sample-data"
    _write_json(root / "fleet" / "areas.json", {
        "areas": [{"area_id": "AREA-1", "name": "Area One", "team_id": "TEAM-1", "center": {"lat": 1, "lon": 2}, "asset_ids": ["WELL-0001"]}],
        "teams": [{"team_id": "TEAM-1", "name": "Team One", "lead_user_id": "U-1"}],
    })
    _write_json(root / "fleet" / "users.json", {"users": [{"user_id": "U-1", "name": "A User", "role": "field_operator", "team_id": "TEAM-1"}]})
    manuals = root / "fleet" / "well-types"
    manuals.mkdir(parents=True, exist_ok=True)
    (manuals / "T200.md").write_text("Producing when at least **15 °C above ambient** air temperature.\n", encoding="utf-8")
    (manuals / "T350.md").write_text("Producing when at least **20 °C above ambient** air temperature.\n", encoding="utf-8")
    sop = root / "fleet" / "sops" / "spill-response-sop.md"
    sop.parent.mkdir(parents=True, exist_ok=True)
    sop.write_text(
        "| Class | Estimated crude volume | Notes |\n"
        "| Minor | below 1 bbl | record |\n"
        "| Moderate | 1 bbl to below 5 bbl | HSE |\n"
        "| Reportable | 5 bbl to below 25 bbl | report |\n"
        "| Major | 25 bbl or more | command |\n\n"
        "The classes and the 4-hour containment limit (SR-02) are company rules.\n"
        "Remediation must be verified within **60 days** of discovery.\n"
        "File the written notice within **24 hours** of discovery, or within **2 hours** for a major spill.\n",
        encoding="utf-8",
    )
    (sop.parent / "regulatory-compliance-sop.md").write_text(
        "Every well must be inspected at least once every **14 days**.\n"
        "Any well down for more than **14 consecutive days** must be reported.\n"
        "Agency notices of violation must be answered within **30 days**.\n"
        "Every flowline must pass an integrity test once per calendar year.\n",
        encoding="utf-8",
    )
    (sop.parent / "field-work-sop.md").write_text(
        "Write the maintenance report within 3 days of finishing the work.\n", encoding="utf-8"
    )
    assets = root / "assets" / "WELL-0001"
    _write_json(assets / "metadata.json", {
        "asset_id": "WELL-0001", "name": "Well One", "well_type": "T200", "area_id": "AREA-1",
        "team_id": "TEAM-1", "in_charge_user_id": "U-1",
    })
    inspections = [
        {"inspection_id": "INS-1", "asset_id": "WELL-0001", "inspected_at": "2026-01-01T07:00:00Z", "ambient_temp_c": 10, "wellhead_temp_c": 20, "spill_detected": True, "spill_est_volume_bbl": 5},
        {"inspection_id": "INS-2", "asset_id": "WELL-0001", "inspected_at": "2026-01-08T07:00:00Z", "ambient_temp_c": 10, "wellhead_temp_c": 20, "spill_detected": False, "spill_est_volume_bbl": None},
        {"inspection_id": "INS-3", "asset_id": "WELL-0001", "inspected_at": "2026-01-29T07:00:00Z", "ambient_temp_c": 10, "wellhead_temp_c": 20, "spill_detected": False, "spill_est_volume_bbl": None},
        {"inspection_id": "INS-4", "asset_id": "WELL-0001", "inspected_at": "2026-02-05T07:00:00Z", "ambient_temp_c": 10, "wellhead_temp_c": 25, "spill_detected": False, "spill_est_volume_bbl": None},
    ]
    _write_jsonl(assets / "inspections.jsonl", inspections)
    report_path = assets / "maintenance-reports" / "report-1.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# Repair report\nChecked the well.\n", encoding="utf-8")
    _write_jsonl(assets / "maintenance.jsonl", [{
        "maintenance_id": "MNT-1", "asset_id": "WELL-0001", "started_at": "2026-01-09T08:00:00Z",
        "maintenance_type": "corrective", "technician_user_id": "U-1", "triggered_by_inspection_id": "INS-2",
        "report_file": "assets/WELL-0001/maintenance-reports/report-1.md",
    }])
    _write_jsonl(assets / "regulatory-events.jsonl", [])
    _write_jsonl(assets / "context.jsonl", [
        {"note_id": "CTX-1", "asset_id": "WELL-0001", "created_at": "2026-01-02T07:00:00Z", "author_user_id": "U-1", "note_type": "correction", "inspection_id": "INS-1", "text": "Inspection INS-1: the dark patch is rainwater mixed with soil, not crude. Not a spill.", "valid_from": "2026-01-01", "valid_to": None},
        {"note_id": "CTX-2", "asset_id": "WELL-0001", "created_at": "2025-12-31T07:00:00Z", "author_user_id": "U-1", "note_type": "operator_note", "text": "planned shut-in for scheduled pump work", "valid_from": "2026-01-01", "valid_to": "2026-01-08"},
    ])
    return root


def test_loader_is_idempotent_and_indexes_documents(sample_data: Path, tmp_path: Path) -> None:
    db = tmp_path / "asset.db"
    first = load_dataset(sample_data, db)
    first_counts = table_counts(db)
    second = load_dataset(sample_data.parent, db)
    assert first.to_dict()["error_count"] == second.to_dict()["error_count"] == 0
    assert first_counts == table_counts(db)
    assert first_counts["inspection"] == 4
    assert first_counts["document"] == 8
    with sqlite3.connect(db) as connection:
        result = connection.execute(
            "SELECT source_path FROM documents_fts WHERE documents_fts MATCH ?", ("repair",)
        ).fetchall()
    assert result == [("assets/WELL-0001/maintenance-reports/report-1.md",)]
    assert search_human_notes("planned pump", database_path=db)[0]["source_path"].endswith("#CTX-2")
    assert search_wells("Well One", database_path=db)[0]["asset_id"] == "WELL-0001"
    well = get_well_details("WELL-0001", dataset_root=sample_data, database_path=db, as_of="2026-02-05")
    assert well["derived_status"]["status"] == "producing"


def test_failed_validation_does_not_replace_previous_database(sample_data: Path, tmp_path: Path) -> None:
    db = tmp_path / "asset.db"
    load_dataset(sample_data, db)
    original_counts = table_counts(db)
    with (sample_data / "assets" / "WELL-0001" / "inspections.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{broken json\n")
    with pytest.raises(DatasetValidationError):
        load_dataset(sample_data, db)
    assert table_counts(db) == original_counts


def test_manual_thresholds_are_read_from_source(sample_data: Path) -> None:
    assert load_production_rule("T200", sample_data).minimum_delta_c == 15
    assert load_production_rule("T350", sample_data).minimum_delta_c == 20


def test_compliance_deadlines_are_read_from_sops(sample_data: Path) -> None:
    rules = load_compliance_rules(str(sample_data))
    assert rules.inspection_interval_days == 14
    assert rules.spill_containment_hours == 4
    assert rules.spill_verification_days == 60
    assert rules.maintenance_report_days == 3


def test_downtime_counts_inspections_and_excludes_planned_time(sample_data: Path) -> None:
    inspections = [
        {"inspection_id": "INS-1", "asset_id": "WELL-0001", "inspected_at": "2026-01-01T07:00:00Z", "ambient_temp_c": 10, "wellhead_temp_c": 20},
        {"inspection_id": "INS-2", "asset_id": "WELL-0001", "inspected_at": "2026-01-08T07:00:00Z", "ambient_temp_c": 10, "wellhead_temp_c": 20},
        {"inspection_id": "INS-3", "asset_id": "WELL-0001", "inspected_at": "2026-01-22T07:00:00Z", "ambient_temp_c": 10, "wellhead_temp_c": 20},
        {"inspection_id": "INS-4", "asset_id": "WELL-0001", "inspected_at": "2026-01-29T07:00:00Z", "ambient_temp_c": 10, "wellhead_temp_c": 25},
    ]
    contexts = [{
        "note_type": "operator_note", "text": "planned shut-in for scheduled pump work",
        "valid_from": "2026-01-01", "valid_to": "2026-01-08",
    }]
    result = calculate_downtime(inspections, "T200", sample_data, contexts=contexts, as_of="2026-01-29")
    assert result["downtime_days"] == 21
    assert result["unplanned_downtime_days"] == 7
    assert result["maximum_consecutive_downtime_days"] == 14
    assert result["readings"][0]["citation"].endswith("#INS-1")


def test_spill_boundaries_and_valid_correction_preserve_source(sample_data: Path) -> None:
    rules = load_spill_rules(sample_data)
    assert classify_spill(4.99, rules).name == "moderate"
    assert classify_spill(5, rules).name == "reportable"
    assert classify_spill(25, rules).name == "major"
    inspection = {
        "inspection_id": "INS-1", "asset_id": "WELL-0001", "inspected_at": "2026-01-01T07:00:00Z",
        "spill_detected": True, "spill_est_volume_bbl": 6,
    }
    correction = {
        "note_id": "CTX-1", "asset_id": "WELL-0001", "inspection_id": "INS-1", "note_type": "correction",
        "created_at": "2026-01-02T07:00:00Z", "valid_from": "2026-01-01", "text": "Not crude. Not a spill.",
    }
    original = dict(inspection)
    result = assess_spill(inspection, [correction], rules, as_of="2026-01-03")
    assert result is not None and result["spill_detected"] is False
    assert result["correction_applied"] is True
    assert any("context.jsonl#CTX-1" in citation for citation in result["citations"])
    assert inspection == original
    assert spill_report_status(23, {"external_report_required": True, "report_deadline_hours": 24, "spill_detected": True}) == "met"
    assert spill_report_status(25, {"external_report_required": True, "report_deadline_hours": 24, "spill_detected": True}) == "missed"


def test_spill_compliance_uses_regulator_event_and_repair_report(sample_data: Path) -> None:
    inspection = {
        "inspection_id": "INS-1", "asset_id": "WELL-0001", "inspected_at": "2026-01-01T07:00:00Z",
        "spill_detected": True, "spill_est_volume_bbl": 6,
    }
    job = {
        "maintenance_id": "MNT-1", "asset_id": "WELL-0001", "triggered_by_inspection_id": "INS-1",
        "report_file": "maintenance-reports/report-1.md",
    }
    event = {
        "event_id": "REG-1", "asset_id": "WELL-0001", "related_inspection_id": "INS-1",
        "event_type": "spill_report_filed", "hours_to_report": 25,
    }
    findings = assess_spill_compliance(
        [inspection], [], [job], [event],
        {"MNT-1": "The release was contained about 4.5 hours after the inspection."},
        str(sample_data), "2026-01-03",
    )
    statuses = {finding["protocol_id"]: finding["status"] for finding in findings}
    assert statuses == {"SR-01": "confirmed_violation", "SR-02": "confirmed_violation", "SR-03": "pending"}
