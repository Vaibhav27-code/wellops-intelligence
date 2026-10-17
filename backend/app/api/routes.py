from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.app.llm.engine import CopilotEngine
from backend.app.llm.service import LLMQuestionService
from backend.app.memory.store import (
    decode_correction,
    open_memory,
    record_answer_feedback,
    record_correction,
    retrieve_private_memory,
    retrieve_shared_memory,
)
from backend.app.tools.db import get_db_path, query_records
from backend.app.tools.wells import get_well_details, search_wells

router = APIRouter()
engine = CopilotEngine()


@router.get("/users")
def api_get_users() -> dict[str, Any]:
    rows = query_records("user")
    users = [
        {
            "user_id": str(r.get("user_id")),
            "name": str(r.get("name", r.get("user_id"))),
            "role": str(r.get("role", "operator")),
            "team_id": r.get("team_id"),
            "area_id": r.get("area_id"),
        }
        for r in rows
    ]
    return {"users": users}



class ChatRequestModel(BaseModel):
    question: str
    user_id: str
    session_id: str | None = None


class CorrectionRequestModel(BaseModel):
    scope: str
    field: str
    corrected_value: Any
    author: str
    reason: str
    well_id: str | None = None
    well_type: str | None = None
    inspection_id: str | None = None
    original_value: Any = None
    evidence: str | None = None
    equipment_kind: str | None = None


class FeedbackRequestModel(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=256)
    rating: Literal["positive", "negative"]
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("user_id", "message_id")
    @classmethod
    def strip_identifiers(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


@router.post("/chat")
def chat(req: ChatRequestModel) -> dict[str, Any]:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    service = LLMQuestionService()
    return service.answer(
        req.question,
        lambda intent: engine.process_query(req.question, req.user_id, req.session_id, intent),
    )


@router.get("/wells/search")
def api_search_wells(q: str = "") -> dict[str, Any]:
    wells = search_wells(query=q)
    return {"wells": wells}


@router.get("/wells/{well_id}")
def api_get_well(well_id: str) -> dict[str, Any]:
    well = get_well_details(well_id)
    if not well:
        raise HTTPException(status_code=404, detail=f"Well {well_id} not found")
    return well


@router.get("/corrections")
def api_get_corrections() -> dict[str, Any]:
    conn = open_memory(get_db_path())
    try:
        shared = retrieve_shared_memory(conn)
        return {"corrections": shared.get("corrections", [])}
    finally:
        conn.close()


@router.post("/corrections")
def api_post_correction(req: CorrectionRequestModel) -> dict[str, Any]:
    conn = open_memory(get_db_path())
    try:
        res = record_correction(
            conn,
            scope=req.scope,
            field=req.field,
            original_value=req.original_value,
            corrected_value=req.corrected_value,
            author=req.author,
            reason=req.reason,
            well_id=req.well_id,
            well_type=req.well_type,
            inspection_id=req.inspection_id,
            evidence=req.evidence,
            equipment_kind=req.equipment_kind,
        )
        return {"correction_id": res["correction_id"], "status": "recorded"}
    finally:
        conn.close()


@router.post("/feedback")
def api_post_feedback(req: FeedbackRequestModel) -> dict[str, Any]:
    conn = open_memory(get_db_path())
    try:
        feedback = record_answer_feedback(
            conn,
            user_id=req.user_id,
            message_id=req.message_id,
            rating=req.rating,
            comment=req.comment,
        )
        return {
            "feedback_id": feedback["feedback_id"],
            "rating": feedback["rating"],
            "status": "recorded",
        }
    finally:
        conn.close()


@router.get("/memory/private/{user_id}")
def api_get_private_memory(user_id: str) -> dict[str, Any]:
    conn = open_memory(get_db_path())
    try:
        messages = retrieve_private_memory(conn, user_id=user_id)
        return {"messages": messages}
    finally:
        conn.close()
