from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx


def _questions(payload: Any) -> list[dict[str, str]]:
    if isinstance(payload, dict):
        payload = payload.get("questions")
    if not isinstance(payload, list):
        raise ValueError("Questions JSON must be an array or an object with a 'questions' array")
    result = []
    for index, item in enumerate(payload, 1):
        if isinstance(item, str):
            question, label = item, str(index)
        elif isinstance(item, dict) and isinstance(item.get("question"), str):
            question, label = item["question"], str(item.get("id", index))
            per_item_user = item.get("user_id")
            if per_item_user is not None and not isinstance(per_item_user, str):
                raise ValueError(f"Question {index} user_id must be a string")
        else:
            raise ValueError(f"Question {index} must be a string or an object with a string 'question'")
        if not question.strip():
            raise ValueError(f"Question {index} cannot be empty")
        normalized = {"id": label, "question": question.strip()}
        if isinstance(item, dict) and isinstance(item.get("user_id"), str):
            normalized["user_id"] = item["user_id"]
        if isinstance(item, dict) and isinstance(item.get("session_id"), str):
            normalized["session_id"] = item["session_id"]
        result.append(normalized)
    return result


def _markdown(results: list[dict[str, Any]]) -> str:
    sections = ["# Question Run Results", ""]
    for index, result in enumerate(results, 1):
        sections.extend(
            [
                f"## {result.get('scenario_id', index)}. {result['question']}",
                "",
                f"- Provider path: `{result.get('provider_path', 'unknown')}`",
                f"- Visualization: `{(result.get('visualization') or {}).get('type', 'none')}`",
                "",
                "### Answer",
                "",
                str(result.get("answer_text", result.get("answer", ""))),
                "",
                "### Citations",
                "",
            ]
        )
        citations = result.get("citations") or []
        if citations:
            for citation in citations:
                sections.append(f"- `{json.dumps(citation, ensure_ascii=False, sort_keys=True)}`")
        else:
            sections.append("- None")
        sections.append("")
    return "\n".join(sections)


def run_questions(
    questions: list[dict[str, str]],
    *,
    base_url: str,
    user_id: str,
    transport: httpx.BaseTransport | None = None,
) -> list[dict[str, Any]]:
    results = []
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=90.0, transport=transport) as client:
        for item in questions:
            request_body = {
                "question": item["question"],
                "user_id": item.get("user_id", user_id),
            }
            if item.get("session_id"):
                request_body["session_id"] = item["session_id"]
            response = client.post(
                "/chat",
                json=request_body,
            )
            response.raise_for_status()
            payload = response.json()
            results.append({"scenario_id": item.get("id"), "question": item["question"], **payload})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run questions against the Asset Intelligence Copilot API")
    parser.add_argument("questions_json", type=Path)
    parser.add_argument("--user-id", default="eval-user")
    parser.add_argument("--base-url", default=os.getenv("ASSET_INTELLIGENCE_API", "http://localhost:8000"))
    parser.add_argument("--output", type=Path, default=Path("results.md"))
    args = parser.parse_args(argv)

    questions = _questions(json.loads(args.questions_json.read_text(encoding="utf-8")))
    results = run_questions(questions, base_url=args.base_url, user_id=args.user_id)
    args.output.write_text(_markdown(results), encoding="utf-8")
    print(f"Wrote {len(results)} results to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
