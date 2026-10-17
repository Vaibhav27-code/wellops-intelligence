from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DB = (ROOT / "data" / "demo.db").resolve()
EXPECTED_CACHE = (ROOT / "data" / "demo_llm_cache.db").resolve()


def _configured_path(name: str) -> Path:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Refusing demo reset: {name} must be set explicitly.")
    candidate = Path(value).expanduser()
    return (candidate if candidate.is_absolute() else ROOT / candidate).resolve()


def main() -> int:
    database_path = _configured_path("ASSET_INTELLIGENCE_DB")
    if database_path != EXPECTED_DB:
        raise SystemExit(
            "Refusing demo reset: ASSET_INTELLIGENCE_DB must resolve to data/demo.db."
        )
    cache_path = _configured_path("LLM_CACHE_PATH")
    if cache_path != EXPECTED_CACHE:
        raise SystemExit(
            "Refusing demo reset: LLM_CACHE_PATH must resolve to data/demo_llm_cache.db."
        )

    dataset_value = os.getenv("ASSET_INTELLIGENCE_DATASET", "data/raw/flytbase-ahc-swe-asset-intelligence-dataset")
    dataset_path = Path(dataset_value).expanduser()
    if not dataset_path.is_absolute():
        dataset_path = ROOT / dataset_path
    if not dataset_path.is_dir():
        raise SystemExit(f"Sample dataset folder does not exist: {dataset_path}")

    sys.path.insert(0, str(ROOT))
    from backend.app.ingest.loader import load_dataset
    from backend.app.memory.store import open_memory

    report = load_dataset(dataset_path, database_path)
    connection = open_memory(database_path)
    try:
        for table in ("corrections", "shared_notes", "private_messages", "answer_feedback"):
            connection.execute(f"DELETE FROM {table}")
        connection.commit()
    finally:
        connection.close()

    print(f"Demo database rebuilt: {database_path.relative_to(ROOT)}")
    print(f"Source dataset: {dataset_path}")
    print(f"Records: {report.counts}")
    print(f"Errors: {len(report.errors)}; warnings: {len(report.warnings)}")
    print("Demo corrections, shared notes, private messages, and feedback cleared.")
    print("LLM cache preserved for pre-warmed answers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
