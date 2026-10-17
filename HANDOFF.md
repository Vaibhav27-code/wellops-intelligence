# HANDOFF.md: Asset Intelligence Copilot (FlytBase, Hacktoberfest 2026)

Paste this file into Codex, Antigravity, or Cursor at the start of every session. Update the STATUS LOG at the bottom before switching tools.

Date: Sat 17 Oct 2026. Real deadline: 6:00 PM IST. Personal finish target: 5:30 PM IST.

---

## 1. Mission (one paragraph)
Chat copilot that answers plain-English questions about ~200 oil wells using wells, inspections, repairs, regulator events, human notes, manuals/SOPs. Every answer cites evidence. UI shows the right inline visual (status card, table, line chart, bar chart, map, heatmap). Two-level memory (shared well corrections + private per-user history). Honest about conflicts. Must work on an UNSEEN test dataset (same format) released in the final 2 hours.

## 2. Hard rules (all tools must follow)
1. Never invent columns, results, citations, or expected answers. Inspect real files first.
2. Never hardcode answers to example questions. Logic must generalize.
3. All arithmetic (downtime, spill deadlines, costs) is deterministic Python, never the LLM.
4. Thresholds come from the manuals/SOPs (per well type). Never assume them.
5. Downtime: each weekly inspection that shows non-production = 7 days. Consecutive ones accumulate. Missed inspection = 0. Repair duration is NOT downtime. Planned shut-in notes mean not unplanned.
6. Spill >= 5 bbl must be reported within 24h. A later valid correction overrides the classification but the original record is preserved.
7. Corrections are scoped (one well vs. well type) and audited (author, time, reason, original, corrected, evidence).
8. Private memory never leaks across users.
9. API keys only in env vars. Never commit `.env`.
10. Ingestion is idempotent and format-driven so the test dataset loads with no code changes.
11. Do not claim anything works until it has been run.

## 3. Time plan (IST). Hard stops matter more than perfection

| Time | Block | Output | Owner tool |
|---|---|---|---|
| 12:10-12:35 | Inspect files + Dataset Guide + Example Questions, repo skeleton, venv, git init, LICENSE (MIT) | `data_inventory.md`, schemas noted below | Codex |
| 12:35-1:45 | P0: ingestion to SQLite, validation report, downtime + spill/compliance functions + unit tests | green `pytest` on calc + ingestion | Codex |
| 1:45-2:00 | Break / buffer / commit | | you |
| 2:00-3:00 | P1: tools (search_*, get_well_details, calculate_downtime...), FTS/vector over manuals + notes + repair reports, QA pipeline, citations, LLM wiring | `/chat` endpoint answering with citations | Codex (backend) + Cursor (small edits) |
| 2:15-3:15 | P2: React+Vite UI in parallel: user picker, chat, chips, status card, table, line + bar chart, citations drawer | working UI against mocked-then-real API | Antigravity |
| 3:00-3:40 | P3: corrections (shared) + private memory + conflict messages | isolation + scope tests | Codex |
| 3:40-4:00 | FREEZE FEATURES. Run all 18 example questions, record pass/fail, fix top 3 bugs | `eval_report.md` | Codex + Antigravity |
| ~4:00 | TEST DATASET RELEASED. Drop into data dir, rerun ingest, run validation, no code changes | | Codex |
| 4:00-4:45 | Final questions: run, record answers, fix real bugs (no hardcoding) | answers saved to `results.md` | all |
| 4:15-4:45 | Record 5-min video while fixing (record last run at ~4:45) | video file | you |
| 4:45-5:15 | 2-page write-up (page 1 design, page 2 final results), README, .env.example, push public repo | PDF + repo link | Cursor/Claude |
| 5:15-5:30 | Submit on OrganizerHQ. STOP CODING | submitted | you |
| 5:30-6:00 | Buffer only (upload failures, link fixes) | | |

Note: the test dataset release time is approximate. If it arrives earlier, switch immediately. The vertical slice (ingest -> downtime -> cited answer -> UI) must exist by 3:00 even if ugly.

