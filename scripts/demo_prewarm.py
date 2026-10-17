from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("ASSET_INTELLIGENCE_API", "http://127.0.0.1:8000").rstrip("/")
QUESTIONS = [
    ("U-201", "Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart."),
    ("U-204", "Tyler Hughes says WELL-0175 is running fine and not shut in. Is that correct? Show its status card."),
    ("U-202", "Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table."),
    ("U-202", "For the three wells we discussed yesterday, what have repairs cost this year?"),
    ("U-201", "For the three wells we discussed yesterday, what have repairs cost this year?"),
    ("U-202", "Which wells in Southwest Block 23 had the highest repair costs in 2026?"),
]


def _request(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    with urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    try:
        health = _request("/health")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise SystemExit(f"Demo backend is not reachable at {BASE_URL}: {exc}") from exc
    if health.get("status") != "ok" or health.get("demo_mode") is not True or health.get("demo_db_safe") is not True:
        raise SystemExit("Refusing to pre-warm: backend health does not confirm the isolated demo database and cache.")

    for index, (user_id, question) in enumerate(QUESTIONS, 1):
        payload = _request("/chat", {"question": question, "user_id": user_id})
        print(f"Warmed {index}/{len(QUESTIONS)}: {question[:70]} [{payload.get('provider_path', 'unknown')}]")

    _request(
        "/corrections",
        {
            "scope": "well",
            "well_id": "WELL-0164",
            "field": "wellhead_temp_c",
            "original_value": "24.0",
            "corrected_value": "41.0",
            "reason": "Handheld thermal gun was faulty; field crew re-measured the wellhead.",
            "evidence": "15 Oct 2026 field re-measurement",
            "author": "U-201",
        },
    )
    # Warm the area answer after the same shared correction state as the recording.
    post_correction = _request(
        "/chat",
        {
            "question": "Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.",
            "user_id": "U-202",
        },
    )
    print(f"Warmed shared-correction area result [{post_correction.get('provider_path', 'unknown')}]")
    print("Pre-warm changed demo corrections and private messages. Run demo_reset again before recording; the LLM cache is preserved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
