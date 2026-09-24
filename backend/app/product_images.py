import asyncio
import fcntl
import hashlib
import io
import json
import re
import sqlite3
from pathlib import Path

from PIL import Image

from .config import ROOT
from .db import canonical, digest, now
from .enrichment import PROMPTS, load_json
from .errors import AppError
from .events import event
from .moderation import Moderation
from .schemas import RawProduct

SIZE = "816x816"
QUALITY = "low"
LABEL = "AI-generated product illustration — fictional product, not verified appearance."


def save_manifest(path, manifest):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n")
    temporary.replace(path)


async def generate_product_images(settings, provider, *, retry_incomplete=False, destination=None, products=None):
    if settings.demo_mode != "live" or not settings.openai_api_key:
        raise AppError("LIVE_IMAGES_REQUIRED", "Product images require DEMO_MODE=live and OPENAI_API_KEY. No fixtures generated.")
    products = [RawProduct.model_validate(p) for p in (
        products if products is not None else load_json(ROOT / "data/seed/raw_products.json"))]
    if len({p.product_id for p in products}) != len(products):
        raise ValueError("Duplicate product IDs")
    destination = Path(destination) if destination else settings.product_image_dir
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / ".generation.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AppError("PRODUCT_IMAGES_BUSY", "Another product image generation process is running.", 409) from exc
        path = destination / "manifest.json"
        manifest = load_json(path) if path.exists() else {"version": 1, "images": {}}
        template = (PROMPTS / "product_image.txt").read_text()
        moderation = Moderation(settings, provider)
        generated, skipped = 0, 0
        for product in products:
            source = {"name": product.name, "description": product.description}
            key = digest({"product_id": product.product_id, "source": source, "prompt": template,
                          "model": settings.openai_image_model, "size": SIZE, "quality": QUALITY})
            image_path = destination / f"{key}.png"
            record = manifest["images"].get(key)
            if record and record["status"] == "completed":
                if not image_path.is_file() or hashlib.sha256(image_path.read_bytes()).hexdigest() != record["sha256"]:
                    raise AppError("PRODUCT_IMAGE_CORRUPT", f"Saved image for {product.product_id} is missing or changed.", 409, False)
                skipped += 1
                continue
            if record and not retry_incomplete:
                raise AppError("PRODUCT_IMAGE_INCOMPLETE",
                               f"{product.product_id} has an incomplete attempt. Inspect manifest, then use --retry-incomplete "
                               "to authorize another potentially billable request.", 409, False)
            prompt = template + "\n" + canonical(source)
            await moderation.screen(prompt, "image_prompt", key)
            record = {"product_id": product.product_id, "source": source, "model": settings.openai_image_model,
                      "size": SIZE, "quality": QUALITY, "label": LABEL, "mode": "live",
                      "status": "generating", "started_at": now(), "file": image_path.name}
            manifest["images"][key] = record
            save_manifest(path, manifest)
            try:
                data = await provider.image(prompt, size=SIZE, quality=QUALITY)
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != "PNG" or image.size != (816, 816):
                        raise AppError("PRODUCT_IMAGE_SIZE", "Provider output is not an 816x816 PNG.", 503, False)
                    image.verify()
                temporary = image_path.with_suffix(".tmp")
                temporary.write_bytes(data)
                temporary.replace(image_path)
                record.update(status="completed", completed_at=now(), sha256=hashlib.sha256(data).hexdigest())
                save_manifest(path, manifest)
            except (AppError, OSError, ValueError) as exc:
                record.update(status="failed", error=exc.code if isinstance(exc, AppError) else type(exc).__name__)
                save_manifest(path, manifest)
                raise
            generated += 1
            event("product_image_saved", product_id=product.product_id, generated=generated,
                  skipped=skipped, total=len(products), file=image_path.name)
            # Keep starts below the documented entry-tier five images per minute.
            if generated + skipped < len(products):
                await asyncio.sleep(13)
        return {"products": len(products), "generated": generated, "skipped": skipped,
                "size": SIZE, "quality": QUALITY, "manifest": str(path)}


class ProductImageCatalog:
    """Import generation manifests off the HTTP request path."""

    def __init__(self, db, directory):
        self.db, self.directory = db, directory
        self.signature = None
        self.verified = {}
        self.error = None

    def sync(self):
        path = self.directory / "manifest.json"
        if not path.exists():
            return
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        if signature == self.signature:
            return
        manifest = load_json(path)
        if manifest.get("version") != 1 or not isinstance(manifest.get("images"), dict):
            raise ValueError("Invalid product image manifest")
        with self.db.connect() as conn:
            products = {r["product_id"]: r for r in conn.execute("SELECT * FROM raw_products")}
            rows = []
            for key, record in manifest["images"].items():
                if record["status"] != "completed":
                    continue
                if not re.fullmatch(r"[0-9a-f]{64}", key) or record["file"] != f"{key}.png":
                    raise ValueError("Invalid product image filename")
                product = products.get(record["product_id"])
                if product is None:
                    continue
                raw = json.loads(product["source_json"])
                if record["source"] != {"name": raw["name"], "description": raw["description"]}:
                    continue
                if record["mode"] != "live" or record["size"] != SIZE or record["quality"] != QUALITY:
                    raise ValueError("Invalid product image provenance")
                fingerprint = digest(record)
                if self.verified.get(key) != fingerprint:
                    image_path = self.directory / record["file"]
                    if image_path.is_symlink():
                        raise ValueError("Product image cannot be a symlink")
                    data = image_path.read_bytes()
                    if hashlib.sha256(data).hexdigest() != record["sha256"]:
                        raise ValueError("Product image checksum mismatch")
                    with Image.open(io.BytesIO(data)) as image:
                        if image.format != "PNG" or image.size != (816, 816):
                            raise ValueError("Product image must be an 816x816 PNG")
                        image.verify()
                    self.verified[key] = fingerprint
                rows.append((key, record["product_id"], product["source_hash"], record["file"],
                             record["sha256"], record["completed_at"], "completed"))
            conn.executemany("INSERT OR REPLACE INTO product_images VALUES (?,?,?,?,?,?,?)", rows)
        self.signature = signature
        event("product_images_imported", completed=len(rows))

    def sync_logged(self):
        try:
            self.sync()
            self.error = None
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
            self.error = "PRODUCT_IMAGE_IMPORT_FAILED"
            event("product_image_import_failed", code=self.error, detail=str(exc))

    async def watch(self):
        while True:
            await asyncio.sleep(15)
            await asyncio.to_thread(self.sync_logged)

    def image(self, key):
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise AppError("NOT_FOUND", "Product image not found.", 404, False)
        with self.db.connect() as conn:
            row = conn.execute("""
                SELECT i.file_name FROM product_images i JOIN raw_products r USING(product_id)
                WHERE i.generation_key=? AND i.source_hash=r.source_hash AND i.status='completed'
            """, (key,)).fetchone()
        if row is None or row["file_name"] != f"{key}.png":
            raise AppError("NOT_FOUND", "Product image not found.", 404, False)
        path = self.directory / row["file_name"]
        if path.is_symlink() or not path.is_file():
            raise AppError("NOT_FOUND", "Product image file unavailable.", 404, False)
        return path
