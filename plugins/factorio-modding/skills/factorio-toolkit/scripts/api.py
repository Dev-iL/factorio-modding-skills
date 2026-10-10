#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["httpx2"]
# ///
"""Look up Factorio API entries and diff API versions, from lua-api.factorio.com's JSON (cached per version).

Examples:
  api.py lookup LuaEntity.get_inventory --version 2.1.21
  api.py lookup AssemblingMachinePrototype
  api.py lookup on_built_entity --full
  api.py diff 2.0.77 2.1.21 | grep "^ADDED prototype property"
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

import httpx2
from _lib.apidata import ApiStore
from _lib.apidiff import diff_docs
from _lib.apilookup import Docs, lookup
from _lib.apimodel import STAGES
from _lib.errors import ToolkitError, cli_main
from _lib.http import make_client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verbose", "-v", action="store_true", help="say on stderr what is downloaded and what comes from the cache")
    parser.add_argument("--refresh", action="store_true", help="download the JSON again even if it is cached")
    parser.add_argument("--stage", choices=["both", *STAGES], default="both", help="restrict to runtime (control stage) or prototype (data stage) docs")
    sub = parser.add_subparsers(dest="command", required=True)

    look = sub.add_parser(
        "lookup",
        help="show one class, member, prototype, property, event, concept or define",
        description="Show an API entry. Members are found through parent classes, so LuaEntity.get_inventory works. "
        "Parameters, event data and properties are listed in the documentation's declared order.",
    )
    look.add_argument("name", help="e.g. LuaEntity, LuaEntity.get_inventory, AssemblingMachinePrototype, assembling-machine, on_built_entity, defines.inventory")
    look.add_argument("--version", default="installed", help="X.Y.Z, `latest`, or `installed` (the local game; falls back to latest). Default: installed")
    look.add_argument("--full", action="store_true", help="print complete descriptions in class and prototype listings")
    look.add_argument("--inherited", action="store_true", help="in a class listing, include members inherited from parent classes")

    diff = sub.add_parser(
        "diff",
        help="list API changes between two versions, one grep-friendly line per item",
        description="Compare two versions: lines look like `ADDED runtime class LuaFoo`, `REMOVED prototype property X.y`, "
        "`CHANGED prototype property AssemblingMachinePrototype.energy_usage: <old> -> <new>` and `MOVED ...` "
        "(a member that moved to a parent class). Pipe through grep.",
    )
    diff.add_argument("old", help="X.Y.Z, `latest` or `installed`")
    diff.add_argument("new", help="X.Y.Z, `latest` or `installed`")
    return parser


def _resolve_lookup_version(store: ApiStore, spec: str, refresh: bool) -> str:
    if spec != "installed":
        return store.resolve(spec, refresh=refresh)
    try:
        return store.resolve("installed")
    except ToolkitError as exc:
        print(f"note: {exc.message} Using the latest published version instead.", file=sys.stderr)
        return store.resolve("latest", refresh=refresh)


def _load(store: ApiStore, version: str, stage: str, refresh: bool) -> Docs:
    runtime = store.runtime(version, refresh=refresh) if stage in ("both", "runtime") else None
    prototype = store.prototype(version, refresh=refresh) if stage in ("both", "prototype") else None
    return Docs(version, runtime, prototype)


def run(args: argparse.Namespace, client: httpx2.Client, log: Callable[[str], None]) -> list[str]:
    store = ApiStore(client, log=log)
    stage: str = args.stage
    if args.command == "lookup":
        version = _resolve_lookup_version(store, args.version, args.refresh)
        docs = _load(store, version, stage, args.refresh)
        return lookup(args.name, docs, full=args.full, inherited=args.inherited)
    old, new = store.resolve(args.old, refresh=args.refresh), store.resolve(args.new, refresh=args.refresh)
    old_docs, new_docs = _load(store, old, stage, args.refresh), _load(store, new, stage, args.refresh)
    return diff_docs(old, new, old_docs.runtime, new_docs.runtime, old_docs.prototype, new_docs.prototype)


def main(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(argv)
    log = (lambda message: print(f"[api] {message}", file=sys.stderr)) if args.verbose else (lambda _: None)
    with make_client(follow_redirects=True) as client:
        for line in run(args, client, log):
            print(line)
    return 0


if __name__ == "__main__":
    cli_main(main)
