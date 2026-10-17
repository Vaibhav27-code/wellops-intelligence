from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

from backend.app.memory.store import open_memory
from backend.app.tools.db import get_db_path

client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def reset_memory():
    conn = open_memory(get_db_path())
    try:
        conn.execute("DELETE FROM corrections")
        conn.execute("DELETE FROM shared_notes")
        conn.execute("DELETE FROM private_messages")
        conn.commit()
    finally:
        conn.close()
    yield
    conn = open_memory(get_db_path())
    try:
        conn.execute("DELETE FROM corrections")
        conn.execute("DELETE FROM shared_notes")
        conn.execute("DELETE FROM private_messages")
        conn.commit()
    finally:
        conn.close()


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_q1_well_0001_status():
    res = client.post(
        "/chat",
        json={
            "question": "Is WELL-0001 producing oil right now? When was it last inspected, and by whom? Show me its status card.",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "not producing" in data["answer"].lower()
    assert "INS-0001-0203" in data["answer"]
    assert "Ryan Brooks" in data["answer"]
    assert "3.2" in data["answer"]
    assert data["visualization"] is not None
    assert data["visualization"]["type"] == "card"
    assert len(data["citations"]) >= 2


def test_q2_northeast_block_8_non_producing():
    res = client.post(
        "/chat",
        json={
            "question": "Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    viz = data["visualization"]
    assert viz["type"] == "table"
    wells = [r["Well"] for r in viz["data"]]
    # Should include 4 wells initially
    assert set(wells) == {"WELL-0164", "WELL-0170", "WELL-0172", "WELL-0175"}


def test_q3_line_chart_temperature():
    res = client.post(
        "/chat",
        json={
            "question": "Show a line chart of WELL-0001's wellhead temperature against air temperature for the last 13 weeks, and mark when it was not producing oil.",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    viz = data["visualization"]
    assert viz["type"] == "line"
    assert len(viz["data"]) == 13


def test_q4_spills_table_well_0001():
    res = client.post(
        "/chat",
        json={
            "question": "How many oil spills has WELL-0001 had in the last 4 years, and how much oil in total? List them in a table.",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "6" in data["answer"]
    assert "15.1" in data["answer"]
    assert data["visualization"]["type"] == "table"
    assert len(data["visualization"]["data"]) == 6


def test_q5_downtime_well_0001_2025():
    res = client.post(
        "/chat",
        json={
            "question": "How many days was WELL-0001 down in 2025?",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "21 days" in data["answer"]


def test_q6_top_downtime_bar_chart():
    res = client.post(
        "/chat",
        json={
            "question": "Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    viz = data["visualization"]
    assert viz["type"] == "bar"
    top_wids = [r["well_id"] for r in viz["data"]]
    assert top_wids == ["WELL-0121", "WELL-0107", "WELL-0138"] or set(top_wids) == {"WELL-0121", "WELL-0107", "WELL-0138"}


def test_q7_spills_map():
    res = client.post(
        "/chat",
        json={
            "question": "Show on a map every well in Northeast Block 8 with a real spill in the last 90 days.",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    viz = data["visualization"]
    assert viz["type"] == "map"
    wids = [r["well_id"] for r in viz["data"]]
    assert set(wids) == {"WELL-0151", "WELL-0165", "WELL-0175", "WELL-0186"}


def test_q8_heatmap():
    res = client.post(
        "/chat",
        json={
            "question": "Show a heatmap of 2026 spills by geographic area and month.",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    viz = data["visualization"]
    assert viz["type"] == "heatmap"
    rows_by_area = {r["Area"]: r for r in viz["data"]}
    assert rows_by_area["Southwest Block 23"]["Total"] == 35
    assert rows_by_area["Southwest Block 24"]["Total"] == 43
    assert rows_by_area["Northeast Block 7"]["Total"] == 37
    assert rows_by_area["Northeast Block 8"]["Total"] == 26


def test_q9_rules_broken():
    res = client.post(
        "/chat",
        json={
            "question": "Which rules has WELL-0001 broken in the last 12 months, and what is still open?",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "SR-01" in data["answer"]
    assert "SR-02" in data["answer"]
    assert "SR-03" in data["answer"]
    assert "RC-04" in data["answer"]


def test_q10_containment_breaches():
    res = client.post(
        "/chat",
        json={
            "question": "In Southwest Block 24, which spills in the last 90 days were not contained within the SOP time limit?",
            "user_id": "test-user",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "WELL-0082" in data["answer"]
    assert "WELL-0100" in data["answer"]


def test_q11_and_q16_private_memory_isolation():
    # User 1: Michael Turner asks Q6 first
    client.post(
        "/chat",
        json={
            "question": "Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months? Show a bar chart.",
            "user_id": "michael-turner",
        },
    )

    # User 1 asks about repair costs
    res1 = client.post(
        "/chat",
        json={
            "question": "For the three wells we discussed yesterday, what have repairs cost this year?",
            "user_id": "michael-turner",
        },
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert "25,794" in d1["answer"]
    assert "46,942" in d1["answer"]
    assert "5,176" in d1["answer"]

    # User 2: Jessica Reed asks the same question in her own session
    res2 = client.post(
        "/chat",
        json={
            "question": "For the three wells we discussed yesterday, what have repairs cost this year?",
            "user_id": "jessica-reed",
        },
    )
    assert res2.status_code == 200
    d2 = res2.json()
    # Private memory must NOT leak to Jessica Reed!
    assert "no record" in d2["answer"].lower() or "no earlier conversation" in d2["answer"].lower()
    assert "25,794" not in d2["answer"]


def test_q12_temperature_correction_and_re_evaluation():
    # Correction by Michael Turner
    res_corr = client.post(
        "/chat",
        json={
            "question": "The 15 Oct reading for WELL-0164 is wrong. The handheld thermal gun used in that inspection was faulty; the field crew re-measured the wellhead at 41.0 °C.",
            "user_id": "michael-turner",
        },
    )
    assert res_corr.status_code == 200
    data_corr = res_corr.json()
    assert "producing oil" in data_corr["answer"].lower()
    assert data_corr["conflict"] is True

    # Re-ask Q2: WELL-0164 must no longer be non-producing!
    res_q2 = client.post(
        "/chat",
        json={
            "question": "Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.",
            "user_id": "michael-turner",
        },
    )
    assert res_q2.status_code == 200
    viz = res_q2.json()["visualization"]
    wells = [r["Well"] for r in viz["data"]]
    assert "WELL-0164" not in wells
    assert set(wells) == {"WELL-0170", "WELL-0172", "WELL-0175"}


def test_q13_spill_volume_correction():
    res = client.post(
        "/chat",
        json={
            "question": "The AI estimated the 24 Sep spill at WELL-0151 as 4.5 bbl. The field crew measured 5.4 bbl.",
            "user_id": "michael-turner",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "reportable" in data["answer"].lower()
    assert "SR-01" in data["answer"]
    assert "5.4" in data["answer"]


def test_q14_team_rule_override():
    # Initial query
    res1 = client.post(
        "/chat",
        json={
            "question": "Which wells in Northeast Block 7 need a root-cause analysis on their pump jack?",
            "user_id": "michael-turner",
        },
    )
    data1 = res1.json()
    assert "WELL-0108" in data1["answer"]
    assert "WELL-0121" in data1["answer"]
    assert "WELL-0138" in data1["answer"]
    assert "WELL-0120" not in data1["answer"]

    # Rule change for T350
    res_rule = client.post(
        "/chat",
        json={
            "question": "Note for all T350 wells: our team now wants a pump jack root-cause analysis after 2 repairs, not 3.",
            "user_id": "michael-turner",
        },
    )
    assert res_rule.status_code == 200

    # Re-query: WELL-0120 (T350 with 2 repairs) is added, WELL-0102 (T200 with 2 repairs) is NOT added!
    res2 = client.post(
        "/chat",
        json={
            "question": "Which wells in Northeast Block 7 need a root-cause analysis on their pump jack?",
            "user_id": "michael-turner",
        },
    )
    data2 = res2.json()
    assert "WELL-0120" in data2["answer"]
    assert "WELL-0102" not in data2["answer"]
