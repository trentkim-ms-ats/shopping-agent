import asyncio
from collections import Counter
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app import enrichment
from app.config import ROOT
from app.db import Database, digest
from app.enrichment import enrich, load_json, seed
from app.provider import Provider
from app.schemas import RawProduct, Variant
from scripts.expand_catalog import BASE_IDS, expanded_cases, expanded_catalog


def test_catalog_reproducible_diverse_and_schema_valid():
    raw, commerce, annotations = expanded_catalog()
    assert raw == load_json(ROOT / "data/seed/raw_products.json")
    assert commerce == load_json(ROOT / "data/seed/commerce.json")
    assert expanded_cases(raw, commerce, annotations) == load_json(ROOT / "evals/cases.json")
    assert Counter(p["category"] for p in raw) == {
        "jacket": 120, "midlayer": 40, "pants": 40, "accessory": 40,
    }
    assert len({p["product_id"] for p in raw}) == len({p["name"] for p in raw}) == 240
    assert len({p["description"] for p in raw}) == 240
    assert len({c for p in raw for c in p["colors"]}) >= 10
    assert len({p["price_cents"] for p in commerce}) >= 30
    for product in raw:
        RawProduct.model_validate(product)
        assert set(product) == {"product_id", "category", "name", "colors", "sizes", "description"}
    all_ids = [v["variant_id"] for p in commerce for v in p["variants"]]
    assert len(all_ids) == len(set(all_ids))
    assert any(all(v["stock"] == 0 for v in p["variants"]) for p in commerce)
    assert all(2500 <= p["price_cents"] <= 26000 for p in commerce)


def test_three_digit_product_and_variant_identifiers():
    raw, commerce, _ = expanded_catalog()
    product = next(p for p in raw if p["product_id"] == "J120")
    fact = next(p for p in commerce if p["product_id"] == "J120")
    assert RawProduct.model_validate(product).product_id == "J120"
    assert Variant.model_validate(fact["variants"][0]).variant_id.startswith("J120-")
    for invalid in ("J1", "J1200", "bad"):
        with pytest.raises(ValidationError):
            RawProduct.model_validate({**product, "product_id": invalid})


def test_seed_append_preserves_publication_and_state(settings, monkeypatch):
    raw, commerce, _ = expanded_catalog()
    incoming = {
        "raw_products.json": [p for p in raw if p["product_id"] in BASE_IDS],
        "commerce.json": [p for p in commerce if p["product_id"] in BASE_IDS],
    }
    original_loader = enrichment.load_json
    monkeypatch.setattr(enrichment, "load_json", lambda path: incoming[path.name]
                        if path.name in incoming else original_loader(path))
    db = Database(settings.database_path)
    assert seed(db) == 24
    asyncio.run(enrich(db, settings, Provider(settings)))
    version, before = db.catalog()
    with db.connect() as conn:
        conn.execute("INSERT INTO sessions VALUES ('preserved-session', '{}')")
    db.set_meta("index_manifest", {"count": 24})
    incoming.update({"raw_products.json": raw, "commerce.json": commerce})
    assert seed(db) == 240
    assert db.meta("index_manifest") is None
    assert db.catalog()[0] == version
    old_products = [p for p in db.catalog()[1] if p["raw"]["product_id"] in BASE_IDS]
    assert old_products == before
    assert all(p["enriched"] is None for p in db.catalog()[1] if p["raw"]["product_id"] not in BASE_IDS)
    db.set_meta("index_manifest", {"count": 240})
    assert seed(db) == 240
    assert db.meta("index_manifest") == {"count": 240}
    with db.connect() as conn:
        assert conn.execute("SELECT state_json FROM sessions").fetchone()[0] == "{}"


@pytest.mark.parametrize("mutation", ["change", "remove"])
def test_seed_rejects_existing_source_changes_atomically(settings, monkeypatch, mutation):
    db = Database(settings.database_path)
    seed(db)
    before = db.catalog()
    raw = deepcopy(load_json(ROOT / "data/seed/raw_products.json"))
    commerce = deepcopy(load_json(ROOT / "data/seed/commerce.json"))
    if mutation == "change":
        raw[0]["description"] += " A changed source."
    else:
        pid = raw.pop()["product_id"]
        commerce = [p for p in commerce if p["product_id"] != pid]
    commerce[0]["price_cents"] += 1
    incoming = {"raw_products.json": raw, "commerce.json": commerce}
    original_loader = enrichment.load_json
    monkeypatch.setattr(enrichment, "load_json", lambda path: incoming[path.name]
                        if path.name in incoming else original_loader(path))
    with pytest.raises(ValueError, match="Immutable"):
        seed(db)
    assert db.catalog() == before


async def test_replay_rules_invalidate_cached_enrichment(settings, db, monkeypatch):
    before = {p["raw"]["product_id"]: p["enriched"]["validation_run_id"] for p in db.catalog()[1]}
    rules = deepcopy(load_json(ROOT / "data/fixtures/replay_rules.json"))
    rules["rules"].append({"phrase": "zip pocket", "kind": "use_cases", "value": "zip pocket storage"})
    original_loader = enrichment.load_json
    monkeypatch.setattr(enrichment, "load_json", lambda path: rules if path.name == "replay_rules.json"
                        else original_loader(path))
    await enrich(db, settings, Provider(settings))
    for product in db.catalog()[1]:
        assert product["enriched"]["validation_run_id"] != before[product["raw"]["product_id"]]
        assert product["source_hash"] == digest(product["raw"])
