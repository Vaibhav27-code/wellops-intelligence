# Asset Intelligence Copilot

An evidence-grounded chat copilot for oil-well operations. The project scaffold is being prepared; source data and manuals have not yet been supplied, so no dataset-specific behavior is implemented.

## Current status

- FastAPI health endpoint: available at /health.
- Dataset ingestion, deterministic operational calculations, retrieval, citations, corrections, private memory, and visualizations: pending inspection of the real source bundle.
- Source inventory: data_inventory.md.
- Operating constraints: AGENTS.md and HANDOFF.md.

## Setup

Run these commands in PowerShell:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m pytest
    uvicorn backend.app.main:app --reload

Open http://127.0.0.1:8000/health to check the service.

## Configuration

Copy .env.example to .env and fill in provider settings locally when an LLM provider is selected. Keep .env out of version control. LLMs may help interpret questions and phrase answers; calculations and evidence retrieval must remain deterministic and source-grounded.
