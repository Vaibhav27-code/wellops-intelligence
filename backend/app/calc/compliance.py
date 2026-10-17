from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .downtime import calculate_downtime
from .rules import assess_spill, load_spill_rules, spill_report_status


@dataclass(frozen=True)
class ComplianceRules:
    inspection_interval_days: int
    consecutive_downtime_reporting_days: int
    nov_response_days: int
    spill_containment_hours: float
    spill_verification_days: int
    maintenance_report_days: int
    annual_flowline_test: bool
    inspection_citation: str
    regulatory_citation: str
    spill_citation: str
    field_work_citation: str


def _integer(text: str, pattern: str, label: str) -> int:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not read {label} from source SOP")
    return int(match.group(1))


def load_compliance_rules(sample_data_root: str) -> ComplianceRules:
    from pathlib import Path

    root = Path(sample_data_root)
    regulatory = (root / "fleet" / "sops" / "regulatory-compliance-sop.md").read_text(encoding="utf-8")
    spill = (root / "fleet" / "sops" / "spill-response-sop.md").read_text(encoding="utf-8")
    field_work = (root / "fleet" / "sops" / "field-work-sop.md").read_text(encoding="utf-8")
    inspection_interval = _integer(regulatory, r"at least once every\s+\*\*(\d+) days", "RC-01 inspection interval")
    downtime_days = _integer(regulatory, r"more than\s+\*\*(\d+) consecutive days", "RC-03 downtime interval")
    nov_days = _integer(regulatory, r"within\s+\*\*(\d+) days\*\*", "RC-04 NOV response interval")
    containment = _integer(spill, r"(\d+)-hour containment limit", "SR-02 containment interval")
    verification_days = _integer(spill, r"verified within\s+\*{0,2}(\d+) days", "SR-03 verification interval")
    report_days = _integer(field_work, r"maintenance report\*{0,2}\s+within\s+(\d+) days", "WS-07 report interval")
    annual_test = bool(re.search(r"once per calendar year", regulatory, flags=re.IGNORECASE))
    return ComplianceRules(
        inspection_interval_days=inspection_interval,
        consecutive_downtime_reporting_days=downtime_days,
        nov_response_days=nov_days,
        spill_containment_hours=float(containment),
        spill_verification_days=verification_days,
        maintenance_report_days=report_days,
        annual_flowline_test=annual_test,
        inspection_citation="fleet/sops/regulatory-compliance-sop.md#section 2",
        regulatory_citation="fleet/sops/regulatory-compliance-sop.md#section 2 (RC-04)",
        spill_citation="fleet/sops/spill-response-sop.md#section 4 (SR-02, SR-03)",
        field_work_citation="fleet/sops/field-work-sop.md#section 3 (WS-07)",
    )


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _inspection_time(row: dict[str, Any]) -> datetime | None:
    value = row.get("inspected_at")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _finding(
    protocol_id: str,
    status: str,
    summary: str,
    citations: list[str],
    **values: Any,
) -> dict[str, Any]:
    return {"protocol_id": protocol_id, "status": status, "summary": summary, "citations": citations, **values}


def assess_inspection_interval(
    inspections: list[dict[str, Any]],
    as_of: str | date,
    sample_data_root: str,
) -> dict[str, Any]:
    rules = load_compliance_rules(sample_data_root)
    cutoff = _as_date(as_of)
    rows = sorted(((_inspection_time(row), row) for row in inspections), key=lambda pair: pair[0] or datetime.min.replace(tzinfo=timezone.utc))
    rows = [(timestamp, row) for timestamp, row in rows if timestamp and (cutoff is None or timestamp.date() <= cutoff)]
    if not rows or cutoff is None:
        return _finding("RC-01", "unknown", "Inspection evidence or a valid as_of date is missing.", [rules.inspection_citation])
    gaps: list[dict[str, Any]] = []
    evidence_rows: dict[str, dict[str, Any]] = {}
    for (left_at, left), (right_at, right) in zip(rows, rows[1:]):
        days = (right_at.date() - left_at.date()).days
        if days > rules.inspection_interval_days:
            gaps.append({"from": left_at.date().isoformat(), "to": right_at.date().isoformat(), "days": days})
            evidence_rows[str(left.get("inspection_id"))] = left
            evidence_rows[str(right.get("inspection_id"))] = right
    latest_at, latest = rows[-1]
    days_since_latest = (cutoff - latest_at.date()).days
    if days_since_latest > rules.inspection_interval_days:
        gaps.append({"from": latest_at.date().isoformat(), "to": cutoff.isoformat(), "days": days_since_latest, "open": True})
        evidence_rows[str(latest.get("inspection_id"))] = latest
    if not evidence_rows:
        evidence_rows[str(latest.get("inspection_id"))] = latest
    citations = [
        f"assets/{row.get('asset_id', 'unknown')}/inspections.jsonl#{row.get('inspection_id', 'unknown')}"
        for row in evidence_rows.values()
    ]
    citations.append(rules.inspection_citation)
    return _finding(
        "RC-01",
        "confirmed_violation" if gaps else "compliant",
        f"Found {len(gaps)} inspection interval(s) over the documented {rules.inspection_interval_days}-day limit." if gaps else "Observed inspection intervals meet the documented limit.",
        citations[-min(len(citations), max(1, len(gaps) + 1)):],
        maximum_interval_days=rules.inspection_interval_days,
        gaps=gaps,
    )


