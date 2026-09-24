import asyncio
import hashlib
import io
import json
import re
import sqlite3
import time

from PIL import Image

from .db import canonical, digest, now
from .enrichment import PROMPTS
from .errors import AppError
from .events import event
from .product_images import QUALITY, SIZE


class ColorImages:
    def __init__(self, db, settings, provider, moderation, catalog):
        self.db, self.settings, self.provider = db, settings, provider
        self.moderation, self.catalog = moderation, catalog
        self.directory = settings.product_image_dir / "colors"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.tasks = {}
        self.slot = asyncio.Semaphore(1)
        self.last_start = 0
        with db.connect() as conn:
            for row in conn.execute("SELECT state_json FROM product_color_images").fetchall():
                state = json.loads(row[0])
                if state["status"] in ("queued", "running"):
                    self.fail(state, "PROCESS_RESTARTED", "Color image generation was interrupted. Retry may incur another charge.")

    def save(self, state):
        with self.db.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO product_color_images VALUES (?,?,?,?,?)",
                         (state["key"], state["product_id"], state["color"], state["base_key"], canonical(state)))

    def get(self, key):
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise AppError("NOT_FOUND", "Color image not found.", 404, False)
        with self.db.connect() as conn:
            row = conn.execute("SELECT state_json FROM product_color_images WHERE generation_key=?", (key,)).fetchone()
        if not row:
            raise AppError("NOT_FOUND", "Color image not found.", 404, False)
        return json.loads(row[0])

    @staticmethod
    def public(state):
        return {k: state[k] for k in ("key", "status", "image_url", "color", "error")}

    def spec(self, product_id, color):
        with self.db.connect() as conn:
            row = conn.execute("""
                SELECT r.source_json, r.source_hash, c.facts_json, i.generation_key, i.sha256
                FROM raw_products r JOIN commerce c USING(product_id) JOIN product_images i USING(product_id)
                WHERE r.product_id=? AND i.source_hash=r.source_hash
                ORDER BY i.completed_at DESC, i.generation_key LIMIT 1
            """, (product_id,)).fetchone()
        if not row:
            raise AppError("PRODUCT_REFERENCE_MISSING", "Generate the base product image first.", 409, False)
        if color not in {v["color"] for v in json.loads(row["facts_json"])["variants"]}:
            raise AppError("INVALID_COLOR", "Color is not in the product catalog.", 422, False)
        raw = json.loads(row["source_json"])
        prompt = (PROMPTS / "product_color.txt").read_text() + "\n" + canonical({
            "name": raw["name"], "description": raw["description"], "target_color": color,
        })
        key = digest({"product_id": product_id, "color": color, "base_key": row["generation_key"],
                      "base_sha256": row["sha256"], "source_hash": row["source_hash"], "prompt": prompt,
                      "model": self.settings.openai_image_model, "size": SIZE, "quality": QUALITY})
        return key, row, prompt

    def ensure(self, product_id, color):
        key, base, prompt = self.spec(product_id, color)
        with self.db.connect() as conn:
            row = conn.execute("SELECT state_json FROM product_color_images WHERE generation_key=?", (key,)).fetchone()
        if row:
            state = json.loads(row[0])
            if state["status"] == "completed" and not (self.directory / f"{key}.png").is_file():
                self.fail(state, "COLOR_IMAGE_MISSING", "Saved color image is missing. Retry to regenerate.")
            return state
        state = {"key": key, "product_id": product_id, "color": color, "base_key": base["generation_key"],
                 "base_sha256": base["sha256"], "prompt": prompt, "status": "queued", "image_url": None,
                 "error": None, "sha256": None, "created_at": now()}
        self.enqueue(state)
        return state

    def enqueue(self, state):
        if len(self.tasks) >= 20:
            self.fail(state, "COLOR_QUEUE_FULL", "Color image queue is full. Retry shortly.")
            return
        state.update(status="queued", error=None, image_url=None)
        self.save(state)
        task = asyncio.create_task(self.run(state))
        self.tasks[state["key"]] = task
        task.add_done_callback(lambda _: self.tasks.pop(state["key"], None))

    def decorate(self, cards):
        for card in cards:
            card["color_image"] = None
            if self.settings.demo_mode == "fixture":
                continue
            try:
                state = self.ensure(card["product_id"], card["variant"]["color"])
                card.update(image_url=state["image_url"], color_image=self.public(state))
            except AppError as exc:
                event("color_image_unavailable", product_id=card["product_id"], code=exc.code)
                card["color_image"] = {"key": None, "status": "unavailable", "image_url": None,
                                       "color": card["variant"]["color"], "error": exc.payload()}
        return cards

    def retry(self, key):
        if self.settings.demo_mode != "live":
            raise AppError("LIVE_IMAGES_REQUIRED", "Color editing is available only in live mode.", 409, False)
        state = self.get(key)
        if state["status"] != "failed":
            return self.public(state)
        current, _, _ = self.spec(state["product_id"], state["color"])
        if current != key:
            raise AppError("PRODUCT_REFERENCE_CHANGED", "Product reference changed. Search again.", 409, False)
        self.enqueue(state)
        return self.public(state)

    def fail(self, state, code, message):
        state.update(status="failed", image_url=None, error={"code": code, "message": message, "retryable": True})
        self.save(state)
        event("color_image_failed", key=state["key"], code=code)

    async def run(self, state):
        try:
            async with self.slot:
                # Serialize and pace new edits; never automatically repeat an uncertain billable call.
                await asyncio.sleep(max(0, 13 - (time.monotonic() - self.last_start)))
                state["status"] = "running"
                self.save(state)
                source = self.catalog.image(state["base_key"]).read_bytes()
                if hashlib.sha256(source).hexdigest() != state["base_sha256"]:
                    raise AppError("PRODUCT_REFERENCE_CHANGED", "Base image changed. Search again.", 409, False)
                await self.moderation.screen(state["prompt"], "image_prompt", state["key"])
                await self.moderation.screen_photo(source, state["key"])
                self.last_start = time.monotonic()
                self.db.reserve_image_call(self.settings.daily_image_call_limit, "product_color")
                data = await self.provider.edit_image(state["prompt"], source, size=SIZE, quality=QUALITY)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != "PNG" or image.size != (816, 816):
                        raise AppError("INVALID_COLOR_IMAGE", "Color edit must be an 816x816 PNG.", 503, False)
                    image.verify()
                await self.moderation.screen_photo(data, state["key"])
                path = self.directory / f"{state['key']}.png"
                temporary = path.with_suffix(".tmp")
                temporary.write_bytes(data)
                temporary.replace(path)
                state.update(status="completed", image_url=f"/api/product-color-images/{state['key']}.png",
                             sha256=hashlib.sha256(data).hexdigest(), error=None)
                self.save(state)
                event("color_image_completed", key=state["key"], product_id=state["product_id"], color=state["color"])
        except AppError as exc:
            self.fail(state, exc.code, exc.message)
        except (OSError, ValueError, sqlite3.Error) as exc:
            self.fail(state, "COLOR_IMAGE_FAILED", "Unable to prepare color image. Retry may incur another charge.")
            event("color_image_error", key=state["key"], error=type(exc).__name__)
        except asyncio.CancelledError:
            self.fail(state, "PROCESS_STOPPED", "Color generation interrupted. Retry may incur another charge.")
            raise

    def image(self, key):
        state = self.get(key)
        path = self.directory / f"{key}.png"
        if state["status"] != "completed" or path.is_symlink() or not path.is_file():
            raise AppError("NOT_FOUND", "Color image is not ready.", 404, False)
        return path

    def references(self, variants):
        _, products = self.db.catalog()
        references = []
        for vid in variants:
            match = next(((p, v) for p in products for v in p["commerce"]["variants"] if v["variant_id"] == vid), None)
            if not match:
                raise AppError("NOT_FOUND", "Selected variant not found.", 404, False)
            product, variant = match
            key, _, _ = self.spec(product["raw"]["product_id"], variant["color"])
            try:
                state = self.get(key)
            except AppError as exc:
                raise AppError("PRODUCT_IMAGES_PENDING", "Wait for selected color images before generating an outfit.", 409) from exc
            if state["status"] != "completed":
                raise AppError("PRODUCT_IMAGES_PENDING", "Selected color images are not ready. Check their status.", 409)
            data = self.image(key).read_bytes()
            if hashlib.sha256(data).hexdigest() != state["sha256"]:
                raise AppError("PRODUCT_REFERENCE_CHANGED", "Product image integrity check failed.", 409, False)
            references.append({"key": key, "sha256": state["sha256"], "variant_id": vid,
                               "color": variant["color"], "data": data})
        return references

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
