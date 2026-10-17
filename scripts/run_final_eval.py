from __future__ import annotations

import os
import sys
from pathlib import Path

# Set environment BEFORE any backend imports
os.environ["ASSET_INTELLIGENCE_DATASET"] = "data/raw/flytbase-ahc-swe-asset-intelligence-dataset/test-data/dataset"
os.environ["ASSET_INTELLIGENCE_DB"] = "data/test.db"
os.environ["REFERENCE_DATE"] = "2027-01-15"
os.environ["LLM_PROVIDER"] = "rules"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json
from starlette.testclient import TestClient
from backend.app.main import app
from scripts.run_questions import _questions, _markdown

def main():
    questions_file = ROOT / "verification" / "final_questions.json"
    output_md = ROOT / "results_final.md"
    output_json = ROOT / "results_final.json"

    print("Loading questions from:", questions_file)
    raw_payload = json.loads(questions_file.read_text(encoding="utf-8"))
    questions = _questions(raw_payload)

    print(f"Executing {len(questions)} final questions against test.db via TestClient...")
    results = []
    with TestClient(app) as client:
        import time
        for item in questions:
            req_body = {
                "question": item["question"],
                "user_id": item.get("user_id", "U-201"),
            }
            if item.get("session_id"):
                req_body["session_id"] = item["session_id"]
            start = time.perf_counter()
            resp = client.post("/chat", json=req_body)
            lat = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code != 200:
                print(f"Error {resp.status_code} on {item['id']}: {resp.text}")
            payload = resp.json() if resp.status_code == 200 else {"answer": f"Error {resp.status_code}: {resp.text}", "citations": []}
            results.append({"scenario_id": item.get("id"), "question": item["question"], "latency_ms": lat, **payload})

    md_content = _markdown(results)
    output_md.write_text(md_content, encoding="utf-8")
    output_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} results to {output_md}")

if __name__ == "__main__":
    main()
