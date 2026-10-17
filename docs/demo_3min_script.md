# Three-minute demo narration

Use the matching numbered screenshot in `docs/screenshots/demo/` as a reference. The driver pauses for four seconds by default, then waits for Enter in its terminal so the speaker controls the pace. The automatic dry run targets 3:00.

## 0:00–0:25 — Architecture

**Show:** `00_architecture.png`.

- The sample brings together inspections, repairs, regulator events, operator notes, and manuals.
- Structured records go into SQLite; manuals and notes are indexed for text search.
- Python tools calculate the numbers and attach the records that support each result.

## 0:25–1:15 — Area downtime

**Show:** `01_downtime_bar_evidence.png`, then `02_downtime_table.png`. User: Michael Turner.

Ask: “Which three wells in Northeast Block 7 had the most downtime in the last four months?”

- The chart ranks wells using weekly inspection records and the downtime rule from the project handoff.
- I can open the source citations and the calculation rule, then switch the same result to a table.
- The model can interpret the question, but the metric itself comes from deterministic Python.

## 1:15–1:50 — Status conflict

**Show:** `03_status_conflict_card.png`. User: Tyler Hughes.

Ask: “Tyler Hughes says WELL-0175 is running fine and not shut in. Is that correct? Show its status card.”

- The latest inspection reports a low temperature difference and a note that the pump jack is not moving.
- The status card shows the current rule-based state, while the banner marks the conflicting claim for field verification.
- The freshness label comes from the latest inspection timestamp in the loaded database.

## 1:50–2:25 — Shared correction

**Show:** `04_correction_original_preserved.png`, `05_correction_audit_panel.png`, then `06_shared_correction_area.png`.

- As Michael, I record 24.0 °C to 41.0 °C for WELL-0164, with a reason and a single-well scope.
- The audit view keeps the original value, corrected value, author, and reason together.
- Jessica’s area query uses that shared correction. The original inspection note remains visible as a conflict instead of being erased.

## 2:25–2:45 — Private memory

**Show:** `07_jessica_private_no_history.png`, then `08_michael_private_recall_costs.png`.

- Jessica has no earlier request for a specific three-well set, so her recall question returns no record.
- Michael’s earlier question did ask for three wells, so his private history can resolve the follow-up.
- The repair costs are calculated from maintenance records after the wells are recovered from his history.

## 2:45–3:00 — Generalization

**Show:** `09_unseen_area_repair_costs.png` and leave the app on that result.

Ask: “Which wells in Southwest Block 23 had the highest repair costs in 2026?”

- This question uses a different area and metric from the downtime example.
- The answer comes from the same parameterized tools and cites the underlying records.

