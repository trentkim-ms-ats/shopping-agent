import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from .config import ROOT
from .db import canonical, digest, now
from .errors import AppError
from .events import event
from .schemas import (
    AttributeJudgment,
    CandidateAttribute,
    CandidateSet,
    CommerceFact,
    CustomerProfile,
    EnrichedProduct,
    Evidence,
    JudgeOutput,
    RawProduct,
    ValidationReport,
)

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def load_json(path):
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def _load_profiles(path: Path, revision: tuple[int, int, int, int]) -> dict[str, CustomerProfile]:
    return {p["profile_id"]: CustomerProfile.model_validate(p)
            for p in load_json(path)}


def profiles() -> dict[str, CustomerProfile]:
    path = ROOT / "data/seed/profiles.json"
    stat = path.stat()
    revision = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)
    # Cache only source profiles, never session intent or mutable caller-owned models.
    return {key: profile.model_copy(deep=True) for key, profile in _load_profiles(path, revision).items()}


def seed(db):
    raw = [RawProduct.model_validate(p) for p in load_json(ROOT / "data/seed/raw_products.json")]
    facts = [CommerceFact.model_validate(p) for p in load_json(ROOT / "data/seed/commerce.json")]
    products = {p.product_id: p for p in raw}
    if len(products) != len(raw) or len({f.product_id for f in facts}) != len(facts):
        raise ValueError("Duplicate product IDs")
    if set(products) != {f.product_id for f in facts}:
        raise ValueError("Commerce must match the catalog")
    variants = set()
    for f in facts:
        p = products[f.product_id]
        combinations = set()
        for v in f.variants:
            combination = (v.color, v.size)
            if (v.variant_id in variants or v.color not in p.colors or v.size not in p.sizes
                    or not v.variant_id.startswith(p.product_id + "-") or combination in combinations):
                raise ValueError("Invalid or duplicate commerce variant")
            variants.add(v.variant_id)
            combinations.add(combination)
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = {r["product_id"]: r["source_hash"] for r in conn.execute("SELECT * FROM raw_products")}
        incoming = {p.product_id: digest(p) for p in raw}
        if any(incoming.get(pid) != source_hash for pid, source_hash in existing.items()):
            raise ValueError("Immutable source changed. Use a new DATABASE_PATH and re-enrich, do not overwrite.")
        for p in raw:
            conn.execute("INSERT OR IGNORE INTO raw_products VALUES (?,?,?)",
                         (p.product_id, canonical(p), digest(p)))
        for f in facts:
            conn.execute("INSERT OR REPLACE INTO commerce VALUES (?,?)", (f.product_id, canonical(f)))
        if incoming.keys() - existing.keys():
            conn.execute("DELETE FROM meta WHERE key='index_manifest'")
    profiles()
    event("seed", products=len(raw))
    return len(raw)


def valid_evidence(raw, evidence):
    if not evidence:
        return False
    for e in evidence:
        value = raw[e.field]
        values = value if isinstance(value, list) else [value]
        if not e.quote.strip() or not any(e.quote in item for item in values):
            return False
    return True


def normalize_candidates(raw, candidate_set):
    if candidate_set.product_id != raw["product_id"]:
        raise ValueError("Candidate product mismatch")
    attributes, seen = [], set()
    for a in candidate_set.attributes:
        value = " ".join(a.value.split()).casefold()
        if not value or not valid_evidence(raw, a.evidence):
            raise ValueError("Invalid candidate evidence")
        key = (a.kind, value)
        if key in seen:
            continue
        seen.add(key)
        attributes.append(a.model_copy(update={
            "value": value, "attribute_id": raw["product_id"] + "-" + digest(key)[:16],
        }))
    if any(count > 3 for count in Counter(a.kind for a in attributes).values()):
        raise ValueError("At most three attributes per kind")
    return CandidateSet(product_id=raw["product_id"], attributes=attributes)


TECHNICAL = re.compile(r"\d|gore.?tex|certif|waterproof|windproof|temperature|fit guarantee", re.IGNORECASE)


def validate_judgments(raw, candidates, judgments):
    wanted = {a.attribute_id for a in candidates.attributes}
    found = [j.attribute_id for j in judgments]
    if len(set(found)) != len(found) or set(found) != wanted:
        raise ValueError("Judgments must be complete, unique and one-to-one")
    accepted = []
    for a in candidates.attributes:
        j = next(j for j in judgments if j.attribute_id == a.attribute_id)
        if j.decision != "accept":
            continue
        if j.support == "unsupported" or not valid_evidence(raw, j.evidence):
            raise ValueError("Accepted judgment lacks valid evidence")
        support = "inferred" if "inferred" in (a.support, j.support) else "explicit"
        if TECHNICAL.search(a.value) or (a.kind in ("benefits", "season_suitability") and support != "explicit"):
            raise ValueError("Technical or inferred performance cannot be published")
        accepted.append(a.model_copy(update={"support": support}))
    return accepted


