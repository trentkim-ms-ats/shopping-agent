from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import ROOT
from app.enrichment import load_json, profiles
from app.errors import AppError
from app.provider import Provider
from app.retrieval import Retrieval, build_index, recommendation_summary
from app.retrieval import card as product_card
from app.schemas import Intent
from app.tools import Tools


def intent(**updates):
    return Intent(category="jacket", activity="hiking", season="fall", priority="light_rain",
                  max_price_cents=20000, size="M", color=None, require_in_stock=True,
                  required_benefits=[], preferred_benefits=[]).model_copy(update=updates)


@pytest.mark.parametrize("case", load_json(ROOT / "evals/cases.json"), ids=lambda c: c["id"])
async def test_at04_expected_eligible_sets_and_constraints(settings, db, case):
    profile = profiles()[case["profile"]]
    filters = intent(size=profile.preferred_size, max_price_cents=profile.budget_cents).model_copy(update=case["intent"])
    retrieval = Retrieval(db, settings, Provider(settings))
    result = await retrieval.search(filters, profile, limit=len(db.catalog()[1]))
    assert {p["product_id"] for p in result["results"]} == set(case["eligible"])
    shortlist = await retrieval.search(filters, profile)
    assert len(shortlist["results"]) == min(3, len(case["eligible"]))
    for card in shortlist["results"]:
        assert card["variant"]["stock"] > 0
        assert card["variant"]["size"] == filters.size
        assert card["price_cents"] <= filters.max_price_cents
        source = next(p for p in db.catalog()[1] if p["raw"]["product_id"] == card["product_id"])
        assert card["price_cents"] == source["commerce"]["price_cents"]
        assert {a["attribute_id"] for a in card["reasons"]} <= \
            {a["attribute_id"] for a in source["enriched"]["accepted_attributes"]}


async def test_at04_stock_size_and_color_same_variant(settings, db):
    result = await Retrieval(db, settings, Provider(settings)).search(
        intent(color="Black", required_benefits=["light rain protection"]), profiles()["alex"],
        limit=len(db.catalog()[1]))
    ids = [r["product_id"] for r in result["results"]]
    assert "J12" not in ids and "J07" not in ids and "J09" not in ids and "J11" not in ids
    assert all(r["variant"]["color"] == "Black" for r in result["results"])


async def test_at09_embedding_failure_explicit_lexical_fallback(settings, db):
    live = settings.model_copy(update={"demo_mode": "live"})
    retrieval = Retrieval(db, live, Provider(settings))
    retrieval.semantic = AsyncMock(side_effect=AppError("PROVIDER_UNAVAILABLE", "Unavailable"))
    result = await retrieval.search(intent(), profiles()["alex"])
    assert result["mode"] == "lexical-fallback"
    assert all("semantic" not in r["scores"] for r in result["results"])
    assert result["degradation"] == "PROVIDER_UNAVAILABLE"


async def test_index_full_search_and_model_dimension_mismatch(settings, db):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    provider.embeddings = AsyncMock(side_effect=lambda texts: [[1.0, float(i + 1)] for i, _ in enumerate(texts)])
    manifest = await build_index(db, live, provider)
    assert manifest["count"] == len(db.catalog()[1]) == 240 and manifest["dimensions"] == 2
    retrieval = Retrieval(db, live, provider)
    scores = await retrieval.semantic("hiking", db.catalog()[0], db.catalog()[1])
    assert len(scores) == 240
    provider.embeddings = AsyncMock(return_value=[[1, 2, 3]])
    result = await retrieval.search(intent(), profiles()["alex"])
    assert result["mode"] == "lexical-fallback"
    manifest["model"] = "different-model"
    db.set_meta("index_manifest", manifest)
    result = await retrieval.search(intent(), profiles()["alex"])
    assert result["degradation"] == "INDEX_UNAVAILABLE"


async def test_inactive_signals_renormalize_without_dropping_active_unknowns(settings, db):
    result = await Retrieval(db, settings, Provider(settings)).search(
        intent(), profiles()["alex"], limit=len(db.catalog()[1]))
    city = next(p for p in result["results"] if p["product_id"] == "J11")
    assert city["scores"]["intent"] == 0 and city["scores"]["season"] == 0
    scores = city["scores"]
    assert scores["total"] == pytest.approx(
        (.2 * scores["lexical"] + .2 * scores["intent"] + .1 * scores["season"]
         + .05 * scores["profile"] + .05 * scores["popularity"]) / .6)


def test_comparison_unknowns_and_order(settings, db):
    tools = Tools(db, Retrieval(db, settings, Provider(settings)), None)
    comparison = tools.compare(["J03", "J01"])
    assert comparison["product_ids"] == ["J03", "J01"]
    assert comparison["rows"][0]["values"] == ["$179.00", "$149.00"]
    assert comparison["rows"][-1]["values"] == ["Not specified", "Not specified"]


