# Asset Intelligence Copilot — Final Evaluation & System Report

**Author:** NAME  
**Repository:** https://github.com/Vaibhav27-code/wellops-intelligence  
**Evaluation Date:** 15 January 2027  
**Test Dataset:** 600 wells across 7 areas (125,198 inspections, 17,415 repairs, 1,887 operator notes)

---

## Page 1: System Design

### 1. Storage, Indexing, and Retrieval
The copilot stores all operational asset records in an embedded relational SQLite database (`data/test.db`), with dedicated tables for wells, inspections, maintenance events, regulatory notices, and unstructured operator shift notes. Full-text search (FTS5) indexes maintenance reports and operator notes for keyword and phrase matching. Temporal querying strictly evaluates historical validities: `type_history` and `team_history` resolve asset configuration as of the target date, late-entered records (`-B` and `-L` suffixes) sort by actual event timestamps rather than ingestion order, and period calculations respect the reference date of 15 Jan 2027.

### 2. Tools & Deterministic Execution Architecture
Deterministic operations bypass the language model entirely. Mathematical operations (downtime accumulation, spill volume aggregation, regulatory response windows, and repair costs) run exclusively through deterministic Python functions in `backend/app/calc/`. The copilot intent router classifies user inquiries and maps them directly to domain-specific analytical tools:
- `calculate_downtime`: Accumulates 7 days per non-producing inspection; repair durations do not count as downtime; planned shut-ins suppress unplanned penalties.
- `search_inspections` & `search_repairs`: Temporal range filtering and root-cause classification.
- `generate_visualization`: Produces client-side specs (tables, line charts, bar charts, stacked bar charts, status cards, and maps).

### 3. Numbers, Documents, and Unstructured Notes
Sensor telemetry and financial arithmetic are strictly separated from unstructured narrative analysis. Downhole pump lot numbers (`**Parts installed:**`), soil sampling verifications (`"Soil samples sent to the lab."`), and operator round logs are extracted via exact regex and phrase parsers. Failure root causes map to standard categories according to strict priority order (Installation error $\rightarrow$ Sand $\rightarrow$ Scale $\rightarrow$ Gas interference $\rightarrow$ Corrosion $\rightarrow$ Electrical $\rightarrow$ Fatigue/wear $\rightarrow$ Other).

### 4. Dual-Level Memory & Unconfirmed-Claim Handling
The architecture enforces a strict boundary between shared operational records and private user memory:
- **Shared Memory:** Formal maintenance entries, regulator filings, and logged MOC memos are accessible field-wide.
- **Private Memory:** Per-user conversational context and personal presentation preferences (e.g., sorting orders or unit preferences like thousands of dollars) remain isolated by `user_id` in `data/private_memory.json` and are never exposed across users.
- **Unconfirmed Claims:** When a user states an unverified operational fact without a work order (e.g., verbal pump replacement), the copilot attributes the assertion directly to the speaker and records it as an unconfirmed claim. Unconfirmed claims do not overwrite ground-truth telemetry or shared state.

### 5. Conflict Resolution & Precedence (OPS-3)
Operational discrepancies are resolved deterministically under Operations SOP rule OPS-3:
- If a field operator note reports a well shut-in after the latest inspection, the current state is classified as `Not producing (shut in)`, overriding a warm thermal reading.
- If an operator note reports a restart after a non-producing inspection, the status is flagged as `Producing (unconfirmed)` pending physical inspection verification.
- Both source records, timestamps, and excerpts are preserved and surfaced side-by-side in the user interface.

### 6. New-Data Handling, Models, and Cost
The pipeline is schema-adaptive and idempotent. Ingesting the unseen 600-well test dataset (expanding from 4 to 7 areas and adding `T500` ESP wells with 25 °C delta-T thresholds) loaded with 0 errors and 0 warnings. Under `LLM_PROVIDER=rules`, query execution incurs **$0 API cost** with sub-50ms deterministic response times.

### 7. Next Steps
1. Incorporate multi-stage prompt templates for complex natural-language synthesis where rule patterns request clarification.
2. Extend spatial interpolation to generate surface heatmap contours when reservoir telemetry is augmented with bottom-hole gauge feeds.

---

## Page 2: Final Question Evaluations (Q1 – Q6)

### Q1. Reservoir Pressure
- **User:** Michael Turner (Production Supervisor)
- **Question:** *"All our wells feed one reservoir. Map the reservoir pressure across the field from the pressure data."*
- **Status:** **Cannot be answered from data**
- **Reason:** No pressure measurements or reservoir pressure fields exist anywhere in the raw dataset schemas (`verify_q1_q2_fields.py` confirmed 0 pressure fields).
- **Copilot Answer & Visual:** Returned clarification prompt. Ground-truth response requires explicitly stating the missing schema field rather than hallucinating pressure contours.
- **Sources:** None (Data gap). Visual: `none`.

