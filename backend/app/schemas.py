from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


Category = Literal["jacket", "midlayer", "pants", "accessory"]
Kind = Literal["season_suitability", "activities", "use_cases", "style", "benefits", "search_keywords"]
PRIORITY_CHOICES = {
    "Light rain protection": "light_rain", "Warmth": "warmth",
    "Lightweight": "lightweight", "Skip — use known preferences": "balanced",
}


class RawProduct(Model):
    product_id: str = Field(pattern=r"^[A-Z]\d{2,3}$")
    category: Category
    name: str = Field(min_length=1, max_length=100)
    colors: list[str] = Field(min_length=1)
    sizes: list[str] = Field(min_length=1)
    description: str = Field(min_length=1, max_length=2000)


class Variant(Model):
    variant_id: str = Field(pattern=r"^[A-Z]\d{2,3}-[A-Za-z0-9-]+$")
    color: str = Field(min_length=1, max_length=30)
    size: str = Field(min_length=1, max_length=20)
    stock: int = Field(ge=0, strict=True)


class CommerceFact(Model):
    product_id: str = Field(pattern=r"^[A-Z]\d{2,3}$")
    currency: Literal["USD"]
    price_cents: int = Field(ge=0, strict=True)
    variants: list[Variant] = Field(min_length=1)
    popularity_30d: int = Field(ge=0, strict=True)
    snapshot_at: datetime


class Evidence(Model):
    field: Literal["name", "category", "description", "colors", "sizes"]
    quote: str = Field(min_length=1, max_length=2000)


class CandidateAttribute(Model):
    attribute_id: str = Field(min_length=1, max_length=100)
    kind: Kind
    value: str = Field(min_length=1, max_length=100)
    support: Literal["explicit", "inferred"]
    evidence: list[Evidence] = Field(min_length=1, max_length=5)


class CandidateSet(Model):
    product_id: str
    attributes: list[CandidateAttribute] = Field(max_length=18)


class AttributeJudgment(Model):
    attribute_id: str
    decision: Literal["accept", "reject", "uncertain"]
    support: Literal["explicit", "inferred", "unsupported"]
    evidence: list[Evidence]
    reason: str = Field(min_length=1, max_length=1000)


class JudgeOutput(Model):
    judgments: list[AttributeJudgment]


class ValidationReport(Model):
    product_id: str
    judgments: list[AttributeJudgment]
    source_hash: str
    candidate_hash: str
    generator_model: str
    judge_model: str
    prompt_version: str
    run_id: str
    created_at: datetime


class EnrichedProduct(Model):
    product_id: str
    source_hash: str
    publication_version: str
    accepted_attributes: list[CandidateAttribute]
    validation_run_id: str
    status: Literal["enriched", "raw_only"]


class CustomerProfile(Model):
    profile_id: str
    display_name: str
    preferred_size: str | None
    preferred_colors: list[str]
    budget_cents: int | None
    preferred_style: list[str]
    owned_product_ids: list[str]


class Intent(Model):
    category: Category | None
    activity: str | None = Field(max_length=100)
    season: str | None = Field(max_length=40)
    priority: Literal["light_rain", "warmth", "lightweight", "balanced"] | None
    max_price_cents: int | None = Field(ge=0, strict=True)
    size: str | None = Field(max_length=20)
    color: str | None = Field(max_length=30)
    require_in_stock: bool
    required_benefits: list[str] = Field(max_length=8)
    preferred_benefits: list[str] = Field(max_length=8)


class Session(Model):
    session_id: UUID
    profile_id: str
    intent: Intent
    intent_sources: dict[str, Literal["user", "profile", "demo_context"]]
    last_result_ids: list[str]
    last_variant_ids: list[str] = []
    selected_variant_ids: list[str]
    clarification_asked: bool
    messages: list[dict]
    created_at: datetime


class AgentReply(Model):
    kind: Literal["clarify", "results", "comparison_unavailable", "complements", "status",
                  "selection", "confirmed", "preview", "feedback"]
    message: str = Field(max_length=1000)
    choices: list[str] = Field(max_length=4)
    product_ids: list[str] = Field(max_length=3)
    evidence_refs: list[str]
    job_id: str | None


class CreateSession(Model):
    profile_id: Literal["alex", "sam"]


class MessageRequest(Model):
    request_id: UUID
    text: str = Field(min_length=1, max_length=2000)
    priority_choice: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def known_priority(self):
        if self.priority_choice and self.text not in PRIORITY_CHOICES:
            raise ValueError("Choose one of the offered priorities")
        return self


class CompareRequest(Model):
    product_ids: list[str] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.product_ids)) != len(self.product_ids):
            raise ValueError("Products must be distinct")
        return self


class SelectionRequest(Model):
    variant_ids: list[str] = Field(min_length=1, max_length=3)


class OutfitRequest(SelectionRequest):
    request_id: UUID


class TryOnRequest(OutfitRequest):
    photo_base64: str = Field(min_length=1, max_length=7 * 1024 * 1024)
    consent: bool = Field(strict=True)


class SamplePersonRequest(Model):
    request_id: UUID


class SampleTryOnRequest(OutfitRequest):
    sample_job_id: UUID


class ComplementRequest(Model):
    selected_product_id: str


class SearchRequest(Model):
    intent: Intent


class Empty(Model):
    pass


class ConfirmSelection(Model):
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    accept_exceptions: bool = Field(default=False, strict=True)


class JourneyObservation(Model):
    event_id: UUID
    name: Literal["shortlist_shown", "comparison_opened"]


class JourneyFeedback(Model):
    helpful: bool = Field(strict=True)
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class RelaxRequest(Model):
    alternative_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class ModerationDecision(Model):
    stage: Literal["user_input", "image_prompt", "chat_output", "try_on_photo"]
    request_id: str
    provider_id: str | None
    model: str
    policy_version: str
    decision: Literal["allow", "block", "error"]
    flagged: bool | None
    flagged_categories: list[str]
    latency_ms: float
    error_code: str | None
