import argparse
import asyncio
import json
import logging
import statistics
import time

from .config import ROOT, Settings
from .db import Database, canonical, now
from .enrichment import (
    PROMPTS,
    enrich,
    load_json,
    profiles,
    seed,
    validate_judgments,
)
from .errors import AppError
from .moderation import Moderation
from .product_images import generate_product_images
from .provider import Provider
from .retrieval import Retrieval, build_index
from .schemas import AgentReply, AttributeJudgment, CandidateSet, Intent, JudgeOutput
from .tools import Tools


async def adversarial_test(db, settings, provider):
    fixture = load_json(ROOT / "data/fixtures/adversarial.json")
    candidates = CandidateSet.model_validate(fixture["candidates"])
    if settings.demo_mode == "fixture":
        judgments = [AttributeJudgment(
            attribute_id=a.attribute_id, decision="reject", support="unsupported", evidence=[],
            reason="Simulated adversarial rejection: the source does not establish this claim.",
        ) for a in candidates.attributes]
    else:
        report = await provider.structured(
            settings.openai_judge_model, (PROMPTS / "judge.txt").read_text(),
            canonical({"raw": fixture["raw"], "candidates": fixture["candidates"]}), JudgeOutput,
            reasoning_effort=settings.openai_judge_reasoning_effort,
            phase="adversarial-test",
        )
        judgments = report.judgments
    accepted = validate_judgments(fixture["raw"], candidates, judgments)
    result = {"label": fixture["label"], "mode": settings.demo_mode,
              "judgments": [j.model_dump() for j in judgments], "passed": len(accepted) == 0, "created_at": now()}
    db.set_meta("adversarial_report", result)
    if accepted:
        raise ValueError("Adversarial unsupported claims were accepted")
    return result


async def evaluate(db, settings, provider):
    retrieval = Retrieval(db, settings, provider)
    tools = Tools(db, retrieval, None)
    rows, latencies = [], []
    for case in load_json(ROOT / "evals/cases.json"):
        profile = profiles()[case["profile"]]
        intent = Intent(
            category="jacket", activity=None, season="fall", priority="balanced", size=profile.preferred_size,
            max_price_cents=profile.budget_cents, color=None, require_in_stock=True,
            required_benefits=[], preferred_benefits=[],
        ).model_copy(update=case["intent"])
        for strategy in ("source_lexical", "enriched_lexical", "hybrid"):
            start = time.monotonic()
            result = await retrieval.search(intent, profile, strategy=strategy)
            duration = (time.monotonic() - start) * 1000
            latencies.append(duration)
            ids = [p["product_id"] for p in result["results"]]
            row = {
                "case": case["id"], "strategy": strategy, "mode": result["mode"], "ids": ids,
                "hit_at_3": int(bool(set(ids) & set(case["relevant"]))) if case["relevant"] else None,
                "constraint_violations": len(set(ids) - set(case["eligible"])),
                "eligible_count_expected": len(case["eligible"]), "eligible_count_observed": result["eligible_count"],
                "retrieval_ms": round(duration, 3),
            }
            if case["behavior"] == "compare first two" and len(ids) >= 2:
                row["ordinal_order_preserved"] = tools.compare(ids[:2])["product_ids"] == ids[:2]
            if case["behavior"] == "unknown temperature" and len(ids) >= 2:
                row["unknown_spec_preserved"] = tools.compare(ids[:2])["rows"][-1]["values"] == ["Not specified"] * 2
            rows.append(row)
    summary = {
        "created_at": now(), "mode": settings.demo_mode, "models": settings.models(),
        "publication_version": db.meta("publication_version"), "samples": len(rows),
        "median_retrieval_ms": round(statistics.median(latencies), 3),
        "constraint_violations": sum(r["constraint_violations"] for r in rows),
        "eligible_set_count_mismatches": sum(r["eligible_count_expected"] != r["eligible_count_observed"] for r in rows),
        "hit_at_3": {
            strategy: statistics.mean(r["hit_at_3"] for r in rows if r["strategy"] == strategy and r["hit_at_3"] is not None)
            for strategy in ("source_lexical", "enriched_lexical", "hybrid")
        },
        "human_reviewed_unsupported_claim_count": None,
        "live_chat_latency_ms": None, "live_image_latency_ms": None,
        "limitations": [
            "Fixture results are synthetic replay, not live model quality.",
            "All strategies share identical hard filters, including approved required-benefit filters.",
            "hit@3 is binary any-hit against seed-authored relevant IDs, averaged only over nonempty labels.",
            ("Original 24 labels are manual; added product labels use authored recipe benefits, fall-hiking "
             "suitability and commerce facts, independently of retrieval output. This is not a human relevance study."),
            "Behavioral chat, injection and complements coverage is in pytest; this report measures retrieval.",
            "No human fact-review, cost, live chat or image measurement is implied.",
        ],
        "cases": rows,
    }
    destination = ROOT / "evals" / ("results.fixture.json" if settings.demo_mode == "fixture" else "results.json")
    destination.write_text(json.dumps(summary, indent=2) + "\n")
    return {k: v for k, v in summary.items() if k != "cases"}