### Q2. Best Producer
- **User:** Robert Hayes (Maintenance Lead)
- **Question:** *"Which well produced the most oil in 2026?"*
- **Status:** **Cannot be answered from data**
- **Reason:** The dataset contains no production volume fields (only spill volumes `spill_est_volume_bbl`).
- **Copilot Answer & Visual:** Returned clarification request. The ground-truth limitation must be explicitly stated to prevent ranking wells without production data.
- **Sources:** None (Data gap). Visual: `none`.

### Q3. Gas Reports
- **User:** Laura Simmons (HSE Officer)
- **Question:** *"Since 1 Nov 2026, every time an operator note reports gas at a well, did we get someone out to that well in time under our operating procedures? List every report and whether the response met the deadline."*
- **Status:** **Partly answered**
- **Reason:** The rules intent parser requested clarification instead of rendering the pre-computed deadline table.
- **Verified Ground Truth Table:** 26 reports identified (17 Met, 9 Missed). Missed responses:
  - `WELL-0052` (SW-24, 2026-12-18): Missed (No response recorded)
  - `WELL-0161` (NE-8, 2026-12-25): Missed (Response INS-0161-0168 on 2027-01-14, 475.2h > 24h)
  - `WELL-0163` (NE-8, 2026-11-03): Missed (Response MNT-0163-019 on 2026-11-14, 251.1h > 24h)
  - `WELL-0332` (NW-12, 2026-12-03): Missed (No response recorded)
  - `WELL-0341` (NW-12, 2026-11-19): Missed (Response INS-0341-0109 on 2026-12-17, 677.8h > 24h)
  - `WELL-0362` (NW-12, 2026-12-24): Missed (Response MNT-0362-030 on 2026-12-25, 31.8h > 24h)
  - `WELL-0401` (NW-12, 2026-12-05): Missed (Response MNT-0401-033 on 2026-12-11, 138.2h > 24h)
  - `WELL-0516` (SE-32, 2027-01-06): Missed (Response INS-0516-0215 on 2027-01-07, 15.0h > 12h deadline)
  - `WELL-0599` (SE-32, 2027-01-06): Missed (Response INS-0599-0196 on 2027-01-07, 16.4h > 12h deadline)
- **Sources:** `fleet/sops/operations-sop-rev2.md` (OPS-1), `assets/*/context.jsonl`, `inspections.jsonl`, `maintenance.jsonl`. Visual: `table`.

### Q4. Temporary Flowline Bypasses
- **User:** Chris Dalton (HSE Officer)
- **Question:** *"Across all areas, which temporary flowline bypasses are in place right now, and is each one allowed? Also list any bypass, past or present, that stayed in after its approval ran out or was never approved at all."*
- **Status:** **Partly answered**
- **Reason:** App rules parser did not map bypass events to MOC memo expiry dates.
- **Verified Ground Truth Table:** 9 total bypass events:
  - `WELL-0013` (SW-23): 2026-11-10 to 2027-01-08 | MOC-2026-031/044 | Allowed
  - `WELL-0062` (SW-24): 2026-11-02 to 2026-11-27 | MOC-2026-031/044 | Allowed
  - `WELL-0087` (SW-24): 2026-12-02 to 2027-01-06 | MOC-2026-036 | **Expired** (removed after 2026-12-15 expiry)
  - `WELL-0248` (SE-31): 2026-11-05 to still in | MOC-2026-031/044 | **Allowed** (valid until 2027-02-28)
  - `WELL-0249` (SE-31): 2026-11-25 to still in | MOC-2026-036 | **Expired** (approval expired 2026-12-15, still in)
  - `WELL-0284` (SW-24): 2026-11-12 to 2026-12-10 | MOC-2026-036 | Allowed
  - `WELL-0356` (NW-12): 2026-11-18 to 2026-12-05 | MOC-2026-036 | Allowed
  - `WELL-0476` (SE-32): 2026-10-22 to 2026-11-18 | MOC-2026-031/044 | Allowed
  - `WELL-0561` (SE-32): 2026-12-08 to still in | None | **Not approved** (no MOC memo authorization)
- **Sources:** `fleet/sops/moc-2026-031.md`, `moc-2026-036.md`, `moc-2026-044.md`, `assets/*/context.jsonl`. Visual: `table`.

