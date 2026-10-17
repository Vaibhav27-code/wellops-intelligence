from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class SourceRecord:
    entity_type: str
    record_id: str
    asset_id: str | None
    event_at: str | None
    source_path: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SourceDocument:
    source_path: str
    document_type: str
    asset_id: str | None
    title: str
    content: str


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    source_path: str | None = None
    record_id: str | None = None


@dataclass
class ValidationReport:
    dataset_root: str
    counts: dict[str, int] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_root": self.dataset_root,
            "counts": self.counts,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [asdict(issue) for issue in self.issues],
        }


class DatasetValidationError(ValueError):
    def __init__(self, report: ValidationReport):
        self.report = report
        super().__init__(f"Dataset validation failed with {len(report.errors)} error(s)")


_JSONL_ENTITIES = (
    ("inspection", "inspections.jsonl", "inspection_id", "inspected_at"),
    ("maintenance", "maintenance.jsonl", "maintenance_id", "started_at"),
    ("regulatory_event", "regulatory-events.jsonl", "event_id", "date"),
    ("context", "context.jsonl", "note_id", "created_at"),
)
_RECORD_IDS = {
    "well": "asset_id",
    "inspection": "inspection_id",
    "maintenance": "maintenance_id",
    "regulatory_event": "event_id",
    "context": "note_id",
    "area": "area_id",
    "team": "team_id",
    "user": "user_id",
}


def resolve_dataset_root(path: str | Path) -> Path:
    """Accept either a sample-data folder, the challenge checkout, or its data folder."""
    root = Path(path).expanduser().resolve()
    candidates = [root, root / "sample-data", root / "data" / "sample-data"]
    for candidate in candidates:
        if (candidate / "assets").is_dir() and (candidate / "fleet").is_dir():
            return candidate
    raise FileNotFoundError(
        f"Could not find assets/ and fleet/ under {root}; pass sample-data or its parent"
    )


def _read_json(path: Path, report: ValidationReport) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.issues.append(
            ValidationIssue("error", "invalid_json", str(exc), path.relative_to(Path(report.dataset_root)).as_posix())
        )
        return None
    if not isinstance(value, dict):
        report.issues.append(
            ValidationIssue("error", "invalid_record", "Expected a JSON object", path.relative_to(Path(report.dataset_root)).as_posix())
        )
        return None
    return value


def _read_jsonl(path: Path, report: ValidationReport) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    report.issues.append(
                        ValidationIssue(
                            "error",
                            "invalid_jsonl",
                            f"Line {line_number}: {exc}",
                            path.relative_to(Path(report.dataset_root)).as_posix(),
                        )
                    )
                    continue
                if not isinstance(value, dict):
                    report.issues.append(
                        ValidationIssue(
                            "error",
                            "invalid_record",
                            f"Line {line_number}: expected a JSON object",
                            path.relative_to(Path(report.dataset_root)).as_posix(),
                        )
                    )
                    continue
                rows.append(value)
    except OSError as exc:
        report.issues.append(
            ValidationIssue("error", "unreadable_file", str(exc), path.relative_to(Path(report.dataset_root)).as_posix())
        )
    return rows


def _record(
    entity_type: str,
    payload: dict[str, Any],
    source_path: str,
    event_field: str | None = None,
) -> SourceRecord | None:
    record_id = payload.get(_RECORD_IDS[entity_type])
    if not isinstance(record_id, str) or not record_id.strip():
        return None
    event_at = payload.get(event_field) if event_field else None
    return SourceRecord(
        entity_type=entity_type,
        record_id=record_id,
        asset_id=payload.get("asset_id") if isinstance(payload.get("asset_id"), str) else None,
        event_at=event_at if isinstance(event_at, str) else None,
        source_path=source_path,
        payload=payload,
    )


def _add_record(
    records: list[SourceRecord],
    payload: dict[str, Any],
    entity_type: str,
    source_path: str,
    report: ValidationReport,
    event_field: str | None = None,
) -> None:
    row = _record(entity_type, payload, source_path, event_field)
    if row is None:
        report.issues.append(
            ValidationIssue(
                "error",
                "missing_record_id",
                f"Missing or invalid {_RECORD_IDS[entity_type]}",
                source_path,
            )
        )
        return
    records.append(row)


def _read_fleet_array(
    path: Path, key: str, entity_type: str, report: ValidationReport
) -> list[dict[str, Any]]:
    payload = _read_json(path, report)
    if payload is None:
        return []
    values = payload.get(key)
    if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
        report.issues.append(
            ValidationIssue(
                "error",
                "invalid_fleet_file",
                f"Expected top-level {key!r} array of objects",
                path.relative_to(Path(report.dataset_root)).as_posix(),
            )
        )
        return []
    return values


