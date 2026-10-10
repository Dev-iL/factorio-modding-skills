"""Find the Factorio install, resolve its read/write data directories, and name the cache directory."""

from __future__ import annotations

import configparser
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import ToolkitError

EXE_RELATIVE = Path("bin") / "x64" / "factorio.exe"
README_ANCHOR = "README.md, section 'Point the plugin at your game'"


@dataclass(frozen=True)
class GameInstall:
    """A located standalone Factorio install and where it keeps its data."""

    root: Path
    exe: Path
    read_data: Path
    write_data: Path
    config_ini: Path | None
    portable: bool

    @property
    def log_path(self) -> Path:
        return self.write_data / "factorio-current.log"

    @property
    def mods_dir(self) -> Path:
        return self.write_data / "mods"

    @property
    def saves_dir(self) -> Path:
        return self.write_data / "saves"

    @property
    def player_data(self) -> Path:
        return self.write_data / "player-data.json"

    @property
    def changelog(self) -> Path:
        return self.read_data / "changelog.txt"


def _candidate_roots(env: Mapping[str, str]) -> list[Path]:
    """Common standalone locations on Windows, in the order they are tried."""
    home = Path(env.get("USERPROFILE") or Path.home())
    program_files = [env.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)")]
    roots = [Path(pf) / "Factorio" for pf in program_files if pf]
    roots += [Path(pf) / "Steam" / "steamapps" / "common" / "Factorio" for pf in program_files if pf]
    roots += [home / "Factorio", home / "Downloads" / "Factorio", Path("C:/Factorio")]
    return roots


def _normalise_root(raw: str | Path) -> Path:
    """Accept the install root, its `bin/x64` folder, or the exe itself."""
    path = Path(raw).expanduser()
    if path.name.lower() == "factorio.exe":
        return path.parent.parent.parent
    if path.name.lower() == "x64" and path.parent.name.lower() == "bin":
        return path.parent.parent
    return path


def _is_install(root: Path) -> bool:
    return (root / EXE_RELATIVE).is_file()


def _expand(value: str, exe_dir: Path, system_write: Path) -> Path:
    value = value.replace("__PATH__executable__", str(exe_dir))
    value = value.replace("__PATH__system-write-data__", str(system_write))
    value = value.replace("__PATH__system-read-data__", str(exe_dir.parent.parent / "data"))
    return Path(os.path.normpath(value))


def _read_cfg_value(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(.*?)\s*$", path.read_text("utf-8", "replace"), re.M)
    return match.group(1) if match else None


def _read_ini_paths(config_ini: Path) -> tuple[str | None, str | None]:
    parser = configparser.RawConfigParser(strict=False, interpolation=None)
    parser.optionxform = str  # keys are case-sensitive and use dashes
    parser.read(config_ini, encoding="utf-8")
    if not parser.has_section("path"):
        return None, None
    return parser.get("path", "read-data", fallback=None), parser.get("path", "write-data", fallback=None)


def resolve_install(root: Path, env: Mapping[str, str] | None = None) -> GameInstall:
    """Resolve data directories for the install at `root`, honouring `config-path.cfg` and `config.ini`."""
    env = os.environ if env is None else env
    exe = root / EXE_RELATIVE
    exe_dir = exe.parent
    appdata = Path(env.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    system_write = appdata / "Factorio"

    use_system = (_read_cfg_value(root / "config-path.cfg", "use-system-read-write-data-directories") or "false").lower() == "true"
    config_path_value = _read_cfg_value(root / "config-path.cfg", "config-path")
    if config_path_value:
        config_dir: Path | None = _expand(config_path_value, exe_dir, system_write)
    elif use_system:
        config_dir = system_write / "config"
    else:
        config_dir = root / "config"
    config_ini = config_dir / "config.ini" if config_dir else None
    if config_ini is not None and not config_ini.is_file():
        config_ini = None

    read_raw = write_raw = None
    if config_ini is not None:
        read_raw, write_raw = _read_ini_paths(config_ini)
    default_read = root / "data"
    default_write = system_write if use_system else root
    read_data = _expand(read_raw, exe_dir, system_write) if read_raw else default_read
    write_data = _expand(write_raw, exe_dir, system_write) if write_raw else default_write
    return GameInstall(root=root, exe=exe, read_data=read_data, write_data=write_data, config_ini=config_ini, portable=not use_system)


def locate_game(explicit: str | Path | None = None, env: Mapping[str, str] | None = None) -> GameInstall:
    """Find the install: an explicit path, then `FACTORIO_PATH`, then common standalone locations."""
    env = os.environ if env is None else env
    source = None
    if explicit:
        source, raw = "the --path argument", str(explicit)
    elif env.get("FACTORIO_PATH"):
        source, raw = "FACTORIO_PATH", env["FACTORIO_PATH"]
    else:
        raw = ""
    if source:
        root = _normalise_root(raw)
        if not _is_install(root):
            raise ToolkitError(
                f"{source} is {raw!r}, but there is no {EXE_RELATIVE} under {root}.",
                f"point {source} at the folder that contains bin/x64/factorio.exe ({README_ANCHOR}).",
            )
        return resolve_install(root, env)
    for root in _candidate_roots(env):
        if _is_install(root):
            return resolve_install(root, env)
    raise ToolkitError(
        "no standalone Factorio install found: FACTORIO_PATH is not set and none of the usual locations has one.",
        f"set FACTORIO_PATH to the folder that contains bin/x64/factorio.exe ({README_ANCHOR}).",
    )


def game_version(install: GameInstall) -> str:
    """Return the game version, e.g. `2.1.21`, by asking the executable."""
    try:
        out = subprocess.run([str(install.exe), "--version"], capture_output=True, text=True, timeout=60, check=False).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolkitError(f"could not run {install.exe} --version: {exc}", "check that the install is intact and not blocked by antivirus.") from exc
    match = re.search(r"Version:\s*(\d+\.\d+\.\d+)", out)
    if not match:
        raise ToolkitError(f"{install.exe} --version printed no version line.", "reinstall or repair the game.")
    return match.group(1)


def cache_dir(env: Mapping[str, str] | None = None) -> Path:
    """Directory for downloaded API JSON and other per-version caches (`FM_CACHE_DIR` overrides it)."""
    env = os.environ if env is None else env
    if env.get("FM_CACHE_DIR"):
        return Path(env["FM_CACHE_DIR"])
    base = env.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    return Path(base) / "factorio-modding-skills"
