# Asset Intelligence Copilot

Evidence-grounded operations support for the fictional FlytBase oil-well fleet. The backend ingests structured records and manuals into SQLite + FTS5, calculates fleet metrics deterministically, and returns cited answers with a visualization specification. A React + Vite frontend renders cards, tables, charts, maps, and heatmaps.

## Architecture

```text
Question → validated intent (Gemini / Ollama / rules) → parameterized SQLite tools
         → deterministic calculations → citations and conflicts
         → optional LLM wording → visualization specification → React UI
```

LLMs may extract intent/entities and reword completed results. They do not calculate values. The metric tool accepts filters for area, well type, well ID, date range, season, and quarter; metrics include downtime days, spill volume, repair cost, late reports, and containment breaches. Results can be grouped by well, area, month, or well type.

## Multi-user Memory, Corrections, and Feedback

Private chat history and answer feedback are stored with a `user_id` scope. Each assistant answer has helpful / needs-improvement controls and an optional comment. `POST /feedback` records only the user ID, local message ID, rating, and comment; it does not copy the question or answer text. Submitting again for the same user and message updates that feedback entry. Avoid putting sensitive details in comments.

## Quick Start

### Backend setup

**Windows (PowerShell)**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:LLM_PROVIDER = "rules"
python -m backend.app.ingest
uvicorn backend.app.main:app --reload --port 8000
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
export LLM_PROVIDER=rules
python -m backend.app.ingest
uvicorn backend.app.main:app --reload --port 8000
```

Clone the sample data before ingestion if `data/raw/flytbase-ahc-swe-asset-intelligence-dataset` is empty:

```bash
git clone https://github.com/FlytBaseAILabs/flytbase-ahc-swe-asset-intelligence-dataset data/raw/flytbase-ahc-swe-asset-intelligence-dataset
```

The API is available at <http://127.0.0.1:8000>; health and Swagger UI are at `/health` and `/docs`. The `/health` response shows the selected provider and only a boolean for Gemini key presence.

### Frontend

```bash
cd frontend
npm install
npm run build
npm run dev
```

The development server runs at <http://localhost:5173>.

## Recording the demo

The demo driver uses the real sample data and live `/chat` responses. Its reset and server checks refuse any database other than `data/demo.db`; answer-cache traffic uses `data/demo_llm_cache.db`. `DEMO_PROVIDER` defaults to `rules` so a recording uses no model quota. Set it to `gemini` only when you want Gemini wording. The driver opens a headed 1600×900 browser, types at a human pace, highlights the cursor, saves step screenshots under `docs/screenshots/demo/`, and writes a silent Playwright video to the ignored `dist/demo_raw.webm`. During the live run, press Enter in the driver terminal to continue after each step. `DEMO_PAUSE` defaults to 4 seconds; `--dry-run` automatically paces the six segments to about three minutes.

### Windows (PowerShell)

Run these in order from the repository root. Use separate terminals for the backend and frontend.

**Terminal 1 — backend, isolated demo paths:**

```powershell
$env:ASSET_INTELLIGENCE_DATASET = "data/raw/flytbase-ahc-swe-asset-intelligence-dataset"
$env:ASSET_INTELLIGENCE_DB = "data/demo.db"
$env:LLM_CACHE_PATH = "data/demo_llm_cache.db"
$env:DEMO_PROVIDER = "rules" # set to "gemini" to use Gemini
.\.venv\Scripts\python.exe scripts\demo_server.py
```

**Terminal 2 — frontend:**

```powershell
cd frontend
npm run dev -- --host localhost
```

**Terminal 3 — clean and run the demo:**

```powershell
.\scripts\demo_reset.ps1
# Optional cache warm-up; reset again to clear its corrections and private messages.
.\.venv\Scripts\python.exe scripts\demo_prewarm.py
.\scripts\demo_reset.ps1
node scripts\demo_driver.mjs
```

When the driver opens the architecture slide, start your screen recorder with microphone audio enabled. The Playwright backup remains silent. To verify the full flow automatically, run `node scripts\demo_driver.mjs --dry-run` after the reset; it uses the same pages and API behavior without waiting for terminal input.

### macOS / Linux

Run these in order from the repository root. Use separate terminals for the backend and frontend.

**Terminal 1 — backend, isolated demo paths:**

```bash
export ASSET_INTELLIGENCE_DATASET=data/raw/flytbase-ahc-swe-asset-intelligence-dataset
export ASSET_INTELLIGENCE_DB=data/demo.db
export LLM_CACHE_PATH=data/demo_llm_cache.db
export DEMO_PROVIDER=rules # set to gemini to use Gemini
.venv/bin/python scripts/demo_server.py
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev -- --host localhost
```

**Terminal 3 — clean and run the demo:**

```bash
bash scripts/demo_reset.sh
# Optional cache warm-up; reset again to clear its corrections and private messages.
.venv/bin/python scripts/demo_prewarm.py
bash scripts/demo_reset.sh
node scripts/demo_driver.mjs
```

Start your screen recorder with microphone audio enabled after the architecture slide appears. The Playwright backup remains silent. Run `node scripts/demo_driver.mjs --dry-run` for the automatically paced verification flow.

## Configuration

Copy `.env.example` to the ignored `.env`. Put any real API key in `.env` or the process environment; never commit `.env`. The checked-in example intentionally contains no secret.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | Select `gemini`, `ollama`, or `rules`. Use `rules` for deterministic, network-free development and tests. |
| `GEMINI_API_KEY` | empty | Gemini API credential. Never expose it in logs or responses. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model used for intent extraction and optional answer wording. |
| `OLLAMA_HOST` | `http://localhost:11434` | Local Ollama HTTP API address. |
| `OLLAMA_MODEL` | `gemma4:e4b` | Locally installed Ollama model. |
| `LLM_TIMEOUT_SECONDS` | `30` | Hard timeout for one provider call. |
| `LLM_CACHE_PATH` | `data/llm_cache.db` | SQLite cache for successful LLM responses. |
| `REFERENCE_DATE` | latest inspection in DB | Optional `YYYY-MM-DD` override for relative periods. |
| `ASSET_INTELLIGENCE_DB` | `data/asset_intelligence.db` | SQLite database path. |
| `ASSET_INTELLIGENCE_DATASET` | sample-data folder | Dataset root to ingest and use for manuals/SOPs. |

