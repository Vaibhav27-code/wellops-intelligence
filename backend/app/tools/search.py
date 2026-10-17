from __future__ import annotations

from typing import Any

from backend.app.tools.db import query_documents_fts, query_records


def search_manuals_and_sops(query: str, well_type: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    docs = query_documents_fts(query, limit=limit * 2)
    filtered = []
    for d in docs:
        if d.get("document_type") not in ("manual", "sop", "well_type_manual"):
            continue
        if well_type and d.get("asset_id") and d.get("asset_id") != well_type:
            continue
        filtered.append(
            {
                "title": d.get("title"),
                "source_path": d.get("source_path"),
                "document_type": d.get("document_type"),
                "content": d.get("content"),
                "match_snippet": d.get("match_snippet"),
            }
        )
        if len(filtered) >= limit:
            break
    return filtered


def search_human_notes(
    query: str | None = None,
    well_id: str | None = None,
    note_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    notes = query_records("context", asset_id=well_id, order_by_event=True, descending=True)
    results = []
    for n in notes:
        if note_type and n.get("note_type") != note_type:
            continue
        if query:
            q = query.lower()
            text = str(n.get("text", "")).lower()
            if q not in text:
                continue
        results.append(n)
        if len(results) >= limit:
            break
    return results
