import asyncio
import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_product_images import png
from test_retrieval import intent

from app.color_images import ColorImages
from app.db import now
from app.errors import AppError
from app.images import Images
from app.product_images import ProductImageCatalog
from app.provider import Provider
from app.schemas import Session


@pytest.fixture
def color_service(settings, db):
    key = "b" * 64
    data = png()
    settings.product_image_dir.mkdir(parents=True, exist_ok=True)
    (settings.product_image_dir / f"{key}.png").write_bytes(data)
    raw = next(p for p in db.catalog()[1] if p["raw"]["product_id"] == "J01")
    with db.connect() as conn:
        conn.execute("INSERT INTO product_images VALUES (?,?,?,?,?,?,?)",
                     (key, "J01", raw["source_hash"], f"{key}.png",
                      hashlib.sha256(data).hexdigest(), now(), "completed"))
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = SimpleNamespace(edit_image=AsyncMock(return_value=png()), image=AsyncMock())
    moderation = SimpleNamespace(screen=AsyncMock(), screen_photo=AsyncMock())
    service = ColorImages(db, live, provider, moderation, ProductImageCatalog(db, settings.product_image_dir))
    return service, provider, moderation


async def test_nonblocking_deduplicated_color_edit_cache_and_references(color_service):
    service, provider, _ = color_service
    try:
        first = service.ensure("J01", "Black")
        assert first["status"] == "queued"
        assert service.ensure("J01", "Black")["key"] == first["key"]
        assert len(service.tasks) == 1
        provider.edit_image.assert_not_awaited()
        with pytest.raises(AppError, match="not ready"):
            service.references(["J01-Black-M"])
        await asyncio.gather(*service.tasks.values())
        kwargs = provider.edit_image.await_args.kwargs
        assert kwargs == {"size": "816x816", "quality": "low"}
        assert provider.edit_image.await_args.args[1] == png()
        assert '"target_color":"Black"' in provider.edit_image.await_args.args[0]
        saved = service.ensure("J01", "Black")
        assert saved["status"] == "completed"
        refs = service.references(["J01-Black-M"])
        assert refs[0]["data"] == png() and refs[0]["key"] == saved["key"]
        assert service.references(["J01-Black-L"])[0]["key"] == saved["key"]
        assert service.spec("J01", "Slate")[0] != saved["key"]
        provider.edit_image.assert_awaited_once()
        provider.image.assert_not_called()
        with service.db.connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM image_call_reservations").fetchone()[0] == 1
        restarted = ColorImages(service.db, service.settings, provider, service.moderation, service.catalog)
        assert restarted.ensure("J01", "Black")["key"] == saved["key"]
        assert not restarted.tasks
        await restarted.close()
    finally:
        await service.close()


async def test_daily_cap_prevents_color_provider_call(color_service):
    service, provider, _ = color_service
    service.settings = service.settings.model_copy(update={"daily_image_call_limit": 0})
    try:
        state = service.ensure("J01", "Black")
        await asyncio.gather(*service.tasks.values())
        assert service.get(state["key"])["error"]["code"] == "DAILY_IMAGE_LIMIT"
        provider.edit_image.assert_not_called()
    finally:
        await service.close()


async def test_failures_require_explicit_retry_and_bad_base_is_not_replaced(color_service):
    service, provider, _ = color_service
    try:
        provider.edit_image.side_effect = AppError("PROVIDER_UNAVAILABLE", "Edit failed")
        state = service.ensure("J01", "Black")
        await asyncio.gather(*service.tasks.values())
        assert service.ensure("J01", "Black")["status"] == "failed"
        assert not service.tasks
        provider.edit_image.assert_awaited_once()
        provider.edit_image.side_effect = None
        service.last_start = 0
        assert service.retry(state["key"])["status"] == "queued"
        await asyncio.gather(*service.tasks.values())
        assert service.get(state["key"])["status"] == "completed"
        # Changed design invalidates the color and outfit reference identity.
        with service.db.connect() as conn:
            conn.execute("UPDATE product_images SET sha256=?", ("c" * 64,))
        assert service.spec("J01", "Black")[0] != state["key"]
        with pytest.raises(AppError, match="Wait for selected"):
            service.references(["J01-Black-M"])
    finally:
        await service.close()


