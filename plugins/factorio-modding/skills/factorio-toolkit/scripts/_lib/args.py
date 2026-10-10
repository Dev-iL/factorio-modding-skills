"""Command-line arguments shared by the scripts that launch the game."""

from __future__ import annotations

import argparse
from pathlib import Path

from .errors import ToolkitError
from .gamerun import DEFAULT_TIMEOUT


def add_game_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--path",
        help="Factorio install folder (the one with bin\\x64\\factorio.exe); default: FACTORIO_PATH, then common locations",
    )


def add_sandbox_args(parser: argparse.ArgumentParser) -> None:
    """Arguments for scripts that run the game in an isolated environment with mods linked in."""
    add_game_args(parser)
    parser.add_argument(
        "--mod", action="append", type=Path, required=True, metavar="DIR",
        help="mod folder to link in (contains info.json); repeat for several mods",
    )
    parser.add_argument(
        "--enable", action="append", default=[], metavar="NAME",
        help="also enable this official mod (elevated-rails, quality, space-age, recycler); "
        "official mods named in info.json dependencies are enabled automatically",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds to wait for each game launch (default: %(default)s)")
    parser.add_argument("--keep", action="store_true", help="keep the temporary sandbox (log, saves, script output) and print its path")


def require_mod_dirs(mods: list[Path]) -> list[Path]:
    for mod in mods:
        if not mod.is_dir():
            raise ToolkitError(f"mod folder {mod} does not exist.", "pass the folder that contains info.json.")
    return mods
