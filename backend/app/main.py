import asyncio
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from starlette.responses import Response

from .agent import Agent
from .color_images import ColorImages
from .config import ROOT, Settings
from .db import Database, canonical, digest, now
from .demo_person import load_demo_person
from .enrichment import load_json, profiles
from .errors import AppError
from .events import event
from .images import PRIVATE_KINDS, Images
from .journey import Journey
from .moderation import Moderation
from .photos import MAX_REQUEST_BYTES
from .product_images import ProductImageCatalog
from .provider import Provider
from .retrieval import Retrieval, attributes
from .schemas import (
    ComplementRequest,
    ConfirmSelection,
    CreateSession,
    Intent,
    JourneyFeedback,
    JourneyObservation,
    MessageRequest,
    OutfitRequest,
    RelaxRequest,
    SamplePersonRequest,
    SampleTryOnRequest,
    SelectionRequest,
    Session,
    TryOnRequest,
)
from .tools import Tools


def create_app(settings=None, provider=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        settings.require_live_config()
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        db = Database(settings.database_path)
        mode = db.meta("publication_mode")
        if mode and mode != settings.demo_mode:
            raise RuntimeError("Catalog mode mismatch. Never serve replay enrichment as live.")
        actual_provider = provider or Provider(settings)
        moderation = Moderation(settings, actual_provider)
        retrieval = Retrieval(db, settings, actual_provider)
        product_images = ProductImageCatalog(db, settings.product_image_dir)
        await asyncio.to_thread(product_images.sync_logged)
        color_images = ColorImages(db, settings, actual_provider, moderation, product_images)
        app.state.color_images = color_images
        images = Images(db, settings, actual_provider, moderation, color_images)
        tools = Tools(db, retrieval, images)
        app.state.db, app.state.images, app.state.tools = db, images, tools
        app.state.journey = Journey(db)
        app.state.agent = Agent(settings, actual_provider, moderation, tools)
        app.state.moderation, app.state.retrieval = moderation, retrieval
        app.state.locks = {}
        app.state.photo_slots = asyncio.Semaphore(4)
        app.state.product_images = product_images
        product_image_sync = asyncio.create_task(product_images.watch())
        private_cleanup = asyncio.create_task(images.sweep_private())
        # The single-worker process owns pending requests; none can survive restart.
        with db.connect() as conn:
            conn.execute("DELETE FROM message_requests WHERE response_json IS NULL")
        yield
        product_image_sync.cancel()
        await asyncio.gather(product_image_sync, return_exceptions=True)
        private_cleanup.cancel()
        await asyncio.gather(private_cleanup, return_exceptions=True)
        await images.close()
        await color_images.close()
        if actual_provider.client:
            await actual_provider.client.close()

    app = FastAPI(title="Trailshop", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[settings.allowed_origin],
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def request_ids(request, call_next):
        start = time.monotonic()
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        if "/try-ons" in request.url.path or "/outfits/" in request.url.path or "/sample-people" in request.url.path:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        event("http_request", request_id=request.state.request_id, method=request.method,
              path=request.url.path, status=response.status_code, duration_ms=round((time.monotonic() - start) * 1000, 2))
        return response

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(status_code=exc.status, content={
            "error": exc.payload(), "request_id": request.state.request_id})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={
            "error": {"code": "VALIDATION_ERROR", "message": "Request does not match the API contract.", "retryable": False},
            "request_id": request.state.request_id})

    def lock_for(session_id):
        app.state.db.session(session_id)
        return app.state.locks.setdefault(str(session_id), asyncio.Lock())

    @app.get("/api/health")
    def health():
        version, catalog = app.state.db.catalog()
        manifest = app.state.db.meta("index_manifest")
        return {"readiness": "ready" if catalog else "seed_required", "catalog_version": version,
                "index_version": manifest["version"] if manifest else None, "mode": settings.demo_mode,
                "models": settings.models(), "products": len(catalog),
                "product_image_import_error": app.state.product_images.error,
                "label": "Replay — simulated API outputs" if settings.demo_mode == "fixture" else "Live OpenAI APIs"}

    @app.post("/api/sessions", status_code=201)
    def create_session(body: CreateSession):
        profile = profiles()[body.profile_id]
        intent = Intent(category="jacket", activity=None, season=settings.demo_season, priority=None,
                        max_price_cents=profile.budget_cents, size=profile.preferred_size, color=None,
                        require_in_stock=True, required_benefits=[], preferred_benefits=[])
        session = Session(session_id=uuid4(), profile_id=profile.profile_id, intent=intent,
                          intent_sources={"size": "profile", "max_price_cents": "profile", "season": "demo_context"},
                          last_result_ids=[], selected_variant_ids=[], clarification_asked=False,
                          messages=[], created_at=now())
        app.state.db.save_session(session)
        app.state.db.record_event(session.session_id, "start", "journey_started", {"mode": settings.demo_mode})
        return {"session_id": str(session.session_id), "profile": profile.model_dump(),
                "intent": intent.model_dump(), "demo_context": {"season": "fall", "scenario": "Northern Hemisphere"}}

    @app.post("/api/sessions/{session_id}/messages")
    async def message(session_id: UUID, body: MessageRequest, request: Request):
        request.state.request_id = str(body.request_id)
        lock = lock_for(session_id)
        if lock.locked():
            raise AppError("SESSION_BUSY", "Another request is pending. Retry shortly.", 409)
        async with lock:
            db = app.state.db
            text_hash = digest({"text": body.text, "priority_choice": True}) if body.priority_choice else digest(body.text)
            with db.connect() as conn:
                saved = conn.execute("SELECT * FROM message_requests WHERE session_id=? AND request_id=?",
                                     (str(session_id), str(body.request_id))).fetchone()
            if saved:
                if saved["text_hash"] != text_hash:
                    raise AppError("REQUEST_CONFLICT", "Request ID was already used with different text.", 409, False)
                if saved["response_json"]:
                    result = json.loads(saved["response_json"])
                    color_images = app.state.color_images
                    color_images.decorate(result["cards"])
                    color_images.decorate(result["complements"])
                    color_images.decorate(result.get("selected") or [])
                    result["selection_state"] = app.state.journey.selection(db.session(session_id))
                    return result
                raise AppError("REQUEST_PENDING", "Request is pending. Retry shortly.", 409)
            session = db.session(session_id)
            try:
                async with asyncio.timeout(45):
                    await app.state.moderation.screen(body.text, "user_input", body.request_id)
                    with db.connect() as conn:
                        conn.execute("INSERT INTO message_requests VALUES (?,?,?,NULL)",
                                     (str(session_id), str(body.request_id), text_hash))
                    if body.priority_choice:
                        result = await app.state.agent.choose_priority(session, body.text, body.request_id)
                    else:
                        result = await app.state.agent.turn(session, body.text, body.request_id)
                    if db.session(session_id).intent != session.intent:
                        await app.state.images.remove_private(session_id)
                        with db.connect() as conn:
                            conn.execute("DELETE FROM selection_confirmations WHERE session_id=?", (str(session_id),))
                    result["selection_state"] = app.state.journey.selection(session)
                    app.state.color_images.decorate(result["cards"])
                    app.state.color_images.decorate(result["complements"])
                    app.state.color_images.decorate(result.get("selected") or [])
                    session.messages[-2]["content"] = body.text
                    with db.connect() as conn:
                        conn.execute("UPDATE sessions SET state_json=? WHERE session_id=?",
                                     (session.model_dump_json(), str(session_id)))
                        conn.execute("UPDATE message_requests SET response_json=? WHERE session_id=? AND request_id=?",
                                     (canonical(result), str(session_id), str(body.request_id)))
                    db.record_event(session_id, f"reply:{body.request_id}", "response_ready",
                                    {"kind": result["reply"]["kind"], "result_count": len(result["cards"])})
                    return result
            except (AppError, TimeoutError):
                with db.connect() as conn:
                    conn.execute("DELETE FROM message_requests WHERE session_id=? AND request_id=? AND response_json IS NULL",
                                 (str(session_id), str(body.request_id)))
                raise

    @app.exception_handler(TimeoutError)
    async def timeout_error(request, exc):
        return await app_error(request, AppError("TURN_TIMEOUT", "The request exceeded 45 seconds. Please retry."))

    @app.get("/api/products/{product_id}")
    def product(product_id: str):
        p = app.state.tools.product(product_id)
        return {"source": p["raw"], "commerce": p["commerce"], "accepted_attributes": attributes(p),
                "image_url": p["image_url"]}

    @app.get("/api/product-images/{key}.png")
    def product_image(key: str):
        return FileResponse(app.state.product_images.image(key), media_type="image/png", headers={
            "Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff",
        })

    @app.get("/api/product-color-images/{key}.png")
    def color_image(key: str):
        return FileResponse(app.state.color_images.image(key), media_type="image/png", headers={
            "Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff",
        })

    @app.get("/api/product-color-images/{key}")
    def color_image_status(key: str):
        return JSONResponse(app.state.color_images.public(app.state.color_images.get(key)),
                            headers={"Cache-Control": "no-store"})

    @app.post("/api/product-color-images/{key}/retry")
    async def color_image_retry(key: str):
        return app.state.color_images.retry(key)

    @app.post("/api/sessions/{session_id}/selection")
    async def select(session_id: UUID, body: SelectionRequest):
        async with lock_for(session_id):
            session = app.state.db.session(session_id)
            result = await app.state.tools.select(session, body.variant_ids)
            app.state.color_images.decorate(result["items"])
            app.state.db.save_session(session)
            return result

    @app.get("/api/sessions/{session_id}/journey")
    def journey(session_id: UUID):
        with app.state.db.connect() as conn:
            used = conn.execute("SELECT COUNT(*) FROM image_call_reservations WHERE day=?", (now()[:10],)).fetchone()[0]
        return {**app.state.journey.metrics(app.state.db.session(session_id)),
                "image_budget": {"used": used, "limit": settings.daily_image_call_limit, "day": now()[:10]}}

    @app.post("/api/sessions/{session_id}/selection/confirm")
    async def confirm_selection(session_id: UUID, body: ConfirmSelection):
        async with lock_for(session_id):
            return app.state.journey.confirm(app.state.db.session(session_id), body.revision, body.accept_exceptions)

    @app.post("/api/sessions/{session_id}/journey/events")
    async def observe_journey(session_id: UUID, body: JourneyObservation):
        async with lock_for(session_id):
            session = app.state.db.session(session_id)
            if not session.last_result_ids:
                raise AppError("NO_SHORTLIST", "Show a shortlist before recording this interaction.", 409)
            app.state.db.record_event(session_id, f"observed:{body.event_id}", body.name)
            return {"recorded": True}

    @app.post("/api/sessions/{session_id}/journey/feedback")
    async def feedback(session_id: UUID, body: JourneyFeedback):
        async with lock_for(session_id):
            return app.state.journey.feedback(app.state.db.session(session_id), body.revision, body.helpful)

    @app.get("/api/sessions/{session_id}/baseline")
    def controlled_baseline(session_id: UUID, q: str = ""):
        if len(q) > 2000:
            raise AppError("QUERY_TOO_LONG", "Use at most 2000 characters.", 422, False)
        session = app.state.db.session(session_id)
        return app.state.retrieval.controlled_baseline(q, session.intent)

    @app.post("/api/sessions/{session_id}/relax")
    async def relax(session_id: UUID, body: RelaxRequest):
        async with lock_for(session_id):
            session = app.state.db.session(session_id)
            alternative = next((a for a in app.state.retrieval.alternatives(session.intent)
                                if a["id"] == body.alternative_id), None)
            if not alternative:
                raise AppError("ALTERNATIVE_CHANGED", "This alternative is no longer valid. Search again.", 409)
            previous = session.intent
            session.intent = Intent.model_validate(alternative["intent"])
            for key in previous.model_dump():
                if getattr(previous, key) != getattr(session.intent, key):
                    session.intent_sources[key] = "user"
            session.clarification_asked = True
            result = await app.state.retrieval.search(session.intent, profiles()[session.profile_id])
            session.last_result_ids = [r["product_id"] for r in result["results"]]
            app.state.color_images.decorate(result["results"])
            await app.state.images.remove_private(session_id)
            with app.state.db.connect() as conn:
                conn.execute("DELETE FROM selection_confirmations WHERE session_id=?", (str(session_id),))
            app.state.db.save_session(session)
            app.state.db.record_event(session_id, str(uuid4()), "constraint_relaxed",
                                     {"label": alternative["label"]})
            return {**result, "constraints": session.intent.model_dump(),
                    "selection_state": app.state.journey.selection(session)}

    @app.post("/api/sessions/{session_id}/complements")
    async def complements(session_id: UUID, body: ComplementRequest):
        async with lock_for(session_id):
            result = await app.state.tools.complements(app.state.db.session(session_id), body.selected_product_id)
            app.state.color_images.decorate(result["results"])
            return result

    @app.post("/api/sessions/{session_id}/outfits", status_code=202)
    async def outfit(session_id: UUID, body: OutfitRequest, request: Request):
        request.state.request_id = str(body.request_id)
        async with lock_for(session_id):
            return await app.state.images.create(app.state.db.session(session_id), body.request_id,
                                                 body.variant_ids, explicit=True)

    @app.get("/api/sessions/{session_id}/outfits/{job_id}")
    def outfit_status(session_id: UUID, job_id: UUID):
        app.state.db.session(session_id)
        return app.state.images.get(session_id, job_id)

    @app.post("/api/sessions/{session_id}/try-ons", status_code=202, openapi_extra={
        "requestBody": {"required": True, "content": {"application/json": {"schema": TryOnRequest.model_json_schema()}}},
    })
    async def try_on(session_id: UUID, request: Request):
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise AppError("INVALID_CONTENT_TYPE", "Use application/json for photo requests.", 415, False)
        lock = lock_for(session_id)
        if lock.locked() or app.state.photo_slots.locked():
            raise AppError("PHOTO_BUSY", "Photo processing is busy. Retry shortly.", 429)
        async with lock, app.state.photo_slots:
            payload = bytearray()
            try:
                async with asyncio.timeout(15):
                    async for chunk in request.stream():
                        if len(payload) + len(chunk) > MAX_REQUEST_BYTES:
                            raise AppError("PHOTO_TOO_LARGE", "Photo request exceeds 7 MiB.", 413, False)
                        payload.extend(chunk)
            except TimeoutError as exc:
                raise AppError("UPLOAD_TIMEOUT", "Photo upload timed out. Please retry.", 408) from exc
            try:
                body = TryOnRequest.model_validate_json(payload)
            except ValidationError as exc:
                raise AppError("INVALID_PHOTO_REQUEST", "Provide photo data, selected variants, request ID and explicit consent.", 422, False) from exc
            payload.clear()
            request.state.request_id = str(body.request_id)
            return await app.state.images.create(
                app.state.db.session(session_id), body.request_id, body.variant_ids, explicit=True,
                photo_base64=body.photo_base64, consent=body.consent,
            )

    @app.post("/api/sessions/{session_id}/sample-people", status_code=202)
    async def sample_person(session_id: UUID, body: SamplePersonRequest, request: Request):
        request.state.request_id = str(body.request_id)
        async with lock_for(session_id):
            return await app.state.images.create(
                app.state.db.session(session_id), body.request_id, [], explicit=True, sample_person=True,
            )

    @app.get("/api/demo/sample-person.png")
    def demo_person():
        data = load_demo_person()
        return Response(content=data, media_type="image/png", headers={
            "Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
        })

    @app.post("/api/sessions/{session_id}/try-ons/demo", status_code=202)
    async def demo_try_on(session_id: UUID, body: OutfitRequest, request: Request):
        request.state.request_id = str(body.request_id)
        async with lock_for(session_id):
            return await app.state.images.create(
                app.state.db.session(session_id), body.request_id, body.variant_ids, explicit=True,
                fixed_sample=True,
            )

    @app.post("/api/sessions/{session_id}/try-ons/sample", status_code=202)
    async def sample_try_on(session_id: UUID, body: SampleTryOnRequest, request: Request):
        request.state.request_id = str(body.request_id)
        async with lock_for(session_id):
            return await app.state.images.create(
                app.state.db.session(session_id), body.request_id, body.variant_ids, explicit=True,
                sample_job_id=body.sample_job_id,
            )

    @app.delete("/api/sessions/{session_id}/try-ons")
    async def remove_try_ons(session_id: UUID):
        async with lock_for(session_id):
            return await app.state.images.remove_private(session_id)

    @app.get("/api/sessions/{session_id}/outfits/{job_id}/image")
    def private_image(session_id: UUID, job_id: UUID):
        app.state.db.session(session_id)
        return Response(content=app.state.images.private_media(session_id, job_id), media_type="image/png",
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @app.get("/api/media/{media_id}.png")
    def media(media_id: str):
        if not re.fullmatch(r"[0-9a-f-]{36}", media_id):
            raise AppError("NOT_FOUND", "Image not found.", 404, False)
        if not any(j["media_id"] == media_id and j["status"] == "completed" and j.get("kind") not in PRIVATE_KINDS
                   for j in app.state.db.jobs()):
            raise AppError("NOT_FOUND", "Image not found.", 404, False)
        path = settings.image_dir / f"{media_id}.png"
        if not path.is_file():
            raise AppError("NOT_FOUND", "Image file not found.", 404, False)
        return FileResponse(path, media_type="image/png")

    @app.get("/api/demo/enrichment/{product_id}")
    def audit(product_id: str):
        if not settings.demo_audit_enabled:
            raise AppError("NOT_FOUND", "Audit is disabled.", 404, False)
        p = app.state.tools.product(product_id)
        run = None
        if p["enriched"]:
            with app.state.db.connect() as conn:
                row = conn.execute("SELECT * FROM enrichment_runs WHERE run_id=?",
                                   (p["enriched"]["validation_run_id"],)).fetchone()
                if row:
                    run = {"candidates": json.loads(row["candidates_json"]), "report": json.loads(row["report_json"]),
                           "status": row["status"]}
        return {"raw": p["raw"], "accepted": attributes(p), "run": run, "mode": settings.demo_mode,
                "validation_test": load_json(ROOT / "data/fixtures/adversarial.json"),
                "validation_test_result": app.state.db.meta("adversarial_report")}

    @app.get("/api/demo/baseline")
    def baseline(q: str = ""):
        if len(q) > 2000:
            raise AppError("VALIDATION_ERROR", "Query is too long.", 422, False)
        return app.state.retrieval.baseline(q)

    return app


app = create_app()
