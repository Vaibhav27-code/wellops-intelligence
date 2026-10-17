# Asset Intelligence Copilot: Evaluation Report

**Evaluation Date:** Sat 17 Oct 2026  
**Reference Date for Evaluation:** 16 Oct 2026  
**Dataset:** FlytBase Asset Intelligence Challenge Dataset (200 wells, 39,567 inspections, 5,665 maintenance jobs, 90 regulator events, 141 context notes, 1,514 documents)  
**Test Suite Status:** 23 / 23 unit & integration tests passing (`pytest`)  
**Frontend Build Status:** React + Vite + TypeScript (0 errors, production build passes)

---

## 1. Summary of Question Results (Part A & Part B)

| Question | Topic | Expected Behavior | Visual Spec | Status | Evidence / Citations |
|---|---|---|---|---|---|
| **Q1** | Single well current status | Not producing; 3.2 °C delta (below T200 15 °C limit); inspected 15 Oct by Ryan Brooks (drone); planned shut-in rod string replacement (Jake Morales CTX-0001-003); recorded status out of date | **Status Card** | ✅ **PASS** | `assets/WELL-0001/inspections.jsonl#INS-0001-0203`, `fleet/well-types/T200.md#section 9.3`, `assets/WELL-0001/context.jsonl#CTX-0001-003` |
| **Q2** | Non-producing wells in area | 4 wells in Northeast Block 8 (WELL-0164: 4.1 °C delta, inspector note 'Pump jack not moving'; WELL-0170: 2.9 °C, open repair MNT-0170-031; WELL-0172: 5.7 °C, open repair MNT-0172-028; WELL-0175: 0.4 °C, no reason recorded) | **Table** | ✅ **PASS** | Per-well inspections and maintenance files; explicitly avoids inventing unrecorded causes |
| **Q3** | Temperature trend over 13 weeks | 13 weekly readings (23 Jul to 15 Oct 2026); wellhead vs ambient temperature; marks non-producing readings on 8 Oct and 15 Oct | **Line Chart** | ✅ **PASS** | `assets/WELL-0001/inspections.jsonl` (13 readings) |
| **Q4** | 4-year spill history | 6 confirmed spills totaling 15.1 bbl; excludes rainwater detection INS-0001-0070 (CTX-0001-001) | **Table** | ✅ **PASS** | `assets/WELL-0001/inspections.jsonl`, `assets/WELL-0001/context.jsonl#CTX-0001-001` |
| **Q5** | 2025 downtime days | 21 days from 3 weekly non-producing inspections (24 Jul, 16 Oct, 23 Oct 2025) | Text + Citations | ✅ **PASS** | `assets/WELL-0001/inspections.jsonl`, `fleet/well-types/T200.md#section 9.3` |
| **Q6** | Top downtime wells in area | 3 wells in Northeast Block 7 in last 4 months: WELL-0121 (49 days, T200), WELL-0107 (42 days, T350), WELL-0138 (42 days, T350) | **Bar Chart** | ✅ **PASS** | Weekly non-producing inspections accumulated deterministically (7 days per qualifying inspection) |
| **Q7** | 90-day spills in area | 4 wells in Northeast Block 8 with real spills: WELL-0151 (4.5 bbl), WELL-0165 (1.2 bbl), WELL-0175 (3.9 bbl), WELL-0186 (0.6 bbl) with precise lat/lon | **Map** | ✅ **PASS** | Pad coordinates and inspection detections |
| **Q8** | Spills by area and month | Heatmap matrix for 2026 (Jan–Oct): SW-23 (35), SW-24 (43), NE-7 (37), NE-8 (26). Excludes false positives | **Heatmap** | ✅ **PASS** | Aggregated across all 200 wells, respects context note invalidations |
| **Q9** | Regulatory compliance & open items | WELL-0001 breaches from 11 Jun 2026 spill (SR-01 late report, SR-02 late containment, SR-03 open verification, RC-04 late NOV response). Identifies open flowline RCA and unrecorded planned shut-in | **Table** | ✅ **PASS** | `assets/WELL-0001/regulatory-events.jsonl`, `fleet/sops/spill-response-sop.md`, `fleet/sops/regulatory-compliance-sop.md` |
| **Q10** | Spills exceeding containment limit | 2 spills in Southwest Block 24 in last 90 days exceeding 4-hour limit: WELL-0082 (~7.1 h) and WELL-0100 (~8.1 h) | **Table** | ✅ **PASS** | Text extraction from `maintenance-reports/**/*.md`, `fleet/sops/spill-response-sop.md#section 4 (SR-02)` |
| **Q11** | Conversation memory recall | Michael Turner asks for repair costs of the 3 wells discussed yesterday: WELL-0121 (USD 25,794), WELL-0138 (USD 46,942), WELL-0107 (USD 5,176) | **Table** | ✅ **PASS** | Private memory per user ID; exact sum from `maintenance.jsonl` |
| **Q12** | Raw data correction & re-evaluation | Corrects WELL-0164 15 Oct temp from 24.0 °C to 41.0 °C. Flags conflict with 'Pump jack not moving.' Re-evaluating Q2 removes WELL-0164, returning 3 wells | Response + Table | ✅ **PASS** | `corrections` audit trail (preserves original 24.0 °C); dynamic re-query reflects correction |
| **Q13** | AI analysis correction | Corrects WELL-0151 spill volume from 4.5 bbl to 5.4 bbl. Elevates spill to reportable (SR-01), flags missing written report and 60-day SR-03 verification | Response | ✅ **PASS** | Provenance retained; overrides classification deterministically |
| **Q14** | Well-type rule override | Standard pump jack RCA threshold: 3 repairs. Michael Turner sets T350 threshold to 2. Re-query adds WELL-0120 (T350 with 2 repairs), but excludes WELL-0102 (T200 with 2 repairs) | **Table** | ✅ **PASS** | Scoped strictly to `well_type = 'T350'`; cites user rule vs manual |
| **Q15** | Shared corrections across users | Jessica Reed sees WELL-0164 producing (from Michael Turner's correction) with conflict note. Laura Simmons sees WELL-0151 as only reportable spill in NE-8 | Response | ✅ **PASS** | Corrections table shared across all sessions and users |
| **Q16** | Shared knowledge vs private memory | Jake Morales posts shared note for WELL-0007 workover; Michael Turner sees it. Jessica Reed asks about 'three wells we discussed yesterday'; system states no prior history | Response | ✅ **PASS** | Private memory strictly isolated by `user_id`; shared notes accessible to all |
| **Q17** | Handling conflicting statements | Tyler Hughes claims WELL-0175 is running fine; system checks 15 Oct inspection (0.4 °C cold) and confirms Michael Turner's shut-in, flagging Tyler's statement as unconfirmed. Jake Morales claims WELL-0001 online; system checks inspection and flags unconfirmed | Response | ✅ **PASS** | Flags conflict, cites conflicting telemetry, records unconfirmed claims without overwriting ground truth |
| **Q18** | Disagreements on AI analysis | Evaluates 20 Aug spill on WELL-0101: Ryan Brooks (CTX-0101-002, produced water) vs Chris Dalton (CTX-0101-003, crude). Because MNT-0101-029 executed and no formal invalidation filed, confirms spill but surfaces dispute | Response | ✅ **PASS** | Cites both human notes, inspection, and maintenance report |

---

## 2. Verification Checklist

- [x] **Ingestion Idempotency:** Tested with repeated ingestion runs, row counts identical.
- [x] **Well-Type Thresholds:** Dynamically parsed from markdown manuals (T200: 15.0 °C; T350: 20.0 °C).
- [x] **Downtime Calculation:** 7 days per weekly non-producing inspection; consecutive accumulation; missed inspection = 0; repair time excluded; planned shut-in excluded from unplanned downtime.
- [x] **Spill Compliance:** Thresholds (1, 5, 25 bbl) from SOP-SR; 24h reporting deadline; 4h containment limit; 60d agency verification; false positives excluded; valid corrections override classification while preserving original.
- [x] **Memory Isolation:** Strict partition of conversation history by `user_id`.
- [x] **Conflict Transparency:** Discrepancies between telemetry, human notes, and user claims are surfaced with conflict banners and multi-source citations.
- [x] **Visual Generation:** Generates valid schema-compliant specs for card, table, line, bar, map, and heatmap with responsive table view-switchers.
