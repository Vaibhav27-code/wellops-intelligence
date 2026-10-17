from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.calc.rules import load_production_rule  # noqa: E402
from backend.app.ingest.loader import resolve_dataset_root  # noqa: E402
from backend.app.tools.db import get_reference_date  # noqa: E402


GROUND_TRUTH_TESTS = (
    "backend/tests/test_metrics_ground_truth.py::test_fleet_metric_totals_match_independent_pandas_ground_truth",
    "backend/tests/test_metrics_ground_truth.py::test_mutated_unseen_dataset_matches_independent_ground_truth",
    "backend/tests/test_unseen_metric_questions.py::test_unseen_questions_match_independent_pandas_ground_truth",
)
STRUCTURED_FIELDS = (
    "visualization",
    "intent",
    "calculation_explanation",
    "conflicts",
    "conflict",
)


def _run(command: list[str], *, env: dict[str, str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=False,
    )
    if completed.returncode and not capture:
        printable_command = " ".join(command[:3])
        raise RuntimeError(f"Command failed ({completed.returncode}): {printable_command}")
    return completed


def _manual_thresholds(dataset_root: Path) -> list[tuple[str, bool, float | None]]:
    well_types: set[str] = set()
    for metadata_path in (dataset_root / "assets").glob("*/metadata.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        well_type = metadata.get("well_type")
        if isinstance(well_type, str) and well_type.strip():
            well_types.add(well_type.strip())

    report = []
    for well_type in sorted(well_types):
        manual_path = dataset_root / "fleet" / "well-types" / f"{well_type}.md"
        threshold: float | None = None
        if manual_path.is_file():
            try:
                threshold = load_production_rule(well_type, dataset_root).minimum_delta_c
            except (OSError, ValueError):
                pass
        report.append((well_type, manual_path.is_file(), threshold))
    return report


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(process: subprocess.Popen[Any], base_url: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("The local API server stopped before it became ready; server logs were withheld")
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.0)
            if response.is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    process.terminate()
    process.wait(timeout=10)
    raise RuntimeError("The local API server did not become ready within 45 seconds; server logs were withheld")


def _run_question_path(
    *,
    provider: str,
    database: Path,
    dataset: Path,
    questions: Path,
    user: str,
    run_dir: Path,
    base_env: dict[str, str],
) -> tuple[Path, Path]:
    provider_db = run_dir / f"asset-intelligence-{provider}.db"
    shutil.copy2(database, provider_db)
    env = base_env.copy()
    env.update(
        {
            "ASSET_INTELLIGENCE_DATASET": str(dataset),
            "ASSET_INTELLIGENCE_DB": str(provider_db),
            "LLM_PROVIDER": provider,
            "LLM_CACHE_PATH": str(run_dir / f"llm-cache-{provider}.db"),
        }
    )

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    markdown_path = run_dir / f"results_{provider}.md"
    json_path = run_dir / f"results_{provider}.json"
    log_handle = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_server(server, base_url)
        _run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "run_questions.py"),
                str(questions),
                "--user",
                user,
                "--base-url",
                base_url,
                "--output",
                str(markdown_path),
                "--json-output",
                str(json_path),
            ],
            env=env,
        )
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        log_handle.close()
    return markdown_path, json_path


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _compare_results(rules_path: Path, gemini_path: Path) -> None:
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    gemini = json.loads(gemini_path.read_text(encoding="utf-8"))
    rules_by_id = {str(item.get("scenario_id")): item for item in rules}
    gemini_by_id = {str(item.get("scenario_id")): item for item in gemini}
    all_ids = sorted(rules_by_id.keys() | gemini_by_id.keys())
    differences = []
    for question_id in all_ids:
        left = rules_by_id.get(question_id)
        right = gemini_by_id.get(question_id)
        if left is None or right is None:
            differences.append((question_id, True, True, "missing from one path"))
            continue
        structured_diff = _canonical({field: left.get(field) for field in STRUCTURED_FIELDS}) != _canonical(
            {field: right.get(field) for field in STRUCTURED_FIELDS}
        )
        citations_diff = _canonical(left.get("citations", [])) != _canonical(right.get("citations", []))
        if structured_diff or citations_diff:
            differences.append((question_id, structured_diff, citations_diff, str(left.get("question", ""))))

    print("\nStructured output and citation differences:")
    if not differences:
        print("  None")
        return
    for question_id, structured_diff, citations_diff, question in differences:
        print(
            f"  {question_id}: structured_output={'different' if structured_diff else 'same'}, "
            f"citations={'different' if citations_diff else 'same'}"
        )
        if question:
            print(f"    {question}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest a new dataset, run its validation/oracle suite, and compare rules/Gemini question runs."
    )
    parser.add_argument("dataset", type=Path, help="New dataset folder or its parent checkout")
    parser.add_argument("questions_json", type=Path, help="Final question JSON file")
    parser.add_argument("--user", default="eval-user", help="Fallback user_id when question entries omit one")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "test_day_runs",
        help="Parent directory for a timestamped run folder (default: data/test_day_runs)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    dataset_arg = args.dataset.expanduser().resolve()
    questions = args.questions_json.expanduser().resolve()
    if not dataset_arg.exists():
        raise FileNotFoundError(f"Dataset folder does not exist: {dataset_arg}")
    if not questions.is_file():
        raise FileNotFoundError(f"Questions JSON does not exist: {questions}")
    dataset_root = resolve_dataset_root(dataset_arg)

    load_dotenv(REPO_ROOT / ".env", override=False)
    reference_override = os.getenv("REFERENCE_DATE", "").strip()
    reference_override_set = bool(reference_override)
    gemini_key_present = bool(os.getenv("GEMINI_API_KEY", "").strip())
    run_name = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    run_dir = args.output_dir.expanduser().resolve() / run_name
    run_dir.mkdir(parents=True, exist_ok=False)
    database = run_dir / "asset-intelligence-validation.db"

    env = os.environ.copy()
    env.update(
        {
            "ASSET_INTELLIGENCE_DATASET": str(dataset_arg),
            "ASSET_INTELLIGENCE_DB": str(database),
            "TEST_DAY_DATABASE": str(database),
            "LLM_PROVIDER": "rules",
        }
    )

    print(f"Run directory: {run_dir}")
    print(f"ASSET_INTELLIGENCE_DATASET: {dataset_arg}")
    print(f"ASSET_INTELLIGENCE_DB: {database}")
    print("\nIngestion validation report:")
    ingest = _run(
        [sys.executable, "-m", "backend.app.ingest", str(dataset_arg), "--database", str(database)],
        env=env,
        capture=True,
    )
    try:
        validation = json.loads(ingest.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ingestion did not emit a JSON validation report") from exc
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    print("Detected well types and manual thresholds:")
    for well_type, manual_exists, threshold in _manual_thresholds(dataset_root):
        threshold_text = f"{threshold:g} deg C" if threshold is not None else "not detected"
        print(
            f"  {well_type}: manual={'yes' if manual_exists else 'no'}, "
            f"production threshold={'yes' if threshold is not None else 'no'} ({threshold_text})"
        )

    if ingest.returncode:
        raise RuntimeError("Ingestion validation reported errors; see the report above")

    if reference_override_set:
        os.environ.pop("REFERENCE_DATE", None)
    detected_reference = get_reference_date(database)
    if reference_override_set:
        os.environ["REFERENCE_DATE"] = reference_override
    print(f"\nReference date detected from latest inspection: {detected_reference}")
    print(f"REFERENCE_DATE set: {'true' if reference_override_set else 'false'}")
    if reference_override_set:
        print(f"Reference date used with override: {get_reference_date(database)}")

    test_env = env.copy()
    test_env["LLM_PROVIDER"] = "rules"
    print("\nRunning mutated-dataset and pandas-oracle tests against the fresh database:")
    _run([sys.executable, "-m", "pytest", "-q", *GROUND_TRUTH_TESTS], env=test_env)

    print("\nRunning questions with LLM_PROVIDER=rules:")
    rules_markdown, rules_json = _run_question_path(
        provider="rules",
        database=database,
        dataset=dataset_arg,
        questions=questions,
        user=args.user,
        run_dir=run_dir,
        base_env=env,
    )
    print(f"Rules results: {rules_markdown}")

    if gemini_key_present:
        print("\nGEMINI_API_KEY present: true; running one Gemini question pass.")
        try:
            gemini_markdown, gemini_json = _run_question_path(
                provider="gemini",
                database=database,
                dataset=dataset_arg,
                questions=questions,
                user=args.user,
                run_dir=run_dir,
                base_env=env,
            )
        except Exception:
            gemini_markdown = run_dir / "results_gemini.md"
            gemini_markdown.write_text(
                "# Gemini Results\n\nThe Gemini run failed; diagnostic details were withheld from output.\n",
                encoding="utf-8",
            )
            print("Gemini run failed; diagnostic details were withheld from output.")
            print(f"Gemini results: {gemini_markdown}")
            return 1
        print(f"Gemini results: {gemini_markdown}")
        _compare_results(rules_json, gemini_json)
    else:
        gemini_markdown = run_dir / "results_gemini.md"
        gemini_markdown.write_text(
            "# Gemini Results\n\nSkipped because GEMINI_API_KEY is not configured.\n",
            encoding="utf-8",
        )
        print("\nGEMINI_API_KEY present: false; Gemini pass skipped.")
        print(f"Gemini results: {gemini_markdown}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
