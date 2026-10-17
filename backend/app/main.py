from __future__ import annotations

import os

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
    return {
        "status": "ok",
        "llm_provider": provider,
        "llm_key_present": key_present,
    }
