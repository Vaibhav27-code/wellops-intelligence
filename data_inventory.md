# Data inventory

Inventory date: 2026-10-17 (IST)
Workspace scanned: D:\Hactoberfest

## Findings

The repository contains a React/Vite starter and a FastAPI health stub. The data directory contains no source dataset. No Dataset Guide, official example-question set, manuals, or SOPs were found. The three files under docs are empty submission placeholders, not source evidence.

The frontend currently has provisional domain interfaces and 10 draft prompt chips in frontend/src/types/index.ts and frontend/src/store/index.ts. These were not validated against source records and must not be treated as source columns or the official 18-question evaluation set.

No source schemas, join keys, date formats, well types, regulatory thresholds, or source citation identifiers can be established yet.

| Source | Files found | Format / schema | Status |
|---|---:|---|---|
| Wells | 0 | Unknown | Awaiting source data |
| Inspections | 0 | Unknown | Awaiting source data |
| Repairs | 0 | Unknown | Awaiting source data |
| Regulator events | 0 | Unknown | Awaiting source data |
| Human notes | 0 | Unknown | Awaiting source data |
| Manuals / SOPs | 0 | Unknown | Awaiting source data |
| Dataset Guide | 0 | Unknown | Awaiting source data |
| Official example questions | 0 | Unknown | Awaiting source data |

## Existing code scaffold

- backend/app/main.py exposes a FastAPI /health route; backend/tests/test_health.py covers that route.
- frontend is a React + TypeScript + Vite starter. Its current domain types and sample users/questions are provisional.
- docs/eval_report.md, docs/writeup.md, and docs/demo_script.md are placeholders.

## Next inspection

When the source bundle is supplied, enumerate every data/document file, identify formats and schemas, record join keys, date formats, null rates, duplicates, and citation identifiers, then derive well-type thresholds only from the manuals/SOPs. Update this inventory with evidence before implementing source-specific ingestion or calculations.
