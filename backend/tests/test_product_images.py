import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image

from app.config import ROOT
from app.enrichment import load_json
from app.errors import AppError
from app.product_images import ProductImageCatalog, generate_product_images, save_manifest
from app.provider import Provider


def png(size=(816, 816)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "gray").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def generation(settings, tmp_path, monkeypatch):
    monkeypatch.setattr("app.product_images.Moderation.screen", AsyncMock())
    monkeypatch.setattr("app.product_images.asyncio.sleep", AsyncMock())
    live = settings.model_copy(update={"demo_mode": "live", "openai_api_key": "test-key"})
    provider = SimpleNamespace(image=AsyncMock(return_value=png()))
    return live, provider, tmp_path / "product-images"


async def test_entire_catalog_generated_once_and_resumed(generation):
    settings, provider, destination = generation
    result = await generate_product_images(settings, provider, destination=destination)
    products = load_json(ROOT / "data/seed/raw_products.json")
    assert result["products"] == result["generated"] == len(products)
    assert result["skipped"] == 0
    assert len(list(destination.glob("*.png"))) == len(products)
    for call, product in zip(provider.image.await_args_list, products, strict=True):
        assert call.kwargs == {"size": "816x816", "quality": "low"}
        source = json.loads(call.args[0].split("\n")[-1])
        assert source == {"name": product["name"], "description": product["description"]}
    provider.image.reset_mock()
    resumed = await generate_product_images(settings, provider, destination=destination)
    assert resumed["generated"] == 0 and resumed["skipped"] == len(products)
    provider.image.assert_not_awaited()


async def test_wrong_dimensions_fail_without_silent_regeneration(generation):
    settings, provider, destination = generation
    products = load_json(ROOT / "data/seed/raw_products.json")[:1]
    provider.image.return_value = png((1024, 1024))
    with pytest.raises(AppError, match="816x816"):
        await generate_product_images(settings, provider, destination=destination, products=products)
    assert not list(destination.glob("*.png"))
    provider.image.reset_mock()
    with pytest.raises(AppError, match="incomplete attempt"):
        await generate_product_images(settings, provider, destination=destination, products=products)
    provider.image.assert_not_awaited()
    provider.image.return_value = png()
    result = await generate_product_images(settings, provider, destination=destination,
                                          products=products, retry_incomplete=True)
    assert result["generated"] == 1


async def test_missing_key_or_fixture_mode_never_generates(settings, tmp_path):
    provider = SimpleNamespace(image=AsyncMock())
    for config in (settings, settings.model_copy(update={"demo_mode": "live", "openai_api_key": ""})):
        with pytest.raises(AppError, match="No fixtures"):
            await generate_product_images(config, provider, destination=tmp_path)
    provider.image.assert_not_awaited()


async def test_product_image_adapter_sends_exact_size_and_quality(settings):
    provider = Provider(settings)
    create = AsyncMock(return_value=SimpleNamespace(
        data=[SimpleNamespace(b64_json=base64.b64encode(png()).decode())]))
    provider.client = SimpleNamespace(images=SimpleNamespace(generate=create))
    assert await provider.image("product", size="816x816", quality="low") == png()
    assert create.await_args.kwargs["size"] == "816x816"
    assert create.await_args.kwargs["quality"] == "low"


@pytest.fixture
def saved_image(settings, db):
    import hashlib

    from app.db import digest, now

    raw = db.catalog()[1][0]["raw"]
    key = digest(raw)
    data = png()
    settings.product_image_dir.mkdir(parents=True)
    (settings.product_image_dir / f"{key}.png").write_bytes(data)
    record = {
        "product_id": raw["product_id"], "source": {k: raw[k] for k in ("name", "description")},
        "mode": "live", "status": "completed", "size": "816x816", "quality": "low",
        "file": f"{key}.png", "sha256": hashlib.sha256(data).hexdigest(), "completed_at": now(),
    }
    manifest = {"version": 1, "images": {key: record}}
    save_manifest(settings.product_image_dir / "manifest.json", manifest)
    return key, raw, manifest


def test_image_import_persists_and_serves_without_manifest(settings, db, saved_image, monkeypatch):
    from fastapi.testclient import TestClient

    from app.db import Database
    from app.main import create_app
    from app.retrieval import card

    key, raw, _ = saved_image
    with TestClient(create_app(settings)) as client:
        def no_manifest_reads(*args):
            raise AssertionError("HTTP requests must query SQLite, not the manifest")

        monkeypatch.setattr("app.product_images.load_json", no_manifest_reads)
        p = next(p for p in Database(settings.database_path).catalog()[1] if p["raw"]["product_id"] == raw["product_id"])
        url = p["image_url"]
        assert url == f"/api/product-images/{key}.png"
        assert card(p, p["commerce"]["variants"][0])["image_url"] == url
        assert client.get(f"/api/products/{raw['product_id']}").json()["image_url"] == url
        image = client.get(url)
        assert image.status_code == 200 and image.content == png()
        assert "immutable" in image.headers["cache-control"]
        assert client.get("/api/product-images/" + "a" * 64 + ".png").status_code == 404
        assert client.get("/api/product-images/invalid.png").status_code == 404
        (settings.product_image_dir / f"{key}.png").unlink()
        assert client.get(url).status_code == 404


def test_import_picks_up_later_completion_and_skips_unchanged_manifest(settings, db, saved_image, monkeypatch):
    key, _, manifest = saved_image
    path = settings.product_image_dir / "manifest.json"
    catalog = ProductImageCatalog(db, settings.product_image_dir)
    manifest["images"][key]["status"] = "generating"
    save_manifest(path, manifest)
    catalog.sync()
    assert not any(p["image_url"] for p in db.catalog()[1])
    manifest["images"][key]["status"] = "completed"
    save_manifest(path, manifest)
    catalog.sync()
    assert sum(bool(p["image_url"]) for p in db.catalog()[1]) == 1
    reader = Mock(side_effect=AssertionError("unnecessary read"))
    monkeypatch.setattr("app.product_images.load_json", reader)
    catalog.sync()
    reader.assert_not_called()


@pytest.mark.parametrize("problem", ["filename", "checksum", "symlink", "source"])
def test_unsafe_corrupt_or_mismatched_images_are_not_published(settings, db, saved_image, problem):
    key, _, manifest = saved_image
    record = manifest["images"][key]
    path = settings.product_image_dir / record["file"]
    if problem == "filename":
        record["file"] = "../outside.png"
    elif problem == "checksum":
        path.write_bytes(png((32, 32)))
    elif problem == "symlink":
        original = settings.product_image_dir / "original.png"
        path.rename(original)
        path.symlink_to(original)
    else:
        record["source"]["name"] = "A different product"
    save_manifest(settings.product_image_dir / "manifest.json", manifest)
    importer = ProductImageCatalog(db, settings.product_image_dir)
    if problem == "source":
        importer.sync()
    else:
        with pytest.raises(ValueError):
            importer.sync()
        importer.sync_logged()
        assert importer.error == "PRODUCT_IMAGE_IMPORT_FAILED"
    assert not any(p["image_url"] for p in db.catalog()[1])