async def test_complements_find_distinct_categories_beyond_first_24(settings, db):
    retrieval = Retrieval(db, settings, Provider(settings))
    tools = Tools(db, retrieval, None)
    all_results = await retrieval.search(intent(category=None, max_price_cents=None), profiles()["alex"], limit=240)
    jackets = [p for p in all_results["results"] if p["category"] == "jacket"]
    others = [p for p in all_results["results"] if p["category"] != "jacket" and p["product_id"] != "M01"]
    assert len(jackets) > 24

    async def jacket_first(*args, limit, **kwargs):
        return {**all_results, "results": (jackets + others)[:limit]}

    retrieval.search = AsyncMock(side_effect=jacket_first)
    variant = next(v for v in tools.product("J01")["commerce"]["variants"] if v["size"] == "M" and v["stock"])
    session = SimpleNamespace(profile_id="alex", intent=intent(), selected_variant_ids=[variant["variant_id"]])
    result = await tools.complements(session, "J01")
    assert len({p["category"] for p in result["results"]}) == 2
    assert all(p["category"] != "jacket" and p["product_id"] != "M01" for p in result["results"])
    assert retrieval.search.call_args.kwargs["limit"] == 240


def test_seed_immutability_rejects_modified_existing_hash(db):
    from app.enrichment import seed
    with db.connect() as conn:
        conn.execute("UPDATE raw_products SET source_hash=?", ("changed",))
    with pytest.raises(ValueError, match="Immutable"):
        seed(db)


async def test_recommendation_summaries_use_each_products_facts_and_request(settings, db):
    result = await Retrieval(db, settings, Provider(settings)).search(intent(), profiles()["alex"])
    assert len({item["match_summary"] for item in result["results"]}) == len(result["results"])
    for item in result["results"]:
        summary = item["match_summary"]
        assert f'From the product description: "{item["description"]}"' in summary
        assert f'At ${item["price_cents"] / 100:.2f}, it is within your $200.00 budget.' in summary
        assert f'Your requested size M is in stock in {item["variant"]["color"]}.' in summary
        for reason in item["reasons"]:
            assert reason["value"] in summary
        assert "no approved request-specific attributes shown" not in summary


@pytest.mark.parametrize("stale", [False, True])
def test_source_only_summary_does_not_invent_request_matches(db, stale):
    product = next(p for p in db.catalog()[1] if p["raw"]["product_id"] == "J01")
    matched = [a["attribute_id"] for a in product["enriched"]["accepted_attributes"]]
    if stale:
        product["enriched"]["source_hash"] = "outdated"
    else:
        product["enriched"] = None
    variant = next(v for v in product["commerce"]["variants"] if v["stock"] and v["size"] == "M")
    item = product_card(product, variant, matched=matched, intent=intent(), profile=profiles()["alex"])
    assert item["reasons"] == []
    assert product["raw"]["description"] in item["match_summary"]
    assert "within your $200.00 budget" in item["match_summary"]
    assert "Approved matches" not in item["match_summary"]
    assert "Reviewed inferences" not in item["match_summary"]


def test_summary_distinguishes_inferences_and_does_not_overclaim_eligibility(db):
    product = next(p for p in db.catalog()[1] if p["raw"]["product_id"] == "J01")
    variant = {"variant_id": "test", "color": "Red", "size": "L", "stock": 0}
    reasons = [{"value": "hiking", "support": "explicit"},
               {"value": "fall layering", "support": "inferred"}]
    summary = recommendation_summary(product, variant, reasons, intent(max_price_cents=100), profiles()["alex"])
    assert "Approved matches to your request: hiking." in summary
    assert "Reviewed inferences, not explicit specifications: fall layering." in summary
    assert "Red / L is currently out of stock." in summary
    assert "within your" not in summary
    assert "Your requested size" not in summary
    assert "saved preferences" not in summary


async def test_complement_summary_tracks_final_variant_and_not_jacket_budget(settings, db):
    tools = Tools(db, Retrieval(db, settings, Provider(settings)), None)
    jacket = tools.product("J01")
    variant = next(v for v in jacket["commerce"]["variants"] if v["size"] == "M" and v["stock"])
    session = SimpleNamespace(profile_id="alex", intent=intent(max_price_cents=100),
                              selected_variant_ids=[variant["variant_id"]])
    result = await tools.complements(session, "J01")
    assert result["results"]
    for item in result["results"]:
        if item["variant"]["size"] == "M":
            assert f'Your requested size M is in stock in {item["variant"]["color"]}.' in item["match_summary"]
        else:
            assert item["variant"]["size"] == "One Size"
            assert f'{item["variant"]["color"]} / One Size is in stock.' in item["match_summary"]
        assert "within your" not in item["match_summary"]


