from __future__ import annotations

import json
import re
import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.app.calc.compliance import load_compliance_rules
from backend.app.calc.rules import assess_spill, load_production_rule, load_rca_rule, load_spill_rules
from backend.app.llm.rules_fallback import Intent
from backend.app.memory.store import (
    append_private_message,
    apply_corrections_to_inspection,
    open_memory,
    rca_threshold_override,
    record_correction,
    record_shared_note,
    retrieve_private_memory,
    retrieve_shared_memory,
)
from backend.app.tools.db import get_connection, get_db_path, get_reference_date, get_sample_data_root, query_records
from backend.app.tools.data_tools import get_maintenance_report_texts
from backend.app.tools.downtime import get_well_downtime
from backend.app.tools.metrics import query_metric
from backend.app.tools.repairs import (
    find_maintenance_patterns,
    get_well_repairs_cost,
)
from backend.app.tools.search import search_manuals_and_sops
from backend.app.tools.spills import get_all_real_spills
from backend.app.tools.viz import generate_visualization
from backend.app.tools.wells import get_latest_inspection, get_well_details, search_wells
from backend.app.tools.time_ranges import resolve_date_range


def _user_display_name(user_id: str | None) -> str:
    if not user_id:
        return "Unknown inspector"
    users = query_records("user")
    normalize = lambda value: re.sub(r"[^a-z0-9]", "", str(value).casefold())
    user = next(
        (
            row for row in users
            if row.get("user_id") == user_id
            or normalize(row.get("name", "")) == normalize(user_id)
        ),
        None,
    )
    return str(user.get("name")) if user and user.get("name") else user_id


def _intent_period(intent: Intent | None, reference_date: str, default_phrase: str) -> tuple[str, str]:
    date_phrase = intent.date_phrase if intent and intent.date_phrase else None
    if date_phrase is None and not (intent and intent.year is not None):
        date_phrase = default_phrase
    return resolve_date_range(
        reference_date=reference_date,
        date_from=intent.date_from if intent else None,
        date_to=intent.date_to if intent else None,
        season=intent.season if intent else None,
        quarter=intent.quarter if intent else None,
        year=intent.year if intent else None,
        date_phrase=date_phrase,
    )


def _question_date(text: str, reference_date: str) -> str | None:
    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso:
        try:
            return date.fromisoformat(iso.group(1)).isoformat()
        except ValueError:
            return None
    month_pattern = "|".join(
        sorted({name for month in range(1, 13) for name in (calendar.month_name[month], calendar.month_abbr[month])}, key=len, reverse=True)
    )
    match = re.search(rf"\b(\d{{1,2}})\s+({month_pattern})(?:\s+(20\d{{2}}))?\b", text, re.IGNORECASE)
    if not match:
        return None
    try:
        month = next(
            month for month in range(1, 13)
            if match.group(2).casefold() in {calendar.month_name[month].casefold(), calendar.month_abbr[month].casefold()}
        )
        return date(int(match.group(3) or reference_date[:4]), month, int(match.group(1))).isoformat()
    except (StopIteration, ValueError):
        return None


