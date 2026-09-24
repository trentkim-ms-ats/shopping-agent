import asyncio
import hashlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.enrichment import enrich, seed
from app.images import fixture_png
from app.main import create_app
from app.provider import Provider


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, demo_mode="fixture", database_path=tmp_path / "catalog.sqlite",
                    index_dir=tmp_path / "index", image_dir=tmp_path / "images",
                    product_image_dir=tmp_path / "product-images")


@pytest.fixture
def db(settings):
    database = Database(settings.database_path)
    seed(database)
    asyncio.run(enrich(database, settings, Provider(settings)))
    return database


@pytest.fixture
def client(settings, db):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def session(client):
    response = client.post("/api/sessions", json={"profile_id": "alex"})
    assert response.status_code == 201
    return response.json()["session_id"]


@pytest.fixture
def garment_references():
    data = fixture_png()
    return SimpleNamespace(references=lambda variants: [
        {"key": "a" * 64, "sha256": hashlib.sha256(data).hexdigest(),
         "variant_id": vid, "color": vid.split("-")[1], "data": data}
        for vid in variants
    ])
