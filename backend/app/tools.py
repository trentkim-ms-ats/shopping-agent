import re
from uuid import uuid4

from .enrichment import profiles
from .errors import AppError
from .journey import Journey
from .retrieval import attributes, available_variants, card, matched_attr, recommendation_summary
from .schemas import PRIORITY_CHOICES, Intent

QUESTION = "What matters most for your hike?"
CHOICES = list(PRIORITY_CHOICES)


class Tools:
    def __init__(self, db, retrieval, images):
        self.db, self.retrieval, self.images = db, retrieval, images
        self.journey = Journey(db)

    def product(self, product_id):
        _, products = self.db.catalog()
        product = next((p for p in products if p["raw"]["product_id"] == product_id), None)
        if product is None:
            raise AppError("NOT_FOUND", "Product not found.", 404, False)
        return product

    def variant(self, variant_id):
        _, products = self.db.catalog()
        return next(((p, v) for p in products for v in p["commerce"]["variants"]
                     if v["variant_id"] == variant_id), None)

    def offered(self, session):
        """The most recent list shown to the shopper, numbered exactly as the chat shows it."""
        options = []
        for variant_id in session.last_variant_ids:
            match = self.variant(variant_id)
            if not match:
                continue
            product, variant = match
            options.append({
                "position": len(options) + 1, "product_id": product["raw"]["product_id"],
                "name": product["raw"]["name"], "category": product["raw"]["category"],
                "variant_id": variant_id, "color": variant["color"], "size": variant["size"],
            })
        return options

    def remember(self, session, results):
        """Ordinals always refer to the latest list, so positions never drift from the screen."""
        session.last_variant_ids = list(dict.fromkeys(
            r["variant"]["variant_id"] for r in results if r.get("variant")))[:12]

    def context(self, session):
        context = {
            "profile": profiles()[session.profile_id].model_dump(), "demo_season": "fall",
            "intent": session.intent.model_dump(), "intent_sources": session.intent_sources,
            "selected_variant_ids": session.selected_variant_ids, "last_result_ids": session.last_result_ids,
            "clarification_asked": session.clarification_asked,
        }
        if self.db is not None:
            context["offered_options"] = self.offered(session)
            context["selection_state"] = self.journey.selection(session)
        return context

    async def search(self, session, intent: Intent, *, explicit_text=""):
        previous = session.intent.model_dump()
        mention_patterns = {
            "season": r"\b(fall|autumn|spring|summer|winter)\b|가을|봄|여름|겨울",
            "category": r"\b(jacket|shell|pants|midlayer|accessory)\b|재킷|자켓|바지",
            "activity": r"\b(hik\w*|walk\w*)\b|등산|하이킹|산책",
            "max_price_cents": r"\$\s*\d|budget|under\s+\d|예산|달러",
            "size": r"\bsize\b|사이즈",
            "priority": r"rain|drizzle|warm|lightweight|skip|보온|경량|비|건너",
            "color": r"\b(black|slate|stone|sand|red|moss)\b",
        }
        for key, value in intent.model_dump().items():
            if value != previous[key] or (key in mention_patterns and re.search(
                mention_patterns[key], explicit_text, re.IGNORECASE,
            )):
                session.intent_sources[key] = "user"
        session.intent = intent
        if not intent.priority and not session.clarification_asked:
            session.clarification_asked = True
            return {"clarification": True, "question": QUESTION, "choices": CHOICES, "results": []}
        results = await self.retrieval.search(intent, profiles()[session.profile_id])
        session.last_result_ids = [r["product_id"] for r in results["results"]]
        self.remember(session, results["results"])
        return results

    def compare(self, product_ids, session=None):
        products = [self.product(pid) for pid in product_ids]
        result = {
            "product_ids": product_ids,
            "columns": [{"product_id": p["raw"]["product_id"], "name": p["raw"]["name"]} for p in products],
            "rows": [
                {"label": "Price", "values": [f"${p['commerce']['price_cents'] / 100:.2f}" for p in products]},
                {"label": "Source colors", "values": [", ".join(p["raw"]["colors"]) for p in products]},
                {"label": "Source sizes", "values": [", ".join(p["raw"]["sizes"]) for p in products]},
                {"label": "Description", "values": [p["raw"]["description"] for p in products]},
                {"label": "Supported benefits", "values": [
                    ", ".join(a["value"] for a in attributes(p) if a["kind"] == "benefits") or "Not specified"
                    for p in products]},
                {"label": "Waterproof rating", "values": ["Not specified"] * len(products)},
                {"label": "Temperature rating", "values": ["Not specified"] * len(products)},
            ],
            "evidence": [a for p in products for a in attributes(p)],
        }
        if session:
            intent = session.intent
            variants = [available_variants(p, intent, profiles()[session.profile_id]) for p in products]
            options = [card(p, vs[0]) for p, vs in zip(products, variants, strict=True) if vs]
            priority = {"light_rain": "light rain protection", "warmth": "warmth",
                        "lightweight": "lightweight"}.get(intent.priority)
            result["rows"][1:1] = [
                {"label": "Available option for you", "values": [
                    f"{vs[0]['color']} / {vs[0]['size']} · In stock" if vs else "No option meets your size/color"
                    for vs in variants]},
                {"label": "Jacket budget", "values": [
                    "Within budget" if intent.max_price_cents is None or
                    p["commerce"]["price_cents"] <= intent.max_price_cents else "Above budget" for p in products]},
                {"label": f"Your priority: {priority or 'balanced'}", "values": [
                    "; ".join(a["value"] for a in matched_attr(p, "benefits", priority)) or
                    "Not specified in approved attributes" if priority else "Compare the source-backed details below"
                    for p in products]},
                {"label": "Packability evidence", "values": [
                    "; ".join(a["value"] for a in attributes(p)
                              if a["kind"] == "use_cases" and "pack" in a["value"].lower()) or "Not specified"
                    for p in products]},
            ]
            result.update(options=options, constraints=intent.model_dump(),
                          price_difference_cents=max(p["commerce"]["price_cents"] for p in products) -
                          min(p["commerce"]["price_cents"] for p in products))
        return result

    def selection(self, session, variant_ids):
        if len(set(variant_ids)) != len(variant_ids):
            raise AppError("INVALID_SELECTION", "Choose distinct variants.", 422, False)
        _, products = self.db.catalog()
        found, seen_products = [], set()
        for vid in variant_ids:
            match = next(((p, v) for p in products for v in p["commerce"]["variants"] if v["variant_id"] == vid), None)
            if not match:
                raise AppError("NOT_FOUND", "Selected variant not found.", 404, False)
            p, v = match
            if v["stock"] <= 0:
                raise AppError("UNAVAILABLE_VARIANT", "A selected variant is out of stock.", 409)
            if p["raw"]["product_id"] in seen_products:
                raise AppError("INVALID_SELECTION", "Choose one variant per product.", 422, False)
            seen_products.add(p["raw"]["product_id"])
            found.append(card(p, v))
        session.selected_variant_ids = variant_ids
        return {"items": found, "variant_ids": variant_ids,
                "product_ids": [item["product_id"] for item in found]}

    async def select(self, session, variant_ids):
        """Conversational selection: same side effects as the REST path, driven by the agent."""
        previous = self.db.session(session.session_id).selected_variant_ids
        result = self.selection(session, variant_ids)
        if previous != session.selected_variant_ids:
            await self.images.remove_private(session.session_id)
            with self.db.connect() as conn:
                conn.execute("DELETE FROM selection_confirmations WHERE session_id=?", (str(session.session_id),))
            self.db.record_event(session.session_id, str(uuid4()), "item_selected",
                                 {"variant_ids": session.selected_variant_ids})
        result["selection_state"] = self.journey.selection(session)
        return result

    def confirm(self, session, accept_exceptions):
        state = self.journey.selection(session)
        return {"selection_state": self.journey.confirm(session, state["revision"], accept_exceptions)}

    def feedback(self, session, helpful):
        state = self.journey.selection(session)
        self.journey.feedback(session, state["revision"], helpful)
        return {"helpful": helpful, "selection_state": self.journey.selection(session)}

    async def preview(self, session, request_id, variant_ids):
        if sorted(variant_ids) != sorted(session.selected_variant_ids):
            raise AppError("SELECTION_CHANGED", "Select these items before previewing them.", 409)
        self.journey.require_preview(session)
        return await self.images.create(session, request_id, variant_ids, explicit=True, fixed_sample=True)

    async def complements(self, session, selected_id):
        jacket = self.product(selected_id)
        if jacket["raw"]["category"] != "jacket":
            raise AppError("INVALID_SELECTION", "Select a jacket before completing your outfit.", 409, False)
        selected = [v for v in jacket["commerce"]["variants"] if v["variant_id"] in session.selected_variant_ids]
        if not selected or not selected[0]["stock"]:
            raise AppError("SELECTION_REQUIRED", "Select an available jacket first.", 409, False)
        profile = profiles()[session.profile_id]
        _, products = self.db.catalog()
        excluded = set(profile.owned_product_ids) | {selected_id} | {
            p["raw"]["product_id"] for p in products
            if any(v["variant_id"] in session.selected_variant_ids for v in p["commerce"]["variants"])
        }
        # Jacket-only price, rain and color requirements are not outfit-wide requirements.
        intent = session.intent.model_copy(update={
            "category": None, "max_price_cents": None, "required_benefits": [], "color": None,
            "preferred_benefits": [], "priority": "balanced",
        })
        result = await self.retrieval.search(intent, profile, exclude=excluded, limit=len(products))
        chosen, categories = [], set()
        for item in result["results"]:
            if item["category"] == "jacket" or item["category"] in categories:
                continue
            p = self.product(item["product_id"])
            variants = available_variants(p, intent, profile)
            same_color = next((v for v in variants if v["color"] == selected[0]["color"]), None)
            if same_color:
                item["variant"] = same_color
                item["match_summary"] = recommendation_summary(p, same_color, item["reasons"], intent, profile)
            item["compatibility"] = {
                "category": f"Complements your jacket with a {item['category']}.",
                "color": "Same catalog color as your jacket." if same_color else
                    f"Styling suggestion: {item['variant']['color']} with {selected[0]['color']}.",
                "activity_evidence": [a for a in item["reasons"] if a["kind"] == "activities"],
            }
            chosen.append(item)
            categories.add(item["category"])
            if len(chosen) == 2:
                break
        self.remember(session, chosen)
        return {**result, "results": chosen, "notice": "Prices are per item; jacket budget is not an outfit budget."}