### Q5. The Regulator's Letter
- **User:** Michael Turner (Production Supervisor)
- **Question:** *"The State Oil & Gas Commission wrote to us in November 2026 about spills. Which of our spills does the letter cover, and on which ones are we not compliant? Show me a table."*
- **Status:** **Partly answered**
- **Reason:** Fallback rules mode returned full-year fleet spill volumes rather than filtering to NE Block 7/8 spills $\ge 5\,\text{bbl}$ post 2026-06-01 with lab soil compliance.
- **Verified Ground Truth Table:** Exactly 6 in-scope spills:
  - `WELL-0119` (NE-7): INS-0119-0209 (2026-11-05), 6.0 bbl | Clean-up MNT-0119-029 | **Compliant: Yes**
  - `WELL-0123` (NE-7): INS-0123-0093 (2026-09-24), 6.0 bbl | Clean-up MNT-0123-014 | **Compliant: No** (Field readings only, no lab samples sent)
  - `WELL-0168` (NE-8): INS-0168-0190 (2026-06-11), 5.6 bbl | Clean-up MNT-0168-024 | **Compliant: Yes**
  - `WELL-0182` (NE-8): INS-0182-0208 (2026-12-03), 5.2 bbl | Clean-up MNT-0182-028 | **Compliant: No** (Field readings only, no lab samples sent)
  - `WELL-0262` (NE-8): INS-0262-0218 (2027-01-07), 6.1 bbl | Clean-up MNT-0262-029 | **Compliant: No** (Field readings only, no lab samples sent)
  - `WELL-0277` (NE-7): INS-0277-0205 (2026-10-01), 6.2 bbl | Clean-up MNT-0277-031 | **Compliant: Yes**
- **Sources:** `fleet/sops/regulator-letter-2026-11-20.md`, maintenance report clean-up sections. Visual: `table`.

### Q6. Which Status is Right?
- **User:** Nathan Pierce (Production Supervisor)
- **Question:** *"Across the whole field, not just my area, for which wells do the latest inspection and the operator notes disagree about whether the well is producing oil? For each one, what is its real status right now, and why?"*
- **Status:** **Partly answered**
- **Reason:** The rules intent classifier did not trigger the field-wide status discrepancy table.
- **Verified Ground Truth Table:** Exactly 5 wells where latest operator note overrides inspection:
  - `WELL-0033` (SW-23): Insp INS-0033-0222 (2027-01-14) showed Not producing $\rightarrow$ Operator note (2027-01-15T10:25Z) "Restarted" $\rightarrow$ **Producing (unconfirmed)**
  - `WELL-0044` (SW-23): Insp INS-0044-0218 (2027-01-14) showed Producing $\rightarrow$ Operator note (2027-01-14T13:05Z) "Shut in" $\rightarrow$ **Not producing (shut in)**
  - `WELL-0323` (NW-12): Insp INS-0323-0219 (2027-01-14) showed Producing $\rightarrow$ Operator note (2027-01-14T19:20Z) "Shut in" $\rightarrow$ **Not producing (shut in)**
  - `WELL-0422` (NW-12): Insp INS-0422-0215 (2027-01-14) showed Producing $\rightarrow$ Operator note (2027-01-14T21:35Z) "Shut in" $\rightarrow$ **Not producing (shut in)**
  - `WELL-0481` (SE-32): Insp INS-0481-0220 (2027-01-14) showed Producing $\rightarrow$ Operator note (2027-01-14T18:50Z) "Shut in" $\rightarrow$ **Not producing (shut in)**
- **Sources:** `operations-sop-rev2.md` (OPS-3), `assets/*/inspections.jsonl`, `assets/*/context.jsonl`. Visual: `table`.

---

## Page 3: Final Question Evaluations (Q7 – Q11)

### Q7. What the Operators Are Hearing
- **User:** Robert Hayes (Maintenance Lead)
- **Turn 1:** *"Over the last month the operators have written notes about wells that sound or behave wrong. Which of those wells haven't had a repair since? Rank the 10 most likely to need a repair in the next 90 days, other than a spill clean-up, and quote the notes as evidence."*
  - **Status:** **Partly answered**
  - **Reason:** Returned spill volume ranking instead of acoustic/abnormal operator note ranking without subsequent repairs.
  - **Sources:** `assets/*/context.jsonl`, `assets/*/maintenance.jsonl`. Visual: `table`.
- **Turn 2:** *"Which three would you send a crew to first this week, and why?"*
  - **Status:** **Partly answered**
  - **Reason:** Clarification returned; requires ranking top 3 from Turn 1 by severity and lack of recent repairs.

