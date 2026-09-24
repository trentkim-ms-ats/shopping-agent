import asyncio
import base64
import io
import json
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from PIL import Image, PngImagePlugin
from test_retrieval import intent

from app.db import now
from app.errors import AppError
from app.images import TRY_ON_LABEL, Images, fixture_png
from app.moderation import Moderation
from app.photos import MAX_PHOTO_BYTES, decode_photo, normalize_image
from app.provider import Provider
from app.schemas import Session


def photo_bytes(size=(320, 320), format="PNG", color="blue"):
    target = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("private", "PRIVATE_METADATA_MUST_NOT_SURVIVE")
    Image.new("RGB", size, color).save(target, format=format, pnginfo=info)
    return target.getvalue()


def payload(**changes):
    return {"request_id": str(uuid4()), "variant_ids": ["J01-Black-M"],
            "photo_base64": base64.b64encode(photo_bytes()).decode(), "consent": True, **changes}


def select(client, session):
    assert client.post(f"/api/sessions/{session}/selection",
                       json={"variant_ids": ["J01-Black-M"]}).status_code == 200


def wait_job(client, session, job_id):
    for _ in range(60):
        job = client.get(f"/api/sessions/{session}/outfits/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(.025)
    raise AssertionError("Image job did not finish")


def test_normalize_photo_strips_metadata_and_limits_dimensions():
    image = decode_photo(base64.b64encode(photo_bytes((1800, 1200))).decode())
    with Image.open(io.BytesIO(image)) as decoded:
        assert decoded.format == "PNG" and decoded.size == (1536, 1024)
        assert not decoded.info and not decoded.getexif()
    assert b"PRIVATE_METADATA" not in image
    jpeg = normalize_image(photo_bytes(format="JPEG"))
    assert jpeg.startswith(b"\x89PNG")


@pytest.mark.parametrize("data", [
    b"not an image", b"<svg>untrusted</svg>", photo_bytes((255, 320)),
    photo_bytes((4097, 256)), photo_bytes(format="GIF"),
])
def test_invalid_photo_formats_and_dimensions(data):
    with pytest.raises(AppError) as exc:
        normalize_image(data)
    assert exc.value.status == 422


def test_photo_size_limit_and_invalid_base64():
    with pytest.raises(AppError) as exc:
        normalize_image(b"x" * (MAX_PHOTO_BYTES + 1))
    assert exc.value.status == 413
    with pytest.raises(AppError):
        decode_photo("https://example.com/photo.png")


@pytest.mark.parametrize("consent", [False, None, "true", 1])
def test_photo_requires_explicit_boolean_consent(client, session, consent):
    select(client, session)
    screen = AsyncMock()
    client.app.state.moderation.screen = screen
    result = client.post(f"/api/sessions/{session}/try-ons", json=payload(consent=consent))
    assert result.status_code == 422
    screen.assert_not_called()
    assert client.app.state.db.jobs(session) == []


def test_private_lifecycle_no_disk_no_shared_cache_and_ownership(client, session, settings, db, caplog):
    select(client, session)
    body = payload()
    route = f"/api/sessions/{session}/try-ons"
    initial = client.post(route, json=body)
    assert initial.status_code == 202
    job = wait_job(client, session, initial.json()["job_id"])
    assert job["status"] == "completed" and job["kind"] == "try_on"
    assert job["label"] == TRY_ON_LABEL and job["cached"] is False
    assert datetime.fromisoformat(job["expires_at"]).timestamp() > time.time()
    response = client.get(job["image_url"])
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert client.get(f"/api/media/{job['media_id']}.png").status_code == 404
    assert not list(settings.image_dir.glob("*.png"))
    assert body["photo_base64"] not in json.dumps(db.jobs())
    assert body["photo_base64"] not in caplog.text
    assert db.session(session).messages == []
    duplicate = client.post(route, json=body).json()
    assert duplicate["job_id"] == job["job_id"]
    other = client.post("/api/sessions", json={"profile_id": "sam"}).json()["session_id"]
    assert client.get(f"/api/sessions/{other}/outfits/{job['job_id']}/image").status_code == 404
    select(client, other)
    state = client.get(f"/api/sessions/{other}/journey").json()["selection"]
    assert client.post(f"/api/sessions/{other}/selection/confirm", json={
        "revision": state["revision"], "accept_exceptions": True}).status_code == 200
    next_job = client.post(f"/api/sessions/{other}/try-ons", json=payload()).json()
    assert next_job["cached"] is False and next_job["job_id"] != job["job_id"]
    assert client.delete(route).status_code == 200
    assert client.get(job["image_url"]).status_code == 404
    assert client.app.state.db.session(session).selected_variant_ids == ["J01-Black-M"]


def test_private_expiry_and_restart_remove_access(client, session, settings, db):
    select(client, session)
    job = client.post(f"/api/sessions/{session}/try-ons", json=payload()).json()
    job = wait_job(client, session, job["job_id"])
    job["expires_at"] = "2000-01-01T00:00:00+00:00"
    db.save_job(job)
    assert client.get(job["image_url"]).status_code == 404
    assert client.app.state.images.private_images == {}
    second = client.post(f"/api/sessions/{session}/try-ons", json=payload()).json()
    second = wait_job(client, session, second["job_id"])
    restarted = Images(db, settings, Provider(settings), client.app.state.moderation)
    assert restarted.get(session, second["job_id"])["error"]["code"] == "PROCESS_RESTARTED"
    with pytest.raises(AppError):
        restarted.private_media(session, second["job_id"])


@pytest.mark.parametrize("stage,code,status", [
    ("try_on_photo", "CONTENT_BLOCKED", 400),
    ("image_prompt", "CONTENT_BLOCKED", 400),
    ("try_on_photo", "MODERATION_UNAVAILABLE", 503),
])
def test_photo_and_prompt_gates_cannot_be_bypassed(client, session, stage, code, status):
    select(client, session)
    async def screen(text, actual_stage, request_id):
        if actual_stage == stage:
            raise AppError(code, "Screening stopped this request.", status)
    client.app.state.moderation.screen = screen
    result = client.post(f"/api/sessions/{session}/try-ons", json=payload())
    assert result.status_code == status
    assert client.app.state.db.jobs(session) == []
    assert client.app.state.images.private_images == {}
    assert client.app.state.db.session(session).selected_variant_ids == ["J01-Black-M"]


def test_bounded_request_and_schema_do_not_echo_photo(client, session):
    select(client, session)
    route = f"/api/sessions/{session}/try-ons"
    result = client.post(route, content=b"x" * (7 * 1024 * 1024 + 1),
                         headers={"Content-Type": "application/json"})
    assert result.status_code == 413
    result = client.post(route, json=payload(photo_base64="PRIVATE_INVALID_DATA"))
    assert result.status_code == 422 and "PRIVATE_INVALID_DATA" not in result.text
    assert client.post(route, content="{}").status_code == 415


async def test_edit_adapter_passes_bytes_to_images_edits(settings):
    provider = Provider(settings)
    result = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(fixture_png()).decode())])
    edit = AsyncMock(return_value=result)
    generate = AsyncMock()
    provider.client = SimpleNamespace(images=SimpleNamespace(edit=edit, generate=generate))
    assert await provider.edit_image("visual try-on, no fit prediction", photo_bytes()) == fixture_png()
    kwargs = edit.await_args.kwargs
    assert kwargs["image"][0] == "photo.png" and kwargs["image"][2] == "image/png"
    assert kwargs["image"][1] == photo_bytes() and kwargs["n"] == 1
    generate.assert_not_called()


