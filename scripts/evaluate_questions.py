from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from dotenv import load_dotenv

from backend.app.ingest.loader import load_dataset
from backend.app.main import app
from backend.app.llm.reliability import ReliableLLMClient, SQLiteResponseCache
from backend.app.tools.db import get_sample_data_root


QUESTION_FILE = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "official_eval.json"
RUN_STATE_FILE = PROJECT_ROOT / "docs" / ".eval_run_results.json"


def _check_response(response: dict[str, Any], checks: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    answer = str(response.get("answer_text", response.get("answer", "")))
    lowered = answer.casefold()
    for value in checks.get("contains", []):
        if str(value).casefold() not in lowered:
            errors.append(f"answer missing required text: {value}")
    if checks.get("contains_any") and not any(str(value).casefold() in lowered for value in checks["contains_any"]):
        errors.append(f"answer missing all acceptable text: {checks['contains_any']}")
    for value in checks.get("absent_text", []):
        if str(value).casefold() in lowered:
            errors.append(f"answer unexpectedly contains: {value}")
    expected_conflict = checks.get("conflict")
    if expected_conflict is not None and bool(response.get("conflict")) is not bool(expected_conflict):
        errors.append(f"conflict={response.get('conflict')}, expected {expected_conflict}")
    visualization = response.get("visualization") or {}
    if checks.get("visualization") and visualization.get("type") != checks["visualization"]:
        errors.append(f"visualization={visualization.get('type')}, expected {checks['visualization']}")
    rows = visualization.get("data") if isinstance(visualization, dict) else []
    rows = rows if isinstance(rows, list) else []
    if checks.get("visualization_rows") is not None and len(rows) != checks["visualization_rows"]:
        errors.append(f"visualization row count={len(rows)}, expected {checks['visualization_rows']}")
    for value_check in ("exact_values", "absent_values"):
        spec = checks.get(value_check)
        if not spec:
            continue
        observed = {str(row.get(spec["field"])) for row in rows if row.get(spec["field"]) is not None}
        expected = {str(value) for value in spec["values"]}
        if value_check == "exact_values" and observed != expected:
            errors.append(f"visualization {spec['field']} values differ: expected {sorted(expected)}, got {sorted(observed)}")
        if value_check == "absent_values" and observed.intersection(expected):
            errors.append(f"visualization unexpectedly contains {sorted(observed.intersection(expected))}")
    values_spec = checks.get("field_values")
    if values_spec:
        observed = {str(row.get(values_spec["by"])): row.get(values_spec["field"]) for row in rows}
        for key, expected_value in values_spec["values"].items():
            if observed.get(key) != expected_value:
                errors.append(f"visualization {values_spec['field']} for {key}={observed.get(key)}, expected {expected_value}")
    citations_text = json.dumps(response.get("citations", []), ensure_ascii=False).casefold()
    for value in checks.get("citations_contain", []):
        if str(value).casefold() not in citations_text:
            errors.append(f"citations missing required source identifier: {value}")
    if len(response.get("citations") or []) < int(checks.get("min_citations", 0)):
        errors.append(f"citation count below {checks['min_citations']}")
    return errors


def _run_one(client: TestClient, request: dict[str, str]) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    response = client.post("/chat", json=request)
    response.raise_for_status()
    return response.json(), round((time.perf_counter() - started) * 1000, 2)


def _signature(response: dict[str, Any]) -> str:
    visualization = response.get("visualization") or {}
    citations = response.get("citations") or []
    structured = {
        "visualization_type": visualization.get("type"),
        "visualization_data": visualization.get("data"),
        "citations": [
            {key: item.get(key) for key in ("source_file", "record_id", "well_id", "date") if item.get(key) is not None}
            for item in citations
            if isinstance(item, dict)
        ],
        "conflict": bool(response.get("conflict")),
    }
    return json.dumps(structured, ensure_ascii=False, sort_keys=True, default=str)


def _run_suite(provider: str) -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    dataset_root = get_sample_data_root()
    base_database = data_dir / "eval-base.db"
    if not base_database.exists():
        load_dataset(dataset_root, base_database)
    provider_database = data_dir / f"eval-{provider}.db"
    shutil.copyfile(base_database, provider_database)

    os.environ["ASSET_INTELLIGENCE_DB"] = str(provider_database)
    os.environ["ASSET_INTELLIGENCE_DATASET"] = str(dataset_root)
    os.environ["LLM_PROVIDER"] = provider
    os.environ.pop("REFERENCE_DATE", None)
    if provider == "gemini":
        # Deliberately inspect only presence; do not reveal or serialize the key.
        if not os.getenv("GEMINI_API_KEY", "").strip():
            raise RuntimeError("GEMINI_API_KEY is not configured; Gemini evaluation was not started")

    counts = {"provider_calls": 0, "cache_hits": 0, "actions": 0}
    count_lock = threading.Lock()
    original_call = ReliableLLMClient._call_with_timeout
    original_get = SQLiteResponseCache.get

    def counted_call(self, prompt, system, json_schema):
        with count_lock:
            counts["provider_calls"] += 1
        return original_call(self, prompt, system, json_schema)

    def counted_get(self, key):
        value = original_get(self, key)
        if value is not None:
            with count_lock:
                counts["cache_hits"] += 1
        return value

    ReliableLLMClient._call_with_timeout = counted_call  # type: ignore[method-assign]
    SQLiteResponseCache.get = counted_get  # type: ignore[method-assign]
    try:
        payload = json.loads(QUESTION_FILE.read_text(encoding="utf-8"))
        questions = payload["questions"]
        results = []
        with TestClient(app) as client:
            for item in questions:
                for setup in item.get("setup", []):
                    _run_one(client, setup)
                    counts["actions"] += 1
                main_response, latency = _run_one(
                    client,
                    {"question": item["question"], "user_id": item.get("user_id", "eval-user")},
                )
                counts["actions"] += 1
                errors = _check_response(main_response, item.get("expected", {}))
                followup_results = []
                for followup in item.get("followups", []):
                    followup_response, followup_latency = _run_one(client, followup)
                    counts["actions"] += 1
                    followup_errors = _check_response(followup_response, followup.get("expected", {}))
                    errors.extend(f"follow-up: {error}" for error in followup_errors)
                    followup_results.append(
                        {
                            "answer": followup_response.get("answer_text", followup_response.get("answer", "")),
                            "provider_path": followup_response.get("provider_path", "unknown"),
                            "errors": followup_errors,
                            "latency_ms": followup_latency,
                        }
                    )
                results.append(
                    {
                        "id": item["id"],
                        "question": item["question"],
                        "answer": main_response.get("answer_text", main_response.get("answer", "")),
                        "citations": main_response.get("citations", []),
                        "visualization": main_response.get("visualization"),
                        "provider_path": main_response.get("provider_path", "unknown"),
                        "latency_ms": latency,
                        "passed": not errors,
                        "errors": errors,
                        "signature": _signature(main_response),
                        "followups": followup_results,
                    }
                )
    finally:
        ReliableLLMClient._call_with_timeout = original_call  # type: ignore[method-assign]
        SQLiteResponseCache.get = original_get  # type: ignore[method-assign]

    return {
        "provider": provider,
        "reference_date": _latest_inspection_date(base_database),
        "counts": counts,
        "results": results,
    }


def _latest_inspection_date(database: Path) -> str:
    from backend.app.tools.db import get_reference_date

    return get_reference_date(database)


def _report(runs: dict[str, Any]) -> str:
    rules = runs.get("rules", {})
    gemini = runs.get("gemini", {})
    lines = [
        "# Generated Evaluation Report",
        "",
        "Generated by `scripts/evaluate_questions.py` from the official `ALL_18_QUESTIONS` text in `frontend/src/store/index.ts`; expected checks mirror the runnable assertions in `backend/tests/test_evaluation_queries.py`.",
        "",
    ]
    reference = gemini.get("reference_date") or rules.get("reference_date") or "unknown"
    lines.extend([f"**Reference date:** {reference} (latest inspection timestamp)", ""])
    if rules:
        counts = rules["counts"]
        passed = sum(bool(item["passed"]) for item in rules["results"])
        lines.extend(
            [
                "## Rules provider run",
                "",
                f"- Benchmark questions: {len(rules['results'])}; passed: {passed}; failed: {len(rules['results']) - passed}.",
                f"- API actions including state setup/follow-ups: {counts['actions']}.",
                "- Provider API calls: 0.",
                "",
            ]
        )
    if gemini:
        counts = gemini["counts"]
        passed = sum(bool(item["passed"]) for item in gemini["results"])
        lines.extend(
            [
                "## Gemini provider run",
                "",
                f"- Benchmark questions: {len(gemini['results'])}; passed: {passed}; failed: {len(gemini['results']) - passed}.",
                f"- API actions including state setup/follow-ups: {counts['actions']}.",
                f"- Actual provider API attempts (including retries): {counts['provider_calls']}.",
                f"- SQLite response-cache hits: {counts['cache_hits']}.",
                "- The key value is never read into the report or logs; the script checks only whether it is present.",
                "",
            ]
        )
    if rules and gemini:
        rule_map = {item["id"]: item for item in rules["results"]}
        gemini_map = {item["id"]: item for item in gemini["results"]}
        lines.extend(["## Path comparison", "", "| ID | Rules | Gemini | Path result differs | Answer wording differs |", "|---|---|---|---|---|"])
        structured_differences = []
        wording_differences = []
        pass_differences = []
        for question_id in sorted(rule_map, key=lambda value: int(value[1:])):
            left, right = rule_map[question_id], gemini_map[question_id]
            structural = left["signature"] != right["signature"]
            wording = left["answer"].strip() != right["answer"].strip()
            if structural:
                structured_differences.append(question_id)
            if wording:
                wording_differences.append(question_id)
            if left["passed"] != right["passed"]:
                pass_differences.append(question_id)
            lines.append(
                f"| {question_id} | {'PASS' if left['passed'] else 'FAIL'} | {'PASS' if right['passed'] else 'FAIL'} | {'yes' if structural else 'no'} | {'yes' if wording else 'no'} |"
            )
        lines.extend(
            [
                "",
                f"Questions with different pass/fail outcomes: {', '.join(pass_differences) if pass_differences else 'none'}.",
                f"Questions with different structured tool output or citations: {', '.join(structured_differences) if structured_differences else 'none'}.",
                f"Questions with different answer wording: {', '.join(wording_differences) if wording_differences else 'none'}.",
                "",
            ]
        )
    failed_runs = [run for run in (rules, gemini) if run]
    for run in failed_runs:
        failures = [item for item in run["results"] if not item["passed"]]
        if failures:
            lines.extend([f"## {run['provider'].capitalize()} failures", ""])
            for item in failures:
                lines.append(f"- **{item['id']}** {item['question']}")
                lines.extend([f"  - {error}" for error in item["errors"]])
            lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "Expected checks are executable assertions from the repository's benchmark tests. Numerical results and visual data are supplied by deterministic tools; answer wording may differ by provider. The Gemini attempt count counts actual outbound calls after cache lookup, including any retries.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the official 18-question evaluation and generate docs/eval_report.md")
    parser.add_argument("--provider", choices=("rules", "gemini"), default=os.getenv("LLM_PROVIDER", "rules"))
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "docs" / "eval_report.md")
    args = parser.parse_args(argv)

    RUN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    runs: dict[str, Any] = {}
    if RUN_STATE_FILE.exists():
        try:
            runs = json.loads(RUN_STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            runs = {}
    run = _run_suite(args.provider)
    runs[args.provider] = run
    RUN_STATE_FILE.write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output.write_text(_report(runs), encoding="utf-8")
    passed = sum(bool(item["passed"]) for item in run["results"])
    print(f"{args.provider}: {passed}/{len(run['results'])} benchmark questions passed; {run['counts']['actions']} API actions")
    if args.provider == "gemini":
        print(f"Gemini provider calls: {run['counts']['provider_calls']}; response cache hits: {run['counts']['cache_hits']}")
    print(f"Wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
