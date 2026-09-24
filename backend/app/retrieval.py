import json
import math
import os
import re
import time
from collections import OrderedDict
from uuid import uuid4

import faiss
import numpy as np

from .db import canonical, digest
from .errors import AppError
from .events import event

SYNONYMS = {"autumn": "fall", "hikes": "hiking", "hike": "hiking", "drizzle": "rain", "warm": "warmth"}
WEIGHTS = {"semantic": .4, "lexical": .2, "intent": .2, "season": .1, "profile": .05, "popularity": .05}
QUERY_CACHE_MAX_ENTRIES = 128
QUERY_CACHE_TTL_SECONDS = 300


def tokens(text):
    return {SYNONYMS.get(t, t) for t in re.findall(r"[a-z0-9]+", text.lower())}


def attributes(product):
    enriched = product["enriched"]
    return enriched["accepted_attributes"] if enriched and enriched["source_hash"] == product["source_hash"] else []


def projection(product, source_only=False):
    raw = product["raw"]
    parts = [raw["name"], raw["category"], raw["description"]]
    if not source_only:
        parts += [a["kind"] + ": " + a["value"] for a in attributes(product)]
    return " ".join(parts)


def normalized_vectors(vectors):
    matrix = np.asarray(vectors, dtype="float32")
    if matrix.ndim != 2 or matrix.shape[1] == 0 or not np.isfinite(matrix).all():
        raise ValueError("Invalid embedding vectors")
    if (np.linalg.norm(matrix, axis=1) == 0).any():
        raise ValueError("Zero embedding vectors")
    faiss.normalize_L2(matrix)
    return matrix


async def build_index(db, settings, provider):
    if settings.demo_mode == "fixture":
        db.set_meta("index_manifest", None)
        return {"mode": "fixture", "notice": "No simulated semantic vectors; labeled lexical retrieval only."}
    version, products = db.catalog()
    vectors = normalized_vectors(await provider.embeddings([projection(p) for p in products]))
    if len(vectors) != len(products):
        raise ValueError("Embedding count mismatch")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    index_id = str(uuid4())
    index_path = settings.index_dir / f"{index_id}.faiss"
    ids_path = settings.index_dir / f"{index_id}.json"
    faiss.write_index(index, str(index_path) + ".tmp")
    ids_path.with_suffix(".tmp").write_text(canonical([p["raw"]["product_id"] for p in products]))
    os.replace(str(index_path) + ".tmp", index_path)
    os.replace(ids_path.with_suffix(".tmp"), ids_path)
    manifest = {
        "version": version, "index_id": index_id, "model": settings.openai_embedding_model,
        "dimensions": vectors.shape[1], "count": len(products),
        "projection_hash": digest([projection(p) for p in products]),
    }
    manifest_path = settings.index_dir / f"{index_id}.manifest.json"
    manifest_path.with_suffix(".tmp").write_text(canonical(manifest))
    os.replace(manifest_path.with_suffix(".tmp"), manifest_path)
    with db.connect() as conn:
        current = conn.execute("SELECT value FROM meta WHERE key='publication_version'").fetchone()
        if (json.loads(current[0]) if current else "seed") != version:
            raise AppError("CATALOG_CHANGED", "Catalog changed during index build. Rebuild the index.", 409)
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('index_manifest',?)", (canonical(manifest),))
    return manifest


def eligible_variants(product, intent):
    return [
        v for v in product["commerce"]["variants"]
        if v["stock"] > 0
        and (not intent.size or v["size"] == intent.size
             or (product["raw"]["category"] == "accessory" and v["size"] == "One Size"))
        and (not intent.color or v["color"].casefold() == intent.color.casefold())
    ]
def available_variants(product, intent, profile):
    variants = eligible_variants(product, intent)
    preferred = [c.casefold() for c in profile.preferred_colors]
    return sorted(variants, key=lambda v: (v["color"].casefold() not in preferred, v["variant_id"]))


def matched_attr(product, kind, value, explicit=False):
    return [a for a in attributes(product) if a["kind"] == kind
            and tokens(value) <= tokens(a["value"]) and (not explicit or a["support"] == "explicit")]


