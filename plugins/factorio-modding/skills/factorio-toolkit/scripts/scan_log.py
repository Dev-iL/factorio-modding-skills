#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Scan a Factorio log once and report errors with their stage and location. Never tails the log."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from _lib.args import add_game_args
from _lib.errors import EXIT_FAILED, ToolkitError, cli_main
from _lib.logscan import format_finding, scan_log
from _lib.paths import locate_game


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_game_args(parser)
    parser.add_argument("--log", type=Path, help="log file to scan (default: the located install's factorio-current.log)")
    parser.add_argument("--warnings", action="store_true", help="also print warnings")
    parser.add_argument("--allow-unused", action="store_true", help="do not treat 'prototype value was not used' warnings as errors")
    args = parser.parse_args(argv)

    log_path = args.log or locate_game(args.path).log_path
    if not log_path.is_file():
        raise ToolkitError(f"no log file at {log_path}.", "run the game once (see check_data.py / run_tests.py) or pass --log.")
    result = scan_log(log_path.read_text("utf-8", errors="replace"), unused_is_error=not args.allow_unused)

    for finding in result.errors:
        print(format_finding(finding, log_path.name))
    if args.warnings:
        for finding in result.warnings:
            print(format_finding(finding, log_path.name))
    for test in result.tests:
        print(f"{'PASS' if test.passed else 'FAIL'} test: {test.name}")
    if result.errors:
        print(f"FAIL log scan: {len(result.errors)} error(s) in {log_path}")
        return EXIT_FAILED
    print(f"PASS log scan: no errors in {log_path} ({len(result.warnings)} warning(s), {len(result.tests)} test line(s))")
    return 0


if __name__ == "__main__":
    cli_main(main)