async def preflight(settings, provider, smoke=False, image=False):
    if settings.demo_mode != "live":
        raise ValueError("Preflight/smoke require DEMO_MODE=live; replay is not evidence of account access.")
    settings.require_live_config()
    models = settings.models()
    checks = []
    for model in sorted(set(models.values())):
        await provider.invoke(lambda m=model: provider.client.models.retrieve(m), name="model_access")
        checks.append({"model": model, "accessible": True})
    output = {"created_at": now(), "models": models, "access_checks": checks, "smoke": []}
    if smoke:
        moderation = Moderation(settings, provider)
        await moderation.screen("I need a lightweight jacket for hiking this fall.", "user_input", "smoke")
        start = time.monotonic()
        reply = await provider.structured(
            settings.openai_agent_model,
            "Return a status AgentReply greeting with no product IDs, evidence, choices or job ID.",
            "Hello, I would like help shopping.", AgentReply,
            reasoning_effort=settings.openai_agent_reasoning_effort,
        )
        await moderation.screen(reply.message, "chat_output", "smoke")
        output["smoke"].append({"text_ms": (time.monotonic() - start) * 1000})
        vectors = await provider.embeddings(["lightweight hiking jacket"])
        output["smoke"].append({"embedding_dimensions": len(vectors[0])})
        db = Database(settings.database_path)
        await adversarial_test(db, settings, provider)
        output["smoke"].append({"independent_judge_adversarial": "passed"})
        if image:
            prompt = "A neutral outdoor jacket on a generic adult mannequin, no text or logos. Illustrative outfit concept."
            await moderation.screen(prompt, "image_prompt", "smoke")
            start = time.monotonic()
            data = await provider.image(prompt)
            settings.image_dir.mkdir(parents=True, exist_ok=True)
            (settings.image_dir / "smoke.png").write_bytes(data)
            output["smoke"].append({"image_ms": (time.monotonic() - start) * 1000, "bytes": len(data)})
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    (settings.database_path.parent / "live-preflight.json").write_text(json.dumps(output, indent=2) + "\n")
    return output


async def run(args):
    settings = Settings()
    if args.command != "seed":
        settings.require_live_config()
    provider = Provider(settings)
    try:
        if args.command == "product-images":
            return await generate_product_images(settings, provider, retry_incomplete=args.retry_incomplete)
        db = Database(settings.database_path)
        if args.command == "seed":
            return {"seeded": seed(db), "mode": settings.demo_mode}
        if args.command == "enrich":
            result = await enrich(db, settings, provider)
            result["adversarial_test"] = await adversarial_test(db, settings, provider)
            return result
        if args.command == "index":
            return await build_index(db, settings, provider)
        if args.command == "evaluate":
            return await evaluate(db, settings, provider)
        return await preflight(settings, provider, smoke=args.command == "smoke", image=args.image)
    finally:
        if provider.client:
            await provider.client.close()


def main():
    parser = argparse.ArgumentParser(description="Trailshop local data and OpenAI preflight")
    parser.add_argument("command", choices=["seed", "enrich", "index", "evaluate", "preflight", "smoke", "product-images"])
    parser.add_argument("--image", action="store_true", help="Explicitly authorize one billable smoke image.")
    parser.add_argument("--retry-incomplete", action="store_true",
                        help="Authorize retrying interrupted/failed product images; another charge is possible.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        print(json.dumps(asyncio.run(run(args)), indent=2))
    except (AppError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Trailshop: {exc}\n")


if __name__ == "__main__":
    main()
