import asyncio
import hashlib
import struct
import zlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from .db import digest, now
from .demo_person import load_demo_person
from .enrichment import PROMPTS
from .errors import AppError
from .events import event
from .journey import Journey
from .photos import PRIVATE_TTL_SECONDS, decode_photo, normalize_image

IMAGE_LABEL = "AI outfit concept — appearance and fit may differ."
TRY_ON_LABEL = "AI virtual try-on — visual reference only; appearance may differ. No size or fit prediction."
SAMPLE_LABEL = "AI-generated fictional adult — sample model, not a real shopper."
PRIVATE_KINDS = ("try_on", "sample_person")


def fixture_png():
    """A static diagram fixture, deliberately not represented as GPT-Image output."""
    width, height = 320, 320
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            garment = (100 < x < 220 and 80 < y < 210) or (115 < x < 155 and 210 <= y < 295) \
                or (165 < x < 205 and 210 <= y < 295)
            head = (x - 160) ** 2 + (y - 48) ** 2 < 22 ** 2
            row.extend((99, 103, 107) if garment else (171, 164, 152) if head else (247, 244, 239))
        rows.append(b"\x00" + row)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")


class Images:
    def __init__(self, db, settings, provider, moderation, color_images=None):
        self.db, self.settings, self.provider, self.moderation = db, settings, provider, moderation
        self.color_images = color_images
        self.tasks = set()
        self.job_tasks = {}
        self.private_images: dict[str, bytes] = {}
        settings.image_dir.mkdir(parents=True, exist_ok=True)
        for job in db.jobs():
            if job["status"] in ("queued", "running") or (
                job.get("kind") in PRIVATE_KINDS and job["status"] == "completed"
            ):
                job.update(status="failed", image_url=None, media_id=None, error={
                    "code": "PROCESS_RESTARTED", "message": "Generation interrupted. Please retry.", "retryable": True})
                db.save_job(job)

    def prompt_and_key(self, variants, kind="concept"):
        _, products = self.db.catalog()
        selected = []
        for vid in variants:
            match = next(((p, v) for p in products for v in p["commerce"]["variants"] if v["variant_id"] == vid), None)
            if not match:
                raise AppError("NOT_FOUND", "Selected variant not found.", 404, False)
            p, v = match
            if v["stock"] <= 0:
                raise AppError("UNAVAILABLE_VARIANT", "Selected variant is unavailable.", 409)
            selected.append((p, v))
        template = (PROMPTS / {"try_on": "try_on.txt", "concept": "outfit.txt",
                               "sample_person": "sample_person.txt"}[kind]).read_text()
        prompt = template + "\n" + "\n".join(
            f"{v['color']} {p['raw']['category']}: {p['raw']['description']}" for p, v in selected)
        key = digest({
            "variants": sorted((v["variant_id"], p["source_hash"]) for p, v in selected),
            "model": self.settings.openai_image_model, "prompt_version": digest(template),
            "quality": self.settings.openai_image_quality,
            "mode": self.settings.demo_mode,
            "kind": kind,
        })
        return prompt, key

    async def create(self, session, request_id, variant_ids, *, explicit=False, photo_base64=None, consent=False,
                     sample_person=False, sample_job_id=None, fixed_sample=False):
        self.expire_private()
        if not explicit:
            raise AppError("EXPLICIT_ACTION_REQUIRED", "Use the image button to confirm image generation.", 409, False)
        if not sample_person and sorted(variant_ids) != sorted(session.selected_variant_ids):
            raise AppError("SELECTION_CHANGED", "Save this outfit selection before generating.", 409)
        if len(set(variant_ids)) != len(variant_ids):
            raise AppError("INVALID_SELECTION", "Duplicate variants are not allowed.", 422, False)
        kind = "sample_person" if sample_person else "try_on" if photo_base64 is not None or sample_job_id or fixed_sample else "concept"
        if photo_base64 is not None and consent is not True:
            raise AppError("PHOTO_CONSENT_REQUIRED", "Confirm photo rights and OpenAI processing consent first.", 422, False)
        prompt, key = self.prompt_and_key(variant_ids, kind)
        photo = None
        if sample_person:
            key = digest([key, str(session.session_id)])
        elif fixed_sample:
            photo = load_demo_person()
            key = digest([key, str(session.session_id), "fixed_demo", hashlib.sha256(photo).hexdigest()])
            await self.moderation.screen_photo(photo, str(request_id))
        elif sample_job_id:
            sample = self.get(session.session_id, sample_job_id)
            if sample.get("kind") != "sample_person" or sample["status"] != "completed":
                raise AppError("SAMPLE_UNAVAILABLE", "Generate a new sample person before trying on clothes.", 409)
            photo = self.private_media(session.session_id, sample_job_id)
            key = digest([key, str(session.session_id), str(sample_job_id)])
            await self.moderation.screen_photo(photo, str(request_id))
        elif kind == "try_on":
            photo = await asyncio.to_thread(decode_photo, photo_base64)
            key = digest([key, str(session.session_id), hashlib.sha256(photo).hexdigest()])
            await self.moderation.screen_photo(photo, str(request_id))
        if not sample_person:
            Journey(self.db).require_preview(session)
        references = []
        if self.settings.demo_mode == "live" and not sample_person:
            if self.color_images is None:
                raise AppError("PRODUCT_REFERENCE_MISSING", "Product image references are unavailable.", 409, False)
            references = self.color_images.references(variant_ids)
            if not references:
                raise AppError("PRODUCT_REFERENCE_MISSING", "Select products with completed color images.", 409, False)
            key = digest([key, [(r["key"], r["sha256"]) for r in references]])
            offset = 2 if photo is not None else 1
            prompt += "\nReference image mapping:\n" + "\n".join(
                f"Image {index}: {reference['variant_id']}, catalog color {reference['color']}."
                for index, reference in enumerate(references, offset))
        await self.moderation.screen(prompt, "image_prompt", str(request_id))
        jobs = self.db.jobs()
        duplicate = next((j for j in jobs if j["request_id"] == str(request_id)), None)
        if duplicate:
            if duplicate["session_id"] != str(session.session_id) or duplicate["cache_key"] != key:
                raise AppError("REQUEST_CONFLICT", "Request ID belongs to a different selection.", 409, False)
            return duplicate
        own = [j for j in jobs if j["session_id"] == str(session.session_id)]
        if any(j["status"] in ("queued", "running") for j in own):
            raise AppError("IMAGE_ACTIVE", "An outfit image is already being generated.", 409)
        if kind in PRIVATE_KINDS and sum(j.get("kind") in PRIVATE_KINDS and j["status"] != "failed" for j in jobs) >= 20:
            raise AppError("PHOTO_CAPACITY", "Photo preview capacity reached. Remove old previews or retry later.", 429)
        cached = next((j for j in jobs if kind == "concept" and j.get("kind", "concept") == "concept"
                       and j["status"] == "completed" and j["cache_key"] == key
                       and (self.settings.image_dir / f"{j['media_id']}.png").is_file()), None)
        if not cached and sum(not j["cached"] for j in own) >= 5:
            raise AppError("IMAGE_LIMIT", "This demo session allows five new images. Start a new session.", 429, False)
        job = {
            "job_id": str(uuid4()), "session_id": str(session.session_id), "request_id": str(request_id),
            "variant_ids": variant_ids, "cache_key": key, "status": "completed" if cached else "queued",
            "image_url": cached["image_url"] if cached else None, "media_id": cached["media_id"] if cached else None,
            "error": None, "cached": bool(cached), "created_at": now(),
            "label": {"try_on": TRY_ON_LABEL, "concept": IMAGE_LABEL, "sample_person": SAMPLE_LABEL}[kind],
            "mode": self.settings.demo_mode, "kind": kind,
            "expires_at": (datetime.now(UTC) + timedelta(seconds=PRIVATE_TTL_SECONDS)).isoformat()
                if kind in PRIVATE_KINDS else None,
            "consent_version": "photo-v1" if photo_base64 is not None else None,
            "sample_job_id": str(sample_job_id) if sample_job_id else None,
            "fixed_sample": fixed_sample,
            "product_references": [{k: r[k] for k in ("key", "sha256", "variant_id", "color")} for r in references],
        }
        self.db.save_job(job)
        self.db.record_event(session.session_id, f"image:{job['job_id']}", "visualization_requested",
                             {"kind": kind, "cached": bool(cached)})
        event("image_job", job_id=job["job_id"], session_id=job["session_id"], cached=bool(cached))
        if not cached:
            task = asyncio.create_task(self.run(job, prompt, photo, references))
            self.tasks.add(task)
            self.job_tasks[job["job_id"]] = task
            task.add_done_callback(self.tasks.discard)
            task.add_done_callback(lambda _: self.job_tasks.pop(job["job_id"], None))
        return job

    async def run(self, job, prompt, photo=None, references=None):
        try:
            job["status"] = "running"
            self.db.save_job(job)
            if self.settings.demo_mode == "fixture":
                await asyncio.sleep(.2)
                data = fixture_png()
            elif references:
                garments = [r["data"] for r in references]
                for garment in garments:
                    await self.moderation.screen_photo(garment, job["request_id"])
                self.db.reserve_image_call(self.settings.daily_image_call_limit, job["kind"])
                source = photo if photo is not None else garments[0]
                additional = garments if photo is not None else garments[1:]
                data = await self.provider.edit_image(prompt, source, references=additional)
            elif photo is not None:
                raise AppError("PRODUCT_REFERENCE_MISSING", "Product image references are required.", 409, False)
            else:
                self.db.reserve_image_call(self.settings.daily_image_call_limit, job["kind"])
                data = await self.provider.image(prompt)
            media_id = str(uuid4())
            if job.get("kind") in PRIVATE_KINDS:
                data = await asyncio.to_thread(normalize_image, data, max_bytes=10 * 1024 * 1024)
                if job["kind"] == "sample_person":
                    await self.moderation.screen_photo(data, job["request_id"])
                self.private_images[media_id] = data
                image_url = f"/api/sessions/{job['session_id']}/outfits/{job['job_id']}/image"
            else:
                (self.settings.image_dir / f"{media_id}.png").write_bytes(data)
                image_url = f"/api/media/{media_id}.png"
            job.update(status="completed", media_id=media_id, image_url=image_url)
        except AppError as exc:
            job.update(status="failed", error=exc.payload())
        except OSError:
            job.update(status="failed", error={
                "code": "IMAGE_STORAGE_FAILED", "message": "Unable to save image. Please retry.", "retryable": True})
            event("image_storage_error", job_id=job["job_id"])
        except asyncio.CancelledError:
            job.update(status="failed", image_url=None, error={
                "code": "PROCESS_STOPPED", "message": "Generation interrupted. Please retry.", "retryable": True})
            raise
        finally:
            job["finished_at"] = now()
            self.db.save_job(job)
            self.db.record_event(job["session_id"], f"image-finished:{job['job_id']}",
                                 f"visualization_{job['status']}", {"kind": job["kind"]})
            event("image_job_status", job_id=job["job_id"], status=job["status"], error=job["error"])

    def get(self, session_id, job_id):
        self.expire_private()
        job = next((j for j in self.db.jobs(session_id) if j["job_id"] == str(job_id)), None)
        if not job:
            raise AppError("NOT_FOUND", "Image job not found.", 404, False)
        return job

    def expire_private(self):
        for job in self.db.jobs():
            if job.get("kind") in PRIVATE_KINDS and job["status"] == "completed" and (
                datetime.fromisoformat(job["expires_at"]) <= datetime.now(UTC)
                or job["media_id"] not in self.private_images
            ):
                self.private_images.pop(job["media_id"], None)
                job.update(status="failed", image_url=None, media_id=None, error={
                    "code": "TRY_ON_EXPIRED", "message": "Private preview expired. Generate a new try-on.", "retryable": True})
                self.db.save_job(job)

    async def sweep_private(self):
        while True:
            await asyncio.sleep(30)
            self.expire_private()

    def private_media(self, session_id, job_id):
        job = self.get(session_id, job_id)
        image = self.private_images.get(job["media_id"])
        if job.get("kind") not in PRIVATE_KINDS or job["status"] != "completed" or not image:
            raise AppError("NOT_FOUND", "Private try-on image is unavailable or expired.", 404, False)
        return image

    async def remove_private(self, session_id):
        jobs = [j for j in self.db.jobs(session_id) if j.get("kind") in PRIVATE_KINDS]
        pending = [self.job_tasks[j["job_id"]] for j in jobs if j["job_id"] in self.job_tasks]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for job in jobs:
            self.private_images.pop(job["media_id"], None)
            job.update(status="failed", image_url=None, media_id=None, error={
                "code": "PHOTO_REMOVED", "message": "Photo-derived preview removed.", "retryable": False})
            self.db.save_job(job)
        return {"removed": len(jobs)}

    async def close(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.private_images.clear()
        self.expire_private()
