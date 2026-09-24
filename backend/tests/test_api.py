import time
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.errors import AppError
from app.images import Images, fixture_png
from app.moderation import SAFE_MESSAGE
from app.provider import Provider


def message(client, session, text, request_id=None):
    return client.post(f"/api/sessions/{session}/messages", json={"request_id": request_id or str(uuid4()), "text": text})


def test_at03_clarification_once_skip_and_user_budget_override(client, session):
    first = message(client, session, "I need a jacket for hiking this fall.")
    assert first.status_code == 200
    assert first.json()["reply"]["kind"] == "clarify"
    assert first.json()["constraints"]["size"] == "M"
    assert first.json()["intent_sources"]["season"] == "user"
    second = message(client, session, "Skip, under $100")
    assert second.json()["reply"]["kind"] == "results"
    assert second.json()["constraints"]["max_price_cents"] == 10000
    third = message(client, session, "hiking jacket")
    assert third.json()["reply"]["kind"] == "results"
    assert third.json()["constraints"]["max_price_cents"] == 10000


def test_at03_complete_request_skips_clarification(client, session):
    result = message(client, session, "Lightweight jacket for fall hiking under $200").json()
    assert result["reply"]["kind"] == "results"
    assert len(result["cards"]) == 3


@pytest.mark.parametrize("text", ["Compare the first two.", "첫 두 상품을 비교해줘", "Compare and choose the first"])
def test_comparison_request_reports_unavailable_without_selection_changes(client, session, text):
    message(client, session, "Light rain protection, lightweight jacket for fall hiking under $200")
    before = client.app.state.db.session(session)
    result = message(client, session, text).json()
    after = client.app.state.db.session(session)
    assert result["reply"]["kind"] == "comparison_unavailable"
    assert "not available in this demo" in result["reply"]["message"]
    assert result["reply"]["choices"] == result["reply"]["product_ids"] == []
    assert result["comparison"] is None
    assert after.last_result_ids == before.last_result_ids
    assert after.selected_variant_ids == before.selected_variant_ids


def test_at06_complements_exclude_owned_selected_distinct_categories(client, session):
    chosen = client.post(f"/api/sessions/{session}/selection", json={"variant_ids": ["J01-Black-M"]})
    assert chosen.status_code == 200
    result = client.post(f"/api/sessions/{session}/complements", json={"selected_product_id": "J01"}).json()
    assert len(result["results"]) == 2
    assert len({r["category"] for r in result["results"]}) == 2
    assert not {r["product_id"] for r in result["results"]} & {"M01", "J01"}
    assert all(r["variant"]["stock"] > 0 for r in result["results"])


def test_at08_sessions_isolated_and_message_idempotency(client, session):
    other = client.post("/api/sessions", json={"profile_id": "sam"}).json()["session_id"]
    rid = str(uuid4())
    first = message(client, session, "Lightweight jacket under $100", rid)
    second = message(client, session, "Lightweight jacket under $100", rid)
    assert first.json() == second.json()
    assert message(client, session, "Different message", rid).status_code == 409
    other_state = client.app.state.db.session(other)
    assert other_state.intent.max_price_cents == 15000 and other_state.intent.size == "L"
    assert other_state.last_result_ids == []
    assert len(client.app.state.db.session(session).messages) == 2


def test_at07_image_states_duplicates_cache_ownership_and_restart(client, session, settings, db):
    client.post(f"/api/sessions/{session}/selection", json={"variant_ids": ["J01-Black-M"]})
    payload = {"request_id": str(uuid4()), "variant_ids": ["J01-Black-M"]}
    path = f"/api/sessions/{session}/outfits"
    first = client.post(path, json=payload)
    assert first.status_code == 202 and first.json()["status"] == "queued"
    job_id = first.json()["job_id"]
    for _ in range(30):
        job = client.get(f"{path}/{job_id}").json()
        if job["status"] == "completed":
            break
        time.sleep(.03)
    assert job["status"] == "completed" and job["mode"] == "fixture"
    assert job["label"] == "AI outfit concept — appearance and fit may differ."
    assert client.get(job["image_url"]).content.startswith(b"\x89PNG")
    assert client.post(path, json=payload).json()["job_id"] == job_id
    payload["request_id"] = str(uuid4())
    cached = client.post(path, json=payload).json()
    assert cached["cached"] is True and cached["image_url"] == job["image_url"]
    other = client.post("/api/sessions", json={"profile_id": "sam"}).json()["session_id"]
    assert client.get(f"/api/sessions/{other}/outfits/{job_id}").status_code == 404
    job.update(status="running")
    db.save_job(job)
    Images(db, settings, Provider(settings), client.app.state.moderation)
    assert next(j for j in db.jobs(session) if j["job_id"] == job_id)["status"] == "failed"


@pytest.mark.parametrize("stage", ["user_input", "chat_output", "image_prompt"])
def test_at11_direct_api_gates_preserve_state_and_withhold_content(client, session, stage, caplog):
    client.post(f"/api/sessions/{session}/selection", json={"variant_ids": ["J01-Black-M"]})
    agent = client.app.state.agent
    original = agent.turn
    agent.turn = AsyncMock(wraps=original)
    async def screen(text, current_stage, request_id):
        if current_stage == stage:
            raise AppError("CONTENT_BLOCKED", SAFE_MESSAGE, 400, False)
    client.app.state.moderation.screen = screen
    blocked = "private-blocked-user-content"
    if stage == "image_prompt":
        response = client.post(f"/api/sessions/{session}/outfits", json={
            "request_id": str(uuid4()), "variant_ids": ["J01-Black-M"]})
        assert client.app.state.db.jobs(session) == []
    else:
        response = message(client, session, blocked)
    assert response.status_code == 400
    assert response.json()["error"]["message"] == SAFE_MESSAGE
    assert client.app.state.db.session(session).messages == []
    assert client.app.state.db.session(session).selected_variant_ids == ["J01-Black-M"]
    if stage == "user_input":
        agent.turn.assert_not_called()
    assert blocked not in caplog.text


