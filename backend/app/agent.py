import asyncio
import json
import random
import re
from uuid import uuid4

from pydantic import Field, ValidationError

from .db import canonical
from .enrichment import PROMPTS
from .errors import AppError
from .events import event
from .schemas import (
    PRIORITY_CHOICES,
    AgentReply,
    ComplementRequest,
    Model,
    SearchRequest,
    SelectionRequest,
)
from .tools import CHOICES, QUESTION

FINISH = "True when this tool completes the user's request; false if another tool is needed."


class SearchToolRequest(SearchRequest):
    finish_turn: bool = Field(strict=True, description=FINISH)


class ComplementToolRequest(ComplementRequest):
    finish_turn: bool = Field(strict=True, description=FINISH)


class SelectToolRequest(SelectionRequest):
    finish_turn: bool = Field(
        strict=True,
        description=FINISH + " Selecting a complement adds it to the current outfit; do not drop existing selected items.",
    )


class OutfitToolRequest(SelectionRequest):
    finish_turn: bool = Field(strict=True, description=FINISH)


class ConfirmToolRequest(Model):
    accept_exceptions: bool = Field(strict=True, description="True only when the shopper explicitly accepted the listed exceptions.")
    finish_turn: bool = Field(strict=True, description=FINISH)


class FeedbackToolRequest(Model):
    helpful: bool = Field(strict=True, description="True when the shopper said the assistant helped.")
    finish_turn: bool = Field(strict=True, description=FINISH)


TOOL_MODELS = {
    "search_products": SearchToolRequest,
    "recommend_complements": ComplementToolRequest,
    "select_items": SelectToolRequest, "confirm_selection": ConfirmToolRequest,
    "generate_outfit": OutfitToolRequest, "submit_feedback": FeedbackToolRequest,
}
TOOL_KINDS = {
    "search_products": "results", "recommend_complements": "complements",
    "select_items": "selection", "confirm_selection": "confirmed", "generate_outfit": "preview",
    "submit_feedback": "feedback",
}
SHOPPING_TOOLS = tuple(TOOL_MODELS)
# Short follow-ups that resolve against state already on screen; no deep reasoning is required.
LIGHT_TURN = re.compile(
    r"\b(yes|yeah|yep|no|nope|ok|okay|sure|skip|first|second|third|1st|2nd|3rd|one|two|three|this|that|"
    r"it|them|both|compare|select|choose|pick|take|add|confirm|finish|preview|try|outfit|helpful|"
    r"complete|back|remove)\b|네|예|응|아니|좋아|그래|첫|둘|두\s*번|세\s*번|번째|비교|선택|골라|"
    r"추가|확정|확인|완성|미리|입어|도움|그거|이거", re.IGNORECASE)



def tool_specs():
    return [{
        "type": "function", "name": name, "description": name.replace("_", " "),
        "parameters": model.model_json_schema(), "strict": True,
    } for name, model in TOOL_MODELS.items()]


def replay_intent(text, session):
    value = session.intent.model_dump()
    lower = text.casefold()
    if any(w in lower for w in ("jacket", "shell", "재킷", "자켓")):
        value["category"] = "jacket"
    if any(w in lower for w in ("hiking", "hike", "등산", "하이킹")):
        value["activity"] = "hiking"
    if any(w in lower for w in ("fall", "autumn", "가을")):
        value["season"] = "fall"
    priorities = []
    if any(w in lower for w in ("rain", "drizzle", "비", "우천")):
        priorities.append("light_rain")
    if any(w in lower for w in ("warm", "따뜻", "보온")):
        priorities.append("warmth")
    if any(w in lower for w in ("lightweight", "가벼", "경량")):
        priorities.append("lightweight")
    if priorities:
        value["priority"] = priorities[0]
        value["preferred_benefits"] = [{"light_rain": "light rain protection"}.get(p, p) for p in priorities]
    if any(w in lower for w in ("must", "required", "반드시", "필수")) and "light_rain" in priorities:
        value["required_benefits"] = ["light rain protection"]
    if "skip" in lower or "건너" in lower:
        value["priority"] = "balanced"
    amount = re.search(r"(?:under\s*\$?|budget\s*\$?|\$)(\d+(?:\.\d{1,2})?)", lower)
    if amount:
        value["max_price_cents"] = round(float(amount[1]) * 100)
    size = re.search(r"(?:size|사이즈)\s*(xs|xl|s|m|l)\b", lower)
    if size:
        value["size"] = size[1].upper()
    return SearchRequest.model_validate({"intent": value}).intent


