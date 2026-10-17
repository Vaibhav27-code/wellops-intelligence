# Asset Intelligence Copilot

Evidence-grounded operations support copilot for oil-well fleets, built for FlytBase Hacktoberfest 2026. The system combines high-performance SQLite + FTS5 search, deterministic Python calculation engines (downtime, spills, compliance, costs), two-level memory (audited shared corrections + isolated private history), and an industrial React + Vite frontend with dynamic inline visualizations (Status Cards, Tables, Line Charts, Bar Charts, Maps, Heatmaps).

## Architecture

```
Question → Intent & Entity Extraction (LLM / Rules) → Deterministic Tools (SQLite + FTS5)
         → Deterministic Python Calculations (rules.py, downtime.py, compliance.py)
         → Evidence & Conflict Assembly → Natural Language Answer (LLM)
         → Visualization Spec (Card/Table/Line/Bar/Map/Heatmap) → React Ops UI
```

## Key Principles & Guarantees

1. **Zero Hallucination on Numbers:** All arithmetic (downtime accumulation, spill reporting deadlines, repair costs, SOP temperature delta thresholds) is computed by deterministic Python code, never by the LLM.
2. **Dynamic Manual/SOP Thresholds:** Thresholds (T200 $\ge 15.0\,^\circ\text{C}$ delta, T350 $\ge 20.0\,^\circ\text{C}$ delta, spill reporting $\ge 5\,\text{bbl}$ in 24 hours) are parsed dynamically from the markdown fleet manuals and SOPs.
3. **Verified Provenance & Citations:** Every answer cites the exact filename, record ID/section, and excerpt.
4. **Two-Level Memory:** Shared audited corrections and operational notes apply across all users; private user chat histories are strictly partitioned by `user_id` with zero cross-user leakage.
5. **Conflict Transparency:** Discrepancies between telemetry, human field notes, and user statements are flagged with multi-source evidence banners rather than overwritten.
6. **Format-Driven Idempotent Ingestion:** Re-running ingestion drops and rebuilds tables transactionally, producing identical row counts. Drops of unseen test datasets in the same format load with zero code changes.

## Quick Start

### 1. Backend Setup & Test Suite
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
uvicorn backend.app.main:app --reload --port 8000
```
- Health check: <http://127.0.0.1:8000/health>
- Interactive Swagger docs: <http://127.0.0.1:8000/docs>

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run build   # Type-check and production build (0 errors)
npm run dev     # Starts Vite dev server on http://localhost:5173
```

### 3. Load the Dataset
Clone the official sample dataset into the ignored `data/raw/` directory:
```powershell
git clone https://github.com/FlytBaseAILabs/flytbase-ahc-swe-asset-intelligence-dataset data/raw/flytbase-ahc-swe-asset-intelligence-dataset
python -m backend.app.ingest
```

## Model

The default Gemini model is `gemini-3.5-flash-lite`. A model-not-found response is not retried or cached; the request uses deterministic rules and templated wording instead. The application also supports Ollama and the deterministic rules provider.

## Automated Verification

The test suite validates:
- Ingestion idempotency across 45,686 records (200 wells, 39,567 inspections, 5,665 maintenance jobs, 90 regulator events, 141 context notes, 1,514 FTS5 documents).
- Deterministic downtime accumulation (7 days per qualifying weekly non-production, repair time excluded, planned shut-in excluded).
- Spill reporting compliance ($\ge 5\,\text{bbl}$ within 24 hours, containment deadline compliance, correction overrides).
- All 18 benchmark evaluation scenarios in `docs/eval_report.md`.
- Strict user-to-user memory isolation and audited correction propagation.

Run all tests:
```powershell
pytest -v
```

## Documentation
- `HANDOFF.md`: Project status, operational rules, and time plan.
- `docs/eval_report.md`: Complete evaluation report across Q1–Q18 with pass/fail verification.
- `docs/writeup.md`: 2-page system architecture, design decisions, and results report.
- `docs/demo_script.md`: 5-minute timed demo video script covering all operational flows.

## License
MIT

