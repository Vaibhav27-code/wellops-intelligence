from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS corrections (
            correction_id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            well_id TEXT,
            well_type TEXT,
            inspection_id TEXT,
            field TEXT NOT NULL,
            original_value TEXT,
            corrected_value TEXT NOT NULL,
            author TEXT NOT NULL,
            created_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            evidence TEXT,
            equipment_kind TEXT
        );
        CREATE TABLE IF NOT EXISTS shared_notes (
            note_id TEXT PRIMARY KEY,
            asset_id TEXT,
            well_type TEXT,
            author TEXT NOT NULL,
            created_at TEXT NOT NULL,
            text TEXT NOT NULL,
            confirmed INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS private_messages (
            message_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_private_user_time
            ON private_messages(user_id, created_at);
        CREATE TABLE IF NOT EXISTS answer_feedback (
            feedback_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            rating TEXT NOT NULL CHECK (rating IN ('positive', 'negative')),
            comment TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, message_id)
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_user_time
            ON answer_feedback(user_id, updated_at);
        """
    )


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def record_correction(
    connection: sqlite3.Connection,
    *,
    scope: str,
    field: str,
    original_value: Any,
    corrected_value: Any,
    author: str,
    reason: str,
    well_id: str | None = None,
    well_type: str | None = None,
    inspection_id: str | None = None,
    evidence: str | None = None,
    equipment_kind: str | None = None,
) -> dict[str, Any]:
    if scope not in {"well", "well_type"}:
        raise ValueError("scope must be 'well' or 'well_type'")
    if scope == "well" and not well_id:
        raise ValueError("well-scoped corrections require well_id")
    if scope == "well_type" and not well_type:
        raise ValueError("well-type corrections require well_type")
    if not field or corrected_value is None or not str(author).strip() or not str(reason).strip():
        raise ValueError("field, corrected_value, author and reason are required")
    row = {
        "correction_id": str(uuid.uuid4()),
        "scope": scope,
        "well_id": well_id,
        "well_type": well_type,
        "inspection_id": inspection_id,
        "field": field,
        "original_value": json.dumps(original_value, default=str) if original_value is not None else None,
        "corrected_value": json.dumps(corrected_value, default=str),
        "author": author,
        "created_at": _now(),
        "reason": reason,
        "evidence": evidence,
        "equipment_kind": equipment_kind,
    }
    connection.execute(
        """INSERT INTO corrections(
            correction_id, scope, well_id, well_type, inspection_id, field,
            original_value, corrected_value, author, created_at, reason, evidence, equipment_kind
        ) VALUES (:correction_id, :scope, :well_id, :well_type, :inspection_id, :field,
                 :original_value, :corrected_value, :author, :created_at, :reason, :evidence, :equipment_kind)""",
        row,
    )
    connection.commit()
    return decode_correction(row)


def _decode_json(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def decode_correction(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["original_value"] = _decode_json(row.get("original_value"))
    out["corrected_value"] = _decode_json(row.get("corrected_value"))
    return out


def retrieve_shared_memory(
    connection: sqlite3.Connection,
    *,
    well_id: str | None = None,
    well_type: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    corrections = [decode_correction(_row(row)) for row in connection.execute("SELECT * FROM corrections ORDER BY created_at").fetchall()]
    notes = [_row(row) for row in connection.execute("SELECT * FROM shared_notes ORDER BY created_at").fetchall()]
    if well_id or well_type:
        corrections = [
            item
            for item in corrections
            if (item["scope"] == "well" and well_id and item.get("well_id") == well_id)
            or (item["scope"] == "well_type" and well_type and item.get("well_type") == well_type)
        ]
        notes = [
            item
            for item in notes
            if (well_id and item.get("asset_id") == well_id) or (well_type and item.get("well_type") == well_type)
        ]
    return {"corrections": corrections, "notes": notes}


def retrieve_private_memory(connection: sqlite3.Connection, user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT * FROM private_messages WHERE user_id = ?
           ORDER BY created_at DESC, rowid DESC LIMIT ?""",
        (user_id, max(1, min(limit, 200))),
    ).fetchall()
    result = []
    for row in reversed(rows):
        item = _row(row)
        item["payload"] = _decode_json(item.pop("payload_json"))
        result.append(item)
    return result


def append_private_message(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    role: str,
    content: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not user_id:
        raise ValueError("user_id is required for private memory")
    row = {
        "message_id": str(uuid.uuid4()),
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": _now(),
        "payload_json": json.dumps(payload or {}, ensure_ascii=False),
    }
    connection.execute(
        """INSERT INTO private_messages(message_id, user_id, role, content, created_at, payload_json)
           VALUES (:message_id, :user_id, :role, :content, :created_at, :payload_json)""",
        row,
    )
    connection.commit()
    row["payload"] = payload or {}
    row.pop("payload_json")
    return row


def record_answer_feedback(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    message_id: str,
    rating: str,
    comment: str | None = None,
) -> dict[str, Any]:
    user_id = str(user_id).strip()
    message_id = str(message_id).strip()
    if not user_id or not message_id:
        raise ValueError("user_id and message_id are required")
    if rating not in {"positive", "negative"}:
        raise ValueError("rating must be 'positive' or 'negative'")
    comment = str(comment).strip() if comment is not None else None
    if comment == "":
        comment = None
    if comment is not None and len(comment) > 2000:
        raise ValueError("comment must be 2000 characters or fewer")

    now = _now()
    existing = connection.execute(
        "SELECT feedback_id, created_at FROM answer_feedback WHERE user_id = ? AND message_id = ?",
        (user_id, message_id),
    ).fetchone()
    feedback_id = existing["feedback_id"] if existing else str(uuid.uuid4())
    created_at = existing["created_at"] if existing else now
    connection.execute(
        """INSERT INTO answer_feedback(
               feedback_id, user_id, message_id, rating, comment, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(user_id, message_id) DO UPDATE SET
               rating = excluded.rating,
               comment = excluded.comment,
               updated_at = excluded.updated_at""",
        (feedback_id, user_id, message_id, rating, comment, created_at, now),
    )
    connection.commit()
    saved = connection.execute(
        """SELECT feedback_id, user_id, message_id, rating, comment, created_at, updated_at
           FROM answer_feedback WHERE user_id = ? AND message_id = ?""",
        (user_id, message_id),
    ).fetchone()
    return _row(saved)


def retrieve_answer_feedback(
    connection: sqlite3.Connection,
    user_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT feedback_id, user_id, message_id, rating, comment, created_at, updated_at
           FROM answer_feedback WHERE user_id = ?
           ORDER BY updated_at DESC, feedback_id DESC LIMIT ?""",
        (str(user_id), max(1, min(limit, 500))),
    ).fetchall()
    return [_row(row) for row in rows]


def record_shared_note(
    connection: sqlite3.Connection,
    *,
    author: str,
    text: str,
    asset_id: str | None = None,
    well_type: str | None = None,
    confirmed: bool = True,
) -> dict[str, Any]:
    row = {
        "note_id": str(uuid.uuid4()),
        "asset_id": asset_id,
        "well_type": well_type,
        "author": author,
        "created_at": _now(),
        "text": text,
        "confirmed": 1 if confirmed else 0,
    }
    connection.execute(
        """INSERT INTO shared_notes(note_id, asset_id, well_type, author, created_at, text, confirmed)
           VALUES (:note_id, :asset_id, :well_type, :author, :created_at, :text, :confirmed)""",
        row,
    )
    connection.commit()
    return row


def _matches_scope(correction: dict[str, Any], well: dict[str, Any], inspection: dict[str, Any]) -> bool:
    if correction.get("scope") == "well" and correction.get("well_id") != well.get("asset_id"):
        return False
    if correction.get("scope") == "well_type" and correction.get("well_type") != well.get("well_type"):
        return False
    inspection_id = correction.get("inspection_id")
    if inspection_id and inspection_id != inspection.get("inspection_id"):
        return False
    return True


def _coerce(field: str, value: Any) -> Any:
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    text = str(value).strip()
    if field in {"spill_detected"}:
        return text.lower() in {"true", "1", "yes"}
    if any(token in field for token in ("temp", "volume", "bbl", "pct", "hours", "cost")):
        try:
            return float(text)
        except ValueError:
            return value
    if field.endswith("_count") or "threshold" in field:
        try:
            return int(float(text))
        except ValueError:
            return value
    return value


def apply_corrections_to_inspection(
    inspection: dict[str, Any],
    well: dict[str, Any],
    corrections: list[dict[str, Any]],
) -> dict[str, Any]:
    overlay = dict(inspection)
    applied: list[dict[str, Any]] = []
    for correction in corrections:
        field = correction.get("field")
        if not field or str(field).startswith("rca_"):
            continue
        if not _matches_scope(correction, well, overlay):
            continue
        if field in {"volume_bbl", "spill_volume_bbl"}:
            field = "spill_est_volume_bbl"
        overlay[f"_original_{field}"] = overlay.get(field)
        overlay[field] = _coerce(str(field), correction.get("corrected_value"))
        applied.append(correction)
    if applied:
        overlay["_applied_corrections"] = applied
    return overlay


def rca_threshold_override(
    well: dict[str, Any],
    equipment_kind: str | None,
    corrections: list[dict[str, Any]],
) -> dict[str, Any] | None:
    matches = []
    for correction in corrections:
        if correction.get("field") not in {"rca_corrective_count", "rca_threshold"}:
            continue
        if correction.get("scope") == "well" and correction.get("well_id") != well.get("asset_id"):
            continue
        if correction.get("scope") == "well_type" and correction.get("well_type") != well.get("well_type"):
            continue
        kind = correction.get("equipment_kind")
        if kind and equipment_kind and kind != equipment_kind:
            continue
        matches.append(correction)
    if not matches:
        return None
    return matches[-1]


def open_memory(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(database_path).expanduser().resolve())
    connection.row_factory = sqlite3.Row
    ensure_schema(connection)
    return connection