Switch providers in PowerShell:

```powershell
$env:LLM_PROVIDER = "rules"   # or "gemini" / "ollama"
```

Switch providers in macOS/Linux shells:

```bash
export LLM_PROVIDER=rules     # or gemini / ollama
```

To use Gemini, configure `GEMINI_API_KEY` locally in `.env`. For Ollama, install and start Ollama, then pull the configured model. The rules provider does not contact a model service.

## Model Details and Cost

The default Gemini model is `gemini-3.5-flash-lite`. Google lists free-tier access for this model and, on its Standard paid tier, current text input/output rates of **$0.30 / $2.50 per million tokens**. Pricing and model availability can change; check [Google's Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) and [rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits) for the active project and tier. The project's request quota is account-, project-, and model-dependent; do not assume a fixed daily allowance.

An ordinary Gemini question uses at most two logical model calls: one validated JSON intent extraction and one wording pass over deterministic results. If JSON validation needs its permitted retry, the remaining logical call is used for extraction, with no wording pass. Each logical call can make up to four outbound attempts for transient 429/5xx failures, so transport retries can raise the HTTP request count above two. Successful responses are cached in SQLite by provider, model, system text, and prompt hash; a cache hit makes no provider request. A Gemini model-not-found 404 is not retried or cached and uses rules plus templated wording.

`LLM_PROVIDER=rules` is recommended for development and pytest. It makes no paid/free-tier model calls. The actual token cost for a Gemini request depends on prompt and output size; this application does not promise a fixed per-question dollar cost.

## Verification and Evaluation

Run the backend tests from the repository root:

```powershell
$env:LLM_PROVIDER = "rules"
python -m pytest -q
```

```bash
LLM_PROVIDER=rules python -m pytest -q
```

The suite covers ingestion, manual-derived thresholds, metric/date filtering, 25 unseen metric questions against independent pandas calculations, a shifted/renamed dataset simulation with a new well type, provider reliability, users endpoint, and official benchmark behaviors. The sample snapshot contains 45,686 structured records and 1,655 indexed documents (including human-note documents).

Generate a results file by posting a JSON array or an object containing a `questions` array to `/chat`:

```powershell
python scripts/run_questions.py questions.json --user eval-user
```

```bash
python scripts/run_questions.py questions.json --user eval-user
```

The runner writes `results.md` with each question, answer, citations, visualization type, provider path, and latency. It accepts the repository's official question objects (`id`, `label`, `question`, and optional user/session fields).

Generate the official Q1–Q18 comparison from executable expected checks:

```powershell
$env:LLM_PROVIDER = "rules"
python scripts/evaluate_questions.py --provider rules
```

```bash
LLM_PROVIDER=rules python scripts/evaluate_questions.py --provider rules
```

The script writes [`docs/eval_report.md`](docs/eval_report.md). It supports one Gemini comparison run as well; this makes real API calls on cache misses:

```powershell
$env:LLM_PROVIDER = "gemini"
python scripts/evaluate_questions.py --provider gemini
```

## Limitations

- The included dataset and manuals are synthetic and fictional; the manuals and SOPs are not real-world operating or legal guidance.
- Rules-based extraction is deterministic but covers known intent patterns. Ambiguous or unsupported wording may need a clearer area, metric, or period.
- Relative dates use the latest inspection timestamp in the loaded database, or `REFERENCE_DATE` when configured; a stale database produces a stale reference date.
- Gemini and Ollama are optional services. Quota, network, timeout, or model availability failures use deterministic intent extraction and templated answers; answer wording may be less polished.
- Metric answers are limited to the data fields and evidence present in the ingested dataset. Missing records, incomplete report text, and conflicting source notes can limit conclusions.
- Local response cache and database files contain generated or ingested data and should be protected and removed when no longer needed. These files are ignored by Git.

## Documentation

- [`HANDOFF.md`](HANDOFF.md): project rules, checklist, and verified status log.
- [`docs/eval_report.md`](docs/eval_report.md): generated Q1–Q18 evaluation comparison.
- [`docs/writeup.md`](docs/writeup.md): design and results write-up.
- [`docs/demo_script.md`](docs/demo_script.md): five-minute demo outline.

## License

MIT