def _resolve_report_file(sample_root: Path, report_file: str, asset_id: str | None) -> Path | None:
    candidate_value = Path(report_file)
    candidates = [sample_root / candidate_value]
    if asset_id:
        candidates.append(sample_root / "assets" / asset_id / candidate_value)
    if candidate_value.parts and candidate_value.parts[0] == "sample-data":
        candidates.append(sample_root.parent / candidate_value)
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_relative_to(sample_root.resolve()) and resolved.is_file():
            return resolved
    return None


def _validate_references(records: list[SourceRecord], report: ValidationReport, sample_root: Path) -> None:
    ids_by_type: dict[str, set[str]] = {}
    for row in records:
        if row.record_id in ids_by_type.setdefault(row.entity_type, set()):
            report.issues.append(
                ValidationIssue("error", "duplicate_id", f"Duplicate {row.entity_type} ID", row.source_path, row.record_id)
            )
        ids_by_type[row.entity_type].add(row.record_id)

    well_ids = ids_by_type.get("well", set())
    inspection_ids = ids_by_type.get("inspection", set())
    user_ids = ids_by_type.get("user", set())
    team_ids = ids_by_type.get("team", set())
    area_ids = ids_by_type.get("area", set())

    for row in records:
        payload = row.payload
        if row.entity_type in {"inspection", "maintenance", "regulatory_event", "context"}:
            if row.asset_id not in well_ids:
                report.issues.append(
                    ValidationIssue("error", "unknown_asset", "Record references an unknown asset_id", row.source_path, row.record_id)
                )
        user_fields = {
            "well": ("in_charge_user_id",),
            "inspection": ("inspector_user_id",),
            "maintenance": ("technician_user_id",),
            "context": ("author_user_id",),
            "team": ("lead_user_id",),
        }.get(row.entity_type, ())
        for field_name in user_fields:
            value = payload.get(field_name)
            if value is not None and value not in user_ids:
                report.issues.append(
                    ValidationIssue("error", "unknown_user", f"{field_name} references unknown user", row.source_path, row.record_id)
                )
        if row.entity_type in {"well", "user"}:
            team_id = payload.get("team_id")
            if team_id is not None and team_id not in team_ids:
                report.issues.append(
                    ValidationIssue("error", "unknown_team", "team_id references unknown team", row.source_path, row.record_id)
                )
        if row.entity_type == "well":
            area_id = payload.get("area_id")
            if area_id is not None and area_id not in area_ids:
                report.issues.append(
                    ValidationIssue("error", "unknown_area", "area_id references unknown area", row.source_path, row.record_id)
                )
        inspection_ref = None
        if row.entity_type == "maintenance":
            inspection_ref = payload.get("triggered_by_inspection_id")
            report_file = payload.get("report_file")
            if report_file is not None and _resolve_report_file(sample_root, str(report_file), row.asset_id) is None:
                report.issues.append(
                    ValidationIssue("error", "missing_report_file", "report_file does not resolve within the dataset", row.source_path, row.record_id)
                )
        elif row.entity_type == "regulatory_event":
            inspection_ref = payload.get("related_inspection_id")
        elif row.entity_type == "context":
            inspection_ref = payload.get("inspection_id")
        if inspection_ref is not None and inspection_ref not in inspection_ids:
            report.issues.append(
                ValidationIssue("error", "unknown_inspection", "Inspection reference does not resolve", row.source_path, row.record_id)
            )


def _collect_documents(sample_root: Path, records: list[SourceRecord]) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    fleet_root = sample_root / "fleet"
    for folder, document_type in (("well-types", "manual"), ("sops", "sop")):
        for path in sorted((fleet_root / folder).glob("*.md")):
            content = path.read_text(encoding="utf-8")
            documents.append(
                SourceDocument(path.relative_to(sample_root).as_posix(), document_type, None, content.splitlines()[0].lstrip("# "), content)
            )
    for path in sorted((sample_root / "assets").glob("*/maintenance-reports/**/*.md")):
        content = path.read_text(encoding="utf-8")
        documents.append(
            SourceDocument(
                path.relative_to(sample_root).as_posix(),
                "maintenance_report",
                path.parts[-3],
                content.splitlines()[0].lstrip("# ") if content.splitlines() else path.stem,
                content,
            )
        )
    for row in records:
        if row.entity_type != "context":
            continue
        content = str(row.payload.get("text", ""))
        if not content.strip():
            continue
        documents.append(
            SourceDocument(
                f"{row.source_path}#{row.record_id}",
                "human_note",
                row.asset_id,
                str(row.payload.get("note_type", "Human note")),
                content,
            )
        )
    return documents