## 4. Stack
- Backend: Python, FastAPI, pandas, SQLite (structured + corrections + memory), SQLite FTS5 or ChromaDB/FAISS for documents (use FTS5 first, since it is the least risky).
- Frontend: React + Vite + TypeScript, Recharts, Leaflet (only if coordinates are usable).
- LLM: whichever API key is available in env (inspect env var names only, never print values). Used only for intent extraction, tool selection, and answer wording.
- Layout:
```
/backend   app/ (api, tools, calc, ingest, memory, llm)  tests/
/frontend  src/
/data      (raw files, not edited)
/docs      eval_report.md, writeup.md, demo_script.md
README.md LICENSE .env.example requirements.txt HANDOFF.md
```

## 5. Required tools (backend functions with validated inputs and sourced outputs)
search_wells, get_well_details, calculate_downtime, compare_wells, search_inspections, search_repairs, search_regulator_events, search_manuals_and_sops, search_human_notes, record_correction, retrieve_shared_memory, retrieve_private_memory, generate_visualization.

Pipeline: question -> intent/entities -> validated tool choice -> retrieval -> deterministic calc -> evidence + conflict assembly -> answer -> visualization spec -> cited response.

Visualization spec (JSON): `{type: card|table|line|bar|map|heatmap, title, data, x, y, units}` built from real query results, with a table fallback.

## 6. Skills per tool (what to ask each one to do)

### Codex (backend, tests, long agentic runs)
Use for: ingestion, calculations, API, test suites, eval runs, bug-fix loops.
Setup: put the rules from section 2 into `AGENTS.md` at repo root so it always loads.
Skills to invoke by prompt:
- Data inspection: read every file, print schemas, join keys, date formats, null rates, duplicates, write `data_inventory.md`.
- TDD for calculations: write pytest cases for per-type thresholds, missed inspections, planned shut-in, consecutive weeks, spill correction override, deadline met/missed, then implement until green.
- Eval loop: script that runs each example question through the API, diffs against expected answers, writes pass/fail table, then fixes the logic (never the expected answer).
- Security/reliability review: input validation, parameterized SQL only, no secrets in logs, `/health` endpoint.
- Repo hygiene: requirements.txt, .env.example, README, LICENSE.

### Antigravity (frontend, browser testing, parallel agents)
Use for: React UI, visual verification, end-to-end UI testing via its browser agent, running a second agent in parallel with Codex on a separate folder.
Setup: put UI rules in its rules/instructions area (commonly `.agent/rules`; verify in your version).
Skills to invoke by prompt:
- Build UI from an API contract: user picker, chat thread, example chips (from the real questions), loading + error states, expandable citations, correction button.
- Generative components: status card, sortable/filterable table, line chart, bar chart, heatmap (area x month), Leaflet map, a view-switcher ("show as table").
- Browser E2E: open the app, switch users, ask a question, verify the chart renders from real data, verify private history does not leak between users, screenshot results.
- Responsive/polish pass: industrial-ops look, readable on a projector for the demo.
Work only inside `/frontend` to avoid merge conflicts with Codex.

### Cursor (free tier, limited requests)
Use sparingly for: small targeted edits, refactors, quick fixes, README/write-up polish. Free-tier request limits run out, so don't burn them on big generation. Add the rules from section 2 to `.cursor/rules`.

### Ownership to avoid conflicts
Codex owns `/backend`. Antigravity owns `/frontend`. Cursor does small edits anywhere but commit first. Commit before every tool switch, with small commits and clear messages.

## 7. Test checklist (must be green before the 4:00 freeze)
- [ ] Ingestion idempotent (run twice, same row counts)
- [ ] Well-type thresholds read from the manuals
- [ ] Downtime: consecutive, missed inspection, planned shut-in, repair time excluded
- [ ] Spill >= 5 bbl, 24h deadline, correction override, original preserved
- [ ] Confirmed vs. potential violation
- [ ] Shared correction applies to all users, only at its scope (well vs. well type)
- [ ] Private memory isolated ("wells we discussed yesterday")
- [ ] Conflicting corrections and user-vs-data conflicts are flagged, not overwritten
- [ ] Citations point to real filename + record ID/section
- [ ] 18 example questions run, pass/fail table written
- [ ] New dataset loads with zero code changes
- [ ] API endpoint tests + frontend renders chart/table/card

