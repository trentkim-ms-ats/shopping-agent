from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_api import message

from app.db import canonical
from app.errors import AppError
from app.retrieval import satisfies


def selected(client, session, variants=None):
    response = client.post(f"/api/sessions/{session}/selection",
                           json={"variant_ids": variants or ["J01-Black-M"]})
    assert response.status_code == 200
    return response.json()["selection_state"]


def test_comparison_applies_server_rules_from_shortlist(client, session):
    reply = message(client, session, "Lightweight jacket for fall hiking under $200").json()
    ids = [c["product_id"] for c in reply["cards"][:2]]
    data = client.app.state.tools.compare(ids, client.app.state.db.session(session))
    assert data["product_ids"] == ids
    assert len(data["options"]) == 2
    assert all(c["variant"]["size"] == "M" for c in data["options"])
    assert data["price_difference_cents"] == abs(data["options"][0]["price_cents"] - data["options"][1]["price_cents"])
    assert any(r["label"] == "Your priority: lightweight" for r in data["rows"])


def test_confirmation_idempotency_feedback_and_changed_budget(client, session):
    state = selected(client, session)
    path = f"/api/sessions/{session}"
    body = {"revision": state["revision"]}
    first = client.post(f"{path}/selection/confirm", json=body)
    assert first.status_code == 200 and first.json()["confirmed"]
    assert not first.json()["feedback_recorded"]
    assert client.post(f"{path}/selection/confirm", json=body).json() == first.json()
    assert client.post(f"{path}/journey/feedback", json={**body, "helpful": True}).status_code == 200
    metrics = client.get(f"{path}/journey").json()
    assert metrics["counts"]["selection_confirmed"] == 1
    assert metrics["feedback_recorded"]
    assert metrics["selection"]["feedback_recorded"]
    assert selected(client, session)["feedback_recorded"]
    changed = message(client, session, "Lightweight jacket under $50").json()["selection_state"]
    assert changed["items"] and not changed["confirmed"] and not changed["can_preview"]
    assert not changed["feedback_recorded"]
    assert any("budget" in i["message"] for i in changed["issues"])
    assert client.post(f"{path}/selection/confirm", json=body).status_code == 409
    assert client.post(f"{path}/selection/confirm", json={"revision": changed["revision"]}).status_code == 409
    assert client.post(f"{path}/try-ons/demo", json={
        "variant_ids": ["J01-Black-M"], "request_id": str(uuid4())}).status_code == 409
    accepted = client.post(f"{path}/selection/confirm",
                           json={"revision": changed["revision"], "accept_exceptions": True}).json()
    assert accepted["confirmed"] and accepted["can_preview"]
    assert not client.get(f"{path}/journey").json()["feedback_recorded"]


def test_stock_change_cannot_be_overridden(client, session):
    state = selected(client, session)
    with client.app.state.db.connect() as conn:
        row = conn.execute("SELECT facts_json FROM commerce WHERE product_id='J01'").fetchone()
        import json
        facts = json.loads(row[0])
        next(v for v in facts["variants"] if v["variant_id"] == "J01-Black-M")["stock"] = 0
        conn.execute("UPDATE commerce SET facts_json=? WHERE product_id='J01'", (canonical(facts),))
    updated = client.get(f"/api/sessions/{session}/journey").json()["selection"]
    assert updated["revision"] != state["revision"]
    assert any(not issue["overridable"] for issue in updated["issues"])
    assert client.post(f"/api/sessions/{session}/selection/confirm", json={
        "revision": updated["revision"], "accept_exceptions": True}).status_code == 409


def test_jacket_budget_is_not_outfit_budget_and_no_image_needed(client, session):
    message(client, session, "Lightweight jacket under $200")
    state = selected(client, session, ["J01-Black-M", "P01-Slate-M"])
    assert not state["issues"]
    assert state["subtotal_cents"] == sum(i["price_cents"] for i in state["items"])
    assert client.post(f"/api/sessions/{session}/selection/confirm", json={"revision": state["revision"]}).status_code == 200
    assert client.app.state.db.jobs(session) == []


def test_one_change_alternatives_preserve_other_constraints_and_reject_stale(client, session):
    data = message(client, session, "Lightweight hiking jacket under $1").json()
    assert data["cards"] == []
    option = next(a for a in data["alternatives"] if "budget" in a["label"])
    old = data["constraints"]
    for key in old:
        if key != "max_price_cents":
            assert option["intent"][key] == old[key]
    result = client.post(f"/api/sessions/{session}/relax", json={"alternative_id": option["id"]})
    assert result.status_code == 200 and result.json()["results"]
    assert result.json()["eligible_count"] == option["eligible_count"]
    assert client.post(f"/api/sessions/{session}/relax", json={"alternative_id": option["id"]}).status_code == 409


def test_controlled_baseline_uses_same_eligibility_without_semantic_calls(client, session):
    message(client, session, "Must have light rain protection hiking jacket under $100")
    retrieval = client.app.state.retrieval
    retrieval.semantic = AsyncMock(side_effect=AssertionError("Baseline must not call embeddings"))
    state = client.app.state.db.session(session)
    result = client.get(f"/api/sessions/{session}/baseline?q=hiking").json()
    _, products = client.app.state.db.catalog()
    expected = {p["raw"]["product_id"] for p in products if satisfies(p, state.intent)}
    assert result["eligible_count"] == len(expected)
    assert {r["product_id"] for r in result["results"]} <= expected
    assert "not an enrichment ablation" in result["limitation"]


def test_observations_are_idempotent_and_session_scoped(client, session):
    path = f"/api/sessions/{session}"
    body = {"name": "shortlist_shown", "event_id": str(uuid4())}
    assert client.post(f"{path}/journey/events", json=body).status_code == 409
    message(client, session, "Lightweight hiking jacket")
    for _ in range(2):
        assert client.post(f"{path}/journey/events", json=body).status_code == 200
    stats = client.get(f"{path}/journey").json()
    assert stats["counts"]["shortlist_shown"] == 1
    assert stats["first_seconds"]["shortlist_shown"] >= 0
    other = client.post("/api/sessions", json={"profile_id": "sam"}).json()["session_id"]
    assert "shortlist_shown" not in client.get(f"/api/sessions/{other}/journey").json()["counts"]


def test_daily_image_reservations_persist_and_count_failed_calls(db):
    db.reserve_image_call(2, "product_color")
    db.reserve_image_call(2, "try_on")
    with pytest.raises(AppError, match="Daily image-call limit"):
        db.reserve_image_call(2, "try_on")
    from app.db import Database
    with pytest.raises(AppError):
        Database(db.path).reserve_image_call(2, "product_color")
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM image_call_reservations").fetchone()[0] == 2


def test_requirement_change_invalidates_completed_preview(client, session):
    from test_try_on import wait_job
    selected(client, session)
    job = client.post(f"/api/sessions/{session}/try-ons/demo", json={
        "variant_ids": ["J01-Black-M"], "request_id": str(uuid4())}).json()
    done = wait_job(client, session, job["job_id"])
    assert client.get(done["image_url"]).status_code == 200
    message(client, session, "Lightweight jacket under $50")
    assert client.get(done["image_url"]).status_code == 404
