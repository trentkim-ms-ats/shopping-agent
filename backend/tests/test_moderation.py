from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.errors import AppError
from app.moderation import Moderation
from app.provider import Provider


def response(flagged=False):
    return SimpleNamespace(id="mod-test", results=[SimpleNamespace(
        flagged=flagged,
        categories=SimpleNamespace(model_dump=lambda: {"violence": flagged}),
        category_scores=SimpleNamespace(model_dump=lambda: {"violence": .9 if flagged else .001}),
    )])


@pytest.mark.parametrize("stage", ["user_input", "chat_output", "image_prompt"])
@pytest.mark.parametrize("flagged", [False, True])
async def test_real_adapter_moderation_gates(settings, stage, flagged):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    provider.client = SimpleNamespace(moderations=SimpleNamespace(create=AsyncMock(return_value=response(flagged))))
    moderation = Moderation(live, provider)
    if flagged:
        with pytest.raises(AppError) as exc:
            await moderation.screen("hiking", stage, "request-test")
        assert exc.value.code == "CONTENT_BLOCKED"
    else:
        result = await moderation.screen("hiking", stage, "request-test")
        assert result.decision == "allow" and result.provider_id == "mod-test"
    provider.client.moderations.create.assert_awaited_once_with(model=live.openai_moderation_model, input="hiking")


@pytest.mark.parametrize("value", [SimpleNamespace(results=[]), SimpleNamespace(results=[None]), response("false")])
async def test_malformed_moderation_fails_closed(settings, value):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    provider.client = SimpleNamespace(moderations=SimpleNamespace(create=AsyncMock(return_value=value)))
    with pytest.raises(AppError) as exc:
        await Moderation(live, provider).screen("hiking", "user_input", "test")
    assert exc.value.code == "MODERATION_UNAVAILABLE"


async def test_timeout_one_retry_then_closed(settings, caplog):
    import json
    import logging

    caplog.set_level(logging.INFO)
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    provider.client = SimpleNamespace(moderations=SimpleNamespace(create=AsyncMock(side_effect=TimeoutError)))
    with pytest.raises(AppError) as exc:
        await Moderation(live, provider).screen("hiking", "image_prompt", "test")
    assert exc.value.code == "MODERATION_UNAVAILABLE"
    assert provider.client.moderations.create.await_count == 2
    events = [json.loads(r.message) for r in caplog.records if r.message.startswith("{")]
    failures = [e for e in events if e["event"] == "moderation_call"]
    assert len(failures) == 2
    assert [e["retrying"] for e in failures] == [True, False]
    assert all(e["request_id"] == "test" and e["stage"] == "image_prompt" for e in failures)
    assert all(e["duration_ms"] >= 0 and e["timeout_seconds"] == 5 for e in failures)
    assert failures[0]["retry_delay_ms"] > 0
    assert failures[1]["retry_delay_ms"] == 0
