# Five-minute demo narration

Use this with `node scripts/demo_driver.mjs --five-minute`. The live run uses `LLM_PROVIDER=rules`, the final test dataset, and the isolated demo database. Press Enter at each cue after finishing that part. The Playwright video is silent; use your own microphone and screen recorder for narration.

## 0:00–1:55 — Architecture

The slide highlights the five pipeline stages in order.

- The released dataset has 600 wells across seven areas, plus inspections, maintenance, operator notes, regulator records, and operating documents.
- Structured records go into SQLite, while manuals, reports, and notes are indexed for text retrieval.
- The app retrieves evidence with validated tools. Python calculates metrics; the model can interpret and explain but does not calculate or invent citations.

## 1:55–2:55 — Live app overview and status example

Ask: “Show the latest inspection and current production status for WELL-0332 as a status card.” Show the user picker and then expand the citations.

- User identities come from the loaded dataset’s `/users` endpoint; the final dataset has 27 users.
- The backend is running with the deterministic rules provider, so this recording does not use Gemini quota.
- The card uses the latest inspection, dated 14 January 2027, and the T200 manual threshold.
- The displayed temperature delta is 0.5 °C against a 15 °C threshold, so the current result says the well is not producing.
- Expand citations to show the inspection and rule source.

## 2:55–3:23 — Area status table

Ask: “Which wells in Southwest Block 23 are not producing oil right now? Show a table.”

- The table is calculated from the inspections and well-type thresholds in the loaded dataset.
- This rules-path response found seven wells for the query and includes citations to the source records.
- It uses the same status calculation across an area rather than a written answer for one example.

## 3:23–4:06 — Final-question coverage, Q1–Q6

Show the committed first half of [`final_triage.md`](final_triage.md).

- The data has no reservoir-pressure or oil-production-rate field, so those two questions cannot be answered from this release.
- The raw records can support gas-response, bypass, spill-letter, and status-conflict checks.
- Those checks are not yet all surfaced as complete `/chat` answers, so the triage marks their app coverage as partial.

## 4:06–4:50 — Final-question coverage, Q7–Q11

Show the second half of the triage table and leave it on screen.

- The dataset includes operator notes, recall records, repairs, and temperature readings for these questions.
- The current app still has gaps in ranking, multi-turn recall, repair-waiting breakdowns, and regional temperature summaries.
- This is the verified boundary of the demo: the two live examples work on real records, while the remaining gaps are visible for review.
