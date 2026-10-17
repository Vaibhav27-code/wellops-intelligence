# Independent Verification Report

All verification runs were executed using standalone Python scripts that read raw JSON, JSONL, and Markdown files in `data/raw/flytbase-ahc-swe-asset-intelligence-dataset/test-data/dataset` without importing application or backend code.

Reference Date: **15 Jan 2027**

## Summary Matrix

| Question | Topic | Independent Result Status | Verification Type | Notes |
|---|---|---|---|---|
| **Q1** | Reservoir Pressure | **CANNOT VERIFY** | Data Gap | No pressure fields exist in schemas. System must report data gap. |
| **Q2** | Best Producer | **CANNOT VERIFY** | Data Gap | No production volume fields exist in schemas. System must report data gap. |
| **Q3** | Gas Reports & Response Deadlines | **MATCH** | Deterministic Calculation | 26 reports found: 17 met, 9 missed (12h/24h OPS-1 deadlines). |
| **Q4** | Flowline Bypasses & MOC Status | **MATCH** | Deterministic Audit | 9 bypass events: 5 Allowed, 2 Expired, 1 Not approved (WELL-0561), 1 past Expired. |
| **Q5** | Regulator Letter Spills (NE-7 & NE-8) | **MATCH** | Deterministic Audit | 6 spills >= 5 bbl since 2026-06-01: 3 Compliant (lab soil), 3 Non-compliant. |
| **Q6** | Status Disagreements (Insp vs Notes) | **MATCH** | Deterministic Rule (OPS-3) | Exactly 5 wells where latest operator note overrides inspection. |
| **Q8 / Q9** | Recalled Pumps (Highline RP-175) | **MATCH** | Raw Text Audit | 9 wells currently have affected lots (LOT-2409-A, 2409-C, 2410-B) in the ground. |
| **Q10** | Shut-in Waiting Reasons by Area | **MATCH** | Categorical Aggregation | Weather (7d typical) and Parts (14d typical) dominate 2026 delays across 7 areas. |

## Detailed Question Verifications

### Q1 & Q2: Reservoir Pressure & Production Volume
- Raw schemas analyzed: `metadata.json`, `inspections.jsonl`, `context.jsonl`, `maintenance.jsonl`, `regulatory.jsonl`.
- Zero pressure measurements exist across all 600 wells.
- Zero production volume records exist (only spill volume `spill_est_volume_bbl`).
- Conclusion: Any copilot output providing numbers or graphs for Q1 or Q2 represents hallucination/fabrication unless explicitly identified as a simulated or mock calculation.

### Q3: Gas Odor Reports
- Script: `verification/verify_q3_gas_reports.py`
- Total reports: 26.
- Response criteria: manual inspection (`method == "manual"`) or maintenance (`started_at`).
- Deadlines: 24h prior to 2027-01-01; 12h from 2027-01-01.
- Missed responses:
  - `WELL-0052`: Missed (No response)
  - `WELL-0161`: Missed (475.2h > 24h)
  - `WELL-0163`: Missed (251.1h > 24h)
  - `WELL-0332`: Missed (No response)
  - `WELL-0341`: Missed (677.8h > 24h)
  - `WELL-0362`: Missed (31.8h > 24h)
  - `WELL-0401`: Missed (138.2h > 24h)
  - `WELL-0516`: Missed (15.0h > 12h)
  - `WELL-0599`: Missed (16.4h > 12h)

### Q4: Flowline Bypasses
- Script: `verification/verify_q4_bypasses.py`
- Total events: 9.
  - Active Allowed: `WELL-0248` (MOC-031/044 expires 2027-02-28)
  - Active Expired: `WELL-0249` (MOC-036 expired 2026-12-15)
  - Active Not Approved: `WELL-0561` (No MOC)
  - Past Expired: `WELL-0087` (Removed 2027-01-06 after MOC-036 expired 2026-12-15)
  - Past Allowed: `WELL-0013`, `WELL-0062`, `WELL-0284`, `WELL-0356`, `WELL-0476`.

### Q5: Regulator Letter Spills
- Script: `verification/verify_q5_regulator_spills.py`
- Scope: NE Block 7 and NE Block 8, spills >= 5 bbl since 2026-06-01.
- Compliant (contains "Soil samples sent to the lab."):
  - `WELL-0119` (6.0 bbl)
  - `WELL-0168` (5.6 bbl)
  - `WELL-0277` (6.2 bbl)
- Non-compliant (field readings only / no lab submission):
  - `WELL-0123` (6.0 bbl)
  - `WELL-0182` (5.2 bbl)
  - `WELL-0262` (6.1 bbl)

### Q6: Status Disagreements
- Script: `verification/verify_q6_status.py`
- Rule OPS-3 precedence:
  - `WELL-0033`: Producing (unconfirmed) [restart note after cold inspection]
  - `WELL-0044`: Not producing (shut in) [shut-in note after producing inspection]
  - `WELL-0323`: Not producing (shut in) [shut-in note after producing inspection]
  - `WELL-0422`: Not producing (shut in) [shut-in note after producing inspection]
  - `WELL-0481`: Not producing (shut in) [shut-in note after producing inspection]

### Q8 / Q9: Recalled Pumps
- Script: `verification/verify_q8_recalled_pumps.py`
- Recalled lots: `LOT-2409-A`, `LOT-2409-C`, `LOT-2410-B`.
- 9 wells currently active:
  - `WELL-0031` ($19,625), `WELL-0156` ($23,398), `WELL-0160` ($33,086), `WELL-0263` ($17,254), `WELL-0305` ($24,528), `WELL-0333` ($15,440), `WELL-0426` ($24,044), `WELL-0428` ($27,074), `WELL-0577` ($25,500).
