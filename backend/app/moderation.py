import base64
import math
import time

from .errors import AppError
from .events import event
from .schemas import ModerationDecision

SAFE_MESSAGE = "I can help with product selection and outfit ideas. Please rephrase your request."


class Moderation:
    def __init__(self, settings, provider):
        self.settings, self.provider = settings, provider

    async def screen_photo(self, photo: bytes, request_id):
        content = [{"type": "image_url", "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(photo).decode("ascii"),
        }}]
        return await self.screen(content, "try_on_photo", request_id)

    async def screen(self, text, stage, request_id):
        start = time.monotonic()
        fields = {"stage": stage, "request_id": str(request_id), "provider_id": None,
                  "model": self.settings.openai_moderation_model,
                  "policy_version": self.settings.moderation_policy_version,
                  "flagged": None, "flagged_categories": [], "latency_ms": 0, "error_code": None}
        if self.settings.demo_mode == "fixture":
            decision = ModerationDecision(**{**fields, "model": "fixture-not-moderation"},
                                          decision="allow")
            event("moderation", **decision.model_dump(), mode="fixture")
            return decision
        try:
            response = await self.provider.invoke(
                lambda: self.provider.client.moderations.create(
                    model=self.settings.openai_moderation_model, input=text),
                timeout=min(5, self.settings.moderation_timeout_seconds), name="moderation_call",
                stage=stage, request_id=str(request_id), policy_version=self.settings.moderation_policy_version,
            )
            if not response.results or len(response.results) != 1:
                raise ValueError("Missing moderation result")
            result = response.results[0]
            categories = result.categories.model_dump()
            scores = result.category_scores.model_dump()
            if (type(result.flagged) is not bool or not categories or not scores
                    or any(type(v) is not bool for v in categories.values())
                    or set(categories) != set(scores)
                    or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                           for v in scores.values())):
                raise ValueError("Invalid moderation fields")
            fields.update(provider_id=response.id, flagged=result.flagged,
                          flagged_categories=[k for k, v in categories.items() if v])
        except (AppError, ValueError, AttributeError, TypeError) as exc:
            fields.update(latency_ms=(time.monotonic() - start) * 1000, error_code="MODERATION_UNAVAILABLE")
            event("moderation", **ModerationDecision(**fields, decision="error").model_dump())
            raise AppError("MODERATION_UNAVAILABLE", "Content screening is unavailable. Please retry.") from exc
        fields["latency_ms"] = (time.monotonic() - start) * 1000
        decision = ModerationDecision(**fields, decision="block" if fields["flagged"] else "allow")
        event("moderation", **decision.model_dump())
        if decision.flagged:
            raise AppError("CONTENT_BLOCKED", SAFE_MESSAGE, 400, False)
        return decision