async def test_multi_image_adapter_preserves_person_first_and_garment_order(settings):
    provider = Provider(settings)
    result = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(png()).decode())])
    edit = AsyncMock(return_value=result)
    provider.client = SimpleNamespace(images=SimpleNamespace(edit=edit))
    person, garment1, garment2 = b"person", b"jacket", b"pants"
    await provider.edit_image("reference try-on", person, references=[garment1, garment2])
    assert [i[1] for i in edit.await_args.kwargs["image"]] == [person, garment1, garment2]
    assert edit.await_args.kwargs["timeout"] == 110


async def test_outfit_uses_same_colored_reference_and_cache_changes_with_it(color_service):
    service, provider, moderation = color_service
    state = Session(session_id=uuid4(), profile_id="alex", intent=intent(), intent_sources={},
                    selected_variant_ids=["J01-Black-M"], last_result_ids=[], clarification_asked=True,
                    messages=[], created_at=now())
    service.db.save_session(state)
    images = Images(service.db, service.settings, provider, moderation, service)
    try:
        with pytest.raises(AppError, match="Wait for selected"):
            await images.create(state, uuid4(), state.selected_variant_ids, explicit=True)
        color = service.ensure("J01", "Black")
        await asyncio.gather(*service.tasks.values())
        provider.edit_image.reset_mock()
        job = await images.create(state, uuid4(), state.selected_variant_ids, explicit=True)
        await asyncio.gather(*images.tasks)
        assert job["status"] == "completed"
        assert provider.edit_image.await_args.args[1] == service.image(color["key"]).read_bytes()
        assert "Image 1: J01-Black-M" in provider.edit_image.await_args.args[0]
        assert job["product_references"][0]["key"] == color["key"]
        assert "data" not in job["product_references"][0]
        cached = await images.create(state, uuid4(), state.selected_variant_ids, explicit=True)
        assert cached["cached"]
        with service.db.connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM image_call_reservations").fetchone()[0] == 2
        previous_key = job["cache_key"]
        updated = service.get(color["key"])
        # Changing reference bytes must not reuse an older outfit.
        data = png((816, 816)) + b"new-version"
        service.image(color["key"]).write_bytes(data)
        updated["sha256"] = hashlib.sha256(data).hexdigest()
        service.save(updated)
        fresh = await images.create(state, uuid4(), state.selected_variant_ids, explicit=True)
        assert fresh["cache_key"] != previous_key and not fresh["cached"]
        await asyncio.gather(*images.tasks)
    finally:
        await images.close()
        await service.close()


async def test_readonly_status_and_registered_media_routes(color_service):
    from fastapi.testclient import TestClient

    from app.main import create_app

    service, provider, _ = color_service
    try:
        color = service.ensure("J01", "Black")
        await asyncio.gather(*service.tasks.values())
        provider.edit_image.reset_mock()
        # Fixture API reads registered test assets but must not launch paid edits.
        settings = service.settings.model_copy(update={"demo_mode": "fixture"})
        with TestClient(create_app(settings)) as client:
            response = client.get(f"/api/product-color-images/{color['key']}")
            assert response.status_code == 200
            assert response.json()["status"] == "completed"
            assert "prompt" not in response.json()
            assert client.get(response.json()["image_url"]).content == png()
            assert client.get("/api/product-color-images/unknown").status_code == 404
            assert client.post(f"/api/product-color-images/{color['key']}/retry").status_code == 409
        provider.edit_image.assert_not_called()
    finally:
        await service.close()
