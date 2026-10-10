"""Test setup: put the toolkit scripts on `sys.path` and give pytest a temp root of its own."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "factorio-modding" / "skills" / "factorio-toolkit" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# pytest's default `<temp>/pytest-of-<user>` can be left unreadable by an earlier tool or user account,
# which fails every `tmp_path` test with PermissionError; a root named for this repo avoids it.
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(Path(tempfile.gettempdir()) / "factorio-modding-skills-pytest"))
Path(os.environ["PYTEST_DEBUG_TEMPROOT"]).mkdir(parents=True, exist_ok=True)
