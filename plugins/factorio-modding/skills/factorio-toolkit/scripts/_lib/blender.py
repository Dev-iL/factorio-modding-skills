"""Find the Blender executable (shared by the sprite tool and preflight)."""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

from .errors import ToolkitError


def find_blender(env: Mapping[str, str] | None = None) -> Path:
    """`BLENDER_PATH`, then `blender` on PATH, then the standard Windows install folders (newest version first)."""
    env = os.environ if env is None else env
    configured = env.get("BLENDER_PATH")
    if configured:
        path = Path(configured)
        path = path / "blender.exe" if path.is_dir() else path
        if not path.is_file():
            raise ToolkitError(f"BLENDER_PATH is {configured!r}, but that is not a Blender executable.", "point BLENDER_PATH at blender.exe, or unset it to search the usual places.")
        return path
    on_path = shutil.which("blender", path=env.get("PATH"))
    if on_path:
        return Path(on_path)
    roots = [env.get("ProgramFiles"), env.get("ProgramFiles(x86)"), str(Path(env["LOCALAPPDATA"]) / "Programs") if env.get("LOCALAPPDATA") else None]
    found = [exe for root in roots if root for exe in (Path(root) / "Blender Foundation").glob("Blender *\\blender.exe")]
    if found:
        return max(found, key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)])
    raise ToolkitError(
        "Blender was not found: BLENDER_PATH is not set, `blender` is not on PATH and it is not in the usual install folders.",
        "install Blender (https://www.blender.org/download/) or set BLENDER_PATH to the full path of blender.exe.",
    )
