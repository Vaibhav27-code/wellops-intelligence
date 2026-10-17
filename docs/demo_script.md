# 5-Minute Demo Script: Asset Intelligence Copilot

**Target Duration:** 5 minutes (300 seconds)  
**Presenter:** Single speaker (live voiceover or recorded video)  
**App URLs:** Frontend: `http://localhost:5173` | Backend: `http://localhost:8000/docs`

---

## Pre-Demo Checklist
- [ ] Backend running (`uvicorn backend.app.main:app --port 8000`)
- [ ] Frontend running (`cd frontend && npm run dev`)
- [ ] Browser window open to `http://localhost:5173`
- [ ] Database clean or in known state (`data/asset_intelligence.db`)

---

## Segment 1: Architecture & Engineering Principles (0:00 – 0:45)
**Visual:** Show high-level architecture diagram or README architecture flow.

> "Hello, this is the Asset Intelligence Copilot built for FlytBase Hacktoberfest 2026.
>
> In industrial operations, oilfield operators manage hundreds of assets with telemetry, maintenance tickets, regulatory events, drone inspections, and engineering SOPs.
>
> The core design principle of our copilot is **zero hallucination on numbers and ground-truth isolation**. 
> - All arithmetic—downtime accumulation, spill reporting deadlines, repair costs, and SOP threshold checks—is executed by **deterministic Python code**, never by an LLM.
> - Data is stored in SQLite with full-text search indexing (FTS5) across all markdown manuals, human context notes, and maintenance work orders.
> - The LLM is used strictly for intent classification, entity extraction, and synthesis of natural-language responses.
> - Every answer cites the exact filename, record ID, and relevant excerpt.
> - Let's see it in action across four real production workflows."

---

## Segment 2: Live Question & Analytics with Inline Visualization (0:45 – 2:30)
**Visual:** In UI, select User **Michael Turner** (Production Engineer). Click the chip or type:  
`"Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months?"`

> "We are logged in as Michael Turner. Let's ask: *'Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months?'*
>
> Notice what happens instantly:
> 1. The copilot extracts the area **Northeast Block 7**, the time window of the last 4 months, and identifies the **downtime** intent.
> 2. It queries weekly inspection records for all wells in that block, checking the differential temperature against each well's specific manual—15.0 °C for T200 wells and 20.0 °C for T350 wells.
> 3. Each weekly inspection showing non-production accumulates exactly 7 days of downtime.
> 4. It surfaces a clear **Bar Chart** showing:
>    - **WELL-0121** with **49 days** of downtime
>    - **WELL-0107** with **42 days**
>    - **WELL-0138** with **42 days**
> 5. We can toggle the view switch to see this as a structured **Data Table**.
> 6. Opening the **Citations Drawer**, you see the exact inspection IDs (`INS-0121-...`), dates, and telemetry deltas backing every single day."

---

## Segment 3: Audited Corrections & Real-Time Propagation (2:30 – 3:30)
**Visual:** Show raw inspection for `WELL-0151` (spill volume 4.5 bbl, classified under 5 bbl non-reportable). Click "Submit Correction" or ask the correction query:  
`"The field crew re-measured the spill on WELL-0151 at 5.4 bbl, not 4.5 bbl."`

> "Now let's demonstrate shared audited corrections.
>
> On WELL-0151, an automated inspection estimated an oil release of 4.5 barrels. Because that is under the 5.0 barrel threshold in SOP-SR-01, it was classified as non-reportable.
>
> But field crew measured 5.4 barrels on site. We enter this correction as Michael Turner.
>
> Watch the system response:
> - The original raw record (4.5 bbl) is **fully preserved** in the database audit log.
> - A new verified correction record is created with author, timestamp, reason, original value, and new value.
> - The spill classification is deterministically updated to **Reportable (>= 5 bbl)**.
> - The compliance engine alerts us that this spill now requires a **24-hour formal regulatory report** and **60-day agency verification**.
>
> If we switch user to **Laura Simmons** and ask: *'Which spills in Northeast Block 8 were reportable in the last 90 days?'*, Laura immediately sees WELL-0151 with the updated 5.4 bbl, while citing Michael Turner's audited correction. Ground truth updates for everyone without modifying the raw source files."

---

## Segment 4: Two-Level Memory & Cross-User Privacy Isolation (3:30 – 4:15)
**Visual:** Switch back to **Michael Turner**. Ask:  
`"For the three wells we discussed yesterday, what have repairs cost this year?"`  
Then switch to **Jessica Reed** and ask the identical question.

> "Our system features two-level memory: **shared operational knowledge** and **strictly isolated private user history**.
>
> As Michael Turner, we previously discussed the three highest downtime wells in NE Block 7: WELL-0121, WELL-0107, and WELL-0138.
>
> When Michael asks: *'For the three wells we discussed yesterday, what have repairs cost this year?'*, the private memory store retrieves those 3 specific wells from Michael's conversation history, executes deterministic SQL queries on their `maintenance.jsonl` work orders, and returns exact costs:
> - WELL-0138: $46,942
> - WELL-0121: $25,794
> - WELL-0107: $5,176
> - Total: $77,912
>
> Now, we switch to **Jessica Reed**, who has had no prior discussion about these assets, and ask the exact same prompt: *'For the three wells we discussed yesterday, what have repairs cost this year?'*
>
> Notice the response: the copilot reports that **no previous discussion exists for Jessica**, completely protecting Michael's private session. Zero data leakage across users."

---

## Segment 5: Conflict Handling, Robustness, & Conclusion (4:15 – 5:00)
**Visual:** Show conflicting statement handling (e.g. asking if WELL-0175 is running fine when telemetry says cold). Show test suite running (30/30 passed).

> "Finally, let's look at conflict handling and test robustness:
> - When a user makes a claim that contradicts telemetry—such as claiming a cold well is running fine—the copilot does not overwrite facts. It acknowledges the user's note, compares it against the latest sensor reading, and highlights the conflict transparently.
> - For unseen test datasets, our ingestion pipeline is **100% format-driven and idempotent**. When new files are dropped into the data folder, re-running ingestion reloads all tables without a single code change.
> - Our automated test suite covers all 18 benchmark evaluation queries, compliance thresholds, downtime math, and memory isolation with 100% green tests.
>
> Thank you, and we look forward to your questions!"
