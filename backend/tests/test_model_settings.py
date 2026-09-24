import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.cli import adversarial_test, preflight
from app.config import ROOT, Settings
from app.enrichment import enrich
from app.images import Images, fixture_png
from app.provider import Provider
from app.schemas import AgentReply, AttributeJudgment, CandidateSet, JudgeOutput


@pytest.fixture
def clean_model_env(monkeypatch):
    for name in Settings.model_fields:
        if name.startswith("openai_") or name == "demo_mode":
            monkeypatch.delenv(name.upper(), raising=False)
            monkeypatch.delenv(name, raising=False)


def test_model_defaults_match_example(clean_model_env):
    defaults = Settings(_env_file=None)
    configured = Settings(_env_file=ROOT / ".env.example")
    assert configured.models() == defaults.models()
    for role in ("agent", "enrich", "judge"):
        field = f"openai_{role}_reasoning_effort"
        assert getattr(configured, field) == getattr(defaults, field)
    assert configured.openai_image_quality == "medium"
    assert defaults.openai_agent_model == defaults.openai_enrich_model == "gpt-5.6-terra"
    assert defaults.openai_judge_model == "gpt-6-astra"
    assert defaults.openai_image_model == "gpt-image-2.5-flare"


def test_environment_overrides_dotenv(monkeypatch, tmp_path, clean_model_env):
    env = tmp_path / ".env"
    env.write_text("OPENAI_AGENT_REASONING_EFFORT=low\nOPENAI_IMAGE_QUALITY=medium\n")
    monkeypatch.setenv("OPENAI_AGENT_REASONING_EFFORT", "high")
    monkeypatch.setenv("OPENAI_ENRICH_REASONING_EFFORT", "medium")
    monkeypatch.setenv("OPENAI_JUDGE_REASONING_EFFORT", "max")
    monkeypatch.setenv("OPENAI_IMAGE_QUALITY", "high")
    settings = Settings(_env_file=env)
    assert settings.openai_agent_reasoning_effort == "high"
    assert settings.openai_enrich_reasoning_effort == "medium"
    assert settings.openai_judge_reasoning_effort == "max"
    assert settings.openai_image_quality == "high"


@pytest.mark.parametrize("field", [
    "openai_agent_reasoning_effort", "openai_enrich_reasoning_effort",
    "openai_judge_reasoning_effort", "openai_image_quality",
])
def test_invalid_generation_settings_rejected(field, clean_model_env):
    with pytest.raises(ValidationError, match=field):
        Settings(_env_file=None, **{field: "invalid"})


@pytest.mark.parametrize("role", ["agent", "enrich", "judge"])
def test_astra_requires_reasoning(role, clean_model_env):
    with pytest.raises(ValidationError, match="requires low or higher"):
        Settings(_env_file=None, **{
            f"openai_{role}_model": "gpt-6-astra", f"openai_{role}_reasoning_effort": "none",
        })


@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
async def test_structured_adapter_sends_effort(settings, effort):
    provider = Provider(settings)
    output = CandidateSet(product_id="J01", attributes=[])
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=output))
    provider.client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    assert await provider.structured(
        "gpt-6-astra", "Extract", "{}", CandidateSet, reasoning_effort=effort,
    ) == output
    assert parse.await_args.kwargs["reasoning"] == {"effort": effort}
    assert parse.await_args.kwargs["store"] is False


@pytest.mark.parametrize("quality", ["auto", "low", "medium", "high", "xhigh", "max"])
async def test_image_generation_and_edit_send_quality(settings, quality):
    settings = settings.model_copy(update={"openai_image_quality": quality})
    provider = Provider(settings)
    png = fixture_png()
    result = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png).decode())])
    generate, edit = AsyncMock(return_value=result), AsyncMock(return_value=result)
    provider.client = SimpleNamespace(images=SimpleNamespace(generate=generate, edit=edit))
    assert await provider.image("concept") == png
    assert await provider.edit_image("try on", png) == png
    for operation in (generate, edit):
        kwargs = operation.await_args.kwargs
        assert kwargs["model"] == "gpt-image-2.5-flare"
        assert kwargs["quality"] == quality
        assert kwargs["size"] == "1024x1024" and kwargs["output_format"] == "png"