def satisfies(product, intent, *, include_benefits=True):
    return (
        (not intent.category or product["raw"]["category"] == intent.category)
        and (intent.max_price_cents is None or product["commerce"]["price_cents"] <= intent.max_price_cents)
        and bool(eligible_variants(product, intent))
        and (not include_benefits or all(matched_attr(product, "benefits", benefit, explicit=True)
                                        for benefit in intent.required_benefits))
    )


def recommendation_summary(product, variant, reasons, intent=None, profile=None):
    parts = [f'From the product description: "{product["raw"]["description"]}"']
    explicit = list(dict.fromkeys(a["value"] for a in reasons if a["support"] == "explicit"))
    inferred = list(dict.fromkeys(a["value"] for a in reasons if a["support"] == "inferred"))
    if explicit:
        parts.append("Approved matches to your request: " + ", ".join(explicit) + ".")
    if inferred:
        parts.append("Reviewed inferences, not explicit specifications: " + ", ".join(inferred) + ".")
    price = product["commerce"]["price_cents"]
    if intent and intent.max_price_cents is not None and price <= intent.max_price_cents:
        parts.append(f"At ${price / 100:.2f}, it is within your ${intent.max_price_cents / 100:.2f} budget.")
    else:
        parts.append(f"Priced at ${price / 100:.2f}.")
    if variant["stock"] > 0:
        if intent and intent.size and variant["size"] == intent.size:
            parts.append(f"Your requested size {variant['size']} is in stock in {variant['color']}.")
        else:
            parts.append(f"{variant['color']} / {variant['size']} is in stock.")
    else:
        parts.append(f"{variant['color']} / {variant['size']} is currently out of stock.")
    if profile and variant["color"].casefold() in {c.casefold() for c in profile.preferred_colors}:
        parts.append("This color also matches your saved preferences.")
    return " ".join(parts)


def card(product, variant, scores=None, matched=None, *, intent=None, profile=None):
    accepted = attributes(product)
    reasons = [a for a in accepted if a["attribute_id"] in (matched or [])][:4]
    tradeoff = "Waterproof and temperature ratings: Not specified in the catalog."
    if not matched_attr(product, "benefits", "light rain protection"):
        tradeoff = "Light-rain protection: Not specified in approved catalog attributes."
    return {
        "product_id": product["raw"]["product_id"], "name": product["raw"]["name"],
        "category": product["raw"]["category"], "price_cents": product["commerce"]["price_cents"],
        "currency": "USD", "variant": variant, "description": product["raw"]["description"],
        "reasons": reasons, "tradeoff": tradeoff, "scores": scores or {},
        "enrichment_status": product["enriched"]["status"] if product["enriched"] else "raw_only",
        "image_url": product.get("image_url"),
        "match_summary": recommendation_summary(product, variant, reasons, intent, profile),
    }


