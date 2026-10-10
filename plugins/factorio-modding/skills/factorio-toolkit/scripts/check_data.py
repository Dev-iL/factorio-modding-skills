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
from _lib.gamerun import GameResult, run_game
from _lib.logscan import format_finding, scan_log
from _lib.paths import locate_game
from _lib.sandbox import sandbox


def _loaded_mods(log: str) -> set[str]:
    return set(re.findall(r"Loading mod (\S+) \S+ \(data\.lua\)", log))


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


def _print_failure(result: GameResult, problems: list[str]) -> None:
    for text in problems:
        print(text)
    if not problems:
        tail = "\n".join(f"    | {ln}" for ln in result.log.splitlines()[-15:])
        print(f"game exited with code {result.exit_code} without a recognised error; end of log:\n{tail}")


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_sandbox_args(parser)
    parser.add_argument("--expect", action="append", default=[], metavar="TYPE/NAME", help="require this prototype in data.raw, e.g. item/my-item; repeatable")
    parser.add_argument("--allow-unused", action="store_true", help="do not fail on 'prototype value was not used' warnings")
    parser.add_argument("--dump-to", type=Path, metavar="FILE", help="copy data-raw-dump.json here so it can be searched")
    args = parser.parse_args(argv)

    install = locate_game(args.path)
    mods = require_mod_dirs(args.mod)
    with sandbox(install, mods, args.enable, args.keep) as (box, infos):
        result = run_game(install, box, ["--dump-data", "--check-unused-prototype-data"], args.timeout)
        scan = scan_log(result.log, unused_is_error=not args.allow_unused)
        dump = box.script_output / "data-raw-dump.json"
        names = ", ".join(f"{i.name} {i.version}" for i in infos)
        problems = [format_finding(f) for f in scan.errors]
        if not problems and result.exit_code == 0 and not dump.is_file():
            problems.append(f"data-raw-dump.json was not written under {box.script_output}")
        if result.exit_code != 0 or problems:
            _print_failure(result, problems)
            print(f"FAIL data stage: {names} (game exit code {result.exit_code})")
            return EXIT_FAILED
        not_loaded = sorted({i.name for i in infos} - _loaded_mods(result.log))
        if not_loaded:
            print(f"FAIL data stage: {', '.join(not_loaded)} never loaded; check the mod's info.json name and dependencies")
            return EXIT_FAILED
        types, missing = _check_dump(dump, args.expect)
        if args.dump_to:
            args.dump_to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dump, args.dump_to)
    if missing:
        print(f"FAIL data stage: {names} loaded, but data.raw lacks: {', '.join(missing)}")
        return EXIT_FAILED
    print(f"PASS data stage: {names} loaded; game exit code 0; data-raw-dump.json parsed ({types} prototype types); no log errors")
    return 0


if __name__ == "__main__":
    cli_main(main)
