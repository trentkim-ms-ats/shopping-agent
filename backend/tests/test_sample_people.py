import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_try_on import photo_bytes, select, wait_job

from app.errors import AppError
from app.images import Images
from app.moderation import Moderation
from app.photos import normalize_image
from app.provider import Provider


def create_sample(client, session):
    response = client.post(f"/api/sessions/{session}/sample-people", json={"request_id": str(uuid4())})
    assert response.status_code == 202
    return wait_job(client, session, response.json()["job_id"])


def test_sample_api_edit_delete_and_no_upload(client, session, settings):
    select(client, session)
    request = {"request_id": str(uuid4())}
    route = f"/api/sessions/{session}/sample-people"
    created = client.post(route, json=request)
    assert created.status_code == 202 and created.headers["cache-control"] == "no-store"
    sample = wait_job(client, session, created.json()["job_id"])
    assert sample["kind"] == "sample_person" and sample["status"] == "completed"
    assert sample["variant_ids"] == [] and sample["consent_version"] is None
    assert client.post(route, json=request).json()["job_id"] == sample["job_id"]
    assert client.get(sample["image_url"]).status_code == 200
    assert client.get(f"/api/media/{sample['media_id']}.png").status_code == 404
    body = {"request_id": str(uuid4()), "variant_ids": ["J01-Black-M"], "sample_job_id": sample["job_id"]}
    response = client.post(f"/api/sessions/{session}/try-ons/sample", json=body)
    assert response.status_code == 202
    result = wait_job(client, session, response.json()["job_id"])
    assert result["status"] == "completed" and result["kind"] == "try_on"
    assert result["sample_job_id"] == sample["job_id"] and not result["cached"]
    assert client.post(f"/api/sessions/{session}/try-ons/sample", json=body).json()["job_id"] == result["job_id"]
    assert not list(settings.image_dir.glob("*.png"))
    assert client.delete(f"/api/sessions/{session}/try-ons").json()["removed"] == 2
    assert client.get(sample["image_url"]).status_code == 404
    assert client.get(result["image_url"]).status_code == 404
    assert client.app.state.db.session(session).selected_variant_ids == ["J01-Black-M"]


def test_samples_reject_wrong_session_concepts_and_expired_sources(client, session, db, settings):
    select(client, session)
    sample = create_sample(client, session)
    other = client.post("/api/sessions", json={"profile_id": "sam"}).json()["session_id"]
    select(client, other)
    body = {"request_id": str(uuid4()), "variant_ids": ["J01-Black-M"], "sample_job_id": sample["job_id"]}
    assert client.post(f"/api/sessions/{other}/try-ons/sample", json=body).status_code == 404
    concept = client.post(f"/api/sessions/{session}/outfits",
                          json={"request_id": str(uuid4()), "variant_ids": ["J01-Black-M"]}).json()
    wait_job(client, session, concept["job_id"])
    invalid = {**body, "sample_job_id": concept["job_id"]}
    assert client.post(f"/api/sessions/{session}/try-ons/sample", json=invalid).status_code == 409
    sample["expires_at"] = "2000-01-01T00:00:00+00:00"
    db.save_job(sample)
    assert client.post(f"/api/sessions/{session}/try-ons/sample", json=body).status_code == 409
    fresh = create_sample(client, session)
    restarted = Images(db, settings, Provider(settings), client.app.state.moderation)
    assert restarted.get(session, fresh["job_id"])["status"] == "failed"
    with pytest.raises(AppError):
        restarted.private_media(session, fresh["job_id"])


async def test_live_sample_generates_then_edits_exact_sanitized_image(settings, db, garment_references):
    from test_retrieval import intent

    from app.db import now
    from app.schemas import Session

    state = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                    selected_variant_ids=["J01-Black-M"], last_result_ids=[], clarification_asked=True,
                    messages=[], created_at=now())
    db.save_session(state)
    provider = Provider(settings)
    provider.image = AsyncMock(return_value=photo_bytes())
    provider.edit_image = AsyncMock(return_value=photo_bytes(color="green"))
    moderation = Moderation(settings, provider)
    moderation.screen = AsyncMock()
    images = Images(db, settings.model_copy(update={"demo_mode": "live"}), provider, moderation, garment_references)
    try:
        sample = await images.create(state, uuid4(), [], explicit=True, sample_person=True)
        await asyncio.gather(*images.tasks)
        provider.image.assert_awaited_once()
        assert "entirely fictional adult" in provider.image.await_args.args[0]
        provider.edit_image.assert_not_called()
        edited = await images.create(state, uuid4(), state.selected_variant_ids, explicit=True,
                                     sample_job_id=sample["job_id"])
        await asyncio.gather(*images.tasks)
        provider.edit_image.assert_awaited_once()
        assert provider.edit_image.await_args.args[1] == normalize_image(photo_bytes())
        assert images.private_media(state.session_id, edited["job_id"]) == normalize_image(photo_bytes(color="green"))
        assert [call.args[1] for call in moderation.screen.await_args_list] == [
            "image_prompt", "try_on_photo", "try_on_photo", "image_prompt", "try_on_photo",
        ]
        assert not list(settings.image_dir.glob("*.png"))
    finally:
        await images.close()


@pytest.mark.parametrize("stage", ["image_prompt", "try_on_photo"])
def test_sample_safety_gates_fail_closed(client, session, stage):
    async def screen(text, actual_stage, request_id):
        if actual_stage == stage:
            raise AppError("CONTENT_BLOCKED", "Sample screening blocked.", 400, False)
    client.app.state.moderation.screen = screen
    response = client.post(f"/api/sessions/{session}/sample-people", json={"request_id": str(uuid4())})
    if stage == "image_prompt":
        assert response.status_code == 400
        assert client.app.state.db.jobs(session) == []
    else:
        assert response.status_code == 202
        job = wait_job(client, session, response.json()["job_id"])
        assert job["status"] == "failed" and job["image_url"] is None
        assert job["error"]["code"] == "CONTENT_BLOCKED"
    assert client.app.state.images.private_images == {}


def test_sample_request_has_no_user_prompt_or_photo_and_shares_limit(client, session):
    route = f"/api/sessions/{session}/sample-people"
    assert client.post(route, json={"request_id": str(uuid4()), "prompt": "override"}).status_code == 422
    assert client.post(route, json={"request_id": str(uuid4()), "photo_base64": "not allowed"}).status_code == 422
    for _ in range(5):
        assert create_sample(client, session)["status"] == "completed"
    result = client.post(route, json={"request_id": str(uuid4())})
    assert result.status_code == 429 and result.json()["error"]["code"] == "IMAGE_LIMIT"
