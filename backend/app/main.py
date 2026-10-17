from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router

app = FastAPI(title="Asset Intelligence Copilot", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().casefold()
    key_present = provider == "gemini" and bool(os.getenv("GEMINI_API_KEY", "").strip())
    project_root = Path(__file__).resolve().parents[2]
    demo_mode_requested = os.getenv("DEMO_MODE", "").strip().casefold() in {"1", "true", "yes"}

    def configured_path(variable: str, default: str) -> Path:
        value = Path(os.getenv(variable, default)).expanduser()
        return (value if value.is_absolute() else project_root / value).resolve()

    demo_db_safe = configured_path("ASSET_INTELLIGENCE_DB", "data/asset_intelligence.db") == (project_root / "data" / "demo.db").resolve()
    demo_cache_safe = configured_path("LLM_CACHE_PATH", "data/llm_cache.db") == (project_root / "data" / "demo_llm_cache.db").resolve()
    demo_mode = demo_mode_requested and demo_db_safe and demo_cache_safe
    return {
        "status": "ok" if not demo_mode_requested or demo_mode else "error",
        "llm_provider": provider,
        "llm_key_present": key_present,
        "demo_mode": demo_mode,
        "demo_db_safe": demo_db_safe,
    }