def assess_spill_compliance(
    inspections: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    maintenance: list[dict[str, Any]],
    regulatory_events: list[dict[str, Any]],
    report_text_by_maintenance_id: dict[str, str],
    sample_data_root: str,
    as_of: str | date,
) -> list[dict[str, Any]]:
    """Assess SR-01, SR-02 and SR-03 using structured events and report evidence."""
    rules = load_spill_rules(sample_data_root)
    compliance = load_compliance_rules(sample_data_root)
    cutoff = _as_date(as_of)
    if cutoff is None:
        raise ValueError("as_of must be a date or ISO date string")
    findings: list[dict[str, Any]] = []
    events_by_inspection: dict[str, list[dict[str, Any]]] = {}
    for event in regulatory_events:
        related = event.get("related_inspection_id")
        if related:
            events_by_inspection.setdefault(str(related), []).append(event)

    repairs_by_inspection: dict[str, list[dict[str, Any]]] = {}
    for job in maintenance:
        related = job.get("triggered_by_inspection_id")
        if related:
            repairs_by_inspection.setdefault(str(related), []).append(job)

    for inspection in inspections:
        spill = assess_spill(inspection, contexts, rules, as_of=cutoff.isoformat())
        if spill is None or not spill.get("spill_detected"):
            continue
        inspected_at = _inspection_time(inspection)
        if inspected_at is None:
            continue
        related_events = events_by_inspection.get(str(inspection.get("inspection_id")), [])
        report_events = [event for event in related_events if event.get("event_type") == "spill_report_filed"]
        event = sorted(report_events, key=lambda row: str(row.get("date", "")))[0] if report_events else None
        citations = list(spill["citations"])
        report_hours = event.get("hours_to_report") if event else None
        spill_report = {**spill, "hours_to_report": report_hours}
        report_status = spill_report_status(report_hours, spill_report)
        if spill.get("external_report_required"):
            due_at = inspected_at + timedelta(hours=float(spill["report_deadline_hours"]))
            if event:
                citations.append(f"assets/{event.get('asset_id', 'unknown')}/regulatory-events.jsonl#{event.get('event_id', 'unknown')}")
                sr01_status = "confirmed_violation" if report_status == "missed" else "compliant" if report_status == "met" else "unknown"
                summary = f"Written report was filed after {report_hours} hours; the SOP limit is {spill['report_deadline_hours']} hours." if report_status == "missed" else f"Written report met the {spill['report_deadline_hours']}-hour SOP limit." if report_status == "met" else "A report event exists but its filing time is missing."
            elif due_at.date() <= cutoff:
                sr01_status = "potential_violation"
                summary = f"No spill report event is recorded; the {spill['report_deadline_hours']}-hour deadline has passed."
            else:
                sr01_status = "pending"
                summary = "The written-report deadline has not passed yet."
            findings.append(_finding("SR-01", sr01_status, summary, citations, inspection_id=inspection.get("inspection_id"), due_at=due_at.isoformat(), classification=spill.get("classification")))

        repair_jobs = repairs_by_inspection.get(str(inspection.get("inspection_id")), [])
        containment_hours: float | None = None
        report_citation: str | None = None
        for job in repair_jobs:
            report_text = report_text_by_maintenance_id.get(str(job.get("maintenance_id", "")), "")
            match = re.search(
                r"contained\s+(?:(?:about|approximately)\s+)?(\d+(?:\.\d+)?)\s+hours? after (?:the )?inspection(?:\s+flight)?",
                report_text.replace("*", " "),
                flags=re.IGNORECASE,
            )
            if match:
                containment_hours = float(match.group(1))
                report_citation = f"assets/{job.get('asset_id', 'unknown')}/{job.get('report_file', '')}#{job.get('maintenance_id', 'unknown')}"
                break
        if report_citation:
            citations_with_report = [*citations, report_citation, compliance.spill_citation]
            status = "confirmed_violation" if containment_hours is not None and containment_hours > compliance.spill_containment_hours else "compliant"
            summary = f"Containment took {containment_hours} hours; the SOP limit is {compliance.spill_containment_hours:g} hours."
        else:
            citations_with_report = [*citations, compliance.spill_citation]
            status = "potential_violation" if (inspected_at + timedelta(hours=compliance.spill_containment_hours)).date() <= cutoff else "unknown"
            summary = "No report evidence states when containment occurred."
        findings.append(_finding("SR-02", status, summary, citations_with_report, inspection_id=inspection.get("inspection_id"), containment_hours=containment_hours, limit_hours=compliance.spill_containment_hours))

        if spill.get("classification") in (*rules.reportable_class_names, rules.major_class_name):
            verification_events = [event for event in related_events if event.get("protocol_id") == "SR-03"]
            closed_events = [event for event in verification_events if event.get("status") == "closed"]
            due_date = inspected_at.date() + timedelta(days=compliance.spill_verification_days)
            verification_citations = [*citations, compliance.spill_citation]
            if closed_events:
                closed = sorted(closed_events, key=lambda row: str(row.get("date", "")))[0]
                verification_citations.append(f"assets/{closed.get('asset_id', 'unknown')}/regulatory-events.jsonl#{closed.get('event_id', 'unknown')}")
                closed_date = _as_date(closed.get("date"))
                verification_status = "compliant" if closed_date and closed_date <= due_date else "confirmed_violation"
                verification_summary = f"Agency verification closed on {closed_date}; deadline was {due_date}."
            elif due_date <= cutoff:
                open_events = [event for event in verification_events if event.get("status") == "open"]
                if open_events:
                    event = open_events[0]
                    verification_citations.append(f"assets/{event.get('asset_id', 'unknown')}/regulatory-events.jsonl#{event.get('event_id', 'unknown')}")
                    verification_status = "confirmed_violation"
                    verification_summary = f"Agency verification remains open after the {due_date} deadline."
                else:
                    verification_status = "potential_violation"
                    verification_summary = f"No closed agency-verification event is recorded by the {due_date} deadline."
            else:
                verification_status = "pending"
                verification_summary = f"Agency verification is due by {due_date}."
            findings.append(_finding("SR-03", verification_status, verification_summary, verification_citations, inspection_id=inspection.get("inspection_id"), due_date=due_date.isoformat()))
    return findings


