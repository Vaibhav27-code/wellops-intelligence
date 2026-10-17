from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

from backend.app.calc.compliance import assess_well_compliance
from backend.app.calc.downtime import calculate_downtime
from backend.app.calc.rules import assess_spill, load_production_rule, load_rca_rule, load_spill_rules
from backend.app.ingest.loader import _resolve_report_file, resolve_dataset_root
from backend.app.memory.store import (
    apply_corrections_to_inspection,
    ensure_schema,
    open_memory,
    rca_threshold_override,
    retrieve_shared_memory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "raw" / "flytbase-ahc-swe-asset-intelligence-dataset" / "sample-data"
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "asset_intelligence.db"


class RecordNotFound(LookupError):
    pass


def _citation(source_path: str, record_id: str | None = None) -> str:
    return f"{source_path}#{record_id}" if record_id else source_path


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row["payload_json"])
    payload["_entity_type"] = row["entity_type"]
    payload["_source_path"] = row["source_path"]
    payload["_citation"] = _citation(row["source_path"], row["record_id"])
    return payload


def _records(
    connection: sqlite3.Connection,
    entity_type: str,
    *,
    asset_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    query: str = "",
    limit: int = 1000,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM records WHERE entity_type = ?"
    params: list[Any] = [entity_type]
    if asset_id:
        sql += " AND asset_id = ?"
        params.append(asset_id)
    if start:
        sql += " AND substr(event_at, 1, 10) >= ?"
        params.append(start[:10])
    if end:
        sql += " AND substr(event_at, 1, 10) <= ?"
        params.append(end[:10])
    if query:
        sql += " AND lower(payload_json) LIKE ?"
        params.append(f"%{query.casefold()}%")
    sql += " ORDER BY event_at DESC, record_id LIMIT ?"
    params.append(limit)
    rows = connection.execute(sql, params).fetchall()
    return [_row_dict(row) for row in rows]


def _reference_date(sample_data_root: str | Path) -> str:
    root = Path(sample_data_root)
    guide = root.parent / "02-dataset-guide.md"
    if guide.is_file():
        match = re.search(r"Treat\s+\*\*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\*\*\s+as", guide.read_text(encoding="utf-8"), re.IGNORECASE)
        if match:
            return datetime.strptime(match.group(1), "%d %b %Y").date().isoformat()
    return date.today().isoformat()


@contextmanager
def _connection(database_path: str | Path = DEFAULT_DATABASE) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(Path(database_path).expanduser().resolve())
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def search_wells(
    query: str = "",
    *,
    area_id: str | None = None,
    well_type: str | None = None,
    database_path: str | Path = DEFAULT_DATABASE,
    limit: int = 100,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    pattern = f"%{query.strip().lower()}%"
    with _connection(database_path) as connection:
        rows = connection.execute(
            """SELECT * FROM records
               WHERE entity_type = 'well'
                 AND (? = '%%' OR lower(payload_json) LIKE ?)
                 AND (? IS NULL OR json_extract(payload_json, '$.area_id') = ?)
                 AND (? IS NULL OR json_extract(payload_json, '$.well_type') = ?)
               ORDER BY record_id LIMIT ?""",
            (pattern, pattern, area_id, area_id, well_type, well_type, limit),
        ).fetchall()
        return [_row_dict(row) for row in rows]


def get_well_details(
    asset_id: str,
    *,
    dataset_root: str | Path = DEFAULT_DATASET,
    database_path: str | Path = DEFAULT_DATABASE,
    as_of: str | None = None,
) -> dict[str, Any]:
    reference_date = (as_of or _reference_date(dataset_root))[:10]
    with _connection(database_path) as connection:
        well_row = connection.execute(
            "SELECT * FROM records WHERE entity_type = 'well' AND record_id = ?", (asset_id,)
        ).fetchone()
        if not well_row:
            raise RecordNotFound(f"Unknown asset_id: {asset_id}")
        well = _row_dict(well_row)
        inspections = _records(connection, "inspection", asset_id=asset_id, end=reference_date)
        contexts = _records(connection, "context", asset_id=asset_id, end=reference_date)
        maintenance = _records(connection, "maintenance", asset_id=asset_id, end=reference_date)

    memory = open_memory(database_path)
    try:
        shared = retrieve_shared_memory(memory, well_id=asset_id, well_type=str(well.get("well_type", "")))
    finally:
        memory.close()
    corrections = shared["corrections"]
    inspections = [apply_corrections_to_inspection(row, well, corrections) for row in inspections]

    latest = inspections[0] if inspections else None
    derived_status: dict[str, Any] = {"status": "unknown", "reference_date": reference_date}
    citations = [well["_citation"]]
    if latest:
        citations.append(latest["_citation"])
        ambient = latest.get("ambient_temp_c")
        wellhead = latest.get("wellhead_temp_c")
        if isinstance(ambient, (int, float)) and isinstance(wellhead, (int, float)):
            rule = load_production_rule(str(well.get("well_type", "")), dataset_root)
            delta = round(float(wellhead) - float(ambient), 3)
            status = "producing" if delta >= rule.minimum_delta_c else "not_producing"
            derived_status.update(
                {
                    "status": status,
                    "temperature_delta_c": delta,
                    "threshold_delta_c": rule.minimum_delta_c,
                    "latest_inspection": latest,
                    "rule_citation": rule.citation,
                }
            )
            citations.append(rule.citation)
        else:
            derived_status["latest_inspection"] = latest

        active_notes = [
            note for note in contexts
            if note.get("note_type") in {"operator_note", "operator_feedback"}
            and _note_applies(note, latest.get("inspected_at"))
        ]
        planned = [note for note in active_notes if re.search(r"\b(?:planned|scheduled)\b.{0,40}\bshut[- ]?in\b|\bshut[- ]?in\b.{0,40}\b(?:planned|scheduled)\b", str(note.get("text", "")), re.IGNORECASE)]
        if planned:
            derived_status["planned_shut_in_notes"] = [note.get("text") for note in planned]
            citations.extend(note["_citation"] for note in planned)
        open_jobs = [
            job for job in maintenance
            if job.get("started_at", "")[:10] <= reference_date
            and (not job.get("completed_at") or str(job.get("completed_at"))[:10] > reference_date)
        ]
        if open_jobs:
            derived_status["open_maintenance"] = open_jobs
            citations.extend(job["_citation"] for job in open_jobs)
    derived_status["recorded_status"] = well.get("recorded_status")
    if latest and latest.get("_applied_corrections"):
        derived_status["corrections"] = latest["_applied_corrections"]
        conflicting_notes = [
            note for note in contexts
            if note.get("inspection_id") == latest.get("inspection_id")
            and note.get("note_type") in {"operator_note", "operator_feedback"}
        ]
        if conflicting_notes:
            derived_status["conflicts"] = conflicting_notes
            citations.extend(note["_citation"] for note in conflicting_notes)
    derived_status["citations"] = list(dict.fromkeys(citations))
    well["derived_status"] = derived_status
    well["shared_corrections"] = corrections
    well["shared_notes"] = shared["notes"]
    return well


def _note_applies(note: dict[str, Any], timestamp: Any) -> bool:
    if not isinstance(timestamp, str) or not timestamp:
        return False
    day = timestamp[:10]
    return (not note.get("valid_from") or str(note["valid_from"]) <= day) and (
        not note.get("valid_to") or str(note["valid_to"]) >= day
    )


def downtime_for_well(
    asset_id: str,
    *,
    start: str | None = None,
    end: str | None = None,
    as_of: str | None = None,
    dataset_root: str | Path = DEFAULT_DATASET,
    database_path: str | Path = DEFAULT_DATABASE,
) -> dict[str, Any]:
    with _connection(database_path) as connection:
        well_row = connection.execute(
            "SELECT * FROM records WHERE entity_type = 'well' AND record_id = ?", (asset_id,)
        ).fetchone()
        if not well_row:
            raise RecordNotFound(f"Unknown asset_id: {asset_id}")
        well = _row_dict(well_row)
        inspections = _records(connection, "inspection", asset_id=asset_id, end=end or as_of)
        contexts = _records(connection, "context", asset_id=asset_id, end=end or as_of)
    memory = open_memory(database_path)
    try:
        shared = retrieve_shared_memory(memory, well_id=asset_id, well_type=str(well.get("well_type", "")))
    finally:
        memory.close()
    inspections = [
        apply_corrections_to_inspection(row, well, shared["corrections"])
        for row in inspections
    ]
    return calculate_downtime(
        inspections,
        str(well.get("well_type", "")),
        dataset_root,
        contexts=contexts,
        start=start,
        end=end,
        as_of=as_of or _reference_date(dataset_root),
    )


def search_records(
    entity_type: str,
    query: str = "",
    *,
    asset_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    database_path: str | Path = DEFAULT_DATABASE,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if entity_type not in {"inspection", "maintenance", "regulatory_event", "context"}:
        raise ValueError("Unsupported entity type")
    limit = max(1, min(int(limit), 500))
    with _connection(database_path) as connection:
        return _records(connection, entity_type, asset_id=asset_id, start=start, end=end, query=query, limit=limit)


def _fts_query(query: str) -> str:
    terms = re.findall(r"[\w-]+", query, flags=re.UNICODE)
    if not terms:
        raise ValueError("Search query must contain at least one word")
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms[:20])


def search_documents(
    query: str,
    *,
    document_types: tuple[str, ...] = ("manual", "sop", "maintenance_report", "human_note"),
    asset_id: str | None = None,
    database_path: str | Path = DEFAULT_DATABASE,
    limit: int = 20,
) -> list[dict[str, Any]]:
    match = _fts_query(query)
    limit = max(1, min(int(limit), 100))
    if not document_types:
        return []
    placeholders = ",".join("?" for _ in document_types)
    sql = f"""SELECT d.source_path, d.document_type, d.asset_id, d.title,
                      snippet(documents_fts, 1, '[', ']', ' … ', 18) AS excerpt,
                      bm25(documents_fts) AS rank
               FROM documents_fts JOIN documents d ON d.source_path = documents_fts.source_path
               WHERE documents_fts MATCH ? AND d.document_type IN ({placeholders})"""
    params: list[Any] = [match, *document_types]
    if asset_id:
        sql += " AND d.asset_id = ?"
        params.append(asset_id)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)
    with _connection(database_path) as connection:
        try:
            rows = connection.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            raise ValueError(f"Search could not be parsed: {exc}") from exc
    return [
        {
            "source_path": row["source_path"],
            "document_type": row["document_type"],
            "asset_id": row["asset_id"],
            "title": row["title"],
            "excerpt": row["excerpt"],
            "citation": row["source_path"],
        }
        for row in rows
    ]


def get_maintenance_report_texts(
    maintenance: list[dict[str, Any]],
    *,
    dataset_root: str | Path = DEFAULT_DATASET,
) -> dict[str, str]:
    """Resolve each report_file relative to its well folder, within the dataset only."""
    root = Path(dataset_root).resolve()
    result: dict[str, str] = {}
    for job in maintenance:
        report_file = job.get("report_file")
        asset_id = job.get("asset_id")
        maintenance_id = job.get("maintenance_id")
        if not isinstance(report_file, str) or not isinstance(asset_id, str) or not isinstance(maintenance_id, str):
            continue
        asset_root = (root / "assets" / asset_id).resolve()
        path = (asset_root / report_file).resolve()
        if path.is_relative_to(asset_root) and path.is_file():
            result[maintenance_id] = path.read_text(encoding="utf-8", errors="replace")
    return result


def search_inspections(query: str = "", **filters: Any) -> list[dict[str, Any]]:
    return search_records("inspection", query, **filters)


def search_repairs(query: str = "", **filters: Any) -> list[dict[str, Any]]:
    return search_records("maintenance", query, **filters)


def search_regulator_events(query: str = "", **filters: Any) -> list[dict[str, Any]]:
    return search_records("regulatory_event", query, **filters)


def search_human_notes(query: str, **filters: Any) -> list[dict[str, Any]]:
    return search_documents(query, document_types=("human_note",), **filters)


def search_manuals_and_sops(query: str, **filters: Any) -> list[dict[str, Any]]:
    return search_documents(query, document_types=("manual", "sop"), **filters)


def compare_wells(
    asset_ids: list[str],
    *,
    dataset_root: str | Path = DEFAULT_DATASET,
    database_path: str | Path = DEFAULT_DATABASE,
    as_of: str | None = None,
) -> list[dict[str, Any]]:
    if not asset_ids or len(asset_ids) > 50:
        raise ValueError("Provide between 1 and 50 asset IDs")
    return [
        {
            "well": get_well_details(asset_id, dataset_root=dataset_root, database_path=database_path, as_of=as_of),
            "downtime": downtime_for_well(asset_id, dataset_root=dataset_root, database_path=database_path, as_of=as_of),
        }
        for asset_id in asset_ids
    ]
