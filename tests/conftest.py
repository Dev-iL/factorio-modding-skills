"""Put the toolkit scripts on `sys.path` so tests can `import _lib` and import script modules by name."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "factorio-modding" / "skills" / "factorio-toolkit" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