def assess_nov_responses(
    regulatory_events: list[dict[str, Any]],
    as_of: str | date,
    sample_data_root: str,
) -> list[dict[str, Any]]:
    rules = load_compliance_rules(sample_data_root)
    cutoff = _as_date(as_of)
    if cutoff is None:
        raise ValueError("as_of must be a date or ISO date string")
    notices = [event for event in regulatory_events if event.get("event_type") == "notice_of_violation"]
    responses = [event for event in regulatory_events if event.get("event_type") == "nov_response_filed"]
    findings = []
    for notice in notices:
        notice_date = _as_date(notice.get("date"))
        if notice_date is None:
            continue
        due_date = notice_date + timedelta(days=rules.nov_response_days)
        matches = [row for row in responses if row.get("related_inspection_id") == notice.get("related_inspection_id") and row.get("asset_id") == notice.get("asset_id")]
        citations = [f"assets/{notice.get('asset_id', 'unknown')}/regulatory-events.jsonl#{notice.get('event_id', 'unknown')}", rules.regulatory_citation]
        if matches:
            response = sorted(matches, key=lambda row: str(row.get("date", "")))[0]
            response_date = _as_date(response.get("date"))
            citations.append(f"assets/{response.get('asset_id', 'unknown')}/regulatory-events.jsonl#{response.get('event_id', 'unknown')}")
            status = "compliant" if response_date and response_date <= due_date else "confirmed_violation"
            summary = f"NOV response was filed on {response_date}; deadline was {due_date}."
        elif due_date <= cutoff:
            status = "potential_violation"
            summary = f"No NOV response event is recorded by the {due_date} deadline."
        else:
            status = "pending"
            summary = f"NOV response is due by {due_date}."
        findings.append(_finding("RC-04", status, summary, citations, event_id=notice.get("event_id"), due_date=due_date.isoformat()))
    return findings


