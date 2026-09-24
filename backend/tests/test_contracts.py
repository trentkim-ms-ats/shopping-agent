import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_retrieval import intent

from app.agent import Agent, tool_specs
from app.config import ROOT, Settings
from app.db import now
from app.errors import AppError
from app.moderation import Moderation
from app.provider import Provider
from app.retrieval import Retrieval
from app.schemas import AgentReply, Intent, Session
from app.tools import Tools


def test_strict_model_schemas_and_small_ts_contract():
    for spec in tool_specs():
        schema = spec["parameters"]
        assert schema["additionalProperties"] is False
        assert set(schema.get("required", [])) == set(schema["properties"])
        for model in schema.get("$defs", {}).values():
            assert model["additionalProperties"] is False
            assert set(model.get("required", [])) == set(model["properties"])
    text = (ROOT / "frontend/lib/types.ts").read_text()
    for model in (Intent, AgentReply):
        for field in model.model_fields:
            assert field + ":" in text


def test_live_config_rejects_missing_models_and_key():
    with pytest.raises(RuntimeError, match="OPENAI"):
        Settings(_env_file=None, demo_mode="live", openai_api_key="").require_live_config()
    with pytest.raises(RuntimeError, match="OPENAI_JUDGE_MODEL"):
        Settings(_env_file=None, demo_mode="live", openai_api_key="test-key",
                 openai_judge_model="").require_live_config()


class Item:
    def __init__(self, **fields):
        self.__dict__.update(fields)

    def model_dump(self, **kwargs):
        return self.__dict__


async def test_real_responses_tool_loop_preserves_call_ids_and_store_false(settings, db):
    live = settings.model_copy(update={"demo_mode": "live", "openai_agent_model": "test-model"})
    provider = Provider(settings)
    call = Item(type="function_call", call_id="call-123", name="search_products",
                arguments=json.dumps({"intent": intent().model_dump(), "finish_turn": False}), id="fc_123")
    reply = AgentReply(kind="results", message="Here are matches.", choices=[], product_ids=[],
                       evidence_refs=[], job_id=None)
    response1 = SimpleNamespace(output=[call], output_text="")
    tools = Tools(db, Retrieval(db, settings, provider), None)
    result = await tools.retrieval.search(intent(), __import__("app.enrichment", fromlist=["profiles"]).profiles()["alex"])
    reply.product_ids = [p["product_id"] for p in result["results"]]
    response2 = SimpleNamespace(output=[], output_text=reply.model_dump_json())
    create = AsyncMock(side_effect=[response1, response2])
    provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    moderation = Moderation(settings, provider)
    session = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                      last_result_ids=[], selected_variant_ids=[], clarification_asked=False, messages=[], created_at=now())
    result = await Agent(live, provider, moderation, tools).turn(session, "Light rain hiking jacket", uuid4())
    assert len(result["cards"]) == 3
    assert create.await_count == 2
    for request in create.await_args_list:
        assert "get_customer_context" not in {tool["name"] for tool in request.kwargs["tools"]}
        assert "get_customer_context" not in request.kwargs["instructions"]
    context = json.loads(create.await_args_list[0].kwargs["input"][0]["content"])
    assert context["profile"]["profile_id"] == "alex"
    assert context["profile"]["preferred_size"] == "M"
    assert context["intent"] == intent().model_dump()
    assert [entry["tool"] for entry in result["tool_events"]] == ["search_products"]
    assert all(c.kwargs["store"] is False for c in create.await_args_list)
    assert all(c.kwargs["reasoning"] == {"effort": live.openai_agent_reasoning_effort}
               for c in create.await_args_list)
    inputs = create.await_args_list[-1].kwargs["input"]
    assert any(i.get("type") == "function_call_output" and i["call_id"] == "call-123" for i in inputs)
    assert any(i.get("type") == "function_call" for i in inputs)


def test_invented_reply_ids_evidence_reordered_cards_rejected(settings, db):
    agent = Agent(settings, Provider(settings), None, None)
    data = {"search_products": {"results": [{"product_id": "J01", "reasons": []}, {"product_id": "J02", "reasons": []}]}}
    for ids, refs in [(["J99"], []), (["J02", "J01"], []), (["J01", "J02"], ["invented"])]:
        reply = AgentReply(kind="results", message="x", choices=[], product_ids=ids, evidence_refs=refs, job_id=None)
        with pytest.raises(ValueError):
            agent.validate_reply(reply, data)