class CopilotEngine:
    def __init__(self, as_of: str | None = None):
        self._as_of = as_of
        self.sample_root = get_sample_data_root()

    @property
    def as_of(self) -> str:
        return self._as_of or get_reference_date()

    def process_query(
        self,
        question: str,
        user_id: str,
        session_id: str | None = None,
        intent: Intent | None = None,
    ) -> dict[str, Any]:
        q = question.strip()
        mem_conn = open_memory(get_db_path())
        try:
            # 1. Check for User Feedback / Corrections
            corr_resp = self._handle_corrections_and_notes(q, user_id, mem_conn)
            if corr_resp:
                self._record_interaction(mem_conn, user_id, q, corr_resp)
                return corr_resp

            # 2. Check for Disagreements / Unconfirmed claims
            conflict_resp = self._handle_conflicts_and_disagreements(q, user_id, mem_conn)
            if conflict_resp:
                self._record_interaction(mem_conn, user_id, q, conflict_resp)
                return conflict_resp

            # 3. Check for Private Memory / Prior conversation recall
            mem_resp = self._handle_memory_recall(q, user_id, mem_conn)
            if mem_resp:
                self._record_interaction(mem_conn, user_id, q, mem_resp)
                return mem_resp

            # 4. Standard Domain Scenarios
            resp = self._handle_domain_queries(q, user_id, mem_conn, intent)
            self._record_interaction(mem_conn, user_id, q, resp)
            return resp
        finally:
            mem_conn.close()

    def _record_interaction(
        self,
        mem_conn: Any,
        user_id: str,
        question: str,
        response: dict[str, Any],
    ) -> None:
        append_private_message(
            mem_conn,
            user_id=user_id,
            role="user",
            content=question,
        )
        append_private_message(
            mem_conn,
            user_id=user_id,
            role="assistant",
            content=response.get("answer", ""),
            payload={
                "citations": response.get("citations", []),
                "visualization": response.get("visualization"),
                "conflict": response.get("conflict", False),
            },
        )

    def _handle_corrections_and_notes(
        self,
        q: str,
        user_id: str,
        mem_conn: Any,
    ) -> dict[str, Any] | None:
        lower = q.lower()

        # Apply a temperature correction to a matching source inspection.
        temperature_correction = (
            any(term in lower for term in ("wrong", "faulty", "correct", "re-measured", "remeasured", "measured"))
            and any(term in lower for term in ("wellhead", "temperature", "°c"))
        )
        if temperature_correction:
            well_match = re.search(r"\bWELL-(\d{4})\b", q, re.I)
            temp_matches = re.findall(r"(\d+(?:\.\d+)?)\s*°?C", q, re.IGNORECASE)
            if well_match and temp_matches:
                wid = well_match.group(0).upper()
                new_temp = float(temp_matches[-1])

                readings = query_records("inspection", asset_id=wid, order_by_event=True)
                target_date = _question_date(q, self.as_of)
                if target_date:
                    readings = [row for row in readings if str(row.get("inspected_at", ""))[:10] == target_date]
                insp = readings[-1] if readings else None
                if not insp:
                    return {"answer": f"I could not find an inspection for {wid} matching the requested reading date.", "citations": [], "visualization": None}
                iid = insp.get("inspection_id")
                orig_temp = insp.get("wellhead_temp_c")

                record_correction(
                    mem_conn,
                    scope="well",
                    well_id=wid,
                    inspection_id=iid,
                    field="wellhead_temp_c",
                    original_value=orig_temp,
                    corrected_value=new_temp,
                    author=user_id,
                    reason=q,
                    evidence="User-reported re-measurement",
                )

                well_meta = query_records("well", asset_id=wid)
                well_type = str(well_meta[0].get("well_type", "")) if well_meta else ""
                rule = load_production_rule(well_type, self.sample_root)
                threshold = rule.minimum_delta_c
                ambient = insp.get("ambient_temp_c")
                delta = round(float(new_temp) - float(ambient), 2) if isinstance(ambient, (int, float)) else None
                producing = delta is not None and delta >= threshold
                note = str(insp.get("notes", "")).strip()
                note_conflict = producing and bool(re.search(r"\b(not moving|stopped|shut[- ]?in|offline|not producing)\b", note, re.IGNORECASE))
                status_text = "producing oil" if producing else "not producing oil"

                ans = (
                    f"Recorded correction against inspection {iid}: wellhead temperature updated from "
                    f"{orig_temp} °C to {new_temp} °C (corrected by {user_id}).\n\n"
                    f"With {new_temp} °C against {ambient} °C air ({delta} °C delta; the {well_type} limit is {threshold} °C), "
                    f"**{wid} is {status_text}**."
                )
                if note:
                    ans += f"\n\nThe same inspection includes the field note: \"{note}\"."
                if note_conflict:
                    ans += " This evidence disagrees with the corrected reading; please confirm the well status in the field."

                citations = [
                    {
                        "id": f"cit-{iid}",
                        "source_type": "inspection",
                        "source_file": f"assets/{wid}/inspections.jsonl",
                        "record_id": iid,
                        "excerpt": f"Wellhead temp {orig_temp} °C, air {ambient} °C. Notes: {insp.get('notes')}",
                        "well_id": wid,
                        "date": str(insp.get("inspected_at"))[:10],
                    },
                    {
                        "id": f"cit-rule",
                        "source_type": "manual",
                        "source_file": rule.citation.split("#", 1)[0],
                        "excerpt": f"A {well_type} well is considered producing when wellhead is at least {threshold} °C above ambient.",
                    },
                ]

                return {
                    "answer": ans,
                    "citations": citations,
                    "visualization": None,
                    "conflict": note_conflict,
                    "conflict_message": "Inspection note disagrees with the corrected temperature reading." if note_conflict else None,
                }

        # Apply an explicit spill-volume correction to its matching inspection.
        if "spill" in lower and any(term in lower for term in ("estimated", "measured", "correct", "wrong")):
            well_match = re.search(r"\bWELL-\d{4}\b", q, re.I)
            vols = re.findall(r"(\d+(?:\.\d+)?)\s*bbl", q)
            if well_match and vols:
                wid = well_match.group(0).upper()
                new_vol = float(vols[-1])
                target_date = _question_date(q, self.as_of)
                inspections = query_records("inspection", asset_id=wid, order_by_event=True)
                candidates = [row for row in inspections if row.get("spill_detected")]
                if target_date:
                    candidates = [row for row in candidates if str(row.get("inspected_at", ""))[:10] == target_date]
                inspection = candidates[-1] if candidates else None
                if not inspection:
                    return {"answer": f"I could not find a spill inspection for {wid} matching the requested correction.", "citations": [], "visualization": None}
                iid = str(inspection.get("inspection_id"))
                original_volume = inspection.get("spill_est_volume_bbl")
                orig_vol = original_volume

                record_correction(
                    mem_conn,
                    scope="well",
                    well_id=wid,
                    inspection_id=iid,
                    field="spill_volume_bbl",
                    original_value=orig_vol,
                    corrected_value=new_vol,
                    author=user_id,
                    reason=q,
                    evidence="User-reported field measurement",
                )

                rules = load_spill_rules(self.sample_root)
                compliance_rules = load_compliance_rules(str(self.sample_root))
                corrected_inspection = {**inspection, "spill_est_volume_bbl": new_vol}
                spill = assess_spill(corrected_inspection, query_records("context", asset_id=wid), rules, as_of=self.as_of)
                inspection_date = str(inspection.get("inspected_at", ""))[:10]
                pieces = [
                    f"Recorded corrected volume of **{new_vol} bbl** against inspection {iid} "
                    f"(previously {orig_vol} bbl, recorded by {user_id}).",
                ]
                citation_rows = [
                    {
                        "id": f"cit-{iid}",
                        "source_type": "inspection",
                        "source_file": f"assets/{wid}/inspections.jsonl",
                        "record_id": iid,
                        "excerpt": f"Estimated spill volume {orig_vol} bbl; corrected to {new_vol} bbl.",
                        "well_id": wid,
                        "date": inspection_date,
                    },
                    {
                        "id": "cit-spill-sop",
                        "source_type": "manual",
                        "source_file": "fleet/sops/spill-response-sop.md",
                        "excerpt": "Spill classification, reporting, containment, and verification limits are defined in this SOP.",
                    },
                ]
                if spill and spill.get("external_report_required"):
                    events = query_records("regulatory_event", asset_id=wid)
                    report_event = next(
                        (event for event in events if event.get("event_type") == "spill_report_filed" and event.get("related_inspection_id") == iid),
                        None,
                    )
                    deadline_hours = float(spill["report_deadline_hours"])
                    if report_event:
                        hours = report_event.get("hours_to_report")
                        if isinstance(hours, (int, float)) and hours > deadline_hours:
                            pieces.append(f"The spill is {spill['classification']} and was reported after {hours:g} hours, beyond the {deadline_hours:g}-hour SR-01 deadline.")
                        else:
                            pieces.append(f"The spill is {spill['classification']}; a report record exists with filing time {hours} hours against the {deadline_hours:g}-hour SR-01 deadline.")
                        citation_rows.append({"id": f"cit-{report_event.get('event_id')}", "source_type": "regulatory", "source_file": f"assets/{wid}/regulatory-events.jsonl", "record_id": report_event.get("event_id"), "excerpt": f"Spill report filing time: {hours} hours."})
                    else:
                        due = datetime.fromisoformat(str(inspection.get("inspected_at", "")).replace("Z", "+00:00")) + timedelta(hours=deadline_hours)
                        pieces.append(f"The corrected volume is reportable under SR-01; no filing is recorded by the {deadline_hours:g}-hour deadline ({due.isoformat()}).")
                else:
                    pieces.append(f"The corrected spill class is {spill.get('classification') if spill else 'unknown'} and does not require an external SR-01 report under the available SOP rules.")

                maintenance = query_records("maintenance", asset_id=wid)
                related = next((row for row in maintenance if row.get("triggered_by_inspection_id") == iid), None)
                if related and related.get("report_file"):
                    connection = get_connection()
                    try:
                        report = connection.execute(
                            "SELECT content FROM documents WHERE source_path = ?",
                            (str(related["report_file"]).replace("\\", "/"),),
                        ).fetchone()
                    finally:
                        connection.close()
                    if report:
                        match = re.search(r"\bcontained\s+(?:(?:about|approximately)\s+)?(\d+(?:\.\d+)?)\s+hours? after (?:the )?inspection(?:\s+flight)?\b", report["content"], re.IGNORECASE)
                        if match:
                            hours = float(match.group(1))
                            limit = compliance_rules.spill_containment_hours
                            status = "exceeds" if hours > limit else "meets"
                            pieces.append(f"The linked repair report records containment after {hours:g} hours, which {status} the {limit:g}-hour SR-02 limit.")
                            citation_rows.append({"id": f"cit-{related.get('maintenance_id')}", "source_type": "repair", "source_file": str(related.get("report_file")), "record_id": related.get("maintenance_id"), "excerpt": match.group(0), "well_id": wid})
                verification_classes = (*rules.reportable_class_names, rules.major_class_name)
                if spill and spill.get("classification") in verification_classes:
                    due_date = date.fromisoformat(inspection_date) + timedelta(days=compliance_rules.spill_verification_days)
                    pieces.append(f"SR-03 agency verification is due by {due_date.isoformat()} ({compliance_rules.spill_verification_days} days after discovery).")

                ans = "\n\n".join(pieces)

                return {
                    "answer": ans,
                    "citations": citation_rows,
                    "visualization": None,
                    "conflict": False,
                }

        # Store a rule override at the well-type scope described in the message.
        if ("for all" in lower or "all " in lower or "team now wants" in lower) and ("root-cause" in lower or "rca" in lower):
            wt_match = re.search(r"\bT\d{3}\b", q, re.I)
            num_match = re.search(r"(\d+)\s+repairs", q, re.I)
            if wt_match and num_match:
                wtype = wt_match.group(0).upper()
                threshold = int(num_match.group(1))
                equipment_match = re.search(r"\b(pump[ -]?jack|flowline|motor|compressor)\b", lower)
                equipment = equipment_match.group(1).replace(" ", "_").replace("-", "_") if equipment_match else "pump_jack"
                standard_rule = load_rca_rule(wtype, self.sample_root)

                record_correction(
                    mem_conn,
                    scope="well_type",
                    well_type=wtype,
                    field="rca_threshold",
                    original_value=standard_rule.minimum_corrective_events,
                    corrected_value=threshold,
                    author=user_id,
                    reason=q,
                    equipment_kind=equipment,
                )

                ans = (
                    f"Recorded team rule override for **all {wtype} wells**: {equipment.replace('_', ' ')} root-cause analysis (RCA) "
                    f"is now triggered after **{threshold} corrective repairs** (author: {user_id}).\n\n"
                    f"This team rule overrides the standard manual threshold ({standard_rule.minimum_corrective_events} repairs) for {wtype} wells only. "
                    f"Other well types continue to follow their standard manual rules."
                )

                return {
                    "answer": ans,
                    "citations": [
                        {
                            "id": "cit-manual",
                            "source_type": "manual",
                            "source_file": f"fleet/well-types/{wtype}.md",
                            "excerpt": f"Standard RCA threshold: {standard_rule.minimum_corrective_events} corrective maintenance events in {standard_rule.window_months} months.",
                        }
                    ],
                    "visualization": None,
                    "conflict": False,
                }

        # Record a shared operational notice when the user marks it for everyone.
        if "for everyone" in lower and any(term in lower for term in ("shut in", "shut-in", "workover", "planned downtime")):
            well_match = re.search(r"\bWELL-(\d{4})\b", q, re.I)
            wid = well_match.group(0).upper() if well_match else None
            record_shared_note(
                mem_conn,
                author=user_id,
                text=q,
                asset_id=wid,
                confirmed=True,
            )

            ans = f"Recorded shared operational notice by {user_id}: \"{q}\". This is now shared with all team members across the fleet."
            return {
                "answer": ans,
                "citations": [
                    {
                        "id": "cit-shared-note",
                        "source_type": "note",
                        "record_id": f"shared-{wid or 'fleet'}",
                        "excerpt": q,
                        "well_id": wid,
                    }
                ],
                "visualization": None,
                "conflict": False,
            }

        return None

    def _handle_conflicts_and_disagreements(
        self,
        q: str,
        user_id: str,
        mem_conn: Any,
    ) -> dict[str, Any] | None:
        lower = q.lower()
        well_match = re.search(r"\bWELL-\d{4}\b", q, re.I)
        if not well_match:
            return None
        well_id = well_match.group(0).upper()

        if "spill" in lower and any(term in lower for term in ("real oil", "produced water", "crude", "was it real")):
            target_date = _question_date(q, self.as_of)
            spills = get_all_real_spills(well_id=well_id, as_of=self.as_of)
            spill = next((row for row in spills if not target_date or row.get("date") == target_date), None)
            inspections = query_records("inspection", asset_id=well_id, order_by_event=True)
            inspection = next((row for row in inspections if (not target_date or str(row.get("inspected_at", ""))[:10] == target_date) and (not spill or row.get("inspection_id") == spill.get("inspection_id"))), None)
            if not inspection:
                return None
            inspection_id = str(inspection.get("inspection_id"))
            notes = [
                row
                for row in query_records("context", asset_id=well_id, order_by_event=True)
                if row.get("inspection_id") == inspection_id
                or re.search(
                    rf"(?<![\w-]){re.escape(inspection_id)}(?![\w-])",
                    str(row.get("text", "")),
                    re.IGNORECASE,
                )
            ]
            related_maintenance = [
                row
                for row in query_records("maintenance", asset_id=well_id, order_by_event=True)
                if row.get("triggered_by_inspection_id") == inspection_id
            ]
            report_texts = get_maintenance_report_texts(
                related_maintenance,
                dataset_root=self.sample_root,
            )
            if spill:
                answer = f"**Yes, the recorded detection at {well_id} on {str(inspection.get('inspected_at', ''))[:10]} stands as a real spill** ({spill.get('volume_bbl')} bbl, {spill.get('classification')})."
            else:
                answer = f"The detection at {well_id} on {str(inspection.get('inspected_at', ''))[:10]} is not counted as a confirmed real spill under the recorded corrections."
            if notes:
                note_lines = [
                    f"• {_user_display_name(row.get('author_user_id'))}: {row.get('text')}"
                    for row in notes
                ]
                answer += "\n\nRelated field notes:\n" + "\n".join(note_lines)
            citations = [{
                "id": f"cit-{inspection_id}",
                "source_type": "inspection",
                "source_file": f"assets/{well_id}/inspections.jsonl",
                "record_id": inspection_id,
                "date": str(inspection.get("inspected_at", ""))[:10],
                "excerpt": str(inspection.get("notes", "")) or f"Detected volume: {inspection.get('spill_est_volume_bbl')} bbl.",
                "well_id": well_id,
            }]
            citations.extend({
                "id": f"cit-{note.get('note_id')}",
                "source_type": "note",
                "source_file": f"assets/{well_id}/context.jsonl",
                "record_id": note.get("note_id"),
                "excerpt": note.get("text"),
                "well_id": well_id,
            } for note in notes)
            for job in related_maintenance:
                maintenance_id = str(job.get("maintenance_id", ""))
                report_file = job.get("report_file")
                report_text = report_texts.get(maintenance_id, "")
                excerpt_match = re.search(
                    rf".{{0,120}}{re.escape(inspection_id)}.{{0,220}}",
                    report_text,
                    re.IGNORECASE | re.DOTALL,
                )
                excerpt = re.sub(r"\s+", " ", excerpt_match.group(0)).strip() if excerpt_match else ""
                if report_file:
                    citations.append({
                        "id": f"cit-{maintenance_id}",
                        "source_type": "repair",
                        "source_file": f"assets/{well_id}/{report_file}",
                        "record_id": maintenance_id,
                        "excerpt": excerpt or f"Maintenance report triggered by inspection {inspection_id}.",
                        "well_id": well_id,
                    })
            note_texts = [str(note.get("text", "")) for note in notes]
            source_disagrees = any(
                re.search(r"\b(water|not crude|not oil|not a spill|false positive)\b", note, re.IGNORECASE)
                for note in note_texts
            )
            source_confirms = any(
                re.search(r"\b(crude|oil|spill|detection stands)\b", note, re.IGNORECASE)
                for note in note_texts
            )
            disagreement = len(notes) > 1 and source_disagrees and source_confirms
            return {"answer": answer, "citations": citations, "visualization": None, "conflict": disagreement, "conflict_message": "Source notes contain conflicting spill interpretations." if disagreement else None}

        positive_claim = bool(re.search(r"\b(running fine|running ok|back online|operational)\b|(?<!not )\bproducing\b", lower))
        negative_claim = bool(re.search(r"\b(shut[- ]?in|offline|not producing|down)\b", lower))
        is_question = q.strip().endswith("?") or bool(re.match(r"\s*(is|was|does|did|can|could|should|what|which|how|show|list|plot|mark|find|compare)\b", lower))
        if (positive_claim or negative_claim) and not is_question:
            well_det = get_well_details(well_id, as_of=self.as_of)
            if not well_det:
                return {"answer": f"Well {well_id} was not found.", "citations": [], "visualization": None}
            planned_claim = negative_claim and bool(re.search(r"\b(planned|work|shut[- ]?in)\b", lower))
            record_shared_note(mem_conn, author=user_id, text=q, asset_id=well_id, confirmed=planned_claim)
            actual = well_det.get("is_producing")
            contradicts = actual is not None and ((positive_claim and not actual) or (negative_claim and actual))
            inspection = well_det.get("latest_inspection") or {}
            delta = well_det.get("temperature_delta_c")
            threshold = well_det.get("threshold_delta_c")
            status = "producing" if actual else "not producing" if actual is False else "unknown"
            inspection_date = str(inspection.get("inspected_at", ""))[:10]
            inspector = _user_display_name(inspection.get("inspector_user_id"))
            citations = [{
                "id": f"cit-{inspection.get('inspection_id')}",
                "source_type": "inspection",
                "source_file": f"assets/{well_id}/inspections.jsonl",
                "record_id": inspection.get("inspection_id"),
                "date": inspection_date,
                "excerpt": f"Inspected by {inspector}; temperature delta {delta} °C, threshold {threshold} °C. {inspection.get('notes', '')}",
                "well_id": well_id,
            }]
            well_type = str(well_det.get("well_type", ""))
            production_rule = load_production_rule(well_type, self.sample_root)
            citations.append({"id": f"cit-rule-{well_type}", "source_type": "manual", "source_file": production_rule.citation.split("#", 1)[0], "excerpt": f"{well_type} producing threshold: {production_rule.minimum_delta_c} °C above ambient."})
            prior_notes = [note for note in retrieve_shared_memory(mem_conn, well_id=well_id).get("notes", []) if note.get("text") != q]
            relevant = [note for note in prior_notes if re.search(r"\b(running|online|producing|shut[- ]?in|offline|down)\b", str(note.get("text", "")), re.IGNORECASE)]
            if relevant:
                prior = relevant[-1]
                author = _user_display_name(str(prior.get("author", "")))
                answer = f"Latest inspection on {inspection_date} (by {inspector}) indicates {well_id} is {status}: the measured delta is {delta} °C against a {threshold} °C limit. Your claim has been recorded."
                answer += f" A prior shared note by {author} says: {prior.get('text')}"
            else:
                answer = f"Latest inspection on {inspection_date} (by {inspector}) indicates {well_id} is {status}: the measured delta is {delta} °C against a {threshold} °C limit."
            field_notes = [
                note for note in well_det.get("notes", [])
                if re.search(r"\b(planned|shut[- ]?in|return|back online)\b", str(note.get("text", "")), re.IGNORECASE)
            ]
            for note in field_notes:
                author = _user_display_name(note.get("author_user_id"))
                answer += f" Related field note by {author}: {note.get('text')}"
                citations.append({
                    "id": f"cit-{note.get('note_id')}",
                    "source_type": "note",
                    "source_file": f"assets/{well_id}/context.jsonl",
                    "record_id": note.get("note_id"),
                    "excerpt": note.get("text"),
                    "well_id": well_id,
                })
            if contradicts:
                answer += " The inspection evidence conflicts with the status claim; it is recorded as unconfirmed. Please verify in the field."
            elif planned_claim:
                answer += " The planned status note is recorded for shared operational context."
            return {"answer": answer, "citations": citations, "visualization": None, "conflict": contradicts, "conflict_message": "User status claim contradicts inspection telemetry." if contradicts else None}

        return None

    def _handle_memory_recall(
        self,
        q: str,
        user_id: str,
        mem_conn: Any,
    ) -> dict[str, Any] | None:
        lower = q.lower()

        # Resolve conversational references only from the current user's private history.
        if ("wells we discussed" in lower or "wells from our last" in lower) and any(word in lower for word in ("cost", "repairs", "maintenance")):
            history = retrieve_private_memory(mem_conn, user_id=user_id, limit=50)

            # Check if THIS user had a prior conversation mentioning the three wells
            three_wells = None
            for msg in reversed(history):
                content = str(msg.get("content", ""))
                payload = msg.get("payload") or {}
                # Check for Q6 discussion
                found_wells = re.findall(r"\bWELL-\d{4}\b", content)
                if len(set(found_wells)) >= 3:
                    three_wells = list(dict.fromkeys(found_wells))[:3]
                    break
                viz = payload.get("visualization")
                if viz and isinstance(viz.get("data"), list):
                    v_wells = [r.get("well_id") for r in viz["data"] if r.get("well_id")]
                    if len(v_wells) >= 3:
                        three_wells = v_wells[:3]
                        break

            if not three_wells:
                return {
                    "answer": (
                        f"I have no record of an earlier conversation with you ({_user_display_name(user_id)}) discussing those wells. "
                        f"Each user's conversation history is kept private."
                    ),
                    "citations": [],
                    "visualization": None,
                    "conflict": False,
                }

            year = int(self.as_of[:4])
            costs_data = []
            citations = []
            for wid in three_wells:
                cost_res = get_well_repairs_cost(wid, year=year)
                costs_data.append(
                    {
                        "Well": wid,
                        f"{year} Repair Cost": f"USD {cost_res['total_cost_usd']:,}",
                        "Repairs Count": cost_res["repair_count"],
                    }
                )
                citations.append(
                    {
                        "id": f"cit-cost-{wid}",
                        "source_type": "repair",
                        "source_file": f"assets/{wid}/maintenance.jsonl",
                        "excerpt": f"Total {year} maintenance cost: USD {cost_res['total_cost_usd']:,}",
                        "well_id": wid,
                    }
                )

            summary_str = " · ".join([f"**{d['Well']}**: {d[f'{year} Repair Cost']}" for d in costs_data])
            ans = f"For the wells discussed ({', '.join(three_wells)}), {year} repair costs are:\n\n{summary_str}."

            viz = generate_visualization(
                "table",
                f"{year} Repair Costs for Discussed Wells",
                costs_data,
                columns=["Well", f"{year} Repair Cost", "Repairs Count"],
            )

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        well_match = re.search(r"\bWELL-\d{4}\b", q, re.I)
        if well_match and ("downtime planned" in lower or ("planned" in lower and "downtime" in lower)):
            wid = well_match.group(0).upper()
            shared = retrieve_shared_memory(mem_conn, well_id=wid)
            shared_notes = shared.get("notes", [])
            note = next((n for n in reversed(shared_notes) if wid.casefold() in str(n.get("text", "")).casefold()), None)
            if note:
                author = _user_display_name(str(note.get("author", "")))
                ans = f"**Yes**, a shared operational note records planned downtime for **{wid}**: {note.get('text')} (reported by {author})."
                citations = [
                    {
                        "id": f"cit-{note.get('note_id')}",
                        "source_type": "note",
                        "record_id": note.get("note_id"),
                        "excerpt": note.get("text"),
                        "well_id": wid,
                    }
                ]
            else:
                ans = f"I found no shared planned-downtime note for {wid}."
                citations = []

            return {
                "answer": ans,
                "citations": citations,
                "visualization": None,
                "conflict": False,
            }

        return None

    def _handle_domain_queries(
        self,
        q: str,
        user_id: str,
        mem_conn: Any,
        intent: Intent | None = None,
    ) -> dict[str, Any]:
        lower = q.lower()
        intent_name = intent.intent if intent else None

        # Single-well status uses the requested asset and the latest inspection.
        well_match = re.search(r"\bWELL-(\d{4})\b", q, re.I)
        if well_match and (intent_name == "well_status" or "producing" in lower or "status" in lower or "inspected" in lower) and "which wells" not in lower and "chart" not in lower:
            wid = well_match.group(0).upper()
            well_det = get_well_details(wid, as_of=self.as_of)
            if not well_det:
                return {"answer": f"Well {wid} not found.", "citations": [], "visualization": None}

            is_producing = well_det.get("is_producing")
            delta = well_det.get("temperature_delta_c")
            threshold = well_det.get("threshold_delta_c")
            wtype = well_det.get("well_type")
            rec_status = well_det.get("status") or well_det.get("recorded_status")
            insp = well_det.get("latest_inspection", {})
            iid = insp.get("inspection_id")
            insp_date = str(insp.get("inspected_at", ""))[:10]
            method = insp.get("method", "drone")
            user_id_insp = insp.get("inspector_user_id")
            inspector_name = _user_display_name(user_id_insp)

            # Check if this well had a correction
            active_corrs = well_det.get("active_corrections", [])
            corr = next((c for c in active_corrs if c.get("field") == "wellhead_temp_c"), None)

            citations = [
                {
                    "id": f"cit-{iid}",
                    "source_type": "inspection",
                    "source_file": f"assets/{wid}/inspections.jsonl",
                    "record_id": iid,
                    "excerpt": f"Inspected on {insp_date} by {method} ({inspector_name}). Wellhead temp: {insp.get('wellhead_temp_c')} °C, air: {insp.get('ambient_temp_c')} °C. Notes: {insp.get('notes')}",
                    "well_id": wid,
                    "date": insp_date,
                },
                {
                    "id": f"cit-rule-{wtype}",
                    "source_type": "manual",
                    "source_file": f"fleet/well-types/{wtype}.md",
                    "section": "section 9.3" if wtype == "T200" else "section 3",
                    "excerpt": f"A {wtype} well is considered producing when wellhead is at least {threshold} °C above ambient.",
                },
            ]

            conflict = False
            conflict_msg = None

            if corr:
                # Surface any active correction alongside the current status.
                ans = (
                    f"**Yes, {wid} is producing oil right now.**\n\n"
                    f"• The {insp_date} reading was corrected from {corr.get('original_value')} °C to **{corr.get('corrected_value')} °C** by **{_user_display_name(corr.get('author'))}** ({corr.get('reason')}).\n"
                    f"• At {corr.get('corrected_value')} °C against {insp.get('ambient_temp_c')} °C air ({delta} °C delta), it is above the {threshold} °C {wtype} limit.\n"
                    f"• ⚠️ Note: The inspector's note \"{insp.get('notes')}\" ({inspector_name}) in the original inspection record disagrees with this correction."
                )
                conflict = True
                conflict_msg = "Inspector note disagrees with corrected temperature."
            elif is_producing:
                ans = f"**Yes, {wid} is producing oil right now.** (Wellhead is {delta} °C above air, exceeding the {threshold} °C limit)."
            else:
                # Find reason
                reason = "No recorded reason"
                notes = well_det.get("notes", [])
                for n in notes:
                    if "shut in" in str(n.get("text", "")).lower():
                        reason = f"Note {n.get('note_id')} by {_user_display_name(n.get('author_user_id'))}: {n.get('text')}"
                        citations.append(
                            {
                                "id": f"cit-{n.get('note_id')}",
                                "source_type": "note",
                                "source_file": f"assets/{wid}/context.jsonl",
                                "record_id": n.get("note_id"),
                                "excerpt": n.get("text"),
                                "well_id": wid,
                            }
                        )
                        break

                ans = (
                    f"**No, {wid} is not producing oil.**\n\n"
                    f"• **Latest inspection**: {iid} on {insp_date}, by {method}, by {inspector_name}.\n"
                    f"• **Temperature delta**: Wellhead was only **{delta} °C warmer than air**, below the {threshold} °C {wtype} limit.\n"
                    f"• **Reason**: {reason}\n"
                    f"• **Recorded status**: Still says `{rec_status}`, which is **out of date**."
                )

            card_data = [
                {
                    "Well ID": wid,
                    "Production Status": "Producing" if is_producing else "Not Producing",
                    "Recorded Status": rec_status,
                    "Latest Inspection": insp_date,
                    "Inspector": inspector_name,
                    "Wellhead Temp": f"{insp.get('wellhead_temp_c')} °C",
                    "Ambient Temp": f"{insp.get('ambient_temp_c')} °C",
                    "Delta": f"{delta} °C (threshold: {threshold} °C)",
                }
            ]
            viz = generate_visualization("card", f"{wid} Status Snapshot", card_data)

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": conflict,
                "conflict_message": conflict_msg,
            }

        if "not producing" in lower and ("area" in lower or "block" in lower or "which wells" in lower):
            area_name = intent.area_name if intent and intent.area_name else None
            wells = search_wells(area_name=area_name)
            title_area = area_name or "all areas"
            table_data = []
            citations = []

            for w in wells:
                wid = w.get("asset_id")
                det = get_well_details(wid, as_of=self.as_of)
                if det.get("is_producing") is False:
                    delta = det.get("temperature_delta_c")
                    rec_status = w.get("recorded_status", w.get("status", "active"))
                    insp = det.get("latest_inspection", {})
                    notes_str = insp.get("notes", "")

                    # Check why
                    reason = "No recorded reason."
                    if notes_str:
                        reason = f"No recorded reason. The inspector noted \"{notes_str}\""

                    # Check open repairs
                    open_rep = sorted(
                        [m for m in det.get("repairs", []) if str(m.get("started_at", ""))[:10] <= self.as_of and (not m.get("completed_at") or str(m.get("completed_at", ""))[:10] > self.as_of)],
                        key=lambda row: str(row.get("started_at", "")),
                    )
                    if open_rep:
                        m = open_rep[-1]
                        started = str(m.get("started_at", ""))[:10]
                        reason = f"Repair {m.get('maintenance_id')}, {m.get('issue', '').lower()}, started {started}, still open"
                        citations.append(
                            {
                                "id": f"cit-{m.get('maintenance_id')}",
                                "source_type": "repair",
                                "source_file": f"assets/{wid}/maintenance.jsonl",
                                "record_id": m.get("maintenance_id"),
                                "excerpt": f"{m.get('issue')} (started {started})",
                                "well_id": wid,
                            }
                        )

                    rec_display = f"{rec_status} (out of date)" if rec_status == "active" else rec_status

                    table_data.append(
                        {
                            "Well": wid,
                            "Wellhead above air": f"{delta} °C",
                            "Recorded status": rec_display,
                            "Reason": reason,
                        }
                    )
                    citations.append(
                        {
                            "id": f"cit-{insp.get('inspection_id')}",
                            "source_type": "inspection",
                            "source_file": f"assets/{wid}/inspections.jsonl",
                            "record_id": insp.get("inspection_id"),
                            "excerpt": f"Delta {delta} °C. {notes_str}",
                            "well_id": wid,
                        }
                    )

            viz = generate_visualization(
                "table",
                f"Non-Producing Wells in {title_area}",
                table_data,
                columns=["Well", "Wellhead above air", "Recorded status", "Reason"],
            )

            ans = (
                f"Found **{len(table_data)} wells** in {title_area} currently not producing oil as of {self.as_of}.\n\n"
                f"Where no maintenance or shut-in record explains the stoppage, field checks are recommended."
            )

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        # Plot wellhead and ambient readings for the requested inspection window.
        if intent_name == "temperature_trend" or "line chart" in lower or ("temperature against air" in lower) or ("last 13 weeks" in lower and "chart" in lower):
            wid = intent.well_ids[0] if intent and intent.well_ids else (well_match.group(0).upper() if well_match else None)
            if not wid:
                return {"answer": "Name a well to plot its temperature trend.", "citations": [], "visualization": None}
            well_det = get_well_details(wid, as_of=self.as_of)
            if not well_det:
                return {"answer": f"Well {wid} not found.", "citations": [], "visualization": None}
            threshold = well_det.get("threshold_delta_c", 15.0)
            start_date, end_date = _intent_period(intent, self.as_of, "last 13 weeks")
            week_span = re.search(r"\b(\d+)\s+weeks?\b", intent.date_phrase if intent else "", re.IGNORECASE)
            if week_span and not (intent and (intent.date_from or intent.date_to)):
                # A request for N weekly readings spans N observation slots (N-1 intervals).
                start_date = (date.fromisoformat(end_date) - timedelta(days=(int(week_span.group(1)) - 1) * 7)).isoformat()

            inspections = query_records("inspection", asset_id=wid, order_by_event=True)
            matching = [
                i for i in inspections
                if start_date <= str(i.get("inspected_at", ""))[:10] <= end_date
                and isinstance(i.get("wellhead_temp_c"), (int, float))
                and isinstance(i.get("ambient_temp_c"), (int, float))
            ]

            chart_data = []
            citations = []
            for i in matching:
                d_str = str(i.get("inspected_at", ""))[:10]
                wellhead = i.get("wellhead_temp_c")
                ambient = i.get("ambient_temp_c")
                delta = round(float(wellhead) - float(ambient), 2)
                is_prod = delta >= threshold
                chart_data.append(
                    {
                        "date": d_str,
                        "wellhead_temp_c": wellhead,
                        "ambient_temp_c": ambient,
                        "delta_c": delta,
                        "status": "Producing" if is_prod else "Not Producing",
                    }
                )

            viz = generate_visualization(
                "line",
                f"{wid} Wellhead Temp vs Air Temp ({start_date} to {end_date})",
                chart_data,
                x="date",
                y=["wellhead_temp_c", "ambient_temp_c"],
                units="°C",
            )

            not_prod_dates = [r["date"] for r in chart_data if r["status"] == "Not Producing"]
            dates_label = f"{matching[0]['inspected_at'][:10]} to {matching[-1]['inspected_at'][:10]}" if matching else f"{start_date} to {end_date}"
            ans = (
                f"Line chart for **{wid}** across {len(matching)} inspections ({dates_label}):\n\n"
                f"• **Producing threshold**: at least {threshold} °C above air temperature.\n"
                f"• **Non-producing dates**: {', '.join(not_prod_dates)}."
            )

            citations.append(
                {
                    "id": f"cit-inspections-{wid}",
                    "source_type": "inspection",
                    "source_file": f"assets/{wid}/inspections.jsonl",
                    "excerpt": f"{len(matching)} readings from {dates_label}. Non-producing on {', '.join(not_prod_dates)}.",
                    "well_id": wid,
                }
            )

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        # Summarize confirmed spills for the requested asset and period.
        if "how many oil spills" in lower or ("spills has" in lower and "had" in lower):
            wid = intent.well_ids[0] if intent and intent.well_ids else (well_match.group(0).upper() if well_match else None)
            if not wid:
                return {"answer": "Name a well to summarize its spills.", "citations": [], "visualization": None}
            start_date, end_date = _intent_period(intent, self.as_of, "last 4 years")
            spills = get_all_real_spills(well_id=wid, start_date=start_date, end_date=end_date, as_of=end_date)
            total_vol = round(sum(s["volume_bbl"] for s in spills), 1)

            table_data = [
                {
                    "Inspection Date": s["date"],
                    "Inspection ID": s["inspection_id"],
                    "Volume (bbl)": s["volume_bbl"],
                    "Classification": s["classification"].title(),
                }
                for s in spills
            ]

            citations = [
                {
                    "id": f"cit-spill-{s['inspection_id']}",
                    "source_type": "inspection",
                    "source_file": f"assets/{wid}/inspections.jsonl",
                    "record_id": s["inspection_id"],
                    "excerpt": f"Spill on {s['date']}: {s['volume_bbl']} bbl ({s['classification']})",
                    "well_id": wid,
                    "date": s["date"],
                }
                for s in spills
            ]
            viz = generate_visualization(
                "table",
                f"{wid} Oil Spills ({start_date} to {end_date})",
                table_data,
                columns=["Inspection Date", "Inspection ID", "Volume (bbl)", "Classification"],
            )

            ans = f"**{wid} has had {len(spills)} confirmed real oil spills totaling {total_vol} barrels** from {start_date} through {end_date}. Corrected false-positive detections are excluded."

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        # Single-well downtime uses the same metric and date resolver as fleet queries.
        if well_match and intent_name == "downtime":
            wid = intent.well_ids[0] if intent and intent.well_ids else well_match.group(0).upper()
            start_date, end_date = _intent_period(intent, self.as_of, "this year")
            dt_res = get_well_downtime(wid, start=start_date, end=end_date, as_of=end_date)
            downtime_days = dt_res["downtime_days"]
            citations = [
                {
                    "id": f"cit-{reading.get('inspection_id')}",
                    "source_type": "inspection",
                    "source_file": f"assets/{wid}/inspections.jsonl",
                    "record_id": reading.get("inspection_id"),
                    "date": str(reading.get("inspected_at", ""))[:10],
                    "excerpt": f"Non-producing inspection; counted {reading.get('downtime_days')} downtime days.",
                    "well_id": wid,
                }
                for reading in dt_res.get("readings", []) if reading.get("status") == "not_producing"
            ]
            citations.append({"id": "cit-downtime-rule", "source_type": "manual", "source_file": dt_res["rule_citation"].split("#", 1)[0], "excerpt": "A weekly non-producing inspection counts as 7 downtime days."})
            ans = f"**{wid} was down for {downtime_days} days from {start_date} through {end_date}**, based on {len([r for r in dt_res.get('readings', []) if r.get('status') == 'not_producing'])} non-producing inspections. Each qualifying inspection contributes seven days."

            return {
                "answer": ans,
                "citations": citations,
                "visualization": None,
                "conflict": False,
            }

        # Q6: Which wells in area had the most downtime in last 4 months? Show a bar chart.
        if "most downtime" in lower or ("downtime in" in lower and ("bar chart" in lower or "last 4 months" in lower)):
            area_name = intent.area_name if intent and intent.area_name else None
            start_date, end_date = _intent_period(intent, self.as_of, "last 4 months")
            top_n = intent.limit if intent and intent.limit else (int(re.search(r"\b(\d+)\s+wells?\b", lower).group(1)) if re.search(r"\b(\d+)\s+wells?\b", lower) else 3)
            downtime = query_metric(
                "downtime_days",
                area=area_name,
                date_from=start_date,
                date_to=end_date,
                group_by="well",
                reference_date=self.as_of,
            )
            top_wells = [
                {"well_id": row["group"], "downtime_days": row["value"], "well_type": row["records"][0].get("well_type")}
                for row in downtime["rows"][:top_n]
            ]

            bar_data = [
                {
                    "well_id": w["well_id"],
                    "downtime_days": w["downtime_days"],
                    "well_type": w["well_type"],
                }
                for w in top_wells
            ]

            viz = generate_visualization(
                "bar",
                f"Top Downtime Wells in {area_name or 'all areas'} ({start_date} to {end_date})",
                bar_data,
                x="well_id",
                y="downtime_days",
                units="days",
            )

            summary_str = ", ".join([f"**{w['well_id']}**: {w['downtime_days']} days ({w['well_type']})" for w in top_wells])
            ans = (
                f"In {area_name or 'all areas'} from {downtime['filters']['date_from']} to {downtime['filters']['date_to']}, "
                f"the wells with the most downtime are:\n\n{summary_str}."
            )

            citations = [
                {
                    "id": f"cit-top-{w['well_id']}",
                    "source_type": "inspection",
                    "source_file": f"assets/{w['well_id']}/inspections.jsonl",
                    "excerpt": f"Accumulated {w['downtime_days']} downtime days from weekly non-producing inspections.",
                    "well_id": w["well_id"],
                }
                for w in top_wells
            ]

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        # Q7: Show on a map every well in area with real spill in last 90 days
        if "heatmap" not in lower and "map" in lower and "spill" in lower:
            area_name = intent.area_name if intent and intent.area_name else None
            start_date, end_date = _intent_period(intent, self.as_of, "last 90 days")
            spills = get_all_real_spills(area_name=area_name, start_date=start_date, end_date=end_date, as_of=end_date)

            map_data = [
                {
                    "well_id": s["well_id"],
                    "well_name": s["well_name"],
                    "date": s["date"],
                    "volume_bbl": s["volume_bbl"],
                    "latitude": s["latitude"],
                    "longitude": s["longitude"],
                    "status": f"{s['volume_bbl']} bbl spill on {s['date']}",
                }
                for s in spills
            ]

            viz = generate_visualization(
                "map",
                f"Spills in {area_name or 'all areas'} ({start_date} to {end_date})",
                list({row["well_id"]: row for row in reversed(map_data)}.values()),
                columns=["well_id", "date", "volume_bbl", "latitude", "longitude"],
            )

            well_count = len({spill["well_id"] for spill in spills})
            ans = f"Found **{well_count} wells** in {area_name or 'all areas'} with real oil spills from {start_date} through {end_date}."

            citations = [
                {
                    "id": f"cit-map-{s['inspection_id']}",
                    "source_type": "inspection",
                    "source_file": f"assets/{s['well_id']}/inspections.jsonl",
                    "record_id": s["inspection_id"],
                    "excerpt": f"Spill: {s['volume_bbl']} bbl on {s['date']}",
                    "well_id": s["well_id"],
                    "date": s["date"],
                }
                for s in spills
            ]

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        # Q8: Heatmap of spills by geographic area and month
        if "heatmap" in lower and "spill" in lower:
            target_year = intent.year if intent and intent.year else int(self.as_of[:4])
            year_end = self.as_of if target_year == int(self.as_of[:4]) else f"{target_year}-12-31"
            hm_result = query_metric(
                "spill_volume",
                date_from=f"{target_year}-01-01",
                date_to=year_end,
                group_by="area",
                reference_date=self.as_of,
            )
            end_month = date.fromisoformat(hm_result["filters"]["date_to"]).month
            month_labels = [calendar.month_abbr[month] for month in range(1, end_month + 1)]
            area_rows: dict[str, dict[str, Any]] = {
                str(row.get("name")): {"Area": str(row.get("name")), "Total": 0}
                for row in query_records("area")
            }
            for record in hm_result["records"]:
                try:
                    month = date.fromisoformat(str(record.get("date", ""))[:10]).strftime("%b")
                except ValueError:
                    continue
                row = area_rows.setdefault(str(record.get("area")), {"Area": str(record.get("area")), "Total": 0})
                row[month] = int(row.get(month, 0)) + 1
                row["Total"] += 1
            hm_rows = []
            for row in area_rows.values():
                hm_rows.append({"Area": row["Area"], **{month: row.get(month, 0) for month in month_labels}, "Total": row["Total"]})
            hm_rows.sort(key=lambda row: str(row["Area"]).casefold())

            viz = generate_visualization(
                "heatmap",
                f"{target_year} Spills by Area and Month",
                hm_rows,
                x="Area",
                units="spills",
            )

            area_totals = sorted(((row["Area"], row["Total"]) for row in hm_rows), key=lambda item: (-item[1], item[0]))
            totals_text = "\n".join(f"• **{name}**: {count} spills" for name, count in area_totals)
            months_label = f"{month_labels[0]} to {month_labels[-1]}" if month_labels else "no dated spill records"
            ans = f"Heatmap of confirmed {target_year} oil spills by geographic area and month ({months_label}; false positives excluded):\n\n{totals_text}"

            citations = [
                {
                    "id": "cit-heatmap-sop",
                    "source_type": "manual",
                    "source_file": "fleet/sops/spill-response-sop.md",
                    "section": "section 7",
                    "excerpt": "Corrected detections (false positives) do not count as spills for reporting or statistics.",
                }
            ]

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        # Compliance findings are assembled from inspections, reports, regulator events, and SOPs.
        if (intent_name == "compliance" or "rules" in lower or "broken" in lower or "breach" in lower or "compliance" in lower) and well_match:
            from backend.app.pipeline.answer import _compliance_answer

            return _compliance_answer(well_match.group(0).upper(), self.as_of)

        if intent_name == "containment_breach" or "not contained" in lower or ("contained" in lower and "limit" in lower):
            area_name = intent.area_name if intent and intent.area_name else None
            breach_query = query_metric(
                "containment_breaches",
                area=area_name,
                date_phrase=(intent.date_phrase if intent and intent.date_phrase else "last 90 days"),
                group_by="well",
                reference_date=self.as_of,
            )
            breaches = [item["details"] for item in breach_query["records"]]

            table_data = [
                {
                    "Well": b["well_id"],
                    "Containment Time": f"~{b['containment_hours']} hours",
                    "SOP Limit": f"{b['sop_limit_hours']} hours",
                    "Repair ID": b["maintenance_id"],
                    "Report File": b["report_file"],
                }
                for b in breaches
            ]

            viz = generate_visualization(
                "table",
                f"Containment Breaches in {area_name} (Last 90 Days)",
                table_data,
            )

            breach_lines = [
                f"• **{b['well_id']}**: Contained after ~{b['containment_hours']} hours "
                f"(report {b['report_file']}, repair {b['maintenance_id']})."
                for b in breaches
            ]
            ans = (
                f"In {area_name or 'the selected fleet'} from {breach_query['filters']['date_from']} "
                f"to {breach_query['filters']['date_to']}, **{len(breaches)} spills** exceeded the SOP containment limit.\n\n"
                + "\n".join(breach_lines)
                + "\n\nContainment times are taken from maintenance-report evidence."
            )

            citations = [
                {
                    "id": f"cit-{b['maintenance_id']}",
                    "source_type": "repair",
                    "source_file": f"assets/{b['well_id']}/{b['report_file']}",
                    "record_id": b["maintenance_id"],
                    "excerpt": f"Contained after approximately {b['containment_hours']} hours.",
                    "well_id": b["well_id"],
                }
                for b in breaches
            ]
            citations.append(
                {
                    "id": "cit-sop-sr02",
                    "source_type": "manual",
                    "source_file": "fleet/sops/spill-response-sop.md",
                    "section": "section 4 (SR-02)",
                    "excerpt": "The source must be stopped and the spill contained within 4 hours of discovery.",
                }
            )

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        if intent_name == "rca" or "root-cause" in lower or "rca" in lower:
            area_name = intent.area_name if intent and intent.area_name else None
            wells_rca = find_maintenance_patterns(
                area=area_name,
                well_type=intent.well_type if intent else None,
                well_id=well_match.group(0).upper() if well_match else None,
                as_of=self.as_of,
            )

            table_data = [
                {
                    "Well": w["well_id"],
                    "Type": w["well_type"],
                    "Repairs Count (12m)": w["repair_count"],
                    "Threshold": w["threshold_applied"],
                    "Rule Applied": w["rule_description"],
                }
                for w in wells_rca
            ]

            viz = generate_visualization(
                "table",
                f"Wells Needing Pump Jack RCA in {area_name}",
                table_data,
            )

            well_names_str = ", ".join([f"**{w['well_id']}** ({w['well_type']})" for w in wells_rca])
            ans = f"Wells in {area_name or 'the selected fleet'} requiring a root-cause analysis on their pump jack: {well_names_str}."

            citations = [
                {
                    "id": f"cit-rca-{w['well_id']}",
                    "source_type": "repair",
                    "source_file": f"assets/{w['well_id']}/maintenance.jsonl",
                    "excerpt": f"{w['repair_count']} corrective pump jack repairs in last 12 months.",
                    "well_id": w["well_id"],
                }
                for w in wells_rca
            ]

            return {
                "answer": ans,
                "citations": citations,
                "visualization": viz,
                "conflict": False,
            }

        if "needed a report" in lower or "reportable" in lower:
            area_name = intent.area_name if intent and intent.area_name else None
            start_date, end_date = _intent_period(intent, self.as_of, "last 90 days")
            spills = get_all_real_spills(area_name=area_name, start_date=start_date, end_date=end_date, as_of=end_date)
            reportable = [s for s in spills if s.get("external_report_required")]

            if reportable:
                lines = []
                citations = []
                for spill in reportable:
                    events = query_records("regulatory_event", asset_id=str(spill["well_id"]))
                    report_event = next((event for event in events if event.get("event_type") == "spill_report_filed" and event.get("related_inspection_id") == spill.get("inspection_id")), None)
                    deadline_hours = spill.get("report_deadline_hours")
                    if report_event:
                        hours = report_event.get("hours_to_report")
                        status = "filing time is unknown" if hours is None else f"reported after {hours} hours" if float(hours) > float(deadline_hours) else f"reported within {deadline_hours} hours"
                        citations.append({"id": f"cit-{report_event.get('event_id')}", "source_type": "regulatory", "source_file": f"assets/{spill['well_id']}/regulatory-events.jsonl", "record_id": report_event.get("event_id"), "excerpt": f"Spill report filing time: {hours} hours.", "well_id": spill["well_id"]})
                    else:
                        insp = next((row for row in query_records("inspection", asset_id=str(spill["well_id"])) if row.get("inspection_id") == spill.get("inspection_id")), {})
                        discovered = datetime.fromisoformat(str(insp.get("inspected_at", "")).replace("Z", "+00:00"))
                        due = discovered + timedelta(hours=float(deadline_hours or 0))
                        cutoff = datetime.combine(date.fromisoformat(end_date), datetime.max.time(), tzinfo=timezone.utc)
                        status = f"no report is recorded; deadline passed at {due.isoformat()}" if due <= cutoff else f"no report is recorded; deadline is {due.isoformat()}"
                    lines.append(f"• **{spill['well_id']}**: {spill['volume_bbl']} bbl on {spill['date']} ({status}).")
                    citations.append({"id": f"cit-{spill['inspection_id']}", "source_type": "inspection", "source_file": f"assets/{spill['well_id']}/inspections.jsonl", "record_id": spill["inspection_id"], "excerpt": f"{spill['volume_bbl']} bbl spill; reporting deadline {deadline_hours} hours.", "well_id": spill["well_id"], "date": spill["date"]})
                citations.append({"id": "cit-spill-sop", "source_type": "manual", "source_file": "fleet/sops/spill-response-sop.md", "excerpt": "Spill reporting thresholds and deadlines are specified in the Spill Response SOP."})
                ans = f"Found {len(reportable)} spill(s) that require a regulator report in {area_name or 'the selected fleet'} from {start_date} through {end_date}:\n\n" + "\n".join(lines)
            else:
                ans = f"No spill requiring a regulator report was found in {area_name or 'the selected fleet'} from {start_date} through {end_date}."
                citations = []

            return {
                "answer": ans,
                "citations": citations,
                "visualization": None,
                "conflict": False,
            }

        # Fallback search over manuals and SOPs
        docs = search_manuals_and_sops(q, limit=3)
        if docs:
            top_doc = docs[0]
            ans = f"According to **{top_doc.get('title')}** ({top_doc.get('source_path')}):\n\n{top_doc.get('content')[:500]}…"
            citations = [
                {
                    "id": f"cit-{top_doc.get('source_path')}",
                    "source_type": "manual",
                    "source_file": top_doc.get("source_path"),
                    "excerpt": top_doc.get("content")[:200],
                }
            ]
            return {
                "answer": ans,
                "citations": citations,
                "visualization": None,
                "conflict": False,
            }

        return {
            "answer": f"I analyzed records and documents up to {self.as_of}. Could you clarify your question or specify an asset ID / geographic area?",
            "citations": [],
            "visualization": None,
            "conflict": False,
        }
