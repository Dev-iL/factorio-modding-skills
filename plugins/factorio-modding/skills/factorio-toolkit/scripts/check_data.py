#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Validate a mod's data stage: run `factorio --dump-data` with the mod linked in an isolated sandbox.

Passes when the game exits 0, the log has no errors (unknown prototype properties count as errors),
and `data-raw-dump.json` was written and parses. The user's `mods\\` and `saves\\` are never touched.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections.abc import Sequence
from pathlib import Path

from _lib.args import add_sandbox_args, require_mod_dirs
from _lib.errors import EXIT_FAILED, ToolkitError, cli_main
from _lib.gamerun import GameResult, describe_unrecognised_exit, run_game, run_game_until_error, save_log
from _lib.logscan import format_finding, scan_log
from _lib.paths import GameInstall, locate_game
from _lib.sandbox import Sandbox, sandbox


def _loaded_mods(log: str) -> set[str]:
    """Mods the game loaded. A mod without `data.lua` logs no `Loading mod` line, but every loaded mod gets a checksum line."""
    return set(re.findall(r"Checksum of (\S+): \d+", log))


def _check_dump(dump: Path, expected: Sequence[str]) -> tuple[int, list[str]]:
    """Return (number of prototype types, expected `type/name` entries missing from data.raw)."""
    try:
        raw = json.loads(dump.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolkitError(
            f"{dump.name} is not valid JSON ({exc}).", "re-run; if it repeats, the game wrote a truncated dump (disk full?)."
        ) from exc
    missing = [item for item in expected if item.partition("/")[2] not in raw.get(item.partition("/")[0], {})]
    return len(raw), missing


GRAPHICS_TIMEOUT = 240
SPRITES_LOADED = "Sprites loaded"


def _graphics_load_ok(install: GameInstall, box: Sandbox, args: argparse.Namespace, names: str) -> bool:
    """Start the game with a window just long enough to load every sprite; the first sprite error, or the end of loading, stops it."""
    result = run_game_until_error(
        install, box, ["--dump-icon-sprites", "--window-size", "800x600"], min(args.timeout, GRAPHICS_TIMEOUT), SPRITES_LOADED
    )
    save_log(args.log_dir, "check-data-graphics", result)
    scan = scan_log(result.log, unused_is_error=not args.allow_unused)
    for finding in scan.errors:
        print(format_finding(finding))
    if scan.errors or SPRITES_LOADED not in result.log:
        reason = "a sprite error stopped the game" if scan.errors else ("the game did not finish loading sprites in time" if result.timed_out else f"the game exited with code {result.exit_code} before loading sprites")
        print(f"FAIL graphics load: {names}: {reason}")
        return False
    return True


def _print_failure(result: GameResult, problems: list[str]) -> None:
    for text in problems:
        print(text)
    if not problems:
        print(describe_unrecognised_exit(result))


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_sandbox_args(parser)
    parser.add_argument("--expect", action="append", default=[], metavar="TYPE/NAME", help="require this prototype in data.raw, e.g. item/my-item; repeatable")
    parser.add_argument("--allow-unused", action="store_true", help="do not fail on 'prototype value was not used' warnings")
    parser.add_argument(
        "--graphics", action="store_true",
        help="also load every sprite (a second launch with `--dump-icon-sprites`; a small game window opens for about a minute). "
        "--dump-data does not read sprite files, so a missing PNG or an out-of-range sprite rectangle passes without this",
    )
    parser.add_argument("--dump-to", type=Path, metavar="FILE", help="copy data-raw-dump.json here so it can be searched")
    args = parser.parse_args(argv)

    install = locate_game(args.path)
    mods = require_mod_dirs(args.mod)
    with sandbox(install, mods, args.enable, args.keep) as (box, infos):
        result = run_game(install, box, ["--dump-data", "--check-unused-prototype-data"], args.timeout)
        save_log(args.log_dir, "check-data", result)
        scan = scan_log(result.log, unused_is_error=not args.allow_unused)
        dump = box.script_output / "data-raw-dump.json"
        names = ", ".join(f"{i.name} {i.version}" for i in infos)
        problems = [format_finding(f) for f in scan.errors]
        if not problems and result.exit_code == 0 and not dump.is_file():
            problems.append(f"data-raw-dump.json was not written under {box.script_output}")
        if result.exit_code != 0 or problems:
            _print_failure(result, problems)
            print(f"FAIL data stage: {names} (game exit code {result.exit_code})")
            print("next step: fix the first error shown above, then run check_data.py again")
            return EXIT_FAILED
        not_loaded = sorted({i.name for i in infos} - _loaded_mods(result.log))
        if not_loaded:
            print(f"FAIL data stage: {', '.join(not_loaded)} never loaded; check the mod's info.json name and dependencies")
            return EXIT_FAILED
        types, missing = _check_dump(dump, args.expect)
        if args.graphics and not _graphics_load_ok(install, box, args, names):
            return EXIT_FAILED
        if args.dump_to:
            args.dump_to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dump, args.dump_to)
    if missing:
        print(f"FAIL data stage: {names} loaded, but data.raw lacks: {', '.join(missing)}")
        return EXIT_FAILED
    print(f"PASS data stage: {names} loaded; game exit code 0; data-raw-dump.json parsed ({types} prototype types); no log errors" + ("; all sprites loaded" if args.graphics else ""))
    return 0


if __name__ == "__main__":
    cli_main(main)