def inspect_dataset(path: str | Path) -> tuple[list[SourceRecord], list[SourceDocument], ValidationReport]:
    sample_root = resolve_dataset_root(path)
    report = ValidationReport(dataset_root=str(sample_root))
    records: list[SourceRecord] = []
    fleet_root = sample_root / "fleet"

    areas_path = fleet_root / "areas.json"
    areas_payload = _read_json(areas_path, report)
    if areas_payload is not None:
        for key, entity_type in (("areas", "area"), ("teams", "team")):
            values = areas_payload.get(key)
            if not isinstance(values, list):
                report.issues.append(
                    ValidationIssue("error", "invalid_fleet_file", f"Expected {key!r} array", "fleet/areas.json")
                )
                continue
            for value in values:
                if isinstance(value, dict):
                    _add_record(records, value, entity_type, "fleet/areas.json", report)
                else:
                    report.issues.append(ValidationIssue("error", "invalid_record", f"{key} item must be an object", "fleet/areas.json"))

    users_path = fleet_root / "users.json"
    for user in _read_fleet_array(users_path, "users", "user", report):
        _add_record(records, user, "user", "fleet/users.json", report)

    assets_root = sample_root / "assets"
    for metadata_path in sorted(assets_root.glob("*/metadata.json")):
        metadata = _read_json(metadata_path, report)
        if metadata is None:
            continue
        relative = metadata_path.relative_to(sample_root).as_posix()
        _add_record(records, metadata, "well", relative, report)
        expected_asset = metadata_path.parent.name
        if metadata.get("asset_id") != expected_asset:
            report.issues.append(
                ValidationIssue("error", "asset_folder_mismatch", "metadata asset_id differs from its folder", relative, str(metadata.get("asset_id")))
            )
        for entity_type, filename, id_field, event_field in _JSONL_ENTITIES:
            jsonl_path = metadata_path.parent / filename
            if not jsonl_path.exists():
                report.issues.append(
                    ValidationIssue("error", "missing_entity_file", f"Missing {filename}", jsonl_path.relative_to(sample_root).as_posix())
                )
                continue
            for payload in _read_jsonl(jsonl_path, report):
                _add_record(
                    records,
                    payload,
                    entity_type,
                    jsonl_path.relative_to(sample_root).as_posix(),
                    report,
                    event_field,
                )
                if payload.get("asset_id") != expected_asset:
                    report.issues.append(
                        ValidationIssue("error", "asset_folder_mismatch", "Record asset_id differs from its folder", jsonl_path.relative_to(sample_root).as_posix(), str(payload.get(id_field)))
                    )

    _validate_references(records, report, sample_root)
    documents = _collect_documents(sample_root, records)
    report.counts = {entity_type: sum(row.entity_type == entity_type for row in records) for entity_type in _RECORD_IDS}
    report.counts["document"] = len(documents)
    return records, documents, report


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS records (
            entity_type TEXT NOT NULL,
            record_id TEXT NOT NULL,
            asset_id TEXT,
            event_at TEXT,
            source_path TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (entity_type, record_id)
        );
        CREATE INDEX IF NOT EXISTS idx_records_asset_entity_time
            ON records(asset_id, entity_type, event_at);
        CREATE TABLE IF NOT EXISTS documents (
            document_id INTEGER PRIMARY KEY,
            source_path TEXT NOT NULL UNIQUE,
            document_type TEXT NOT NULL,
            asset_id TEXT,
            title TEXT NOT NULL,
            content TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            source_path UNINDEXED,
            content,
            tokenize = 'unicode61'
        );
        """
    )


def load_dataset(path: str | Path, database_path: str | Path) -> ValidationReport:
    """Validate a dataset, then atomically replace the SQLite snapshot with its contents."""
    records, documents, report = inspect_dataset(path)
    if report.errors:
        raise DatasetValidationError(report)

    db_path = Path(database_path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        _create_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM records")
        connection.execute("DELETE FROM documents")
        connection.execute("DELETE FROM documents_fts")
        connection.executemany(
            """INSERT INTO records(entity_type, record_id, asset_id, event_at, source_path, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (row.entity_type, row.record_id, row.asset_id, row.event_at, row.source_path,
                 json.dumps(row.payload, ensure_ascii=False, separators=(",", ":")))
                for row in records
            ],
        )
        connection.executemany(
            "INSERT INTO documents(source_path, document_type, asset_id, title, content) VALUES (?, ?, ?, ?, ?)",
            [(doc.source_path, doc.document_type, doc.asset_id, doc.title, doc.content) for doc in documents],
        )
        connection.executemany(
            "INSERT INTO documents_fts(source_path, content) VALUES (?, ?)",
            [(doc.source_path, doc.content) for doc in documents],
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return report


def table_counts(database_path: str | Path) -> dict[str, int]:
    connection = sqlite3.connect(database_path)
    try:
        counts = {
            row[0]: row[1]
            for row in connection.execute("SELECT entity_type, COUNT(*) FROM records GROUP BY entity_type")
        }
        counts["document"] = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        return counts
    finally:
        connection.close()