def replay_candidates(raw):
    attrs = []
    for rule in load_json(ROOT / "data/fixtures/replay_rules.json")["rules"]:
        if rule["phrase"] in raw["description"]:
            attrs.append(CandidateAttribute(
                attribute_id="server-replaces", kind=rule["kind"], value=rule["value"], support="explicit",
                evidence=[Evidence(field="description", quote=rule["phrase"])],
            ))
    return CandidateSet(product_id=raw["product_id"], attributes=attrs)


async def enrich(db, settings, provider):
    generator_prompt = (PROMPTS / "enrich.txt").read_text()
    judge_prompt = (PROMPTS / "judge.txt").read_text()
    prompt_version = digest([generator_prompt, judge_prompt, "publication-policy-v1"])
    if settings.demo_mode == "fixture":
        prompt_version = digest([prompt_version, load_json(ROOT / "data/fixtures/replay_rules.json")])
    version = str(uuid4())
    _, catalog = db.catalog()
    if not catalog:
        raise ValueError("Run seed first")
    publications = []
    for product in catalog:
        raw, source_hash = product["raw"], product["source_hash"]
        gen_model = settings.openai_enrich_model if settings.demo_mode == "live" else "fixture-generator"
        judge_model = settings.openai_judge_model if settings.demo_mode == "live" else "fixture-judge"
        efforts = [settings.openai_enrich_reasoning_effort, settings.openai_judge_reasoning_effort] \
            if settings.demo_mode == "live" else []
        cache_key = digest([source_hash, prompt_version, gen_model, judge_model, *efforts])
        with db.connect() as conn:
            cache = conn.execute("SELECT * FROM enrichment_runs WHERE run_id=? AND status='completed'",
                                 (cache_key,)).fetchone()
        candidates = CandidateSet(product_id=raw["product_id"], attributes=[])
        judgments, accepted, error = [], [], None
        if cache:
            candidates = CandidateSet.model_validate_json(cache["candidates_json"])
            report = ValidationReport.model_validate_json(cache["report_json"])
            judgments = report.judgments
            accepted = validate_judgments(raw, candidates, judgments)
        else:
            for attempt in range(2):
                try:
                    proposed = replay_candidates(raw) if settings.demo_mode == "fixture" else \
                        await provider.structured(gen_model, generator_prompt, canonical(raw), CandidateSet,
                                                  reasoning_effort=settings.openai_enrich_reasoning_effort,
                                                  run_id=cache_key, phase="generator", prompt_version=prompt_version)
                    candidates = normalize_candidates(raw, proposed)
                    error = None
                    break
                except (AppError, ValidationError, ValueError) as exc:
                    error = type(exc).__name__
                    event("enrichment_error", product_id=raw["product_id"], phase="generator", attempt=attempt, error=error)
            if error is None:
                for attempt in range(2):
                    try:
                        if settings.demo_mode == "fixture":
                            judgments = [AttributeJudgment(
                                attribute_id=a.attribute_id, decision="accept", support=a.support,
                                evidence=a.evidence, reason="Labeled replay: exact synthetic phrase fixture.",
                            ) for a in candidates.attributes]
                        else:
                            result = await provider.structured(
                                judge_model, judge_prompt, canonical({"raw": raw, "candidates": candidates.model_dump()}),
                                JudgeOutput, run_id=cache_key, phase="judge", prompt_version=prompt_version,
                                reasoning_effort=settings.openai_judge_reasoning_effort,
                            )
                            judgments = result.judgments
                        accepted = validate_judgments(raw, candidates, judgments)
                        error = None
                        break
                    except (AppError, ValidationError, ValueError) as exc:
                        error = type(exc).__name__
                        event("enrichment_error", product_id=raw["product_id"], phase="judge", attempt=attempt, error=error)
            report = ValidationReport(
                product_id=raw["product_id"], judgments=judgments, source_hash=source_hash,
                candidate_hash=digest(candidates), generator_model=gen_model, judge_model=judge_model,
                prompt_version=prompt_version, run_id=cache_key, created_at=now(),
            )
            with db.connect() as conn:
                conn.execute("INSERT OR REPLACE INTO enrichment_runs VALUES (?,?,?,?,?)",
                             (cache_key, raw["product_id"], report.model_dump_json(), candidates.model_dump_json(),
                              "quarantined" if error else "completed"))
        if error:
            accepted = []
        publications.append(EnrichedProduct(
            product_id=raw["product_id"], source_hash=source_hash, publication_version=version,
            accepted_attributes=accepted, validation_run_id=cache_key, status="raw_only" if error else "enriched",
        ))
        event("enrichment", product_id=raw["product_id"], run_id=cache_key, accepted=len(accepted),
              rejected=len(candidates.attributes) - len(accepted), cache_hit=bool(cache), error=error)
    with db.connect() as conn:
        for p in publications:
            conn.execute("INSERT INTO published_products VALUES (?,?,?)",
                         (p.product_id, version, p.model_dump_json()))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('publication_version',?)", (canonical(version),))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('publication_mode',?)", (canonical(settings.demo_mode),))
        conn.execute("DELETE FROM meta WHERE key='index_manifest'")
    return {"publication_version": version, "accepted": sum(len(p.accepted_attributes) for p in publications),
            "raw_only": sum(p.status == "raw_only" for p in publications), "mode": settings.demo_mode}