def assess_well_compliance(
    well: dict[str, Any],
    inspections: list[dict[str, Any]],
    maintenance: list[dict[str, Any]],
    regulatory_events: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    report_text_by_maintenance_id: dict[str, str],
    sample_data_root: str,
    as_of: str | date,
) -> list[dict[str, Any]]:
    """Return evidence-backed compliance findings; missing evidence is never called compliant."""
    rules = load_compliance_rules(sample_data_root)
    cutoff = _as_date(as_of)
    if cutoff is None:
        raise ValueError("as_of must be a date or ISO date string")
    asset_id = str(well.get("asset_id", "unknown"))
    findings = [assess_inspection_interval(inspections, cutoff, sample_data_root)]

    spill_rows = assess_spill_compliance(
        inspections, contexts, maintenance, regulatory_events, report_text_by_maintenance_id, sample_data_root, cutoff
    )
    findings.extend(spill_rows)
    findings.extend(assess_nov_responses(regulatory_events, cutoff, sample_data_root))

    if rules.annual_flowline_test:
        installed = _as_date(well.get("installed_on"))
        first_inspection = min((_as_date(row.get("inspected_at")) for row in inspections if _as_date(row.get("inspected_at"))), default=None)
        # The first observed calendar year can be partial (the published sample
        # starts in October 2022), so do not infer an annual-test breach before
        # the first complete year represented in this well's records.
        first_observed_year = first_inspection.year if first_inspection else cutoff.year
        start_year = max((installed or first_inspection or cutoff).year, first_observed_year + 1)
        completed_test_years = {
            parsed.year
            for job in maintenance
            if "annual flowline integrity test" in str(job.get("issue", "")).lower()
            and (parsed := _as_date(job.get("started_at"))) is not None
            and parsed <= cutoff
        }
        required_years = range(start_year, cutoff.year + 1)
        missing_years = [year for year in required_years if year not in completed_test_years]
        current_year_open = cutoff < date(cutoff.year, 12, 31)
        overdue_years = [year for year in missing_years if year < cutoff.year or not current_year_open]
        status = "confirmed_violation" if overdue_years else "potential_violation" if missing_years else "compliant"
        citations = [rules.inspection_citation]
        citations.extend(
            f"assets/{asset_id}/maintenance.jsonl#{job.get('maintenance_id', 'unknown')}"
            for job in maintenance if "annual flowline integrity test" in str(job.get("issue", "")).lower()
        )
        findings.append(_finding("RC-02", status, f"Missing flowline integrity test years: {missing_years}." if missing_years else "A documented annual flowline integrity test is present for each observed calendar year.", citations, missing_years=missing_years))

    downtime = calculate_downtime(inspections, str(well.get("well_type", "")), sample_data_root, contexts=contexts, as_of=cutoff)
    if downtime["maximum_consecutive_downtime_days"] > rules.consecutive_downtime_reporting_days:
        citations = [row["citation"] for row in downtime["readings"] if row["status"] == "not_producing"]
        citations.append("fleet/sops/regulatory-compliance-sop.md#section 2 (RC-03)")
        reported = any(re.search(r"reported to (?:the )?(?:area )?production supervisor", str(note.get("text", "")), flags=re.IGNORECASE) for note in contexts)
        findings.append(_finding(
            "RC-03",
            "compliant" if reported else "potential_violation",
            "Long downtime has a matching supervisor-report note." if reported else "Observed consecutive downtime exceeds the reporting trigger; no supervisor-report evidence is found in the available notes.",
            citations,
            consecutive_downtime_days=downtime["maximum_consecutive_downtime_days"],
            reporting_trigger_days=rules.consecutive_downtime_reporting_days,
        ))

    report_date_pattern = re.compile(r"\*\*Report written:\*\*\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})")
    for job in maintenance:
        if job.get("maintenance_type") != "corrective":
            continue
        report_text = report_text_by_maintenance_id.get(str(job.get("maintenance_id", "")))
        if not report_text:
            continue
        written_match = report_date_pattern.search(report_text)
        completed = _as_date(job.get("completed_at"))
        if not written_match or not completed:
            continue
        try:
            written = datetime.strptime(written_match.group(1), "%d %b %Y").date()
        except ValueError:
            continue
        if written > cutoff or completed > cutoff:
            continue
        elapsed = (written - completed).days
        citations = [f"assets/{asset_id}/{job.get('report_file', '')}#{job.get('maintenance_id', 'unknown')}", rules.field_work_citation]
        status = "confirmed_violation" if elapsed > rules.maintenance_report_days else "compliant"
        findings.append(_finding("WS-07", status, f"Maintenance report was written {elapsed} day(s) after completion; SOP limit is {rules.maintenance_report_days} days.", citations, maintenance_id=job.get("maintenance_id"), days_after_completion=elapsed))

    return findings
