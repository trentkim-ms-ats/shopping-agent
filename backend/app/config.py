from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
ImageQuality = Literal["auto", "low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", case_sensitive=False)
    openai_api_key: str = ""
    openai_agent_model: str = "gpt-5.6-terra"
    openai_router_model: str = "gpt-5.4-mini"
    openai_enrich_model: str = "gpt-5.6-terra"
    openai_judge_model: str = "gpt-6-astra"
    openai_image_model: str = "gpt-image-2.5-flare"
    openai_agent_reasoning_effort: ReasoningEffort = "low"
    openai_router_reasoning_effort: ReasoningEffort = "none"
    openai_enrich_reasoning_effort: ReasoningEffort = "low"
    openai_judge_reasoning_effort: ReasoningEffort = "medium"
    openai_image_quality: ImageQuality = "medium"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_moderation_model: str = "omni-moderation-latest"
    moderation_policy_version: str = "v1"
    moderation_timeout_seconds: float = 5
    demo_mode: Literal["live", "fixture"] = "live"
    demo_season: Literal["fall"] = "fall"
    demo_audit_enabled: bool = True
    daily_image_call_limit: int = Field(default=100, ge=0)
    database_path: Path = Path("data/runtime/catalog.sqlite")
    index_dir: Path = Path("data/runtime/index")
    image_dir: Path = Path("data/runtime/images")
    product_image_dir: Path = Path("data/runtime/product-images")
    allowed_origin: str = "http://localhost:3000"

    @model_validator(mode="after")
    def validate_reasoning(self):
        for role in ("agent", "router", "enrich", "judge"):
            if getattr(self, f"openai_{role}_model") == "gpt-6-astra" and \
                    getattr(self, f"openai_{role}_reasoning_effort") == "none":
                raise ValueError(f"OPENAI_{role.upper()}_REASONING_EFFORT: gpt-6-astra requires low or higher")
        return self

    def model_post_init(self, context):
        for name in ("database_path", "index_dir", "image_dir", "product_image_dir"):
            path = getattr(self, name)
            if not path.is_absolute():
                setattr(self, name, ROOT / path)
        if self.demo_mode == "fixture":
            self.database_path = self.database_path.with_stem(self.database_path.stem + ".fixture")
            self.index_dir = self.index_dir / "fixture"
            self.image_dir = self.image_dir / "fixture"
            self.product_image_dir = self.product_image_dir / "fixture"

    def require_live_config(self):
        if self.demo_mode == "live":
            missing = [
                name.upper() for name in (
                    "openai_api_key", "openai_agent_model", "openai_router_model", "openai_enrich_model",
                    "openai_judge_model", "openai_image_model",
                ) if not getattr(self, name)
            ]
            if missing:
                raise RuntimeError("Missing live configuration: " + ", ".join(missing))

    def models(self):
        return {name: getattr(self, name) for name in (
            "openai_agent_model", "openai_router_model", "openai_enrich_model", "openai_judge_model",
            "openai_image_model", "openai_embedding_model", "openai_moderation_model",
        )}