async def test_four_model_calls_bounded(settings, db):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    call = Item(type="function_call", call_id="search", name="search_products",
                arguments=json.dumps({"intent": intent().model_dump(), "finish_turn": False}))
    provider.client = SimpleNamespace(responses=SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(output=[call], output_text=""))))
    session = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                      last_result_ids=[], selected_variant_ids=[], clarification_asked=False, messages=[], created_at=now())
    tools = Tools(db, Retrieval(db, settings, provider), None)
    with pytest.raises(AppError) as exc:
        await Agent(live, provider, None, tools).turn(session, "hiking", uuid4())
    assert exc.value.code == "TURN_LIMIT"
    assert provider.client.responses.create.await_count == 4


async def test_live_context_refreshes_each_turn_and_stays_session_scoped(settings):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    reply = AgentReply(kind="status", message="How can I help?", choices=[], product_ids=[],
                       evidence_refs=[], job_id=None)
    create = AsyncMock(return_value=SimpleNamespace(output=[], output_text=reply.model_dump_json()))
    provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    moderation = SimpleNamespace(screen=AsyncMock())
    agent = Agent(live, provider, moderation, Tools(None, None, None))
    session = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                      last_result_ids=[], selected_variant_ids=[], clarification_asked=False, messages=[], created_at=now())
    await agent.turn(session, "Hi", uuid4())
    session.intent.max_price_cents = 10000
    session.intent.size = "L"
    session.intent_sources = {"max_price_cents": "user", "size": "user"}
    session.selected_variant_ids = ["J01-Black-L"]
    session.last_result_ids = ["J01", "J02"]
    session.clarification_asked = True
    await agent.turn(session, "What have I selected?", uuid4())
    other = session.model_copy(deep=True, update={
        "session_id": uuid4(), "profile_id": "sam", "intent": intent(), "intent_sources": {},
        "selected_variant_ids": [], "last_result_ids": [], "clarification_asked": False, "messages": [],
    })
    await agent.turn(other, "Hi", uuid4())

    initial, updated, separate = [
        json.loads(call.kwargs["input"][0]["content"]) for call in create.await_args_list
    ]
    assert initial["intent"]["max_price_cents"] == intent().max_price_cents
    assert initial["selected_variant_ids"] == []
    assert updated["profile"] == initial["profile"]
    assert updated["intent"]["max_price_cents"] == 10000
    assert updated["intent"]["size"] == "L"
    assert updated["intent_sources"] == {"max_price_cents": "user", "size": "user"}
    assert updated["selected_variant_ids"] == ["J01-Black-L"]
    assert updated["last_result_ids"] == ["J01", "J02"]
    assert updated["clarification_asked"] is True
    assert separate["profile"]["profile_id"] == "sam"
    assert separate["profile"]["budget_cents"] == 15000
    assert separate["selected_variant_ids"] == []
    assert separate["last_result_ids"] == []
    assert separate["clarification_asked"] is False
    assert moderation.screen.await_count == 3


@pytest.mark.parametrize("priority,expected_kind", [(None, "clarify"), ("lightweight", "results")])
async def test_standalone_search_needs_one_model_call_and_screens_displayed_content(settings, db, priority, expected_kind):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    filters = intent(priority=priority)
    call = Item(type="function_call", call_id="search", name="search_products",
                arguments=json.dumps({"intent": filters.model_dump(), "finish_turn": True}))
    create = AsyncMock(return_value=SimpleNamespace(output=[call], output_text=""))
    provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    tools = Tools(db, Retrieval(db, settings, provider), None)
    moderation = SimpleNamespace(screen=AsyncMock())
    session = Session(session_id=uuid4(), profile_id="alex", intent=filters, intent_sources={},
                      last_result_ids=[], selected_variant_ids=[], clarification_asked=False, messages=[], created_at=now())
    result = await Agent(live, provider, moderation, tools).turn(session, "Hiking jacket", uuid4())
    assert result["reply"]["kind"] == expected_kind
    assert create.await_count == 1
    assert result["reply"]["product_ids"] == [c["product_id"] for c in result["cards"]]
    screened = json.loads(moderation.screen.await_args.args[0])
    assert screened["reply"] == result["reply"]
    assert screened["cards"] == result["cards"]
    assert moderation.screen.await_args.args[1] == "chat_output"
    assert len(session.messages) == 2


