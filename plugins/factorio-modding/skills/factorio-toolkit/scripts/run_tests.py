#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Run a mod's in-game tests headless: create a map with the mod, then benchmark it for a few ticks.

The mod's control script reports results by logging `[FMS-TEST] PASS <name>` or `[FMS-TEST] FAIL <name>: <why>`
(from `on_init` for tests that run at map creation, or from tick handlers for tests that run during the benchmark).
Passes when both launches exit 0, no error is logged, no test fails and at least one test reported.
The user's `mods\\` and `saves\\` are never touched.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from _lib.args import add_sandbox_args, require_mod_dirs
from _lib.errors import EXIT_FAILED, cli_main
from _lib.gamerun import GameResult, describe_unrecognised_exit, run_game, save_log
from _lib.logscan import Finding, TestResult, format_finding, scan_log
from _lib.paths import locate_game
from _lib.sandbox import sandbox


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_sandbox_args(parser)
    parser.add_argument("--ticks", type=int, default=60, help="ticks to run after the map loads (default: %(default)s)")
    parser.add_argument("--seed", default="1", help="map seed, so runs are reproducible (default: %(default)s)")
    args = parser.parse_args(argv)

    install = locate_game(args.path)
    mods = require_mod_dirs(args.mod)
    findings: list[Finding] = []
    tests: list[TestResult] = []
    failed_launches: list[GameResult] = []
    with sandbox(install, mods, args.enable, args.keep) as (box, infos):
        map_zip = box.root / "test-map.zip"
        launches = [
            ["--create", str(map_zip), "--map-gen-seed", args.seed],
            ["--benchmark", str(map_zip), "--benchmark-ticks", str(args.ticks), "--benchmark-sanitize"],
        ]
        for launch in launches:
            result = run_game(install, box, launch, args.timeout)  # each launch overwrites the log, so scan after each
            save_log(args.log_dir, f"run-tests-{launch[0].lstrip('-')}", result)
            scan = scan_log(result.log)
            findings += scan.errors
            tests += scan.tests
            if result.exit_code != 0 or scan.errors:
                failed_launches.append(result)
            if result.exit_code != 0:
                break
        names = ", ".join(f"{i.name} {i.version}" for i in infos)

    for finding in findings:
        print(format_finding(finding))
    for failed in failed_launches:
        if not findings:
            print(describe_unrecognised_exit(failed))
    for test in tests:
        print(f"{'PASS' if test.passed else 'FAIL'} test: {test.name}")
    failed_tests = [t for t in tests if not t.passed]
    if findings or failed_launches or failed_tests:
        print(f"FAIL in-game tests: {names} ({len(findings)} error(s), {len(failed_tests)} failed test(s))")
        print("next step: fix the first error or failed test shown above, then run run_tests.py again")
        return EXIT_FAILED
    if not tests:
        print(f"FAIL in-game tests: {names} reported no results; the mod's control.lua must log `[FMS-TEST] PASS <name>` lines (see references/in-game-testing.md)")
        return EXIT_FAILED
    print(f"PASS in-game tests: {names}: {len(tests)} test(s) passed; no log errors")
    return 0


if __name__ == "__main__":
    cli_main(main)