## 8. Deliverables checklist
- [ ] Public GitHub repo + MIT LICENSE
- [ ] README (install, config, usage, architecture, model, limitations)
- [ ] requirements.txt + .env.example
- [ ] Tests + `eval_report.md`
- [ ] 2-page write-up (p1 design: storage/indexing/retrieval, tools, numbers+docs+notes, both memories, conflicts, new data, models + cost, next steps; p2 final answers + what worked/failed and why)
- [ ] Video <= 5 min, your own voice: how it's built, then one real question end to end
- [ ] Submitted on OrganizerHQ before 5:30 (deadline 6:00)

## 9. Demo script (5 min)
1. 0:00-0:45 Architecture: data -> SQLite + FTS -> tools -> deterministic calcs -> LLM wording -> cited UI.
2. 0:45-2:30 Live question: "Which wells in my area were down the longest this summer, and why?" Show chart/table, expand citations, show downtime calc and cause from repairs/notes.
3. 2:30-3:30 Correction: correct a spill value as one user, switch user, show the change applies, show the original preserved.
4. 3:30-4:15 Private memory: "the wells we discussed yesterday" for user A vs. user B.
5. 4:15-5:00 New-data robustness, one limitation, next steps.

## 10. Copy-paste kickoff prompt (any tool)
> Read HANDOFF.md fully. Follow section 2 rules. Inspect the real data files first, then continue from the last entry in STATUS LOG. Work in small verified steps, run tests, commit, and update STATUS LOG when done.

---

## STATUS LOG (update before every tool switch)
Format: `[time] tool: done / in progress / blocked / next`

- [12:10] start: source inspection and project setup pending.
- [12:20 IST] Codex: initial listing was incomplete; follow-up scan found the React/Vite starter and placeholder docs, but no dataset, Dataset Guide, official question set, or manuals/SOPs / in progress: data-independent scaffold / next: inspect source bundle when supplied.
- [12:22 IST] Codex: inventory and handoff corrected to distinguish provisional code from source data; backend health stub is ready for verification / next: run backend check with Python 3.11 if available.
- [12:25 IST] Codex: project virtual environment created with Python 3.11; health endpoint test passed (1 passed, Starlette deprecation warning) / done: data-independent scaffold / next: inspect real source bundle when supplied.

## KNOWN SCHEMAS / FINDINGS (fill in after inspection)
- Files and formats: no source files are present in data/raw; repository has a React/Vite starter, provisional TypeScript domain types, a FastAPI /health stub, and placeholder docs.
- Join keys: unknown; source data is not available.
- Date fields and formats: unknown; source data is not available.
- Temperature thresholds per well type (with manual section/page): unknown; manuals/SOPs are not available.
- User records / correction mechanism: no source records; frontend currently has in-memory sample users, histories, and corrections only.
- Risks discovered: source schema, join keys, date formats, thresholds, and official expected questions are unavailable; frontend types and 10 sample prompt chips are provisional and unverified.
- [12:30 IST] Antigravity: DONE — full React+Vite+TS frontend built, TypeScript 0 errors, production build passes.
  Components: AppShell, TopBar, UserPicker (3 users), ChatThread (private history per user via Zustand), ExampleChips (10 chips),
  MessageBubble (avatar, conflict banner, inline viz, citations toggle, correct button), CitationsDrawer (all 7 source types),
  CorrectionModal (scope=well|well_type, audited fields), VizRenderer (dispatches card/table/line/bar/heatmap/map),
  StatusCard, DataTable (sortable+filterable), LineChartViz, BarChartViz, HeatmapViz, MapViz+LeafletMapInner (lazy-loaded, coord fallback).
  Global CSS: full industrial-ops dark theme. VITE_API_URL=http://localhost:8000. Dev server live at http://localhost:5173.
  Committed: 76bbcdd. Next: wire to real backend once Codex completes ingestion + tools (P1).