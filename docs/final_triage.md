# Final Triage & Verification Report

Dataset: [FlytBase official final test dataset](https://github.com/FlytBaseAILabs/flytbase-ahc-swe-asset-intelligence-dataset), loaded in the isolated demo DB. Reference date: 2027-01-15. Status reflects whether the current `/chat` path answers the question with the requested evidence; independently computed raw-data results are kept below under Verifier findings.

| Question | Status | What data exists | Known gaps |
|---|---|---|---|
| Q1. Reservoir pressure | Cannot be answered | Well metadata, inspections, operator context, maintenance, and regulatory records. | No pressure measurement field exists. The current app asks for clarification instead of clearly explaining this missing-data limitation. |
| Q2. Best producer | Cannot be answered | Inspections contain temperature and spill-volume readings; metadata has recorded status. | No oil-production volume or rate exists, so production cannot be ranked. The current app asks for clarification instead of clearly explaining the missing field. |
| Q3. Gas reports | Partly | 26 candidate operator gas notes, inspection method/times, maintenance start times, and the operating SOP deadline rules. | Raw-data verification yields 17 met and 9 missed; the current app did not produce the requested response/deadline table. Earlier verifier summary counts (18/8) were inconsistent with its 26 listed rows and are corrected below. |
| Q4. Temporary flowline bypasses | Partly | Bypass notes and MOC approval/expiry memos; raw-data verification found nine events. | The current app did not match events to approvals or report active, expired, and unapproved states. |
| Q5. Regulator letter | Partly | Spill inspections, cleanup jobs/reports, regulatory records, the commission letter, and cleanup instructions; verifier found six in-scope spills. | The current app returned a broad spill-volume summary rather than letter coverage and a compliance reason for each spill. |
| Q6. Which status is right? | Partly | Latest inspections, operator notes, well metadata, and manual thresholds; verifier identified five status disagreements. | The current app did not generate the field-wide conflict table with both source timestamps and an unconfirmed status where appropriate. |
| Q7. What the operators are hearing | Partly | Recent operator notes, maintenance records, repairs, and repair reports. | The first turn returned a spill ranking, not a note-grounded repair-risk ranking; the follow-up returned a clarification. A supported ranking rule and citations are missing. |
| Q8. Who told you that? | Partly | Supplier recall notice, repair reports with lot/cost details, shared correction storage, and private per-user memory. | The current app did not correctly apply the recall correction, retain the private display preference, flag the cross-user claim, or compute the final personalized list. |
| Q9. One conversation, several topics | Partly | Team/user data, operating SOPs, operator notes, inspections, maintenance history, recall information, and private conversation storage. | The conversation does not reliably connect topics across turns. The H2S question received a production-status answer; team, cold-weather, recall, repair, and prioritization follow-ups remain incomplete. |
| Q10. What are we waiting on? | Partly | Maintenance start/completion/downtime fields, repair reports, operator notes, and status-derived downtime. | Independent raw-data results break out reasons by area, but `/chat` returned downtime totals rather than reason shares, extra days, and the requested stacked bar. |
| Q11. Hotter wells | Partly | Wellhead and ambient temperatures from inspections plus area/team metadata. | The current app did not calculate a repeated regional temperature comparison or cite its supporting records. |

## Verifier findings

### Q1. Reservoir Pressure
- **Status:** CANNOT VERIFY (Data Gap / Missing Schema)
- **Findings:** Scanned all 600 wells in the raw test dataset across all files (`metadata.json`, `inspections.jsonl`, `context.jsonl`, `maintenance.jsonl`, `regulatory.jsonl`).
- **Result:** No `pressure`, `reservoir_pressure`, or `pressure_psi` fields exist in the dataset.
- **Evidence:** `verification/verify_q1_q2_fields.py` inspected every key in all record types; pressure field list is strictly empty `[]`.
- **Copilot Requirement:** Copilot must explicitly state the data gap and refuse to hallucinate or fabricate pressure contours or pressure maps.

### Q2. Best Producer
- **Status:** CANNOT VERIFY (Data Gap / Missing Schema)
- **Findings:** Scanned all 600 wells in the raw test dataset across all files.
- **Result:** No production volume field (`production_volume`, `bbl_oil`, `oil_rate`, etc.) exists in the raw schemas. The only volume field present is `spill_est_volume_bbl` in `inspections.jsonl`.
- **Evidence:** `verification/verify_q1_q2_fields.py` returned only `spill_est_volume_bbl` for volume search.
- **Copilot Requirement:** Copilot must state that well production volumes are not tracked in the asset database and refuse to invent a top producer.

### Q3. Gas Reports (since 2026-11-01)
- **Status:** VERIFIED (Deterministic Python from Raw Data)
- **Rule:** OPS-1: operator notes mentioning gas odor/smell/H2S alarm. Response = maintenance started OR manual inspection (drone does not count). Deadline = 24h prior to 2027-01-01, 12h on/after 2027-01-01.
- **Total Reports:** 26 reports across the field.
  - Met: 17 reports
  - Missed: 9 reports
- **Missed Reports Detail:**
  - `WELL-0052` (Southwest Block 24, 2026-12-18T06:45:00Z): Missed (No response recorded)
  - `WELL-0161` (Northeast Block 8, 2026-12-25T15:45:00Z): Missed (Response INS-0161-0168 on 2027-01-14, 475.2 hours > 24h)
  - `WELL-0163` (Northeast Block 8, 2026-11-03T20:55:00Z): Missed (Response MNT-0163-019 on 2026-11-14, 251.1 hours > 24h)
  - `WELL-0332` (Northwest Block 12, 2026-12-03T12:10:00Z): Missed (No response recorded)
  - `WELL-0341` (Northwest Block 12, 2026-11-19T07:40:00Z): Missed (Response INS-0341-0109 on 2026-12-17, 677.8 hours > 24h)
  - `WELL-0362` (Northwest Block 12, 2026-12-24T00:15:00Z): Missed (Response MNT-0362-030 on 2026-12-25, 31.8 hours > 24h)
  - `WELL-0401` (Northwest Block 12, 2026-12-05T13:50:00Z): Missed (Response MNT-0401-033 on 2026-12-11, 138.2 hours > 24h)
  - `WELL-0516` (Southeast Block 32, 2027-01-06T21:15:00Z): Missed (Response INS-0516-0215 on 2027-01-07, 15.0 hours > 12h deadline)
  - `WELL-0599` (Southeast Block 32, 2027-01-06T17:20:00Z): Missed (Response INS-0599-0196 on 2027-01-07, 16.4 hours > 12h deadline)

### Q4. Temporary Flowline Bypasses
- **Status:** VERIFIED (Deterministic Python from Raw Data)
- **Rule:** OPS-2: MOC-2026-031 extended by MOC-2026-044 (valid until 2027-02-28); MOC-2026-036 (expired 2026-12-15).
- **Findings:** 9 total bypass events:
  - `WELL-0013` (SW-23): 2026-11-10 to 2027-01-08 | MOC-2026-031/044 | Allowed
  - `WELL-0062` (SW-24): 2026-11-02 to 2026-11-27 | MOC-2026-031/044 | Allowed
  - `WELL-0087` (SW-24): 2026-12-02 to 2027-01-06 | MOC-2026-036 | **Expired** (removed after 2026-12-15)
  - `WELL-0248` (SE-31): 2026-11-05 to still in | MOC-2026-031/044 | **Allowed** (valid until 2027-02-28)
  - `WELL-0249` (SE-31): 2026-11-25 to still in | MOC-2026-036 | **Expired** (approval expired 2026-12-15, still in)
  - `WELL-0284` (SW-24): 2026-11-12 to 2026-12-10 | MOC-2026-036 | Allowed
  - `WELL-0356` (NW-12): 2026-11-18 to 2026-12-05 | MOC-2026-036 | Allowed
  - `WELL-0476` (SE-32): 2026-10-22 to 2026-11-18 | MOC-2026-031/044 | Allowed
  - `WELL-0561` (SE-32): 2026-12-08 to still in | None | **Not approved** (no MOC memo authorization)

### Q5. Regulator Letter Spills
- **Status:** VERIFIED (Deterministic Python from Raw Data)
- **Scope:** Reportable spills (>= 5 bbl) in Northeast Block 7 & 8 since 2026-06-01. Compliance requires clean-up report containing "Soil samples sent to the lab."
- **Findings:** Exactly 6 qualifying spills:
  - `WELL-0119` (NE-7): INS-0119-0209 (2026-11-05), 6.0 bbl | Clean-up MNT-0119-029 | **Compliant: Yes**
  - `WELL-0123` (NE-7): INS-0123-0093 (2026-09-24), 6.0 bbl | Clean-up MNT-0123-014 | **Compliant: No** (Field readings only, no lab samples sent)
  - `WELL-0168` (NE-8): INS-0168-0190 (2026-06-11), 5.6 bbl | Clean-up MNT-0168-024 | **Compliant: Yes**
  - `WELL-0182` (NE-8): INS-0182-0208 (2026-12-03), 5.2 bbl | Clean-up MNT-0182-028 | **Compliant: No** (Field readings only, no lab samples sent)
  - `WELL-0262` (NE-8): INS-0262-0218 (2027-01-07), 6.1 bbl | Clean-up MNT-0262-029 | **Compliant: No** (Field readings only, no lab samples sent)
  - `WELL-0277` (NE-7): INS-0277-0205 (2026-10-01), 6.2 bbl | Clean-up MNT-0277-031 | **Compliant: Yes**

### Q6. Producing Status Disagreements
- **Status:** VERIFIED (Deterministic Python from Raw Data)
- **Rule:** OPS-3: Recent operator shut-in note overrides inspection to `Not producing (shut in)`; restart note overrides to `Producing (unconfirmed)`.
- **Findings:** Exactly 5 wells where latest operator note overrides latest inspection:
  - `WELL-0033` (SW-23): Inspection INS-0033-0222 (2027-01-14) showed Not producing (dT=10.0°C). Operator note (2027-01-15T10:25:00Z) "Restarted WELL-0033". **Real Status: Producing (unconfirmed)**
  - `WELL-0044` (SW-23): Inspection INS-0044-0218 (2027-01-14) showed Producing (dT=23.7°C). Operator note (2027-01-14T13:05:00Z) "Shut in WELL-0044 at the wellhead, flowline leak suspected". **Real Status: Not producing (shut in)**
  - `WELL-0323` (NW-12): Inspection INS-0323-0219 (2027-01-14) showed Producing (dT=24.5°C). Operator note (2027-01-14T19:20:00Z) "Shut-in WELL-0323 after pumper reported stuffing box leak". **Real Status: Not producing (shut in)**
  - `WELL-0422` (NW-12): Inspection INS-0422-0215 (2027-01-14) showed Producing (dT=27.7°C). Operator note (2027-01-14T21:35:00Z) "Shut in WELL-0422 for the night, high pressure alarm on separator". **Real Status: Not producing (shut in)**
  - `WELL-0481` (SE-32): Inspection INS-0481-0220 (2027-01-14) showed Producing (dT=22.4°C). Operator note (2027-01-14T18:50:00Z) "Shut in WELL-0481 for the night, high pressure alarm on separator". **Real Status: Not producing (shut in)**

### Q8 / Q9. Recalled Pumps
- **Status:** VERIFIED (Deterministic Python from Raw Data)
- **Recalled Lots:** Highline RP-175: `LOT-2409-A`, `LOT-2409-C`, `LOT-2410-B`.
- **Currently in the Ground (before session-specific user memory corrections):** 9 wells:
  - `WELL-0031` (SW-23): LOT-2409-A, installed MNT-0031-027 (2026-04-24), cost $19,625
  - `WELL-0156` (NE-8): LOT-2409-A, installed MNT-0156-027 (2026-06-27), cost $23,398
  - `WELL-0160` (NE-8): LOT-2409-C, installed MNT-0160-028 (2026-07-18), cost $33,086
  - `WELL-0263` (SW-23): LOT-2410-B, installed MNT-0263-033 (2026-10-16), cost $17,254
  - `WELL-0305` (NW-12): LOT-2409-A, installed MNT-0305-032 (2026-10-16), cost $24,528
  - `WELL-0333` (NW-12): LOT-2409-A, installed MNT-0333-024 (2026-05-09), cost $15,440
  - `WELL-0426` (NW-12): LOT-2409-C, installed MNT-0426-030 (2026-06-19), cost $24,044
  - `WELL-0428` (NW-12): LOT-2410-B, installed MNT-0428-022 (2026-03-07), cost $27,074
  - `WELL-0577` (SE-32): LOT-2409-A, installed MNT-0577-028 (2026-07-31), cost $25,500
- **Interaction Effects in Q8:**
  - Turn 1: Nathan Pierce reports WELL-0333 pump swapped -> removed from recall count in memory.
  - Turn 4: Olivia Grant reports WELL-0577 pump swapped -> unconfirmed claim from peer, must be noted with provenance.
  - Turn 5: Nathan Pierce asks for recalled pumps in his area (Northwest Block 12) -> WELL-0305 ($24,528), WELL-0426 ($24,044), WELL-0428 ($27,074), with WELL-0333 excluded based on his earlier report.

### Q10. Shut-in Waiting Reasons by Area (2026)
- **Status:** VERIFIED (Deterministic Python from Raw Data)
- **Breakdown:**
  - Southeast Block 32: 6 parts delays (avg 14d), 6 weather delays (avg 7d).
  - Southeast Block 31: 2 parts delays (avg 14d), 5 weather delays (avg 7d).
  - Northwest Block 12: 8 weather delays (avg 7d).
  - Northeast Block 7: 4 weather delays (avg 7d).
  - Southwest Block 23: 2 parts delays (avg 14d), 2 weather delays (avg 7d).
  - Southwest Block 24: 2 parts delays (avg 14d).
  - Northeast Block 8: 1 parts delay (avg 14d), 1 weather delay (avg 7d).
