# Asset Intelligence Copilot

Evidence-grounded operations support for the FlytBase synthetic oil-well dataset. The current backend includes source-format ingestion to SQLite, FTS5 indexing for source documents and notes, and deterministic production, downtime, spill, and compliance calculations. The React/Vite frontend is present; the chat API and memory/correction workflows are still in progress.

## Setup

On Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
uvicorn backend.app.main:app --reload
```

The health check is available at <http://127.0.0.1:8000/health>.

## Load the sample dataset

The dataset is not copied into this app repository. Clone the official public sample into the ignored `data/raw/` directory; raw files are not edited:

```powershell
git clone https://github.com/FlytBaseAILabs/flytbase-ahc-swe-asset-intelligence-dataset data/raw/flytbase-ahc-swe-asset-intelligence-dataset
python -m backend.app.ingest
```

By default, this reads `data/raw/flytbase-ahc-swe-asset-intelligence-dataset` and writes `data/asset_intelligence.db`. A different compatible dataset or database path can be supplied:

```powershell
python -m backend.app.ingest "D:\path\to\dataset" --database "D:\path\to\asset_intelligence.db"
```

The loader accepts either the repository root or its `sample-data` directory. It validates record IDs and dataset references before replacing the snapshot in a transaction. Re-running ingestion is safe. Each structured source row remains available as its original JSON payload with its source filename and record ID; manuals, SOPs, maintenance reports, and human notes are searchable through SQLite FTS5.

## Rules and provenance

Production thresholds and spill classes/deadlines are parsed from the supplied well-type manuals and SOPs. Downtime counts seven days for each inspected non-producing reading, adds zero for missed inspection periods, and keeps repair duration out of the calculation. A matching formal correction can override an inspection's spill classification while the ingested original remains intact. Calculations return the source record and document citations they used.

See [data_inventory.md](data_inventory.md) for inspected schemas, joins, validation results, source links, and known interpretation risks. The dataset documents are fictional challenge material and are not real-world operating or legal guidance.

## Configuration

Copy `.env.example` to `.env` and add an LLM provider key locally after selecting a provider. Keep `.env` out of version control. The planned LLM role is question interpretation and answer wording; calculations and evidence retrieval remain deterministic and source-grounded.
