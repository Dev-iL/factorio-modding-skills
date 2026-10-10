"""Remove credential values from text before it is printed, logged or raised."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable

REDACTED = "***"

_QUERY_PARAM = re.compile(r"(?i)\b(username|token|password|api[_-]?key|secret)=([^&\s\"'<>]+)")
_JSON_FIELD = re.compile(
    r"(?i)(\"(?:service-)?(?:username|token|password|api[_-]?key|secret)\"\s*:\s*\")([^\"]*)(\")"
)
_ENV_SECRET_NAMES = ("FACTORIO_TOKEN",)


def _known_secrets() -> list[str]:
    return [v for name in _ENV_SECRET_NAMES if len(v := os.environ.get(name, "")) >= 4]


def redact(text: str, extra_secrets: Iterable[str] = ()) -> str:
    """Return `text` with credential query parameters, JSON fields and known secret values masked."""
    text = _QUERY_PARAM.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    text = _JSON_FIELD.sub(lambda m: f"{m.group(1)}{REDACTED}{m.group(3)}", text)
    for secret in (*_known_secrets(), *extra_secrets):
        if len(secret) >= 4:
            text = text.replace(secret, REDACTED)
    return text