@pytest.mark.parametrize("failure", [False, True])
async def test_live_job_uses_sanitized_photo_and_never_falls_back(settings, db, failure, garment_references):
    state = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                    selected_variant_ids=["J01-Black-M"], last_result_ids=[], clarification_asked=True,
                    messages=[], created_at=now())
    db.save_session(state)
    provider = Provider(settings)
    provider.edit_image = AsyncMock(
        side_effect=AppError("PROVIDER_UNAVAILABLE", "Image editing failed.") if failure else None,
        return_value=photo_bytes(),
    )
    provider.image = AsyncMock()
    images = Images(db, settings.model_copy(update={"demo_mode": "live"}), provider,
                    Moderation(settings, provider), garment_references)
    try:
        job = await images.create(state, uuid4(), state.selected_variant_ids, explicit=True,
                                  photo_base64=payload()["photo_base64"], consent=True)
        await asyncio.gather(*images.tasks)
        completed = images.get(state.session_id, job["job_id"])
        provider.edit_image.assert_awaited_once()
        assert provider.edit_image.await_args.args[1] == normalize_image(photo_bytes())
        assert provider.edit_image.await_args.kwargs["references"] == [fixture_png()]
        provider.image.assert_not_called()
        assert not list(settings.image_dir.glob("*.png"))
        if failure:
            assert completed["status"] == "failed" and completed["image_url"] is None
            assert completed["error"]["code"] == "PROVIDER_UNAVAILABLE"
            assert images.private_images == {}
        else:
            assert completed["status"] == "completed" and not completed["cached"]
            image = images.private_media(state.session_id, job["job_id"])
            assert b"PRIVATE_METADATA" not in image
            assert image == normalize_image(photo_bytes())
    finally:
        await images.close()


async def test_photo_moderation_uses_image_input_without_logging(settings, caplog):
    provider = Provider(settings)
    from test_moderation import response
    create = AsyncMock(return_value=response())
    provider.client = SimpleNamespace(moderations=SimpleNamespace(create=create))
    live = settings.model_copy(update={"demo_mode": "live"})
    result = await Moderation(live, provider).screen_photo(photo_bytes(), "photo-test")
    assert result.stage == "try_on_photo"
    assert create.await_args.kwargs["input"][0]["type"] == "image_url"
    assert create.await_args.kwargs["input"][0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert base64.b64encode(photo_bytes()).decode() not in caplog.text


async def test_running_private_job_can_be_removed_without_losing_outfit(settings, db, garment_references):
    state = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                    selected_variant_ids=["J01-Black-M"], last_result_ids=[], clarification_asked=True,
                    messages=[], created_at=now())
    db.save_session(state)
    provider = Provider(settings)
    started = asyncio.Event()
    async def slow_edit(prompt, photo, *, references):
        assert references == [fixture_png()]
        started.set()
        await asyncio.sleep(60)
        return fixture_png()
    provider.edit_image = AsyncMock(side_effect=slow_edit)
    moderation = Moderation(settings, provider)
    images = Images(db, settings.model_copy(update={"demo_mode": "live"}), provider, moderation, garment_references)
    job = await images.create(state, uuid4(), state.selected_variant_ids, explicit=True,
                              photo_base64=payload()["photo_base64"], consent=True)
    await started.wait()
    await images.remove_private(state.session_id)
    assert images.get(state.session_id, job["job_id"])["error"]["code"] == "PHOTO_REMOVED"
    assert images.private_images == {}
    assert db.session(state.session_id).selected_variant_ids == state.selected_variant_ids
    assert not list(settings.image_dir.glob("*.png"))
