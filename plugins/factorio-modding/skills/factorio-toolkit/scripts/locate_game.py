#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Find the Factorio install and print where it reads and writes data and where its log is.

Order: --path, then FACTORIO_PATH, then common standalone locations. Portable versus system data
directories are read from `config-path.cfg` and `config.ini`, so the log path is the real one.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from _lib.args import add_game_args
from _lib.errors import cli_main
from _lib.paths import game_version, locate_game


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_game_args(parser)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)

    install = locate_game(args.path)
    fields = {
        "version": game_version(install),
        "root": install.root,
        "executable": install.exe,
        "layout": "portable" if install.portable else "system",
        "read-data": install.read_data,
        "write-data": install.write_data,
        "config.ini": install.config_ini or "(none found)",
        "mods": install.mods_dir,
        "saves": install.saves_dir,
        "log": install.log_path,
    }
    if args.json:
        print(json.dumps({k: str(v) for k, v in fields.items()}, indent=2))
    else:
        width = max(map(len, fields))
        for key, value in fields.items():
            print(f"{key:<{width}}  {value}")
    return 0


if __name__ == "__main__":
    cli_main(main)