async def test_live_comparison_is_unavailable_and_not_offered_as_a_tool(settings, db):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    tools = Tools(db, Retrieval(db, settings, provider), None)
    session = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                      last_result_ids=[], selected_variant_ids=[], clarification_asked=False, messages=[], created_at=now())
    await tools.search(session, session.intent)
    before = session.model_copy(deep=True)
    reply = AgentReply(kind="comparison_unavailable", message="Here is the comparison.", choices=[],
                       product_ids=[], evidence_refs=[], job_id=None)
    create = AsyncMock(return_value=SimpleNamespace(output=[], output_text=reply.model_dump_json()))
    provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    moderation = SimpleNamespace(screen=AsyncMock())
    agent = Agent(live, provider, moderation, tools)
    result = await agent.turn(session, "Compare and choose the first.", uuid4())
    assert create.await_count == 1
    assert "compare_products" not in {tool["name"] for tool in create.await_args.kwargs["tools"]}
    assert "there are no selection buttons" not in create.await_args.kwargs["instructions"]
    assert "buttons that send ordinal chat requests" in create.await_args.kwargs["instructions"]
    assert result["reply"]["kind"] == "comparison_unavailable"
    assert "not available in this demo" in result["reply"]["message"]
    assert result["comparison"] is None and result["tool_events"] == []
    assert session.selected_variant_ids == before.selected_variant_ids
    assert session.last_result_ids == before.last_result_ids
    assert json.loads(moderation.screen.await_args.args[0])["reply"] == result["reply"]
    with pytest.raises(ValueError, match="matching visible result"):
        agent.validate_reply(reply, {"select_items": {"product_ids": []}})


@pytest.mark.parametrize("kind", ["results", "status"])
def test_normal_replies_never_invite_unavailable_comparisons(kind):
    reply = AgentReply(kind=kind, message="", choices=[], product_ids=[], evidence_refs=[], job_id=None)
    assert "compare" not in Agent.display_reply(reply, {}).message


async def test_fast_reply_still_blocks_unsafe_output(settings, db):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    call = Item(type="function_call", call_id="search", name="search_products",
                arguments=json.dumps({"intent": intent().model_dump(), "finish_turn": True}))
    provider.client = SimpleNamespace(responses=SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(output=[call], output_text=""))))
    session = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                      last_result_ids=[], selected_variant_ids=[], clarification_asked=False, messages=[], created_at=now())
    moderation = SimpleNamespace(screen=AsyncMock(side_effect=AppError("CONTENT_BLOCKED", "Blocked", 400, False)))
    with pytest.raises(AppError, match="Blocked"):
        await Agent(live, provider, moderation, Tools(db, Retrieval(db, settings, provider), None)).turn(
            session, "hiking", uuid4())
    assert provider.client.responses.create.await_count == 1
    assert session.messages == []


async def test_fast_path_repairs_invalid_tool_arguments_before_returning(settings, db):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    calls = [Item(type="function_call", call_id="bad", name="search_products",
                  arguments=json.dumps({"intent": {"invented": True}, "finish_turn": True})),
             Item(type="function_call", call_id="fixed", name="search_products",
                  arguments=json.dumps({"intent": intent().model_dump(), "finish_turn": True}))]
    create = AsyncMock(side_effect=[SimpleNamespace(output=[c], output_text="") for c in calls])
    provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    session = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                      last_result_ids=[], selected_variant_ids=[], clarification_asked=False, messages=[], created_at=now())
    result = await Agent(live, provider, SimpleNamespace(screen=AsyncMock()),
                         Tools(db, Retrieval(db, settings, provider), None)).turn(session, "hiking", uuid4())
    assert create.await_count == 2
    assert result["reply"]["kind"] == "results"
    assert result["tool_events"] == [{"tool": "search_products", "ok": False}, {"tool": "search_products", "ok": True}]
