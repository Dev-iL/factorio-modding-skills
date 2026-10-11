"""Sort keys for version strings."""

from __future__ import annotations

import re


def version_key(version: str) -> tuple[int, ...]:
    """Key for a strict dotted version such as `2.1.21`; raises ValueError on anything else."""
    return tuple(int(part) for part in version.split("."))


def loose_version_key(version: str) -> tuple[int, ...]:
    """Key for a version string from outside (a portal release): non-numeric parts count as 0, `-` also splits."""
    return tuple(int(part) if part.isdigit() else 0 for part in re.split(r"[.\-]", version))