async def test_enrichment_routes_effort_and_invalidates_live_cache(settings, db):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)

    async def structured(model, prompt, data, schema, **kwargs):
        if schema is CandidateSet:
            assert model == live.openai_enrich_model
            assert kwargs["reasoning_effort"] == live.openai_enrich_reasoning_effort
            return CandidateSet(product_id=json.loads(data)["product_id"], attributes=[])
        assert model == live.openai_judge_model
        assert kwargs["reasoning_effort"] == live.openai_judge_reasoning_effort
        return JudgeOutput(judgments=[])

    provider.structured = AsyncMock(side_effect=structured)
    await enrich(db, live, provider)
    assert provider.structured.await_count == 2 * len(db.catalog()[1])
    original_ids = [p["enriched"]["validation_run_id"] for p in db.catalog()[1]]
    provider.structured.reset_mock()
    await enrich(db, live, provider)
    provider.structured.assert_not_awaited()
    for field in ("openai_enrich_reasoning_effort", "openai_judge_reasoning_effort"):
        live = live.model_copy(update={field: "high"})
        await enrich(db, live, provider)
        assert provider.structured.await_count == 2 * len(db.catalog()[1])
        assert [p["enriched"]["validation_run_id"] for p in db.catalog()[1]] != original_ids
        original_ids = [p["enriched"]["validation_run_id"] for p in db.catalog()[1]]
        provider.structured.reset_mock()


@pytest.mark.parametrize("kind", ["concept", "try_on"])
def test_image_quality_changes_cache_key(settings, db, kind):
    images = Images(db, settings, Provider(settings), None)
    prompt, key = images.prompt_and_key(["J01-Black-M"], kind)
    images.settings = settings.model_copy(update={"openai_image_quality": "high"})
    new_prompt, new_key = images.prompt_and_key(["J01-Black-M"], kind)
    assert new_prompt == prompt and new_key != key


async def test_adversarial_judge_uses_configured_effort(settings, db):
    live = settings.model_copy(update={"demo_mode": "live", "openai_judge_reasoning_effort": "high"})

    async def structured(model, prompt, data, schema, **kwargs):
        assert model == live.openai_judge_model
        assert kwargs["reasoning_effort"] == "high"
        return JudgeOutput(judgments=[
            AttributeJudgment(attribute_id=a["attribute_id"], decision="reject",
                              support="unsupported", evidence=[], reason="Unsupported.")
            for a in json.loads(data)["candidates"]["attributes"]
        ])

    provider = SimpleNamespace(structured=structured)
    assert (await adversarial_test(db, live, provider))["passed"]


async def test_smoke_uses_agent_effort(settings, monkeypatch):
    live = settings.model_copy(update={"demo_mode": "live", "openai_api_key": "test-key",
                                      "openai_agent_reasoning_effort": "high"})
    reply = AgentReply(kind="status", message="Hello", choices=[], product_ids=[], evidence_refs=[], job_id=None)
    provider = SimpleNamespace(
        client=SimpleNamespace(models=SimpleNamespace(retrieve=AsyncMock())),
        invoke=AsyncMock(), structured=AsyncMock(return_value=reply),
        embeddings=AsyncMock(return_value=[[1.0, 0.0]]),
    )
    monkeypatch.setattr("app.cli.Moderation.screen", AsyncMock())
    monkeypatch.setattr("app.cli.adversarial_test", AsyncMock())
    await preflight(live, provider, smoke=True)
    assert provider.structured.await_args.args[0] == live.openai_agent_model
    assert provider.structured.await_args.kwargs["reasoning_effort"] == "high"