class Agent:
    def __init__(self, settings, provider, moderation, tools):
        self.settings, self.provider, self.moderation, self.tools = settings, provider, moderation, tools

    async def execute(self, name, args, session, request_id, text=""):
        parsed = TOOL_MODELS[name].model_validate(args)
        if name == "search_products":
            return await self.tools.search(session, parsed.intent, explicit_text=text)
        if name == "recommend_complements":
            return await self.tools.complements(session, parsed.selected_product_id)
        if name == "select_items":
            return await self.tools.select(session, self.merge_selection(session, parsed.variant_ids))
        if name == "confirm_selection":
            return self.tools.confirm(session, parsed.accept_exceptions)
        if name == "generate_outfit":
            return await self.tools.preview(session, request_id, parsed.variant_ids)
        if name == "submit_feedback":
            return self.tools.feedback(session, parsed.helpful)
        raise AppError("INVALID_TOOL", "Unknown tool.", 422, False)

    def route(self, text, session):
        """Pick the smallest model that can serve the turn; escalate only when it fails."""
        short = len([w for w in text.split() if w]) <= 10
        grounded = bool(session.last_result_ids or session.selected_variant_ids)
        if short and grounded and LIGHT_TURN.search(text) and self.settings.openai_router_model:
            return self.settings.openai_router_model, self.settings.openai_router_reasoning_effort, "light"
        return self.settings.openai_agent_model, self.settings.openai_agent_reasoning_effort, "standard"

    async def turn(self, session, text, request_id):
        trace_id = str(uuid4())
        if self.settings.demo_mode == "fixture":
            return await self.fixture_turn(session, text, request_id, trace_id)
        deterministic = await self.ordinal_selection_turn(session, text, request_id, trace_id)
        if deterministic:
            return deterministic
        context = self.tools.context(session)
        history = session.messages[-12:]
        inputs = [{"role": "developer", "content": canonical(context)}, *history,
                  {"role": "user", "content": text}]
        outputs, events, executions, repaired = {}, [], 0, False
        tool_errors = {}
        model, effort, tier = self.route(text, session)
        routing = {"tier": tier, "model": model, "reasoning_effort": effort, "escalated": False}
        event("routing", trace_id=trace_id, request_id=str(request_id), tier=tier, model=model)
        for call_number in range(4):
            try:
                response = await self.provider.invoke(
                    lambda: self.provider.client.responses.create(
                        model=model, reasoning={"effort": effort},
                        instructions=(PROMPTS / "agent.txt").read_text(),
                        input=inputs, tools=tool_specs(), parallel_tool_calls=False, store=False,
                        text={"format": {"type": "json_schema", "name": "AgentReply", "strict": True,
                                         "schema": AgentReply.model_json_schema()}},
                    ), retries=0, name="agent", model=model, reasoning_effort=effort,
                    trace_id=trace_id, request_id=str(request_id), session_id=str(session.session_id),
                )
            except AppError as exc:
                if not repaired and exc.retryable and call_number < 3:
                    repaired = True
                    model, effort, tier, routing = self.escalate(routing)
                    await asyncio.sleep(.15 + random.random() * .2)
                    continue
                raise
            inputs.extend(item.model_dump(mode="json", exclude_none=True) for item in response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if calls:
                completed_tool = None
                for call in calls:
                    executions += 1
                    if executions > 6:
                        raise AppError("TURN_LIMIT", "Tool limit reached. Please try a simpler request.")
                    try:
                        if call.name not in TOOL_MODELS:
                            raise ValueError("Unknown tool")
                        args = json.loads(call.arguments)
                        data = await self.execute(call.name, args, session, request_id, text)
                        outputs[call.name] = data
                        tool_errors.pop(call.name, None)
                        result = {"ok": True, "data": data, "error": None}
                        if args["finish_turn"] or data.get("clarification"):
                            completed_tool = call.name
                    except (ValidationError, ValueError, KeyError) as exc:
                        if repaired:
                            raise AppError("INVALID_TOOL_ARGUMENTS", "Unable to interpret request. Please rephrase.", 422) from exc
                        repaired = True
                        tool_errors[call.name] = AppError(
                            "INVALID_TOOL_ARGUMENTS", "Unable to interpret tool arguments. Please rephrase.", 422)
                        result = {"ok": False, "data": None, "error": {
                            "code": "INVALID_ARGUMENTS", "message": "Repair tool arguments to the declared schema.", "retryable": True}}
                    except AppError as exc:
                        tool_errors[call.name] = exc
                        result = {"ok": False, "data": None, "error": exc.payload()}
                    events.append({"tool": call.name, "ok": result["ok"]})
                    event("tool", trace_id=trace_id, request_id=str(request_id), tool=call.name, ok=result["ok"])
                    inputs.append({"type": "function_call_output", "call_id": call.call_id, "output": canonical(result)})
                if len(calls) == 1 and completed_tool and not tool_errors:
                    reply = self.tool_reply(completed_tool, outputs[completed_tool])
                    return await self.finalize(reply, outputs, session, request_id, trace_id, events, routing)
                continue
            if tool_errors:
                raise next(reversed(tool_errors.values()))
            try:
                reply = AgentReply.model_validate_json(response.output_text)
                self.validate_reply(reply, outputs)
            except (ValidationError, ValueError) as exc:
                if repaired or call_number == 3:
                    raise AppError("INVALID_REPLY", "Could not verify the response. Please retry.") from exc
                repaired = True
                model, effort, tier, routing = self.escalate(routing)
                inputs.append({"role": "developer", "content": "Repair the final schema and use exact ordered IDs/evidence from current successful tool results."})
                continue
            return await self.finalize(reply, outputs, session, request_id, trace_id, events, routing)
        raise AppError("TURN_LIMIT", "Response limit reached. Please retry with a shorter request.")

    def escalate(self, routing):
        """A light-model turn that could not be verified is retried on the standard model."""
        model = self.settings.openai_agent_model
        effort = self.settings.openai_agent_reasoning_effort
        escalated = routing["tier"] == "light"
        return model, effort, "standard", {
            "tier": "standard", "model": model, "reasoning_effort": effort,
            "escalated": routing["escalated"] or escalated,
        }

    @staticmethod
    def tool_reply(name, data):
        kind = TOOL_KINDS[name]
        if data.get("clarification"):
            kind = "clarify"
        items = data.get("results", [])
        evidence = [a["attribute_id"] for item in items for a in item["reasons"]]
        evidence += [a["attribute_id"] for a in data.get("evidence", [])]
        return AgentReply(kind=kind, message="", choices=[],
                          product_ids=data.get("product_ids", [item["product_id"] for item in items]),
                          evidence_refs=list(dict.fromkeys(evidence)),
                          job_id=data.get("job_id") if kind == "preview" else None)

    async def choose_priority(self, session, text, request_id):
        if text not in PRIORITY_CHOICES:
            raise AppError("INVALID_PRIORITY", "Choose one of the offered priorities.", 422, False)
        if not session.clarification_asked or session.intent.priority is not None:
            raise AppError("STALE_PRIORITY_CHOICE", "This priority question is no longer active. Send a new message.", 409, False)
        priority = PRIORITY_CHOICES[text]
        benefit = {"light_rain": "light rain protection", "warmth": "warmth",
                   "lightweight": "lightweight"}.get(priority)
        intent = session.intent.model_copy(update={
            "priority": priority, "preferred_benefits": [benefit] if benefit else [],
        })
        trace_id = str(uuid4())
        data = await self.tools.search(session, intent, explicit_text=text)
        events = [{"tool": "search_products", "ok": True}]
        event("priority_action", request_id=str(request_id), trace_id=trace_id, priority=priority)
        return await self.finalize(self.tool_reply("search_products", data), {"search_products": data},
                                   session, request_id, trace_id, events,
                                   {"tier": "deterministic", "model": None, "reasoning_effort": None,
                                    "escalated": False})

    async def attach_complements(self, session, reply, outputs, events, trace_id, request_id):
        """Choosing a jacket shows what completes the outfit in the same turn, without a second request."""
        if reply.kind != "selection" or "recommend_complements" in outputs:
            return
        jacket = next((pair[0]["raw"]["product_id"] for vid in session.selected_variant_ids
                       if (pair := self.tools.variant(vid)) and pair[0]["raw"]["category"] == "jacket"), None)
        if jacket is None:
            return
        try:
            outputs["recommend_complements"] = await self.tools.complements(session, jacket)
        except AppError:
            outputs.pop("recommend_complements", None)
            return
        events.append({"tool": "recommend_complements", "ok": True})
        event("tool", trace_id=trace_id, request_id=str(request_id), tool="recommend_complements", ok=True)

    async def finalize(self, reply, outputs, session, request_id, trace_id, events, routing):
        self.validate_reply(reply, outputs)
        await self.attach_complements(session, reply, outputs, events, trace_id, request_id)
        displayed = self.display_reply(reply, outputs)
        # Screen what is actually rendered, including catalog-derived recommendation text.
        content = canonical({
            "reply": displayed.model_dump(),
            "cards": outputs.get("search_products", {}).get("results", []),
            "complements": outputs.get("recommend_complements", {}).get("results", []),
            "alternatives": outputs.get("search_products", {}).get("alternatives", []),
        })
        await self.moderation.screen(content, "chat_output", request_id)
        return self.envelope(displayed, outputs, session, request_id, trace_id, events, routing)

    def validate_reply(self, reply, outputs):
        key = {"results": "search_products",
               "complements": "recommend_complements", "clarify": "search_products",
               "selection": "select_items", "confirmed": "confirm_selection",
               "preview": "generate_outfit", "feedback": "submit_feedback"}.get(reply.kind)
        data = outputs.get(key, {})
        if key and not data:
            raise ValueError("Missing successful tool result")
        ids = data.get("product_ids", [r["product_id"] for r in data.get("results", [])])
        if reply.product_ids != ids:
            raise ValueError("Product IDs or order do not match tool results")
        if reply.kind == "clarify" and not data.get("clarification"):
            raise ValueError("Clarification not requested")
        if reply.kind == "results" and data.get("clarification"):
            raise ValueError("Clarification required")
        refs = {a["attribute_id"] for r in data.get("results", []) for a in r["reasons"]}
        refs |= {a["attribute_id"] for a in data.get("evidence", [])}
        if not set(reply.evidence_refs) <= refs:
            raise ValueError("Invented evidence")
        # Only a completed image tool may surface a job id, and only the one it returned.
        if reply.job_id != (data.get("job_id") if reply.kind == "preview" else None):
            raise ValueError("Unauthorized image job")
        if reply.kind in ("status", "comparison_unavailable") and reply.product_ids:
            raise ValueError("Unhydrated product IDs")
        if reply.kind in ("status", "comparison_unavailable") and any(k in outputs for k in SHOPPING_TOOLS):
            raise ValueError("Successful shopping tools require a matching visible result")

    @staticmethod
    def display_reply(reply, outputs):
        """Product facts and next-step wording stay server-owned; the model never writes them."""
        search = outputs.get("search_products", {})
        selection = (outputs.get("select_items") or outputs.get("confirm_selection") or
                     outputs.get("submit_feedback") or {}).get("selection_state") or {}
        items = selection.get("items", [])
        names = ", ".join(item["name"] for item in items)
        issues = selection.get("issues", [])
        complements = (outputs.get("recommend_complements") or {}).get("results") or []
        message = {
            "clarify": QUESTION,
            "results": search.get("notice") or "Here are your matches, ordered by your preferences. "
                       "Review each card's reasons and ranking scores, then tell me which one you want.",
            "comparison_unavailable": "A side-by-side comparison is not available in this demo. "
                                      "Review the product cards and open Why this match for source evidence. "
                                      "Your selection has not changed.",
            "complements": "These complete the outfit from other categories. Prices are per item. "
                           "You can add one or two, then show the try-on preview.",
            "selection": (f"Added to your selection: {names}. " if names else "Your selection is empty. ") +
                         ("I still need you to review some exceptions before we finish."
                          if issues else
                          "I found a few more pieces that can complete the outfit. "
                          "Add another one, or show the try-on preview whenever you are ready."
                          if complements else
                          "Would you like me to show the try-on preview now?"),
            "confirmed": "Saved to your demo cart. This demo places no order and takes no payment. "
                         "Did this help you choose?",
            "preview": "I am generating the virtual try-on on the fixed demo model. "
                       "It is a visual reference only, with no size or fit prediction.",
            "feedback": "Thank you — your feedback was recorded for this demo journey.",
            "status": "That rating is not specified in the catalog. "
                      "Open Why this match for source evidence, or tell me which item you want.",
        }[reply.kind]
        return reply.model_copy(update={"message": message, "choices": Agent.suggestions(reply, outputs)})

    @staticmethod
    def suggestions(reply, outputs):
        """Reply chips are answers the shopper can actually give right now, in conversation."""
        if reply.kind == "clarify":
            return CHOICES
        selection = (outputs.get("select_items") or outputs.get("confirm_selection") or
                     outputs.get("submit_feedback") or {}).get("selection_state") or {}
        count = len(reply.product_ids)
        if reply.kind == "results":
            return [f"Choose the {word}" for word in ("first", "second", "third")[:count]][:4]
        if reply.kind == "complements":
            return [*[f"Add the {word}" for word in ("first", "second")[:count]],
                    "Show the try-on preview"][:4]
        if reply.kind == "selection":
            complements = (outputs.get("recommend_complements") or {}).get("results") or []
            chips = [f"Add the {word}" for word in ("first", "second")[:len(complements)]]
            chips.append("Show the try-on preview")
            if selection.get("issues"):
                chips.append("Keep these exceptions and save to the demo cart")
            elif not complements:
                chips.append("Save this to the demo cart")
            return chips
        if reply.kind == "preview":
            return ["Save this to the demo cart", "Start a new search"]
        if reply.kind == "confirmed":
            return [] if selection.get("feedback_recorded") else ["Yes, that helped", "Not yet"]
        if reply.kind == "status":
            return ["Choose the first"]
        return []

    def envelope(self, reply, outputs, session, request_id, trace_id, events, routing):
        search = outputs.get("search_products", {})
        complements = outputs.get("recommend_complements", {})
        safe_reply = self.display_reply(reply, outputs)
        session.messages = (session.messages + [{"role": "user", "content": ""}, {
            "role": "assistant", "content": canonical(safe_reply),
        }])[-16:]
        return {
            "reply": safe_reply.model_dump(), "cards": search.get("results", []),
            "comparison": None, "complements": complements.get("results", []),
            "constraints": session.intent.model_dump(), "intent_sources": session.intent_sources,
            "request_id": str(request_id), "trace_id": trace_id,
            "mode": self.settings.demo_mode, "retrieval_mode": search.get("mode", complements.get("mode")),
            "degradation": search.get("degradation", complements.get("degradation")),
            "alternatives": search.get("alternatives", []),
            "selected": outputs.get("select_items", {}).get("items", []),
            "job": outputs.get("generate_outfit"),
            "routing": routing,
            "tool_events": events,
        }

    def fixture_ordinals(self, text):
        lower = text.casefold()
        words = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
                 "첫": 1, "두 번째": 2, "두번째": 2, "세 번째": 3, "세번째": 3}
        found = [rank for word, rank in words.items() if word in lower]
        return sorted(set(found))

    def merge_selection(self, session, chosen):
        """Replay mirrors the live rule: a jacket restarts the outfit, other categories add to it."""
        merged = list(session.selected_variant_ids)
        for variant_id in chosen:
            pair = self.tools.variant(variant_id)
            if not pair:
                continue
            category = pair[0]["raw"]["category"]
            if category == "jacket":
                merged = [variant_id]
                continue
            merged = [vid for vid in merged
                      if (other := self.tools.variant(vid)) and other[0]["raw"]["category"] != category]
            merged.append(variant_id)
        return merged[:3]

    async def ordinal_selection_turn(self, session, text, request_id, trace_id):
        if any(word in text.casefold() for word in ("compare", "comparison", "비교")):
            return None
        offered = self.tools.offered(session)
        ordinals = self.fixture_ordinals(text)
        if not ordinals or not offered or not any(w in text.casefold() for w in
                                                 ("choose", "select", "take", "add", "pick")):
            return None
        chosen = [option["variant_id"] for option in offered if option["position"] in ordinals]
        if not chosen:
            return None
        outputs = {"select_items": await self.tools.select(session, self.merge_selection(session, chosen))}
        return await self.finalize(self.tool_reply("select_items", outputs["select_items"]), outputs,
                                   session, request_id, trace_id,
                                   [{"tool": "select_items", "ok": True}],
                                   {"tier": "deterministic", "model": None, "reasoning_effort": None,
                                    "escalated": False})

    async def fixture_turn(self, session, text, request_id, trace_id):
        lower = text.casefold()
        outputs = {}
        offered = self.tools.offered(session)
        ordinals = self.fixture_ordinals(text)
        selection = self.tools.journey.selection(session)
        if any(w in lower for w in ("compare", "comparison", "비교")):
            kind, ids = "comparison_unavailable", []
        elif any(w in lower for w in ("save", "confirm", "cart", "저장", "확정")) and selection["items"]:
            kind = "confirmed"
            outputs["confirm_selection"] = self.tools.confirm(
                session, any(w in lower for w in ("exception", "예외")))
            ids = []
        elif any(w in lower for w in ("try-on", "try on", "preview", "미리", "입어")) and selection["items"]:
            kind = "preview"
            outputs["generate_outfit"] = await self.tools.preview(
                session, request_id, [item["variant_id"] for item in selection["items"]])
            ids = []
        elif selection.get("confirmed") and any(w in lower for w in
                                                ("helped", "yes", "not yet", "도움", "네", "아니")):
            kind = "feedback"
            outputs["submit_feedback"] = self.tools.feedback(
                session, not any(w in lower for w in ("not yet", "no", "아니")))
            ids = []
        elif any(w in lower for w in ("complete", "complement", "outfit", "보완", "코디")) and selection["items"]:
            kind = "complements"
            jacket = next((pair[0]["raw"]["product_id"] for vid in session.selected_variant_ids
                           if (pair := self.tools.variant(vid)) and pair[0]["raw"]["category"] == "jacket"), None)
            if jacket is None:
                raise AppError("SELECTION_REQUIRED", "Select an available jacket first.", 409, False)
            outputs["recommend_complements"] = await self.tools.complements(session, jacket)
            ids = [p["product_id"] for p in outputs["recommend_complements"]["results"]]
        elif ordinals and offered and any(w in lower for w in
                                          ("choose", "select", "take", "add", "pick", "선택", "고", "담")):
            chosen = [option["variant_id"] for option in offered if option["position"] in ordinals]
            kind = "selection"
            outputs["select_items"] = await self.tools.select(session, self.merge_selection(session, chosen))
            ids = outputs["select_items"]["product_ids"]
        elif any(w in lower for w in ("10°", "temperature", "waterproof", "온도", "방수")):
            kind, ids = "status", []
        else:
            result = await self.tools.search(session, replay_intent(text, session), explicit_text=text)
            outputs["search_products"] = result
            kind = "clarify" if result.get("clarification") else "results"
            ids = [p["product_id"] for p in result.get("results", [])]
        reply = AgentReply(kind=kind, message="Replay transition", choices=[], product_ids=ids, evidence_refs=[],
                           job_id=(outputs.get("generate_outfit") or {}).get("job_id"))
        return await self.finalize(reply, outputs, session, request_id, trace_id,
                                   [{"tool": "fixture replay", "ok": True}],
                                   {"tier": "deterministic", "model": None, "reasoning_effort": None,
                                    "escalated": False})
