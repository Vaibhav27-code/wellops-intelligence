# Project instructions

Follow these constraints for all implementation and evaluation work in this repository:

1. Never invent source columns, results, citations, or expected answers. Inspect the real files first.
2. Never hardcode answers to example questions. Implement logic that generalizes.
3. All arithmetic, including downtime, spill deadlines, and costs, must be deterministic Python, never LLM-generated.
4. Read thresholds from the manuals/SOPs for each well type. Never assume thresholds.
5. Downtime rules: a weekly inspection showing non-production counts as 7 days; consecutive qualifying inspections accumulate; a missed inspection counts as 0; repair duration is not downtime; planned shut-in notes are not unplanned downtime.
6. Spill rules: spills of at least 5 bbl must be reported within 24 hours. A later valid correction overrides classification while preserving the original record.
7. Corrections must be scoped to one well or a well type and audited with author, time, reason, original value, corrected value, and evidence.
8. Private memory must never be shared across users.
9. API keys belong only in environment variables. Never commit .env.
10. Ingestion must be idempotent and driven by the inspected source format so same-format test data can load without code changes.
11. Do not claim a feature works until it has been run.
12. Keep raw source files unchanged. Record derived/normalized data separately.
