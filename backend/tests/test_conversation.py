"""The shopper decides everything in chat: selection, confirmation, preview and feedback."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agent import Agent
from app.config import Settings
from app.schemas import AgentReply


def say(client, session, text):
    return client.post(f"/api/sessions/{session}/messages",
                       json={"request_id": str(uuid4()), "text": text})


@pytest.fixture
def agent(settings):
    return Agent(settings, SimpleNamespace(), SimpleNamespace(), SimpleNamespace())


def conversational_session(client, session):
    assert say(client, session, "Lightweight hiking jacket").status_code == 200
    return say(client, session, "Choose the first one")


def test_selection_happens_in_conversation_and_returns_the_selected_items(client, session):
    response = conversational_session(client, session)
    assert response.status_code == 200
    body = response.json()
    assert body["reply"]["kind"] == "selection"
    assert body["reply"]["product_ids"] == [item["product_id"] for item in body["selected"]]
    assert len(body["selected"]) == 1
    assert body["selection_state"]["items"][0]["variant_id"] == body["selected"][0]["variant"]["variant_id"]
    assert body["reply"]["choices"], "the reply offers conversational next steps"


def test_confirmation_preview_and_feedback_are_driven_by_chat(client, session):
    conversational_session(client, session)
    confirmed = say(client, session, "Save this to the demo cart").json()
    assert confirmed["reply"]["kind"] == "confirmed"
    assert confirmed["reply"]["product_ids"] == []
    assert confirmed["selection_state"]["confirmed"] is True

    preview = say(client, session, "Show the try-on preview").json()
    assert preview["reply"]["kind"] == "preview"
    assert preview["job"]["job_id"] == preview["reply"]["job_id"]

    feedback = say(client, session, "Yes, that helped").json()
    assert feedback["reply"]["kind"] == "feedback"
    assert feedback["selection_state"]["feedback_recorded"] is True


def test_complements_are_requested_in_conversation(client, session):
    conversational_session(client, session)
    body = say(client, session, "Complete my outfit").json()
    assert body["reply"]["kind"] == "complements"
    assert body["complements"]
    assert body["reply"]["product_ids"] == [card["product_id"] for card in body["complements"]]


def test_offered_options_expose_every_shown_variant_for_ordinals(client, session):
    say(client, session, "Lightweight hiking jacket")
    body = say(client, session, "Choose the second one").json()
    assert body["reply"]["kind"] == "selection"
    assert len(body["selected"]) == 1


def test_short_follow_ups_use_the_small_model_and_new_intent_uses_the_reasoning_model(agent, settings):
    session = SimpleNamespace(last_result_ids=["p1"], selected_variant_ids=[])
    assert agent.route("Choose the first one", session) == (
        settings.openai_router_model, settings.openai_router_reasoning_effort, "light")
    fresh = SimpleNamespace(last_result_ids=[], selected_variant_ids=[])
    assert agent.route("Choose the first one", fresh)[2] == "standard"
    assert agent.route("I need a waterproof shell for fall hiking under two hundred dollars "
                       "with pit zips and a helmet hood", session)[2] == "standard"


def test_a_failed_small_model_turn_escalates_to_the_reasoning_model(agent, settings):
    routing = {"tier": "light", "model": settings.openai_router_model,
               "reasoning_effort": settings.openai_router_reasoning_effort, "escalated": False}
    model, effort, tier, updated = agent.escalate(routing)
    assert (model, effort, tier) == (settings.openai_agent_model,
                                     settings.openai_agent_reasoning_effort, "standard")
    assert updated["escalated"] is True


def test_only_a_preview_reply_may_carry_an_image_job(agent):
    outputs = {"generate_outfit": {"job_id": "job-1"}}
    agent.validate_reply(AgentReply(kind="preview", message="x", choices=[], product_ids=[],
                                    evidence_refs=[], job_id="job-1"), outputs)
    with pytest.raises(ValueError):
        agent.validate_reply(AgentReply(kind="preview", message="x", choices=[], product_ids=[],
                                        evidence_refs=[], job_id="other"), outputs)
    with pytest.raises(ValueError):
        agent.validate_reply(AgentReply(kind="confirmed", message="x", choices=[], product_ids=[],
                                        evidence_refs=[], job_id="job-1"),
                             {"confirm_selection": {"selection_state": {}}})


def test_the_router_model_is_configured_and_reported(settings: Settings):
    assert settings.models()["openai_router_model"] == settings.openai_router_model
    assert settings.openai_router_model != settings.openai_agent_model