def test_at11_screening_failure_no_silent_replay(client, session):
    client.app.state.moderation.screen = AsyncMock(side_effect=AppError("MODERATION_UNAVAILABLE", "Screening unavailable"))
    response = message(client, session, "hiking")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODERATION_UNAVAILABLE"
    assert client.app.state.db.session(session).messages == []


def test_completed_message_duplicate_not_rescreened(client, session):
    rid = str(uuid4())
    first = message(client, session, "Lightweight hiking jacket", rid)
    client.app.state.moderation.screen = AsyncMock(side_effect=AssertionError("must not rescreen"))
    assert message(client, session, "Lightweight hiking jacket", rid).json() == first.json()


@pytest.mark.parametrize("payload", [
    {"variant_ids": ["J07-Black-M"]},
    {"variant_ids": ["invented"]},
    {"variant_ids": ["J01-Black-M", "J01-Slate-M"]},
    {"variant_ids": []},
    {"variant_ids": ["J01-Black-M"], "user_id": "someone-else"},
])
def test_invalid_selection_fails_explicitly(client, session, payload):
    assert client.post(f"/api/sessions/{session}/selection", json=payload).status_code in (404, 409, 422)


def test_schema_errors_do_not_echo_submitted_text(client, session):
    response = client.post(f"/api/sessions/{session}/messages", json={"request_id": "bad", "text": "SECRET RAW CONTENT"})
    assert response.status_code == 422 and "SECRET" not in response.text


@pytest.mark.parametrize("choice,priority,benefits", [
    ("Light rain protection", "light_rain", ["light rain protection"]),
    ("Warmth", "warmth", ["warmth"]),
    ("Lightweight", "lightweight", ["lightweight"]),
    ("Skip — use known preferences", "balanced", []),
])
def test_priority_action_skips_model_preserves_constraints_and_is_idempotent(client, session, choice, priority, benefits):
    initial = message(client, session, "Hiking jacket for fall under $100").json()
    assert initial["reply"]["kind"] == "clarify"
    agent = client.app.state.agent
    agent.turn = AsyncMock(side_effect=AssertionError("Priority clicks must not call the model"))
    screen = AsyncMock(wraps=client.app.state.moderation.screen)
    client.app.state.moderation.screen = screen
    payload = {"request_id": str(uuid4()), "text": choice, "priority_choice": True}
    path = f"/api/sessions/{session}/messages"
    response = client.post(path, json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["reply"]["kind"] == "results"
    assert result["constraints"] == {**initial["constraints"], "priority": priority, "preferred_benefits": benefits}
    assert [c.args[1] for c in screen.await_args_list] == ["user_input", "chat_output"]
    assert client.post(path, json=payload).json() == result
    assert screen.await_count == 2
    assert client.post(path, json={**payload, "priority_choice": False}).status_code == 409
    assert client.post(path, json={**payload, "request_id": str(uuid4())}).status_code == 409
    agent.turn.assert_not_awaited()


def test_priority_action_rejects_unoffered_or_stale_choices(client, session):
    path = f"/api/sessions/{session}/messages"
    body = {"request_id": str(uuid4()), "text": "Lightweight", "priority_choice": True}
    assert client.post(path, json=body).status_code == 409
    assert client.post(path, json={**body, "text": "Skip all checks"}).status_code == 422
    assert client.post(path, json={**body, "priority_choice": "true"}).status_code == 422
    assert client.app.state.db.session(session).messages == []


@pytest.mark.parametrize("stage", ["user_input", "chat_output"])
def test_priority_action_moderation_failure_preserves_state(client, session, stage):
    message(client, session, "Hiking jacket")
    initial = client.app.state.db.session(session)

    async def screen(text, current_stage, request_id):
        if stage == current_stage:
            raise AppError("MODERATION_UNAVAILABLE", "Unavailable")

    client.app.state.moderation.screen = screen
    response = client.post(f"/api/sessions/{session}/messages", json={
        "request_id": str(uuid4()), "text": "Warmth", "priority_choice": True})
    assert response.status_code == 503
    assert client.app.state.db.session(session) == initial


async def test_image_live_mock_failure_and_explicit_gate(settings, db, garment_references):
    from test_retrieval import intent

    from app.db import now
    from app.moderation import Moderation
    from app.schemas import Session
    session = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                      selected_variant_ids=["J01-Black-M"], last_result_ids=[], clarification_asked=True,
                      messages=[], created_at=now())
    db.save_session(session)
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    provider.edit_image = AsyncMock(side_effect=AppError("PROVIDER_UNAVAILABLE", "Image unavailable"))
    moderation = Moderation(settings, provider)
    moderation.screen = AsyncMock()
    images = Images(db, live, provider, moderation, garment_references)
    with pytest.raises(AppError, match="confirm image generation"):
        await images.create(session, uuid4(), session.selected_variant_ids)
    job = await images.create(session, uuid4(), session.selected_variant_ids, explicit=True)
    await __import__("asyncio").gather(*images.tasks)
    assert images.get(session.session_id, job["job_id"])["status"] == "failed"
    assert db.session(session.session_id).selected_variant_ids == ["J01-Black-M"]
    provider.edit_image = AsyncMock(return_value=fixture_png())
    second = await images.create(session, uuid4(), session.selected_variant_ids, explicit=True)
    await __import__("asyncio").gather(*images.tasks)
    assert second["status"] == "completed"