async def test_query_cache_reuses_vectors_but_rechecks_budget_and_stock(settings, db):
    import json

    from app.db import canonical

    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    provider.embeddings = AsyncMock(side_effect=lambda texts: [[1.0, 2.0] for _ in texts])
    await build_index(db, live, provider)
    provider.embeddings.reset_mock()
    retrieval = Retrieval(db, live, provider)
    first = await retrieval.search(intent(), profiles()["alex"])
    repeat = await retrieval.search(intent(), profiles()["alex"])
    assert repeat["results"] == first["results"]
    assert provider.embeddings.await_count == 1
    tighter = await retrieval.search(intent(max_price_cents=10000), profiles()["alex"])
    assert tighter["results"] and all(p["price_cents"] <= 10000 for p in tighter["results"])
    assert provider.embeddings.await_count == 1
    removed = first["results"][0]["product_id"]
    with db.connect() as conn:
        row = conn.execute("SELECT facts_json FROM commerce WHERE product_id=?", (removed,)).fetchone()
        facts = json.loads(row[0])
        for variant in facts["variants"]:
            variant["stock"] = 0
        conn.execute("UPDATE commerce SET facts_json=? WHERE product_id=?", (canonical(facts), removed))
    updated = await retrieval.search(intent(), profiles()["alex"])
    assert removed not in [p["product_id"] for p in updated["results"]]
    assert provider.embeddings.await_count == 1


async def test_query_cache_expiry_lru_and_model_dimension_keys(settings, db, monkeypatch):
    monkeypatch.setattr("app.retrieval.QUERY_CACHE_MAX_ENTRIES", 2)
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    provider.embeddings = AsyncMock(side_effect=lambda texts: [[1.0, 2.0] for _ in texts])
    await build_index(db, live, provider)
    provider.embeddings.reset_mock()
    retrieval = Retrieval(db, live, provider)
    version, products = db.catalog()
    for query in ("hiking", "warmth", "hiking", "rain", "warmth"):
        await retrieval.semantic(query, version, products)
    assert provider.embeddings.await_count == 4
    assert len(retrieval.query_cache) == 2
    monkeypatch.setattr("app.retrieval.QUERY_CACHE_TTL_SECONDS", 0)
    await retrieval.semantic("warmth", version, products)
    assert provider.embeddings.await_count == 5
    monkeypatch.setattr("app.retrieval.QUERY_CACHE_TTL_SECONDS", 300)
    live.openai_embedding_model = "changed-model"
    manifest = db.meta("index_manifest")
    manifest["model"] = live.openai_embedding_model
    db.set_meta("index_manifest", manifest)
    await retrieval.semantic("warmth", version, products)
    assert provider.embeddings.await_count == 6
    provider.embeddings = AsyncMock(side_effect=lambda texts: [[1.0, 2.0, 3.0] for _ in texts])
    await build_index(db, live, provider)
    provider.embeddings.reset_mock()
    await retrieval.semantic("warmth", version, products)
    assert provider.embeddings.await_count == 1
    assert (live.openai_embedding_model, 3, "warmth") in retrieval.query_cache


async def test_invalid_query_vector_is_not_cached_and_index_is_validated_on_hits(settings, db):
    live = settings.model_copy(update={"demo_mode": "live"})
    provider = Provider(settings)
    provider.embeddings = AsyncMock(side_effect=lambda texts: [[1.0, 2.0] for _ in texts])
    await build_index(db, live, provider)
    retrieval = Retrieval(db, live, provider)
    version, products = db.catalog()
    provider.embeddings = AsyncMock(side_effect=[[[0, 0]], [[1, 2]]])
    with pytest.raises(ValueError, match="Zero embedding"):
        await retrieval.semantic("hiking", version, products)
    assert not retrieval.query_cache
    await retrieval.semantic("hiking", version, products)
    assert provider.embeddings.await_count == 2
    manifest = db.meta("index_manifest")
    manifest["projection_hash"] = "invalid"
    db.set_meta("index_manifest", manifest)
    with pytest.raises(AppError, match="Index source mismatch"):
        await retrieval.semantic("hiking", version, products)
    assert provider.embeddings.await_count == 2


@pytest.mark.parametrize("updates", [{"max_price_cents": 1}, {"size": "NOT-A-SIZE"},
                                   {"required_benefits": ["unsupported specification"]}])
async def test_empty_eligibility_skips_semantic_api(settings, db, updates):
    live = settings.model_copy(update={"demo_mode": "live"})
    retrieval = Retrieval(db, live, Provider(settings))
    retrieval.semantic = AsyncMock(side_effect=AssertionError("No embedding for zero eligible products"))
    result = await retrieval.search(intent(**updates), profiles()["alex"])
    assert result["results"] == []
    assert result["mode"] == "filtered-empty"
    assert result["degradation"] is None
    assert "No filters were relaxed." in result["notice"]
    retrieval.semantic.assert_not_awaited()
