import asyncio
import base64
import random
import time

from openai import APIConnectionError, APIResponseValidationError, APIStatusError, AsyncOpenAI

from .config import ReasoningEffort
from .errors import AppError
from .events import event


class Provider:
    def __init__(self, settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0, timeout=30) \
            if settings.openai_api_key else None

    async def invoke(self, operation, *, timeout=30, retries=1, name="provider", **metadata):
        if not self.client:
            raise AppError("PROVIDER_UNCONFIGURED", "Configure the OpenAI API key and model IDs.")
        for attempt in range(retries + 1):
            start = time.monotonic()
            try:
                async with asyncio.timeout(timeout):
                    result = await operation()
                event(name, duration_ms=(time.monotonic() - start) * 1000,
                      provider_request_id=getattr(result, "_request_id", None), attempt=attempt,
                      usage=getattr(result, "usage", None), **metadata)
                return result
            except APIResponseValidationError as exc:
                event(name, error="INVALID_PROVIDER_RESPONSE", attempt=attempt,
                      duration_ms=(time.monotonic() - start) * 1000, **metadata)
                raise AppError("INVALID_PROVIDER_RESPONSE", "OpenAI returned a malformed response.") from exc
            except (APIConnectionError, APIStatusError, TimeoutError) as exc:
                transient = not isinstance(exc, APIStatusError) or exc.status_code == 429 or exc.status_code >= 500
                retrying = transient and attempt < retries
                delay = 0.15 + random.random() * 0.2 if retrying else 0
                event(name, error=type(exc).__name__, attempt=attempt,
                      duration_ms=(time.monotonic() - start) * 1000, timeout_seconds=timeout,
                      retrying=retrying, retry_delay_ms=delay * 1000, **metadata)
                if not retrying:
                    raise AppError("PROVIDER_UNAVAILABLE", "OpenAI request failed. Please retry.", retryable=transient) from exc
                await asyncio.sleep(delay)

    async def structured(self, model, prompt, data, schema, *, reasoning_effort: ReasoningEffort, **metadata):
        response = await self.invoke(
            lambda: self.client.responses.parse(
                model=model, instructions=prompt, input=data, text_format=schema, store=False,
                reasoning={"effort": reasoning_effort},
            ), name="responses", model=model, reasoning_effort=reasoning_effort, **metadata,
        )
        if response.output_parsed is None:
            raise AppError("INVALID_MODEL_OUTPUT", "Model refused or returned invalid structured output.")
        return response.output_parsed

    async def embeddings(self, texts):
        response = await self.invoke(
            lambda: self.client.embeddings.create(model=self.settings.openai_embedding_model, input=texts),
            name="embeddings", model=self.settings.openai_embedding_model,
        )
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    async def image(self, prompt, *, size="1024x1024", quality=None):
        quality = quality or self.settings.openai_image_quality
        response = await self.invoke(
            lambda: self.client.images.generate(
                model=self.settings.openai_image_model, prompt=prompt, n=1,
                size=size, output_format="png", quality=quality, timeout=110,
            ), timeout=110, retries=0, name="images", model=self.settings.openai_image_model,
            quality=quality, size=size,
        )
        return self.image_bytes(response)

    async def edit_image(self, prompt, photo: bytes, *, references: list[bytes] | None = None,
                         size="1024x1024", quality=None):
        quality = quality or self.settings.openai_image_quality
        source = ("photo.png", photo, "image/png")
        images = [source, *((f"garment-{i + 1}.png", data, "image/png")
                            for i, data in enumerate(references))] if references else source
        response = await self.invoke(
            lambda: self.client.images.edit(
                model=self.settings.openai_image_model, prompt=prompt,
                image=images, n=1, size=size, output_format="png", quality=quality, timeout=110,
            ), timeout=110, retries=0, name="image_edit", model=self.settings.openai_image_model,
            quality=quality, size=size, input_images=1 + len(references or []),
        )
        return self.image_bytes(response)

    @staticmethod
    def image_bytes(response):
        if not response.data or not response.data[0].b64_json:
            raise AppError("INVALID_IMAGE", "Image provider did not return image bytes.")
        try:
            image = base64.b64decode(response.data[0].b64_json, validate=True)
        except ValueError as exc:
            raise AppError("INVALID_IMAGE", "Image provider returned malformed image data.") from exc
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AppError("INVALID_IMAGE", "Image provider returned a non-PNG image.")
        return image
