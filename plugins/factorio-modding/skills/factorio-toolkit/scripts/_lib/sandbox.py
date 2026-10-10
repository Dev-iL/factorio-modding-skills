"""An isolated Factorio run environment: a temp write-data directory and a temp mod directory.

Test runs never touch the user's mods or saves folders: the game is started with its own `config.ini`
(`write-data` in a temp folder) and `--mod-directory` pointing at a temp folder that holds a directory
junction to each mod under test plus a generated `mod-list.json`. Everything the game writes (log,
saves, script output, `player-data.json`) lands in the temp folder, so the user's install is left as found.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ToolkitError
from .paths import GameInstall

OFFICIAL_MODS = ("elevated-rails", "quality", "space-age", "recycler")
_DEP_PREFIX = re.compile(r"^\s*(?P<flag>\(\?\)|\?|\+|~|!)?\s*(?P<name>[A-Za-z0-9_\- ]+?)\s*(?:[<>=]=?.*)?$")


@dataclass(frozen=True)
class ModInfo:
    """What the sandbox needs to know about a mod folder."""

    name: str
    version: str
    dependencies: tuple[str, ...]
    path: Path


@dataclass
class Sandbox:
    """A temp run environment. Create it with `sandbox()`; it removes itself and its links on exit."""

    root: Path
    config_ini: Path
    write_data: Path
    mods_dir: Path
    links: list[Path] = field(default_factory=list)

    @property
    def log_path(self) -> Path:
        return self.write_data / "factorio-current.log"

    @property
    def script_output(self) -> Path:
        return self.write_data / "script-output"


def read_mod_info(mod_path: Path) -> ModInfo:
    """Read `info.json` from a mod folder."""
    info_file = mod_path / "info.json"
    if not info_file.is_file():
        raise ToolkitError(f"{mod_path} has no info.json, so it is not a mod folder.", "pass the folder that contains info.json, control.lua and data.lua.")
    try:
        data = json.loads(info_file.read_text("utf-8-sig"))
        return ModInfo(
            name=str(data["name"]),
            version=str(data.get("version", "0.0.0")),
            dependencies=tuple(str(d) for d in data.get("dependencies", ["base"])),
            path=mod_path.resolve(),
        )
    except (json.JSONDecodeError, KeyError) as exc:
        raise ToolkitError(f"{info_file} is not valid mod metadata ({exc}).", "fix info.json: it needs at least a `name` and a `version`.") from exc


def _wanted_dependencies(dependencies: Iterable[str]) -> set[str]:
    """Mod names an info.json dependency list asks for (required, optional and load-order-only; not `!` incompatible)."""
    wanted: set[str] = set()
    for dep in dependencies:
        match = _DEP_PREFIX.match(dep)
        if match and match["flag"] != "!":
            wanted.add(match["name"].strip())
    return wanted


def _official_required(install: GameInstall, name: str) -> set[str]:
    """Official mods that official mod `name` requires (read from the install's own info.json)."""
    info = install.read_data / name / "info.json"
    if not info.is_file():
        return set()
    wanted = _wanted_dependencies(json.loads(info.read_text("utf-8-sig")).get("dependencies", []))
    return wanted & set(OFFICIAL_MODS)


def enabled_mod_names(install: GameInstall, mods: Iterable[ModInfo], extra: Iterable[str] = ()) -> list[str]:
    """Names to enable: base, the mods under test, and only the official DLC mods they (transitively) depend on."""
    wanted: set[str] = set(extra)
    for mod in mods:
        wanted |= _wanted_dependencies(mod.dependencies)
    official = {name for name in wanted if name in OFFICIAL_MODS}
    pending = list(official)
    while pending:
        for dep in _official_required(install, pending.pop()):
            if dep not in official:
                official.add(dep)
                pending.append(dep)
    return ["base", *sorted(official), *[m.name for m in mods]]


def _make_link(source: Path, link: Path) -> None:
    """Create a directory junction (Windows) or symlink at `link` pointing to `source`."""
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(source), str(link))
    else:
        os.symlink(source, link, target_is_directory=True)


def remove_link(link: Path) -> None:
    """Remove a link created by `_make_link` without following it. Anything else is left alone."""
    if not (link.is_symlink() or os.path.isjunction(link)):
        return
    if os.name == "nt":
        os.rmdir(link)
    else:
        link.unlink()


@contextmanager
def sandbox(install: GameInstall, mods: Iterable[Path], extra_enabled: Iterable[str] = (), keep: bool = False) -> Iterator[tuple[Sandbox, list[ModInfo]]]:
    """Build the isolated environment, yield it, then remove the links and the temp folder (unless `keep`)."""
    infos = [read_mod_info(p) for p in mods]
    names = [i.name for i in infos]
    if len(set(names)) != len(names):
        raise ToolkitError(f"the same mod name appears twice: {sorted(names)}.", "pass each mod once.")
    root = Path(tempfile.mkdtemp(prefix="fm-sandbox-"))
    box: Sandbox | None = None
    try:
        write_data = root / "wd"
        mods_dir = root / "mods"
        write_data.mkdir()
        mods_dir.mkdir()
        if write_data.resolve().is_relative_to(install.write_data.resolve()):
            raise ToolkitError("refusing to run: the sandbox would sit inside the game's own data folder.", "set TMP/TEMP to a folder outside the Factorio install.")
        config_ini = root / "config.ini"
        config_ini.write_text(f"[path]\nread-data={install.read_data}\nwrite-data={write_data}\n", "utf-8")
        box = Sandbox(root=root, config_ini=config_ini, write_data=write_data, mods_dir=mods_dir)
        for info in infos:
            link = mods_dir / info.name
            _make_link(info.path, link)
            box.links.append(link)
        listing = [{"name": n, "enabled": True} for n in enabled_mod_names(install, infos, extra_enabled)]
        listing += [{"name": n, "enabled": False} for n in OFFICIAL_MODS if n not in {e["name"] for e in listing}]
        (mods_dir / "mod-list.json").write_text(json.dumps({"mods": listing}, indent=2), "utf-8")
        yield box, infos
    finally:
        stuck: list[Path] = []
        for link in box.links if box else []:
            try:
                remove_link(link)
            except OSError:
                stuck.append(link)
        if keep:
            print(f"sandbox kept at {root}")
        elif stuck:  # never rmtree through a link we could not remove: it would reach the mod's own files
            print(f"warning: could not remove link(s) {[str(p) for p in stuck]}; left {root} in place", file=sys.stderr)
        else:
            shutil.rmtree(root, ignore_errors=True)
