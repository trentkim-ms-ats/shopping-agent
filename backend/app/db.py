import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime

from .errors import AppError
from .schemas import Session


def canonical(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def now():
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS raw_products(
                    product_id TEXT PRIMARY KEY, source_json TEXT NOT NULL, source_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS commerce(
                    product_id TEXT PRIMARY KEY REFERENCES raw_products(product_id), facts_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS enrichment_runs(
                    run_id TEXT PRIMARY KEY, product_id TEXT REFERENCES raw_products(product_id),
                    report_json TEXT NOT NULL, candidates_json TEXT NOT NULL, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS published_products(
                    product_id TEXT REFERENCES raw_products(product_id), publication_version TEXT,
                    enriched_json TEXT NOT NULL, PRIMARY KEY(product_id, publication_version));
                CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY, state_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS message_requests(
                    session_id TEXT REFERENCES sessions(session_id), request_id TEXT, text_hash TEXT NOT NULL,
                    response_json TEXT, PRIMARY KEY(session_id,request_id));
                CREATE TABLE IF NOT EXISTS image_jobs(
                    job_id TEXT PRIMARY KEY, session_id TEXT REFERENCES sessions(session_id),
                    request_id TEXT UNIQUE, state_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS product_images(
                    generation_key TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL REFERENCES raw_products(product_id),
                    source_hash TEXT NOT NULL, file_name TEXT NOT NULL, sha256 TEXT NOT NULL,
                    completed_at TEXT NOT NULL, status TEXT NOT NULL CHECK(status='completed'));
                CREATE INDEX IF NOT EXISTS product_images_lookup
                    ON product_images(product_id, source_hash, completed_at DESC);
                CREATE TABLE IF NOT EXISTS product_color_images(
                    generation_key TEXT PRIMARY KEY,
                    product_id TEXT NOT NULL REFERENCES raw_products(product_id),
                    color TEXT NOT NULL, base_key TEXT NOT NULL, state_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS journey_events(
                    session_id TEXT NOT NULL REFERENCES sessions(session_id),
                    event_key TEXT NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL,
                    data_json TEXT NOT NULL, PRIMARY KEY(session_id, event_key));
                CREATE TABLE IF NOT EXISTS selection_confirmations(
                    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id),
                    revision TEXT NOT NULL, confirmed_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS image_call_reservations(
                    call_id TEXT PRIMARY KEY, day TEXT NOT NULL, kind TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def meta(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_meta(self, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, canonical(value)))

    def catalog(self):
        with self.connect() as db:
            db.execute("BEGIN")
            row = db.execute("SELECT value FROM meta WHERE key='publication_version'").fetchone()
            version = json.loads(row[0]) if row else "seed"
            rows = db.execute("""
                SELECT r.*, c.facts_json, p.enriched_json, i.generation_key AS image_key
                FROM raw_products r
                JOIN commerce c USING(product_id) LEFT JOIN published_products p
                ON p.product_id=r.product_id AND p.publication_version=?
                LEFT JOIN product_images i
                ON i.product_id=r.product_id AND i.source_hash=r.source_hash AND i.status='completed'
                ORDER BY r.product_id
            """, (version,)).fetchall()
        return version, [{
            "raw": json.loads(r["source_json"]), "commerce": json.loads(r["facts_json"]),
            "source_hash": r["source_hash"],
            "enriched": json.loads(r["enriched_json"]) if r["enriched_json"] else None,
            "image_url": f"/api/product-images/{r['image_key']}.png" if r["image_key"] else None,
        } for r in rows]

    def session(self, session_id):
        with self.connect() as db:
            row = db.execute("SELECT state_json FROM sessions WHERE session_id=?", (str(session_id),)).fetchone()
        if not row:
            raise AppError("NOT_FOUND", "Session not found. Start a new session.", 404, False)
        return Session.model_validate_json(row[0])

    def save_session(self, session):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO sessions VALUES (?,?)",
                       (str(session.session_id), session.model_dump_json()))

    def save_job(self, job):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO image_jobs VALUES (?,?,?,?)",
                       (job["job_id"], job["session_id"], job["request_id"], canonical(job)))

    def record_event(self, session_id, event_key, name, data=None):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO journey_events VALUES (?,?,?,?,?)",
                       (str(session_id), str(event_key), name, now(), canonical(data or {})))

    def reserve_image_call(self, limit, kind):
        from uuid import uuid4

        day = now()[:10]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute("SELECT COUNT(*) FROM image_call_reservations WHERE day=?", (day,)).fetchone()[0]
            if used >= limit:
                raise AppError("DAILY_IMAGE_LIMIT", "Daily image-call limit reached. Try after midnight UTC.", 429, False)
            db.execute("INSERT INTO image_call_reservations VALUES (?,?,?)", (str(uuid4()), day, kind))

    def jobs(self, session_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT state_json FROM image_jobs" +
                              (" WHERE session_id=?" if session_id else ""),
                              (str(session_id),) if session_id else ()).fetchall()
        return [json.loads(row[0]) for row in rows]
