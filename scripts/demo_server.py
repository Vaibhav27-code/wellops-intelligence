from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def _path_from_env(variable: str, default: str) -> Path:
    value = Path(os.getenv(variable, default)).expanduser()
    return (value if value.is_absolute() else ROOT / value).resolve()


def main() -> None:
    sys.path.insert(0, str(ROOT))
    expected_db = (ROOT / "data" / "demo.db").resolve()
    expected_cache = (ROOT / "data" / "demo_llm_cache.db").resolve()
    if _path_from_env("ASSET_INTELLIGENCE_DB", "") != expected_db:
        raise SystemExit("Refusing to start demo server: ASSET_INTELLIGENCE_DB must resolve to data/demo.db.")
    if _path_from_env("LLM_CACHE_PATH", "") != expected_cache:
        raise SystemExit("Refusing to start demo server: LLM_CACHE_PATH must resolve to data/demo_llm_cache.db.")

    provider = os.getenv("DEMO_PROVIDER", os.getenv("LLM_PROVIDER", "rules")).strip().casefold()
    if provider not in {"rules", "gemini"}:
        raise SystemExit("DEMO_PROVIDER must be 'rules' or 'gemini'.")
    os.environ["LLM_PROVIDER"] = provider
    os.environ["DEMO_MODE"] = "1"
    os.environ["ASSET_INTELLIGENCE_DB"] = str(expected_db)
    os.environ["LLM_CACHE_PATH"] = str(expected_cache)
    test_dataset = (ROOT / "data" / "raw" / "flytbase-ahc-swe-asset-intelligence-dataset" / "test-data" / "dataset").resolve()
    default_dataset = str(test_dataset) if test_dataset.is_dir() else "data/raw/flytbase-ahc-swe-asset-intelligence-dataset"
    os.environ.setdefault("ASSET_INTELLIGENCE_DATASET", default_dataset)
    port = int(os.getenv("DEMO_API_PORT", "8000"))

    import uvicorn

    print(f"Starting demo backend on port {port} with provider={provider}; database and cache paths are guarded.")
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
