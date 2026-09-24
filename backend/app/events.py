import json
import logging

logger = logging.getLogger("trailshop")


def event(name, **fields):
    logger.info(json.dumps({"event": name, **fields}, ensure_ascii=False, default=str))