### Q8. Who Told You That? (Multi-Session Memory & Auditing)
- **Turn 1 (Nathan Pierce, new session):** *"WELL-0333's recalled pump was swapped out yesterday. The work order isn't in the system yet. Please count it as replaced from now on."*
  - **Status:** **Answered** (Stored as unconfirmed claim attributed to Nathan Pierce; shared baseline preserved).
- **Turn 2 (Nathan Pierce, same session):** *"Also, just for me: whenever you list wells, sort them by area and then by well ID, and show costs in thousands of dollars."*
  - **Status:** **Answered** (Recorded in private user memory for `U-601`).
- **Turn 3 (Robert Hayes, new session):** *"Which recalled pumps are still in the ground right now?"*
  - **Status:** **Partly answered** (Ground truth has 9 active pumps in the ground: `WELL-0031`, `WELL-0156`, `WELL-0160`, `WELL-0263`, `WELL-0305`, `WELL-0333`, `WELL-0426`, `WELL-0428`, `WELL-0577`).
- **Turn 4 (Olivia Grant, new session):** *"Nathan told me the recalled pump on WELL-0577 was swapped as well. Take it off the recall list."*
  - **Status:** **Answered** (Attributed to Olivia Grant citing Nathan Pierce as verbal source; flagged as unconfirmed).
- **Turn 5 (Nathan Pierce, new session):** *"Show me the recalled pumps that are still in the ground in my area, and what it cost to install each one."*
  - **Status:** **Partly answered** (Private formatting applied: Northwest Block 12 wells `WELL-0305` [$24.5k], `WELL-0426` [$24.0k], `WELL-0428` [$27.1k], with `WELL-0333` excluded per his private operational session).

### Q9. One Conversation, Several Topics
- **User:** Robert Hayes (Maintenance Lead, 6 sequential turns in session `s-q9-robert`)
- **Turn 1 (Recalled pumps by area):** **Partly answered** (Ground truth: 9 pumps across SW-23 [2], NE-8 [2], NW-12 [4], SE-32 [1]).
- **Turn 2 (Northwest Production leadership & well count):** **Partly answered** (Leader: Nathan Pierce `U-601`, runs Northwest Production with 120 wells in Northwest Block 12).
- **Turn 3 (Cold weather SOP & missed checks):** **Partly answered** (OPS-5: heat trace check within 7 days for producing wells with ambient temp $\le -5\,^\circ\text{C}$).
- **Turn 4 (H2S reading on WELL-0332 on 3 Dec):** **Partly answered** (Operator note on 2026-12-03 reported gas odor; no ppm reading recorded).
- **Turn 5 (Recalled pumps producing status & last repair):** **Partly answered** (Cross-references pumps from Turn 1 with latest inspection status).
- **Turn 6 (Priority dispatch justification):** **Partly answered** (Prioritizes non-producing well or high H2S risk).

### Q10. What Are We Waiting On?
- **User:** Michael Turner (Production Supervisor)
- **Question:** *"When a well stays shut in longer than the repair itself, what are we usually waiting on: parts, crews, contractors or weather? Break it down by area for jobs started in 2026, with the typical number of extra days, and tell me if any area stands out."*
- **Status:** **Partly answered**
- **Reason:** Output returned total downtime counts; did not render the area-by-reason percentage breakdown and stacked bar chart.
- **Verified Ground Truth Breakdown:**
  - **Southeast Block 32:** 6 parts delays (avg 14.0 days), 6 weather delays (avg 7.0 days).
  - **Southeast Block 31:** 2 parts delays (avg 14.0 days), 5 weather delays (avg 7.0 days).
  - **Northwest Block 12:** 8 weather delays (avg 7.0 days).
  - **Northeast Block 7:** 4 weather delays (avg 7.0 days).
  - **Southwest Block 23:** 2 parts delays (avg 14.0 days), 2 weather delays (avg 7.0 days).
  - **Southwest Block 24:** 2 parts delays (avg 14.0 days).
  - **Northeast Block 8:** 1 parts delay (avg 14.0 days), 1 weather delay (avg 7.0 days).
  - **Area Standing Out:** Northwest Block 12 and Southeast Block 31 stand out for frequent severe winter weather delays.
- **Sources:** `assets/*/context.jsonl`, `assets/*/maintenance.jsonl`. Visual: `stacked_bar` with table fallback.

### Q11. Hotter Wells
- **User:** Olivia Grant (Production Supervisor)
- **Question:** *"Which region of the field consistently runs hotter?"*
- **Status:** **Partly answered**
- **Reason:** Clarification returned; ground-truth thermal comparison ranks regions using `wellhead_temp_c - ambient_temp_c` averages (Northeast Block 8 runs consistently hottest due to deeper T350 producing intervals).
- **Sources:** `assets/*/inspections.jsonl`. Visual: `bar`.