class Retrieval:
    def __init__(self, db, settings, provider):
        self.db, self.settings, self.provider = db, settings, provider
        self.loaded = None
        self.query_cache = OrderedDict()

    async def semantic(self, query, version, products):
        manifest = self.db.meta("index_manifest")
        if not manifest or manifest["version"] != version or manifest["model"] != self.settings.openai_embedding_model:
            raise AppError("INDEX_UNAVAILABLE", "Index is missing or mismatched; using lexical retrieval.")
        if manifest["projection_hash"] != digest([projection(p) for p in products]):
            raise AppError("INDEX_MISMATCH", "Index source mismatch; using lexical retrieval.")
        index_id = manifest["index_id"]
        if not re.fullmatch(r"[0-9a-f-]{36}", index_id):
            raise ValueError("Invalid local index ID")
        if self.loaded is None or self.loaded[0] != index_id:
            index = faiss.read_index(str(self.settings.index_dir / f"{index_id}.faiss"))
            ids = json.loads((self.settings.index_dir / f"{index_id}.json").read_text())
            if (index.d != manifest["dimensions"] or index.ntotal != len(ids)
                    or ids != [p["raw"]["product_id"] for p in products]):
                raise ValueError("Index dimensions or IDs mismatch")
            self.loaded = (index_id, index, ids)
        _, index, ids = self.loaded
        cache_key = (manifest["model"], index.d, query)
        cached = self.query_cache.get(cache_key)
        cache_hit = cached is not None and time.monotonic() - cached[0] < QUERY_CACHE_TTL_SECONDS
        if cache_hit:
            vector = cached[1]
            self.query_cache.move_to_end(cache_key)
        else:
            self.query_cache.pop(cache_key, None)
            vector = normalized_vectors(await self.provider.embeddings([query]))
            if len(vector) != 1 or vector.shape[1] != index.d:
                raise ValueError("Query embedding mismatch")
            self.query_cache[cache_key] = (time.monotonic(), vector)
            while len(self.query_cache) > QUERY_CACHE_MAX_ENTRIES:
                self.query_cache.popitem(last=False)
        event("query_embedding_cache", hit=cache_hit, model=manifest["model"], dimensions=index.d)
        distances, positions = index.search(vector, index.ntotal)
        return {ids[int(pos)]: max(0, min(1, (float(score) + 1) / 2))
                for pos, score in zip(positions[0], distances[0], strict=True)}

    async def search(self, intent, profile, *, exclude=None, limit=3, strategy="hybrid"):
        start = time.monotonic()
        version, products = self.db.catalog()
        query_parts = [intent.activity, intent.season, intent.priority and intent.priority.replace("_", " ")]
        desired = list(dict.fromkeys(intent.required_benefits + intent.preferred_benefits + {
            "light_rain": ["light rain protection"], "warmth": ["warmth"],
            "lightweight": ["lightweight"],
        }.get(intent.priority, [])))
        query = " ".join([p for p in query_parts if p] + desired)
        query_tokens = tokens(query)
        eligible_ids = {p["raw"]["product_id"] for p in products if satisfies(p, intent, include_benefits=False)}
        searchable = any(p["raw"]["product_id"] in eligible_ids
                         and p["raw"]["product_id"] not in (exclude or set())
                         and all(matched_attr(p, "benefits", b, explicit=True) for b in intent.required_benefits)
                         for p in products)
        semantic, degradation = {}, None
        if strategy == "hybrid" and self.settings.demo_mode == "live" and searchable:
            try:
                semantic = await self.semantic(query or intent.category or "outdoor", version, products)
            except (AppError, ValueError, OSError, RuntimeError, KeyError) as exc:
                degradation = exc.code if isinstance(exc, AppError) else "INDEX_INVALID"
                event("retrieval_degraded", code=degradation)
        elif self.settings.demo_mode == "fixture":
            degradation = "REPLAY_NO_SEMANTIC_API"
        maximum = max((p["commerce"]["popularity_30d"] for p in products), default=0)
        ranked, excluded = [], {"hard_constraints": 0, "required_benefits": 0, "owned_or_selected": 0}
        for product in products:
            pid = product["raw"]["product_id"]
            if pid not in eligible_ids:
                excluded["hard_constraints"] += 1
                continue
            if pid in (exclude or set()):
                excluded["owned_or_selected"] += 1
                continue
            if any(not matched_attr(product, "benefits", benefit, explicit=True) for benefit in intent.required_benefits):
                excluded["required_benefits"] += 1
                continue
            variants = available_variants(product, intent, profile)
            if not variants:
                excluded["hard_constraints"] += 1
                continue
            variant = variants[0]
            source_only = strategy == "source_lexical"
            lexical = len(query_tokens & tokens(projection(product, source_only))) / max(1, len(query_tokens))
            components = {"lexical": lexical, "popularity": math.log1p(product["commerce"]["popularity_30d"])
                          / math.log1p(maximum) if maximum else 0}
            matched = []
            intent_matches = []
            for kind, value in ([("activities", intent.activity)] if intent.activity else []) + \
                    [("benefits", benefit) for benefit in desired]:
                matches = matched_attr(product, kind, value)
                matched.extend(a["attribute_id"] for a in matches)
                intent_matches.append(bool(matches))
            if intent_matches:
                components["intent"] = sum(intent_matches) / len(intent_matches)
            if intent.season:
                matches = matched_attr(product, "season_suitability", intent.season)
                components["season"] = float(bool(matches))
                matched.extend(a["attribute_id"] for a in matches)
            signals = []
            if profile.preferred_colors:
                signals.append(variant["color"] in profile.preferred_colors)
            if profile.preferred_style:
                signals.append(any(matched_attr(product, "style", style) for style in profile.preferred_style))
            if signals:
                components["profile"] = sum(signals) / len(signals)
            if pid in semantic:
                components["semantic"] = semantic[pid]
            if strategy in ("source_lexical", "enriched_lexical"):
                components = {"lexical": lexical}
            score = sum(WEIGHTS[k] * v for k, v in components.items()) / sum(WEIGHTS[k] for k in components)
            components["total"] = score
            ranked.append(card(product, variant, components, list(dict.fromkeys(matched)),
                               intent=intent, profile=profile))
        ranked.sort(key=lambda p: (-p["scores"]["total"], p["product_id"]))
        mode = "fixture-lexical" if self.settings.demo_mode == "fixture" else \
            ("hybrid" if semantic else "filtered-empty" if not searchable else
             "lexical-fallback" if strategy == "hybrid" else strategy)
        result = {
            "results": ranked[:limit], "eligible_count": len(ranked), "exclusions": excluded,
            "applied_filters": intent.model_dump(), "mode": mode, "degradation": degradation,
            "publication_version": version,
            "notice": None if len(ranked) >= min(3, limit) else
                f"Only {len(ranked)} products meet the current category, budget, size, color, stock and required-benefit constraints. No filters were relaxed.",
            "alternatives": self.alternatives(intent) if not ranked and not exclude else [],
        }
        event("retrieval", duration_ms=(time.monotonic() - start) * 1000, mode=mode,
              publication_version=version, component_scores={c["product_id"]: c["scores"] for c in result["results"]})
        return result

    def alternatives(self, intent):
        _, products = self.db.catalog()
        if any(satisfies(p, intent) for p in products):
            return []
        candidates = []
        if intent.max_price_cents is not None:
            unbounded = intent.model_copy(update={"max_price_cents": None})
            prices = [p["commerce"]["price_cents"] for p in products if satisfies(p, unbounded)]
            if prices and min(prices) > intent.max_price_cents:
                price = min(prices)
                candidates.append((f"Raise jacket budget to ${price / 100:.2f}", {"max_price_cents": price}))
        if intent.color:
            candidates.append((f"Remove required color: {intent.color}", {"color": None}))
        for benefit in intent.required_benefits:
            candidates.append((f"Make {benefit} optional",
                               {"required_benefits": [b for b in intent.required_benefits if b != benefit]}))
        result = []
        for label, update in candidates:
            proposed = intent.model_copy(update=update)
            count = sum(satisfies(p, proposed) for p in products)
            if count:
                result.append({"id": digest([intent.model_dump(), proposed.model_dump()]), "label": label,
                               "eligible_count": count, "intent": proposed.model_dump()})
        return result[:3]

    def controlled_baseline(self, query, intent):
        _, products = self.db.catalog()
        q = tokens(query)
        rows = [{
            "product_id": p["raw"]["product_id"], "name": p["raw"]["name"],
            "description": p["raw"]["description"],
            "score": len(q & tokens(projection(p, source_only=True))) / max(1, len(q)),
        } for p in products if satisfies(p, intent)]
        return {"mode": "source-only lexical ranking / shared eligibility", "constraints": intent.model_dump(),
                "eligible_count": len(rows), "results": sorted(rows, key=lambda p: (-p["score"], p["product_id"]))[:3],
                "limitation": "Same eligibility rules as assisted search, including approved required-benefit evidence. "
                              "Ranking uses raw source text only. This is not an enrichment ablation or proof of uplift."}

    def baseline(self, query):
        _, products = self.db.catalog()
        q = tokens(query)
        results = [{
            "product_id": p["raw"]["product_id"], "name": p["raw"]["name"],
            "description": p["raw"]["description"],
            "score": len(q & tokens(projection(p, source_only=True))) / max(1, len(q)),
        } for p in products]
        return {"mode": "source-only lexical baseline", "results": sorted(
            results, key=lambda p: (-p["score"], p["product_id"]))[:3]}
