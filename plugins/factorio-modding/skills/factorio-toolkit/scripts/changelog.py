#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Print the "Modding:" sections of the game's changelog for the versions after FROM up to and including TO.

The changelog ships with the game as data/changelog.txt. Every output line starts with its version so it
survives grep:

  2.1.21 Modding: Added CraftingMachinePrototype::animation_random_start_frame.

Use --section Scripting to read the runtime-API entries instead (or as well); --section can repeat.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from _lib.errors import ToolkitError, cli_main
from _lib.paths import locate_game

VERSION_LINE = re.compile(r"^Version:\s*(\d+(?:\.\d+)*)\s*$")
DATE_LINE = re.compile(r"^Date:\s*(.*?)\s*$")
SECTION_LINE = re.compile(r"^ {2}([A-Za-z][A-Za-z ]*):\s*$")
ITEM_LINE = re.compile(r"^ {4}- (.*)$")
CONTINUATION_LINE = re.compile(r"^ {6,}(\S.*)$")


@dataclass
class Release:
    version: str
    date: str = ""
    sections: dict[str, list[str]] = field(default_factory=dict)


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def parse_changelog(text: str) -> list[Release]:
    """Parse changelog.txt into releases in file order (newest first). Wrapped entries are joined into one line."""
    releases: list[Release] = []
    release: Release | None = None
    items: list[str] | None = None
    for line in text.splitlines():
        if match := VERSION_LINE.match(line):
            release = Release(match.group(1))
            releases.append(release)
            items = None
        elif release is None:
            continue
        elif match := DATE_LINE.match(line):
            release.date = match.group(1)
        elif match := SECTION_LINE.match(line):
            items = release.sections.setdefault(match.group(1), [])
        elif items is not None and (match := ITEM_LINE.match(line)):
            items.append(match.group(1).strip())
        elif items and (match := CONTINUATION_LINE.match(line)):
            items[-1] += " " + match.group(1).strip()
    return releases


def select(releases: Sequence[Release], after: str, upto: str) -> list[Release]:
    """Releases with `after` < version <= `upto`, oldest first (compared as numbers, not by position in the file)."""
    lo, hi = version_key(after), version_key(upto)
    return sorted((r for r in releases if lo < version_key(r.version) <= hi), key=lambda r: version_key(r.version))


def render(releases: Sequence[Release], sections: Sequence[str]) -> list[str]:
    wanted = [s.lower() for s in sections]
    lines: list[str] = []
    for release in releases:
        picked = [(name, items) for name, items in release.sections.items() if name.lower() in wanted and items]
        if not picked:
            continue
        lines.append(f"## {release.version}" + (f" ({release.date})" if release.date else ""))
        for name, items in picked:
            lines += [f"{release.version} {name}: {item}" for item in items]
    return lines


def _game_changelog(game_path: str | None) -> Path:
    try:
        return locate_game(game_path).changelog
    except ToolkitError as exc:
        raise ToolkitError(exc.message, f"{exc.hint or ''} Or pass a changelog.txt directly with --file.".strip()) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="changelog.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("after", help="version already in use, excluded (for example 2.0.77)")
    parser.add_argument("upto", help="target version, included (for example 2.1.21)")
    parser.add_argument("--file", type=Path, help="changelog.txt to read (default: data/changelog.txt of the located game)")
    parser.add_argument("--path", help="Factorio install folder (default: FACTORIO_PATH, then the usual locations)")
    parser.add_argument("--section", action="append", default=None, help="section to print, e.g. Modding or Scripting (repeatable; default Modding)")
    return parser


def main(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(argv)
    for value in (args.after, args.upto):
        if not re.fullmatch(r"\d+(\.\d+)+", value):
            raise ToolkitError(f"{value!r} is not a version.", "use X.Y.Z, for example `changelog.py 2.0.77 2.1.21`.")
    if version_key(args.after) >= version_key(args.upto):
        raise ToolkitError(
            f"FROM ({args.after}) must be lower than TO ({args.upto}).",
            "the range is FROM exclusive to TO inclusive; downgrades are not supported.",
        )
    path = args.file or _game_changelog(args.path)
    if not path.is_file():
        raise ToolkitError(
            f"changelog not found at {path}.",
            "pass the file with --file, or point FACTORIO_PATH (or --path) at the folder that contains bin\\x64\\factorio.exe.",
        )
    releases = parse_changelog(path.read_text("utf-8", "replace"))
    if not releases:
        raise ToolkitError(f"{path} has no `Version:` entries.", "pass a changelog.txt from a Factorio install with --file.")
    newest = max((r.version for r in releases), key=version_key)
    if version_key(newest) < version_key(args.upto):
        print(f"# note: this changelog ends at {newest}, so changes up to {args.upto} are missing.", file=sys.stderr)
    chosen = select(releases, args.after, args.upto)
    sections = args.section or ["Modding"]
    lines = render(chosen, sections)
    print(f"# changelog {args.after} (excluded) -> {args.upto}: {len(chosen)} versions, sections: {', '.join(sections)}; source {path}")
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    cli_main(main)
