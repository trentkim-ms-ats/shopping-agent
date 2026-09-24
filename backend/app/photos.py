import base64
import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import AppError

MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_REQUEST_BYTES = 7 * 1024 * 1024
PRIVATE_TTL_SECONDS = 15 * 60


def normalize_image(data: bytes, *, max_bytes=MAX_PHOTO_BYTES) -> bytes:
    if len(data) > max_bytes:
        raise AppError("PHOTO_TOO_LARGE", "Use a JPEG or PNG photo no larger than 5 MiB.", 413, False)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ("JPEG", "PNG") or getattr(source, "n_frames", 1) != 1:
                    raise AppError("INVALID_PHOTO", "Use a single-frame JPEG or PNG photo.", 422, False)
                width, height = source.size
                if not (256 <= width <= 4096 and 256 <= height <= 4096) or width * height > 16_000_000:
                    raise AppError("INVALID_PHOTO_DIMENSIONS", "Photo dimensions must be 256–4096 pixels, at most 16 megapixels.", 422, False)
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((1536, 1536))
                # A new pixel-only image discards EXIF, GPS, ICC profiles and embedded text.
                clean = Image.new("RGB", oriented.size, "white")
                if "A" in oriented.getbands() or "transparency" in oriented.info:
                    rgba = oriented.convert("RGBA")
                    clean.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    clean.paste(oriented.convert("RGB"))
                output = io.BytesIO()
                clean.save(output, format="PNG")
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise AppError("INVALID_PHOTO", "The photo could not be decoded safely. Use a valid JPEG or PNG.", 422, False) from exc


def decode_photo(encoded: str) -> bytes:
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise AppError("INVALID_PHOTO", "Photo data must be valid base64, not a URL or file path.", 422, False) from exc
    return normalize_image(data)
