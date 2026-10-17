# Data inventory

Inventory date: 2026-10-17 (IST)
Source repository: https://github.com/FlytBaseAILabs/flytbase-ahc-swe-asset-intelligence-dataset
Cloned commit: b8de8c9bd68f40334e5d06922126169e4f3bf3ca
Local source: data/raw/flytbase-ahc-swe-asset-intelligence-dataset (kept unchanged and ignored by the app repository)

## Dataset scope

The official guide describes a synthetic sample field with 200 wells, four areas, and a reference date of 2026-10-16. Calculations and evaluation windows must use that dataset reference date when answering sample questions. The sample-data tree has 2,516 files: 202 JSON, 800 JSONL, and 1,514 Markdown files. The full challenge repository has 2,523 files.

| Entity / files | Count | Notes |
|---|---:|---|
| Areas / teams | 4 / 4 | 50 wells per area |
| Users | 15 | Six roles |
| Well metadata | 200 | 119 T200, 81 T350 |
| Inspections | 39,567 | WELL-0001 has 203; each row has an ISO 8601 UTC inspected_at |
| Maintenance jobs | 5,665 | 4,156 scheduled; 1,509 corrective |
| Maintenance reports | 1,509 | Every non-null report_file reference resolves |
| Regulator events | 90 | Dates are YYYY-MM-DD |
| Context notes | 141 | 56 corrections, 82 operator notes, 3 operator feedback notes |

The repository also contains the Dataset Guide, 18 official evaluation questions, two well-type manuals, and three SOPs. The image paths in evidence_images are references only; image files are not supplied. Maintenance completed_at may be a planned future end time for work in progress; the guide's reference date is 2026-10-16.

## Source files and fields

Fleet-wide files:

- fleet/areas.json: top-level areas and teams. Area fields: area_id, name, team_id, center.lat/lon, asset_ids. Team fields: team_id, name, lead_user_id.
- fleet/users.json: top-level users. User fields: user_id, name, role, team_id.

Per-well files under assets/WELL-XXXX:

- metadata.json: asset_id, name, asset_category, well_type, area_id, team_id, in_charge_user_id, location, installed_on, equipment, last_inspection, recorded_status.
- inspections.jsonl: inspection_id, asset_id, inspected_at, inspector_user_id, method, ambient_temp_c, wellhead_temp_c, spill_detected, spill_area_pct, spill_est_volume_bbl, evidence_images, notes.
- maintenance.jsonl: maintenance_id, asset_id, started_at, completed_at, maintenance_type, equipment_kind, issue, action_taken, technician_user_id, contractor, downtime_hours, cost_usd, triggered_by_inspection_id, report_file.
- regulatory-events.jsonl: event_id, asset_id, date, agency, event_type, protocol_id, related_inspection_id, hours_to_report, detail, fine_usd, status.
- context.jsonl: note_id, asset_id, created_at, author_user_id, note_type, optional inspection_id, text, valid_from, valid_to.
- maintenance-reports/*.md: unstructured job reports. Resolve their paths from maintenance.report_file; filenames vary.

Nested fields observed: metadata.location has lat/lon; metadata.equipment items have equipment_id/kind/model; metadata.last_inspection has inspection_id/inspected_at/inspector_user_id; maintenance.cost_usd has labor/parts/total.

## Join keys and provenance

- asset_id joins metadata and all per-well record types; the asset folder name matches asset_id.
- inspection_id is referenced by maintenance.triggered_by_inspection_id, regulatory.related_inspection_id, and correction-note inspection_id.
- inspector_user_id, technician_user_id, author_user_id, in_charge_user_id, and team lead IDs refer to fleet/users.json user_id.
- area_id and team_id refer to fleet/areas.json.
- report_file is the authoritative path from a maintenance row to its report.
- Cite records by source file plus their record ID; cite manuals/SOPs by source file and section.

## Date fields and formats

- inspected_at, started_at, completed_at, created_at: ISO 8601 UTC timestamps (Z suffix in source).
- date, installed_on, valid_from, valid_to: YYYY-MM-DD date strings; valid_to can be null.
- Observed inspection range: 2022-10-20T07:00:00Z through 2026-10-15T15:45:00Z.
- Observed maintenance started_at range: 2022-10-21T08:00:00Z through 2026-10-16T08:00:00Z. Some completed_at values extend beyond the reference date because they are planned end times.

## Manual and SOP thresholds

- T200 production: wellhead temperature minus ambient temperature >= 15 °C (T200 manual, section 9.3). Alarm above 85 °C (section 9.4). Shut in for spill area > 5% (section 9.5).
- T350 production: temperature difference >= 20 °C (T350 manual, section 3). Alarm above 95 °C (section 4). Same spill-area shut-in rule (section 5).
- T200 maintenance escalation: at least 3 corrective jobs on the same equipment kind in the prior 12 months require RCA; >14 consecutive downtime days must be reported (section 10). T350 refers to T200 section 10 (T350 section 6).
- Spill classes: minor <1 bbl; moderate 1 to <5; reportable 5 to <25; major >=25 (Spill Response SOP, section 3).
- SR-01 written report: within 24 hours for reportable spills, within 2 hours for major spills; discovery time is inspection time (Spill Response SOP, section 4).
- SR-02 containment: within 4 hours. SR-03 agency verification for reportable/major spills: within 60 days. SR-04 requires recording every spill (Spill Response SOP, section 4).
- RC-01 inspection interval <=14 days; RC-02 annual flowline integrity test; RC-03 report downtime >14 consecutive days; RC-04 NOV response <=30 days; RC-05 weekly flowline/pad visual check (Regulatory Compliance SOP, section 2).
- WS-07 maintenance report due within 3 days of work completion (Field Work SOP, section 3).

## Validation performed

A full JSON/JSONL pass found no malformed rows, duplicate IDs within entity types, or exact duplicate records. Per-well record asset_ids matched their folders; all tested user/inspection/area/team references resolved; all 1,509 report_file paths existed.

Nulls are present where the source guide implies optional values:

- inspections.spill_area_pct and spill_est_volume_bbl: each null on 38,895 of 39,567 rows; all 672 spill detections have both values, and non-spill rows have neither.
- maintenance.contractor: null on 2,280 of 5,665 rows.
- maintenance.report_file and triggered_by_inspection_id: each null on 4,156 of 5,665 scheduled jobs; all 1,509 corrective jobs have reports.
- regulatory.hours_to_report: null on 43 of 90 events.
- context.inspection_id is present on 56 of 141 notes; valid_to is null on 59 of 141 notes.
- All other observed top-level fields were present and non-null in the sample.

## Operational interpretation risks

- recorded_status can be stale; derive current production from the latest inspection and its well-type threshold.
- Planned shut-ins may appear only in context notes and must not be counted as unplanned downtime.
- Downtime is 7 days per inspected non-producing reading; missed weeks count zero and maintenance.downtime_hours is not the downtime metric.
- Source correction notes apply to their named inspection and override a false spill detection. Preserve the raw record.
- Operator notes/feedback are not all formal corrections; user disagreements must remain visible.
- Containment timing may exist only in a maintenance report, not structured fields.
- The sample contains the official 18 questions and expected answers in 03-evaluation-queries.md; they have not yet been run through the app.

## References

- Dataset Guide: data/raw/flytbase-ahc-swe-asset-intelligence-dataset/02-dataset-guide.md
- Example questions: data/raw/flytbase-ahc-swe-asset-intelligence-dataset/03-evaluation-queries.md
- T200/T350 manuals: sample-data/fleet/well-types/
- SOPs: sample-data/fleet/sops/

## Backend ingestion and calculations

The loader in `backend/app/ingest/loader.py` accepts the challenge repository or its `sample-data` directory, validates IDs and references before loading, and replaces its SQLite snapshot transactionally. It retains each source record as its original JSON payload with source path and record ID. Markdown manuals, SOPs, and maintenance reports plus structured human notes are indexed with SQLite FTS5. Repeated ingestion is idempotent.

The deterministic calculation modules read production temperatures, spill volume classes/deadlines, inspection intervals, containment/verification deadlines, notice response deadlines, and maintenance report windows from the supplied manuals and SOPs. Downtime uses weekly inspection readings and does not use repair duration. Spill corrections apply only to their referenced inspection and do not mutate the source record. The first backend test run passed 8 tests; full sample ingestion passed validation with no errors or warnings.
