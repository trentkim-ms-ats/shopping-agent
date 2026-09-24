import hashlib
import json

from .config import ROOT
from .errors import AppError

DEMO_PERSON = ROOT / "data/demo/sample-person.png"
DEMO_PERSON_RECEIPT = ROOT / "data/demo/sample-person.json"


def load_demo_person():
    try:
        receipt = json.loads(DEMO_PERSON_RECEIPT.read_text())
        data = DEMO_PERSON.read_bytes()
        if receipt["status"] != "completed" or hashlib.sha256(data).hexdigest() != receipt["sha256"]:
            raise ValueError("Fixed demo asset integrity check failed")
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AppError("DEMO_PERSON_UNAVAILABLE", "The fixed demo person image is unavailable.", 503, False) from exc
