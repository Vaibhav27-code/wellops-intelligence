from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from backend.app.ingest.loader import resolve_dataset_root

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_db_path() -> Path:
    configured = Path(os.getenv("ASSET_INTELLIGENCE_DB", "data/asset_intelligence.db")).expanduser()
    return configured.resolve() if configured.is_absolute() else (PROJECT_ROOT / configured).resolve()


def get_reference_date(database_path: str | Path | None = None) -> str:
    """Return the configured reference date or latest inspection date in the DB."""
    override = os.getenv("REFERENCE_DATE", "").strip()
    if override:
        try:
            return date.fromisoformat(override).isoformat()
        except ValueError as exc:
            raise ValueError("REFERENCE_DATE must use YYYY-MM-DD format") from exc

    path = Path(database_path).expanduser().resolve() if database_path else get_db_path()
    if not path.is_file():
        raise FileNotFoundError(f"Asset database does not exist: {path}")

    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT MAX(substr(event_at, 1, 10)) FROM records "
            "WHERE entity_type = 'inspection' AND event_at IS NOT NULL"
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise RuntimeError("Asset database has no readable inspection records") from exc
    finally:
        connection.close()

    latest = row[0] if row else None
    if not latest:
        raise RuntimeError("No inspection timestamp is available for the reference date")
    try:
        return date.fromisoformat(str(latest)).isoformat()
    except ValueError as exc:
        raise RuntimeError("Latest inspection timestamp is not a valid ISO date") from exc


def get_sample_data_root() -> Path:
    configured = Path(
        os.getenv(
            "ASSET_INTELLIGENCE_DATASET",
            "data/raw/flytbase-ahc-swe-asset-intelligence-dataset",
        )
    ).expanduser()
    dataset_path = configured if configured.is_absolute() else PROJECT_ROOT / configured
    return resolve_dataset_root(dataset_path)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def query_records(
    entity_type: str,
    asset_id: str | None = None,
    record_id: str | None = None,
    order_by_event: bool = False,
    descending: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        query = "SELECT record_id, asset_id, event_at, source_path, payload_json FROM records WHERE entity_type = ?"
        params: list[Any] = [entity_type]
        if asset_id:
            query += " AND asset_id = ?"
            params.append(asset_id)
        if record_id:
            query += " AND record_id = ?"
            params.append(record_id)
        if order_by_event:
            direction = "DESC" if descending else "ASC"
            query += f" ORDER BY event_at {direction}"
        if limit:
            query += f" LIMIT {limit}"

        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            payload = json.loads(r["payload_json"])
            payload["_record_id"] = r["record_id"]
            payload["_asset_id"] = r["asset_id"]
            payload["_event_at"] = r["event_at"]
            payload["_source_path"] = r["source_path"]
            results.append(payload)
        return results
    finally:
        conn.close()


def query_documents_fts(search_term: str, limit: int = 10) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        # Sanitize query for FTS5
        clean_term = "".join(c if c.isalnum() or c.isspace() else " " for c in search_term).strip()
        if not clean_term:
            return []
        rows = conn.execute(
            """
            SELECT d.source_path, d.document_type, d.asset_id, d.title, d.content,
                   snippet(documents_fts, 1, '<b>', '</b>', '...', 32) as match_snippet
            FROM documents_fts f
            JOIN documents d ON d.source_path = f.source_path
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (clean_term, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        # Fallback if FTS match syntax fails
        rows = conn.execute(
            """
            SELECT source_path, document_type, asset_id, title, content, '' as match_snippet
            FROM documents
            WHERE content LIKE ?
            LIMIT ?
            """,
            (f"%{clean_term}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
