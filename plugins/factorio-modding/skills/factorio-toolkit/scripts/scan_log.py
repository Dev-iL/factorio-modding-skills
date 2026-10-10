#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Scan Factorio logs once and report errors with their stage and location. Never tails a log.

Warnings are reported only with --warnings; they do not fail the scan.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from _lib.args import add_game_args
from _lib.errors import EXIT_FAILED, ToolkitError, cli_main
from _lib.logscan import format_finding, scan_log
from _lib.paths import locate_game


def _log_files(args: argparse.Namespace) -> list[Path]:
    if args.log_dir:
        files = sorted(args.log_dir.glob("*.log"))
        if not files:
            raise ToolkitError(f"no .log files in {args.log_dir}.", "run check_data.py or run_tests.py with --log-dir first.")
        return files
    files = args.log or [locate_game(args.path).log_path]
    missing = [f for f in files if not f.is_file()]
    if missing:
        raise ToolkitError(f"no log file at {missing[0]}.", "run the game once (see check_data.py / run_tests.py) or pass --log.")
    return files


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_game_args(parser)
    parser.add_argument("--log", type=Path, action="append", help="log file to scan; repeatable (default: the located install's factorio-current.log)")
    parser.add_argument("--log-dir", type=Path, help="scan every *.log in this folder (written by check_data.py / run_tests.py --log-dir)")
    parser.add_argument("--warnings", action="store_true", help="also print warnings")
    parser.add_argument("--allow-unused", action="store_true", help="do not treat 'prototype value was not used' warnings as errors")
    args = parser.parse_args(argv)

    files = _log_files(args)
    error_count = warning_count = test_lines = 0
    for log_path in files:
        result = scan_log(log_path.read_text("utf-8", errors="replace"), unused_is_error=not args.allow_unused)
        for finding in result.errors:
            print(format_finding(finding, log_path.name))
        if args.warnings:
            for finding in result.warnings:
                print(format_finding(finding, log_path.name))
        for test in result.tests:
            print(f"{'PASS' if test.passed else 'FAIL'} test: {test.name}")
        error_count += len(result.errors)
        warning_count += len(result.warnings)
        test_lines += len(result.tests)
    where = ", ".join(str(f) for f in files)
    if error_count:
        print(f"FAIL log scan: {error_count} error(s) in {where}")
        return EXIT_FAILED
    print(f"PASS log scan: no errors in {where} ({warning_count} warning(s), {test_lines} test line(s))")
    return 0


if __name__ == "__main__":
    cli_main(main)
