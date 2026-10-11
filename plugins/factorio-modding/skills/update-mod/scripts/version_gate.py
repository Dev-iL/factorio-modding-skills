#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Decide whether update-mod may start: refuse downgrades and source versions older than 2.0.77.

Reads `factorio_version` from the mod's info.json (X, a `major.minor` series such as `2.0`) and compares it with
the target game version Y (for example `2.1.21`). Exit 0 means the update may proceed; exit 2 means it is refused
and no analysis should run. A source series is taken to start at its earliest supported release: 2.0 means 2.0.77 and 2.1 means 2.1.7.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

Version = tuple[int, int, int]

MIN_SOURCE: Version = (2, 0, 77)
# Earliest release of each series with published API JSON on lua-api.factorio.com (2.1.0-2.1.6 answer 404), so the
# earliest version a diff can start from.
SERIES_FLOOR: dict[tuple[int, int], Version] = {(2, 0): MIN_SOURCE, (2, 1): (2, 1, 7)}


class Refused(Exception):
    """The update is not supported; the message says why and what to do instead."""


@dataclass(frozen=True)
class Verdict:
    source_series: str
    source_baseline: Version
    target: Version


def parse_version(text: str, what: str) -> Version:
    match = re.fullmatch(r"\s*(\d+)\.(\d+)(?:\.(\d+))?\s*", text)
    if not match:
        raise Refused(f"cannot read {what} {text!r} as a Factorio version like 2.0 or 2.1.21; fix it and re-run")
    return int(match[1]), int(match[2]), int(match[3] or 0)


def fmt(version: Version) -> str:
    return ".".join(map(str, version))


def read_source_series(mod_dir: Path) -> str:
    info = mod_dir / "info.json"
    if not info.is_file():
        raise Refused(f"{mod_dir} has no info.json; pass the folder that contains the mod's info.json")
    try:
        data = json.loads(info.read_text("utf-8-sig"))
    except (OSError, UnicodeDecodeError) as exc:
        raise Refused(f"cannot read {info} ({exc}); check the file's permissions and that it is UTF-8 text") from exc
    except json.JSONDecodeError as exc:
        raise Refused(f"{info} is not valid JSON ({exc}); fix it and re-run") from exc
    if not isinstance(data, dict):
        raise Refused(f"{info} must hold a JSON object with the mod's name and version; fix it and re-run")
    # info.json omits factorio_version for 0.x-era mods; Factorio then assumes 0.12.
    return str(data.get("factorio_version") or "0.12")


def check(source_series: str, target_text: str) -> Verdict:
    """Return the verdict for updating a mod declaring `source_series` to the game version `target_text`."""
    source = parse_version(source_series, "the mod's factorio_version")
    target = parse_version(target_text, "the target version")
    if (source[0], source[1]) < (2, 0):
        raise Refused(
            f"updating a mod that declares Factorio {source_series} is not yet supported: update-mod starts at 2.0.77. "
            "Next step: port the mod to 2.0 by hand first, then run update-mod on the result"
        )
    baseline = SERIES_FLOOR.get((source[0], source[1]), source)
    if (target[0], target[1]) < (source[0], source[1]):
        raise Refused(
            f"downgrades are not yet supported: the mod declares Factorio {source_series} and the target is {fmt(target)}. "
            f"Next step: choose a target of {source_series} or newer"
        )
    if target < baseline:
        raise Refused(
            f"targets older than {fmt(baseline)} are not yet supported: the API documentation for the {source_series} series starts there. "
            f"Next step: choose {fmt(baseline)} or newer"
        )
    return Verdict(source_series=source_series, source_baseline=baseline, target=target)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod", type=Path, required=True, help="mod folder containing info.json")
    parser.add_argument("--target", required=True, help="target game version, e.g. 2.1.21 (the installed version is printed by factorio-toolkit/scripts/locate_game.py)")
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON")
    args = parser.parse_args(argv)
    try:
        verdict = check(read_source_series(args.mod), args.target)
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"source_series": verdict.source_series, "source_baseline": fmt(verdict.source_baseline), "target": fmt(verdict.target)}))
    else:
        print(f"ok: mod declares {verdict.source_series} (diff from {fmt(verdict.source_baseline)}), target {fmt(verdict.target)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
