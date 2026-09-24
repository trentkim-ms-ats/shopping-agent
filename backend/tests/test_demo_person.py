import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_retrieval import intent
from test_try_on import photo_bytes, select, wait_job

from app.db import now
from app.demo_person import load_demo_person
from app.errors import AppError
from app.images import Images
from app.moderation import Moderation
from app.provider import Provider
from app.schemas import Session


def test_fixed_photo_get_does_not_generate_and_survives_preview_removal(client, session):
    url = "/api/demo/sample-person.png"
    photo = client.get(url)
    assert photo.status_code == 200 and photo.content == load_demo_person()
    assert "public" in photo.headers["cache-control"]
    assert client.app.state.db.jobs(session) == []
    select(client, session)
    body = {"request_id": str(uuid4()), "variant_ids": ["J01-Black-M"]}
    route = f"/api/sessions/{session}/try-ons/demo"
    result = client.post(route, json=body)
    assert result.status_code == 202
    job = wait_job(client, session, result.json()["job_id"])
    assert job["kind"] == "try_on" and job["fixed_sample"] and job["sample_job_id"] is None
    assert job["status"] == "completed"
    assert client.post(route, json=body).json()["job_id"] == job["job_id"]
    assert client.post(route, json={**body, "photo_base64": "untrusted"}).status_code == 422
    assert client.delete(f"/api/sessions/{session}/try-ons").status_code == 200
    assert client.get(job["image_url"]).status_code == 404
    assert client.get(url).content == photo.content
    assert len(client.app.state.db.jobs(session)) == 1


@pytest.mark.parametrize("corrupt", [False, True])
def test_unavailable_fixed_asset_is_explicit_error_without_generation(client, monkeypatch, tmp_path, corrupt):
    path = tmp_path / "sample.png"
    if corrupt:
        path.write_bytes(b"not the approved demo image")
    monkeypatch.setattr("app.demo_person.DEMO_PERSON", path)
    result = client.get("/api/demo/sample-person.png")
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "DEMO_PERSON_UNAVAILABLE"
    with pytest.raises(AppError):
        load_demo_person()


async def test_live_fixed_photo_is_reused_without_generations(settings, db, garment_references):
    state = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                    selected_variant_ids=["J01-Black-M"], last_result_ids=[], clarification_asked=True,
                    messages=[], created_at=now())
    db.save_session(state)
    provider = Provider(settings)
    provider.image = AsyncMock(side_effect=AssertionError("Must not generate another person"))
    provider.edit_image = AsyncMock(return_value=photo_bytes())
    moderation = Moderation(settings, provider)
    images = Images(db, settings.model_copy(update={"demo_mode": "live"}), provider, moderation, garment_references)
    try:
        for _ in range(2):
            job = await images.create(state, uuid4(), state.selected_variant_ids, explicit=True, fixed_sample=True)
            await asyncio.gather(*images.tasks)
            assert job["status"] == "completed"
            assert provider.edit_image.await_args.args[1] == load_demo_person()
            assert provider.edit_image.await_args.kwargs["references"] == [garment_references.references(["J01-Black-M"])[0]["data"]]
        assert provider.edit_image.await_count == 2
        provider.image.assert_not_called()
        assert all(j["kind"] == "try_on" for j in db.jobs(state.session_id))
    finally:
        await images.close()


async def test_daily_cap_prevents_try_on_provider_call(settings, db, garment_references):
    state = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                    selected_variant_ids=["J01-Black-M"], last_result_ids=[], clarification_asked=True,
                    messages=[], created_at=now())
    db.save_session(state)
    provider = Provider(settings)
    provider.edit_image = AsyncMock(side_effect=AssertionError("Daily limit must prevent image calls"))
    provider.image = AsyncMock(side_effect=AssertionError("Must not generate another person"))
    images = Images(db, settings.model_copy(update={"demo_mode": "live", "daily_image_call_limit": 0}),
                    provider, Moderation(settings, provider), garment_references)
    try:
        job = await images.create(state, uuid4(), state.selected_variant_ids, explicit=True, fixed_sample=True)
        await asyncio.gather(*images.tasks)
        assert job["status"] == "failed" and job["error"]["code"] == "DAILY_IMAGE_LIMIT"
        provider.edit_image.assert_not_called()
        provider.image.assert_not_called()
    finally:
        await images.close()
