from __future__ import annotations

import json
import re
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.ingest.loader import load_dataset
from backend.app.llm.engine import CopilotEngine
from backend.app.llm.rules_fallback import extract_intent
from backend.app.tools.db import get_reference_date, get_sample_data_root
from backend.app.tools.metrics import query_metric


_QUESTION_SET = Path(__file__).parent / "fixtures" / "unseen_metric_questions.json"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_source(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    wells: list[dict[str, Any]] = []
    inspections: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    maintenance: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for path in (root / "assets").glob("*/metadata.json"):
        wells.append(json.loads(path.read_text(encoding="utf-8")))
        asset_dir = path.parent
        inspections.extend(_jsonl(asset_dir / "inspections.jsonl"))
        contexts.extend(_jsonl(asset_dir / "context.jsonl"))
        maintenance.extend(_jsonl(asset_dir / "maintenance.jsonl"))
        events.extend(_jsonl(asset_dir / "regulatory-events.jsonl"))
    return tuple(pd.DataFrame(rows) for rows in (wells, inspections, contexts, maintenance, events))  # type: ignore[return-value]


def _period_bounds(spec: dict[str, Any], reference: date) -> tuple[str, str]:
    kind = spec["kind"]
    if kind == "days":
        start, end = reference - timedelta(days=int(spec["amount"])), reference
    elif kind == "months":
        offset = reference.year * 12 + reference.month - 1 - int(spec["amount"])
        year, month_zero = divmod(offset, 12)
        month = month_zero + 1
        start = date(year, month, min(reference.day, monthrange(year, month)[1]))
        end = reference
    elif kind == "last_quarter":
        current = (reference.month - 1) // 3 + 1
        quarter = current - 1 or 4
        year = reference.year if current > 1 else reference.year - 1
        month = 1 + (quarter - 1) * 3
        start = date(year, month, 1)
        end_month = month + 2
        end = min(date(year, end_month, monthrange(year, end_month)[1]), reference)
    elif kind == "this_summer":
        start = date(reference.year, 6, 1)
        end = min(date(reference.year, 8, 31), reference)
        if start > reference:
            end = start
    elif kind == "spring":
        candidates = [date(year, 3, 1) for year in range(reference.year - 2, reference.year + 1)]
        start = max(candidate for candidate in candidates if date(candidate.year, 5, 31) < reference)
        end = date(start.year, 5, 31)
    elif kind == "year":
        year = int(spec["year"])
        start = date(year, 1, 1)
        end = reference if year == reference.year else date(year, 12, 31)
    elif kind == "range":
        return str(spec["from"]), str(spec["to"])
    elif kind == "previous_year":
        start = date(reference.year - 1, 1, 1)
        end = date(reference.year - 1, 12, 31)
    elif kind == "this_year":
        start, end = date(reference.year, 1, 1), reference
    else:
        raise AssertionError(f"Unsupported oracle period: {kind}")
    return start.isoformat(), end.isoformat()


def _thresholds(root: Path, well_types: list[str]) -> dict[str, float]:
    result: dict[str, float] = {}
    for well_type in well_types:
        text = (root / "fleet" / "well-types" / f"{well_type}.md").read_text(encoding="utf-8")
        patterns = (
            r"at least\s+\*\*(\d+(?:\.\d+)?)\s*°\s*C\s+above\s+ambient",
            r"exceeds?\s+ambient(?:\s+temperature)?\s+by\s+a\s+minimum\s+of\s+\*\*(\d+(?:\.\d+)?)\s*°?\s*C",
            r"(?:temperature\s+)?(?:delta|difference)\s+of\s+at\s+least\s+\*\*(\d+(?:\.\d+)?)\s*°\s*C",
        )
        match = next((found for pattern in patterns if (found := re.search(pattern, text, re.IGNORECASE))), None)
        assert match, f"Independent oracle cannot parse {well_type} manual"
        result[well_type] = float(match.group(1))
    return result


def _effective_spill(row: dict[str, Any], notes: list[dict[str, Any]], as_of: str) -> bool:
    event_date = str(row.get("inspected_at", ""))[:10]
    candidates: list[tuple[str, bool]] = []
    for note in notes:
        if note.get("note_type") != "correction" or note.get("inspection_id") != row.get("inspection_id"):
            continue
        created = str(note.get("created_at", ""))[:10]
        valid_from = str(note.get("valid_from", ""))[:10]
        valid_to = str(note.get("valid_to", ""))[:10]
        text = str(note.get("text", "")).casefold()
        if (created and (created < event_date or created > as_of)) or (valid_from and valid_from > event_date) or (valid_to and valid_to < event_date):
            continue
        if re.search(r"\bnot\s+(?:a\s+)?(?:crude\s+)?spill\b|\bnot crude\b|\bfalse positive\b", text):
            candidates.append((created, False))
        elif re.search(r"\bconfirmed\s+(?:as\s+)?(?:a\s+)?spill\b|\bactual crude spill\b", text):
            candidates.append((created, True))
    return sorted(candidates, key=lambda item: item[0])[-1][1] if candidates else bool(row.get("spill_detected"))


def _independent_rows(
    root: Path,
    metric: str,
    *,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    wells, inspections, contexts, maintenance, events = _read_source(root)
    areas_payload = json.loads((root / "fleet" / "areas.json").read_text(encoding="utf-8"))
    area_names = {row["area_id"]: row["name"] for row in areas_payload["areas"]}
    well_metadata = wells.set_index("asset_id").to_dict("index")
    well_types = list(wells["well_type"].dropna().astype(str).unique())
    thresholds = _thresholds(root, well_types)
    notes_by_inspection: dict[str, list[dict[str, Any]]] = {}
    for note in contexts.to_dict("records"):
        if note.get("inspection_id"):
            notes_by_inspection.setdefault(str(note["inspection_id"]), []).append(note)
    evidence: list[dict[str, Any]] = []

    def add(well_id: str, event_date: str, value: float) -> None:
        metadata = well_metadata[well_id]
        evidence.append(
            {
                "well_id": well_id,
                "well_type": metadata.get("well_type"),
                "area": area_names.get(metadata.get("area_id"), "Unknown area"),
                "date": event_date,
                "value": value,
            }
        )

    if metric in {"downtime_days", "spill_volume", "late_reports"}:
        joined = inspections.merge(wells[["asset_id", "well_type", "area_id"]], on="asset_id", how="left")
        joined["date"] = pd.to_datetime(joined["inspected_at"], utc=True).dt.date.astype(str)
        joined = joined.loc[(joined["date"] >= start) & (joined["date"] <= end)]
        sop = (root / "fleet" / "sops" / "spill-response-sop.md").read_text(encoding="utf-8")
        class_lines = {
            cells[0].strip().casefold(): cells[1].strip().casefold()
            for line in sop.splitlines()
            if len(cells := [cell.strip().strip("*") for cell in line.strip().strip("|").split("|")]) >= 2
        }
        report_min = float(re.search(r"\d+(?:\.\d+)?", class_lines["reportable"]).group())
        major_min = float(re.search(r"\d+(?:\.\d+)?", class_lines["major"]).group())
        deadline_match = re.search(
            r"within\s+\*\*(\d+(?:\.\d+)?)\s+hours\*\*.*?within\s+\*\*(\d+(?:\.\d+)?)\s+hours\*\*\s+for a major spill",
            sop,
            flags=re.IGNORECASE | re.DOTALL,
        )
        assert deadline_match, "Independent oracle cannot parse spill report deadlines"
        regular_deadline, major_deadline = map(float, deadline_match.groups())
        events_by_inspection = {
            str(event.get("related_inspection_id")): event
            for event in events.to_dict("records")
            if event.get("event_type") == "spill_report_filed" and event.get("related_inspection_id")
        }
        for row in joined.to_dict("records"):
            well_id = str(row["asset_id"])
            if metric == "downtime_days":
                delta = pd.to_numeric(pd.Series([row.get("wellhead_temp_c")]), errors="coerce").iloc[0] - pd.to_numeric(pd.Series([row.get("ambient_temp_c")]), errors="coerce").iloc[0]
                if pd.notna(delta) and float(delta) < thresholds[str(row["well_type"])]:
                    add(well_id, str(row["date"]), 7.0)
                continue

            notes = notes_by_inspection.get(str(row.get("inspection_id")), [])
            detected = _effective_spill(row, notes, end)
            if not detected:
                continue
            volume_value = pd.to_numeric(pd.Series([row.get("spill_est_volume_bbl")]), errors="coerce").iloc[0]
            volume = 0.0 if pd.isna(volume_value) else float(volume_value)
            if metric == "spill_volume":
                add(well_id, str(row["date"]), volume)
                continue
            if pd.isna(volume_value) or volume < report_min:
                continue
            deadline = major_deadline if volume >= major_min else regular_deadline
            event = events_by_inspection.get(str(row.get("inspection_id")))
            if event is not None:
                hours = event.get("hours_to_report")
                missed = hours is not None and float(hours) > deadline
            else:
                inspected = datetime.fromisoformat(str(row["inspected_at"]).replace("Z", "+00:00"))
                if inspected.tzinfo is None:
                    inspected = inspected.replace(tzinfo=timezone.utc)
                due = inspected + timedelta(hours=deadline)
                cutoff = datetime.combine(date.fromisoformat(end), time.max, tzinfo=timezone.utc)
                missed = due <= cutoff
            if missed:
                add(well_id, str(row["date"]), 1.0)

    elif metric == "repair_cost":
        for row in maintenance.to_dict("records"):
            event_date = str(row.get("started_at", ""))[:10]
            if not event_date or not start <= event_date <= end:
                continue
            cost = row.get("cost_usd") if isinstance(row.get("cost_usd"), dict) else {}
            add(str(row["asset_id"]), event_date, float(cost.get("total") or 0))

    elif metric == "containment_breaches":
        sop = (root / "fleet" / "sops" / "spill-response-sop.md").read_text(encoding="utf-8")
        limit_match = re.search(r"(\d+)-hour containment limit", sop, re.IGNORECASE)
        assert limit_match, "Independent oracle cannot parse the containment limit"
        limit = float(limit_match.group(1))
        pattern = re.compile(r"\bcontained\s+(?:(?:about|approximately)\s+)?(\d+(?:\.\d+)?)\s+hours? after (?:the )?inspection(?:\s+flight)?\b", re.IGNORECASE)
        for row in maintenance.to_dict("records"):
            well_id = str(row.get("asset_id"))
            event_date = str(row.get("started_at", ""))[:10]
            if not event_date or not start <= event_date <= end:
                continue
            report_file = row.get("report_file")
            if not report_file:
                continue
            report_path = root / str(report_file)
            if not report_path.is_file():
                report_path = root / "assets" / well_id / str(report_file)
            if not report_path.is_file():
                continue
            match = pattern.search(report_path.read_text(encoding="utf-8"))
            if match and float(match.group(1)) > limit:
                add(well_id, event_date, 1.0)
    else:
        raise AssertionError(f"Unrecognized oracle metric: {metric}")
    return evidence


def _oracle_grouped(
    root: Path,
    metric: str,
    *,
    area: str | None,
    well_type: str | None,
    well_id: str | None,
    start: str,
    end: str,
    group_by: str,
) -> dict[str, float]:
    areas = json.loads((root / "fleet" / "areas.json").read_text(encoding="utf-8"))["areas"]
    area_ids = {str(row["area_id"]) for row in areas if area and area.casefold() in {str(row["area_id"]).casefold(), str(row["name"]).casefold()}}
    selected = []
    for row in _independent_rows(root, metric, start=start, end=end):
        metadata = row
        if area and metadata["area"] not in {str(item["name"]) for item in areas if str(item["area_id"]) in area_ids}:
            continue
        if well_type and str(metadata["well_type"]).casefold() != well_type.casefold():
            continue
        if well_id and str(metadata["well_id"]).casefold() != well_id.casefold():
            continue
        if group_by == "well":
            group = str(metadata["well_id"])
        elif group_by == "area":
            group = str(metadata["area"])
        elif group_by == "well_type":
            group = str(metadata["well_type"])
        else:
            group = str(metadata["date"])[:7]
        selected.append((group, float(metadata["value"])))
    grouped: dict[str, float] = {}
    for group, value in selected:
        grouped[group] = round(grouped.get(group, 0.0) + value, 2)
    return grouped


def _format_questions(root: Path) -> list[dict[str, Any]]:
    areas = json.loads((root / "fleet" / "areas.json").read_text(encoding="utf-8"))["areas"]
    wells, _, _, _, _ = _read_source(root)
    area_names = [str(row["name"]) for row in sorted(areas, key=lambda row: row["name"])]
    well_types = sorted(wells["well_type"].dropna().astype(str).unique())
    tokens = {f"area{index}": value for index, value in enumerate(area_names)}
    tokens.update({f"type{index}": value for index, value in enumerate(well_types)})
    source = json.loads(_QUESTION_SET.read_text(encoding="utf-8"))
    return [{**item, "question": item["question"].format(**tokens)} for item in source]


def test_unseen_questions_match_independent_pandas_ground_truth(tmp_path: Path, monkeypatch) -> None:
    root = get_sample_data_root()
    database = tmp_path / "unseen-questions.db"
    load_dataset(root, database)
    monkeypatch.setenv("ASSET_INTELLIGENCE_DB", str(database))
    monkeypatch.setenv("ASSET_INTELLIGENCE_DATASET", str(root))
    monkeypatch.delenv("REFERENCE_DATE", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "rules")
    reference = date.fromisoformat(get_reference_date(database))
    questions = _format_questions(root)
    assert len(questions) >= 20

    for case in questions:
        question = case["question"]
        intent = extract_intent(question)
        assert intent.metric == case["metric"], f"{case['id']} intent metric: {question}"
        assert intent.group_by == case["group_by"], f"{case['id']} group: {question}"
        if case.get("area"):
            expected_area = json.loads((root / "fleet" / "areas.json").read_text(encoding="utf-8"))["areas"]
            expected_area = sorted(expected_area, key=lambda row: row["name"])[int(case["area"][4:])]["name"]
            assert intent.area_name == expected_area, f"{case['id']} area: {question}"
        if case.get("well_type"):
            assert intent.well_type == sorted(_read_source(root)[0]["well_type"].dropna().astype(str).unique())[int(case["well_type"][4:])], f"{case['id']} type: {question}"

        start, end = _period_bounds(case["period"], reference)
        tool = query_metric(
            intent.metric,  # type: ignore[arg-type]
            area=intent.area_name,
            well_type=intent.well_type,
            well_id=intent.well_ids[0] if intent.well_ids else None,
            date_from=intent.date_from,
            date_to=intent.date_to,
            season=intent.season,
            quarter=intent.quarter,
            year=intent.year,
            date_phrase=intent.date_phrase,
            group_by=intent.group_by,  # type: ignore[arg-type]
            reference_date=reference.isoformat(),
        )
        expected = _oracle_grouped(
            root,
            case["metric"],
            area=case.get("area") and intent.area_name,
            well_type=intent.well_type,
            well_id=intent.well_ids[0] if intent.well_ids else None,
            start=start,
            end=end,
            group_by=case["group_by"],
        )
        actual = {str(row["group"]): float(row["value"]) for row in tool["rows"]}
        assert tool["filters"]["date_from"] == start, f"{case['id']} start range: {question}"
        assert tool["filters"]["date_to"] == end, f"{case['id']} end range: {question}"
        assert actual == expected, f"{case['id']} mismatch for {question}: expected={expected}, actual={actual}"

    # Exercise the chat engine's generic metric branch with one unseen phrasing.
    case = questions[12]
    intent = extract_intent(case["question"])
    response = CopilotEngine(as_of=reference.isoformat()).process_query(
        case["question"], "unseen-eval-user", intent=intent
    )
    assert response["visualization"]["type"] == "bar"
    assert response["citations"]
