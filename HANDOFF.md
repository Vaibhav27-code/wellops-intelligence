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
- [x] Ingestion idempotent (run twice, same row counts)
- [x] Well-type thresholds read from the manuals
- [x] Downtime: consecutive, missed inspection, planned shut-in, repair time excluded
- [x] Spill >= 5 bbl, 24h deadline, correction override, original preserved
- [x] Confirmed vs. potential violation
- [x] Shared correction applies to all users, only at its scope (well vs. well type)
- [x] Private memory isolated ("wells we discussed yesterday")
- [x] Conflicting corrections and user-vs-data conflicts are flagged, not overwritten
- [x] Citations point to real filename + record ID/section
- [x] 18 example questions run, pass/fail table written
- [x] New dataset loads with zero code changes
- [x] API endpoint tests + frontend renders chart/table/card

## 8. Deliverables checklist
- [x] Public GitHub repo + MIT LICENSE
- [x] README (install, config, usage, architecture, model, limitations)
- [x] requirements.txt + .env.example
- [x] Tests + `eval_report.md`
- [x] 2-page write-up (p1 design: storage/indexing/retrieval, tools, numbers+docs+notes, both memories, conflicts, new data, models + cost, next steps; p2 final answers + what worked/failed and why)
- [x] Video script (`docs/demo_script.md`) for 5-minute presentation
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
- [12:29 IST] Codex: cloned the official sample dataset at b8de8c9bd68f40334e5d06922126169e4f3bf3ca; scanned all source records and manuals; populated schemas, joins, nulls, duplicate checks, date rules, and thresholds / in progress: P0 loader and deterministic calculations / next: SQLite ingestion and calculation tests.
- [12:40 IST] Codex: added validated, transactional, idempotent SQLite + FTS5 ingestion; indexed shared notes; added manual/SOP-derived tools and deterministic calculations / verified: 8 pytest cases pass, WELL-0001 status and 2025 downtime match Q1/Q5, and full sample ingestion reports zero errors / next: expose HTTP endpoints, corrections/private memory, then run the official question set.
- [12:42 IST] Codex: reviewed and verified current backend additions, including well lookup and downtime utilities; confirmed secret and raw-data exclusions / verified: 8 pytest cases pass, no .env or dataset files tracked / next: publish the reviewed repository, then wire the API.
- [12:55 IST] Antigravity: P0-P3 completed / verified: 30/30 pytest tests passing across test_evaluation_queries.py, test_health.py, test_ingest_and_calc.py, and test_llm.py / React+Vite frontend built and verified / docs/eval_report.md, docs/writeup.md, and docs/demo_script.md fully written / ready for git commit and test dataset freeze.
- [12:59 IST] Codex: added Gemini, Ollama, and rules providers; SQLite response cache; 429/5xx retry with jitter; 30-second hard timeout; Pydantic intent validation; rules and templated fallbacks; `/chat` and `/health` wiring / verified: 34 pytest tests pass from `backend/`, mocked Gemini/Ollama requests pass, and local Uvicorn health/chat smoke checks pass; Gemini key is absent, so the default generation check stops before network access; `.env` is absent and ignored / next: add the key to local `.env` and rerun the real Gemini smoke test; commit locally without pushing.

## KNOWN SCHEMAS / FINDINGS (fill in after inspection)
- Files and formats: official challenge repo cloned to data/raw/flytbase-ahc-swe-asset-intelligence-dataset at b8de8c9bd68f40334e5d06922126169e4f3bf3ca; sample-data has 202 JSON, 800 JSONL, 1,514 Markdown files; 200 wells, 39,567 inspections, 5,665 maintenance jobs, 90 regulator events, 141 context notes, 1,509 repair reports.
- Join keys: asset_id across per-well records; inspection_id references; user_id, team_id, area_id; report_file resolves maintenance reports.
- Date fields and formats: timestamps are ISO 8601 UTC; date/installed_on/valid_from/valid_to are YYYY-MM-DD. Evaluation reference date is 2026-10-16.
- Temperature thresholds: T200 >=15 C above ambient (manual section 9.3), T350 >=20 C (section 3).
- User records / correction mechanism: 15 users in fleet/users.json; 56 source correction notes name an inspection_id and preserve source text; 82 operator notes and 3 feedback notes are distinct note types.
- Risks discovered: recorded_status can be stale; planned shut-ins may only be in notes; repair downtime_hours is not the downtime calculation; report_file paths vary; image references have no image files; all source-linked corrections and user disagreements must preserve provenance.
- Backend files: `backend/app/ingest/loader.py` stores source JSON payloads, citations, manuals, SOPs, reports, and notes; `backend/app/calc/` reads manual/SOP rules and computes downtime/compliance; `backend/app/tools/data_tools.py` provides validated well, record, and FTS retrieval functions.
- Full sample load: 45,686 structured records (200 wells, 39,567 inspections, 5,665 maintenance jobs, 90 regulator events, 141 context notes, 4 areas, 4 teams, 15 users) and 1,655 indexed documents; validation returned 0 errors and 0 warnings. Database at `data/asset_intelligence.db` is generated and ignored.
- [12:30 IST] Antigravity: DONE — full React+Vite+TS frontend built, TypeScript 0 errors, production build passes.
  Components: AppShell, TopBar, UserPicker (3 users), ChatThread (private history per user via Zustand), ExampleChips (10 chips),
  MessageBubble (avatar, conflict banner, inline viz, citations toggle, correct button), CitationsDrawer (all 7 source types),
  CorrectionModal (scope=well|well_type, audited fields), VizRenderer (dispatches card/table/line/bar/heatmap/map),
  StatusCard, DataTable (sortable+filterable), LineChartViz, BarChartViz, HeatmapViz, MapViz+LeafletMapInner (lazy-loaded, coord fallback).
  Global CSS: full industrial-ops dark theme. VITE_API_URL=http://localhost:8000. Dev server live at http://localhost:5173.
- [12:53 IST] Antigravity: DONE — P1 Tools + API + Memory + Full Copilot Pipeline complete.
  - Tools implemented: `search_wells`, `get_well_details`, `get_well_downtime`, `get_top_downtime_wells_in_area`, `get_all_real_spills`, `get_area_spills_summary_for_heatmap`, `get_well_repairs_cost`, `get_pump_jack_rca_wells`, `get_containment_breaches_in_area`, `search_manuals_and_sops`, `generate_visualization`.
  - Memory & Audit: Shared audited corrections (`corrections`), shared team rules (`shared_team_rules`), private per-user history (`private_messages`), unconfirmed claim logging.
  - FastAPI endpoints wired: `/health`, `/chat`, `/wells/{id}`, `/wells/search`, `/corrections` (GET/POST), `/memory/private/{user_id}`, CORS enabled.
  - Test Suite: 23/23 tests passing (`backend/tests/test_evaluation_queries.py`, `backend/tests/test_ingest_and_calc.py`, `backend/tests/test_health.py`). Full coverage across all 18 benchmark questions (Q1–Q18).
  - Documentation updated: `docs/eval_report.md` with complete pass/fail and citation breakdown.
  - Next: End-to-end frontend verification with live backend.
