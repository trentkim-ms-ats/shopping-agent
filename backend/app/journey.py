from datetime import datetime

from .db import digest, now
from .errors import AppError
from .retrieval import matched_attr


class Journey:
    def __init__(self, db):
        self.db = db

    def selection(self, session):
        version, products = self.db.catalog()
        items, issues, facts = [], [], []
        for vid in session.selected_variant_ids:
            match = next(((p, v) for p in products for v in p["commerce"]["variants"]
                          if v["variant_id"] == vid), None)
            if not match:
                issues.append({"variant_id": vid, "message": "Selected variant no longer exists.", "overridable": False})
                continue
            p, v = match
            name, price = p["raw"]["name"], p["commerce"]["price_cents"]
            facts.append([p["source_hash"], v, price])
            items.append({"variant_id": vid, "name": name, "color": v["color"], "size": v["size"],
                          "price_cents": price, "category": p["raw"]["category"]})
            reasons = []
            if v["stock"] <= 0:
                issues.append({"variant_id": vid, "message": f"{name}: out of stock.", "overridable": False})
            if session.intent.size and v["size"] != session.intent.size and not (
                p["raw"]["category"] == "accessory" and v["size"] == "One Size"
            ):
                reasons.append(f"size {v['size']} differs from requested {session.intent.size}")
            if p["raw"]["category"] == "jacket":
                if session.intent.max_price_cents is not None and price > session.intent.max_price_cents:
                    reasons.append(f"above your ${session.intent.max_price_cents / 100:.2f} jacket budget")
                if session.intent.color and v["color"].casefold() != session.intent.color.casefold():
                    reasons.append(f"color differs from requested {session.intent.color}")
                for benefit in session.intent.required_benefits:
                    if not matched_attr(p, "benefits", benefit, explicit=True):
                        reasons.append(f"no approved explicit evidence for required {benefit}")
            issues.extend({"variant_id": vid, "message": f"{name}: {reason}.", "overridable": True}
                          for reason in reasons)
        revision = digest([session.intent.model_dump(), session.selected_variant_ids, version, facts])
        with self.db.connect() as conn:
            confirmation = conn.execute("SELECT * FROM selection_confirmations WHERE session_id=?",
                                        (str(session.session_id),)).fetchone()
            feedback = conn.execute("SELECT 1 FROM journey_events WHERE session_id=? AND event_key=?",
                                    (str(session.session_id), f"feedback:{revision}")).fetchone()
        confirmed = bool(items and confirmation and confirmation["revision"] == revision)
        return {"revision": revision, "items": items, "issues": issues,
                "subtotal_cents": sum(i["price_cents"] for i in items),
                "jacket_budget_cents": session.intent.max_price_cents, "confirmed": confirmed,
                "feedback_recorded": feedback is not None,
                "confirmed_at": confirmation["confirmed_at"] if confirmed else None,
                "can_preview": bool(items) and (not issues or confirmed)}

    def confirm(self, session, revision, accept_exceptions):
        state = self.selection(session)
        if state["revision"] != revision:
            raise AppError("SELECTION_CHANGED", "Selection or requirements changed. Review the latest summary.", 409)
        if not state["items"]:
            raise AppError("SELECTION_REQUIRED", "Select an item before finishing.", 409, False)
        if any(not i["overridable"] for i in state["issues"]):
            raise AppError("UNAVAILABLE_VARIANT", "Replace unavailable items before finishing.", 409, False)
        if state["issues"] and not accept_exceptions:
            raise AppError("SELECTION_REVIEW_REQUIRED", "Review and explicitly accept the listed exceptions.", 409, False)
        if not state["confirmed"]:
            with self.db.connect() as conn:
                conn.execute("INSERT OR REPLACE INTO selection_confirmations VALUES (?,?,?)",
                             (str(session.session_id), revision, now()))
            self.db.record_event(session.session_id, f"confirmed:{revision}", "selection_confirmed",
                                 {"exceptions": len(state["issues"]), "subtotal_cents": state["subtotal_cents"]})
        return self.selection(session)

    def require_preview(self, session):
        state = self.selection(session)
        if not state["can_preview"]:
            raise AppError("SELECTION_REVIEW_REQUIRED", "Review your selection against the current requirements first.", 409, False)

    def feedback(self, session, revision, helpful):
        state = self.selection(session)
        if not state["confirmed"] or state["revision"] != revision:
            raise AppError("SELECTION_CHANGED", "Confirm the current selection before leaving feedback.", 409)
        self.db.record_event(session.session_id, f"feedback:{revision}", "feedback_submitted", {"helpful": helpful})
        return self.metrics(session)

    def metrics(self, session):
        with self.db.connect() as conn:
            rows = conn.execute("SELECT name, created_at, data_json FROM journey_events WHERE session_id=? ORDER BY created_at",
                                (str(session.session_id),)).fetchall()
        counts = {}
        first = {}
        start = session.created_at
        for row in rows:
            name = row["name"]
            counts[name] = counts.get(name, 0) + 1
            first.setdefault(name, round(max(0, (datetime.fromisoformat(row["created_at"]) - start).total_seconds()), 2))
        jobs = self.db.jobs(session.session_id)
        state = self.selection(session)
        return {"counts": counts, "first_seconds": first,
                "image_jobs": {status: sum(j["status"] == status for j in jobs)
                               for status in ("queued", "running", "completed", "failed")},
                "feedback_recorded": state["feedback_recorded"],
                "selection": state,
                "measurement_note": "Observed in this session; includes reading and idle time. "
                                    "Not a time-saving or conversion claim. Image statuses include removed or expired "
                                    "previews, not just provider failures."}
