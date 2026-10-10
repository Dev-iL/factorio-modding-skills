#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["httpx2"]
# ///
"""Read-only mod portal client: list, search, inspect and download mods. It never changes anything on the portal.

  portal.py list --version 2.0 --sort updated_at --sort-order desc   (no login)
  portal.py info belt-visualizer                                     (no login; shows the licence)
  portal.py search "belt"                                            (needs FACTORIO_USERNAME / FACTORIO_TOKEN)
  portal.py download belt-visualizer --factorio-version 2.0 --dest ./work   (needs the same credentials)
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import httpx2
from _lib.creds import ALLOW_FLAG, Credentials, get_credentials
from _lib.errors import ToolkitError, cli_main
from _lib.http import make_client
from _lib.portalapi import BASE_URL, ModEntry, ModPage, Portal, newest_release, pick_release, releases_of, version_key

SORT_KEYS = ("name", "created_at", "updated_at")  # `downloads_count` is accepted by the portal but ignored (verified live)


def one_line(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def result_line(mod: ModEntry) -> str:
    """`name  downloads=N  latest=V  factorio=2.0,2.1  owner=O  summary` for list and search results."""
    latest = mod.get("latest_release")
    if isinstance(latest, dict):
        version, factorio = latest.get("version", "?"), [latest.get("info_json", {}).get("factorio_version", "?")]
    else:
        newest = newest_release(releases_of(mod))
        version = mod.get("latest_release_version") or (newest or {}).get("version", "?")
        factorio = mod.get("factorio_versions") or [(newest or {}).get("info_json", {}).get("factorio_version", "?")]
    extras = " space-age" if mod.get("requires_space_age") else ""
    return (
        f"{mod.get('name', '?')}  downloads={mod.get('downloads_count', 0)}  latest={version}  "
        f"factorio={','.join(factorio)}{extras}  owner={mod.get('owner', '?')}  {one_line(mod.get('summary', ''))}"
    ).rstrip()


def page_lines(page: ModPage) -> list[str]:
    footer = f"# page {page.page}/{page.page_count}: {page.count} mods match, {len(page.results)} shown (page size {page.page_size})"
    return [*(result_line(mod) for mod in page.results), footer]


def require_credentials(allow_player_data: bool, action: str) -> Credentials:
    try:
        return get_credentials(allow_player_data=allow_player_data)
    except ToolkitError as exc:
        raise ToolkitError(f"{action} needs mod portal credentials. {exc.message}", exc.hint) from exc


def licence_line(mod: ModEntry) -> str:
    licence = mod.get("license")
    if not licence:
        return "license: none declared on the portal (treat as all rights reserved; read the mod's own LICENSE file, see references/licensing.md)"
    title = licence.get("title") or licence.get("name") or licence.get("id", "?")
    return f"license: {title} ({licence.get('id', '?')}) {licence.get('url', '')}".rstrip()


def info_lines(mod: ModEntry, factorio_version: str | None, all_releases: bool) -> list[str]:
    name = mod.get("name", "?")
    releases = releases_of(mod)
    newest = newest_release(releases, factorio_version)
    by_factorio = Counter(r.get("info_json", {}).get("factorio_version", "?") for r in releases)
    lines = [
        f"name: {name}",
        f"url: {BASE_URL}/mod/{name}",
        f"title: {mod.get('title', '')}",
        f"owner: {mod.get('owner', '')}",
        f"category: {mod.get('category', '')}  tags: {', '.join(mod.get('tags', []))}",
        f"downloads: {mod.get('downloads_count', 0)}",
        f"summary: {one_line(mod.get('summary', ''), 300)}",
        licence_line(mod),
        f"source_url: {mod.get('source_url') or '(none)'}",
        f"homepage: {mod.get('homepage') or '(none)'}",
    ]
    if newest:
        info = newest.get("info_json", {})
        which = f"newest for Factorio {factorio_version}" if factorio_version else "newest"
        lines.append(f"{which} release: {newest.get('version')} (factorio {info.get('factorio_version', '?')}), released {newest.get('released_at', '')[:10]}")
        lines.append(f"  dependencies: {', '.join(info.get('dependencies', [])) or '(none listed)'}")
    elif factorio_version:
        lines.append(f"no release for Factorio {factorio_version}")
    lines.append(f"releases: {len(releases)} ({', '.join(f'factorio {k}: {v}' for k, v in sorted(by_factorio.items()))})")
    if all_releases:
        for r in sorted(releases, key=lambda r: version_key(r.get("version", "0"))):
            lines.append(f"  release {r.get('version')}  factorio={r.get('info_json', {}).get('factorio_version', '?')}  {r.get('released_at', '')[:10]}")
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="portal.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    lst = sub.add_parser("list", help="list or filter mods (no login)")
    lst.add_argument("--version", help="only mods with a release for this Factorio version, such as 2.0 or 2.1")
    lst.add_argument("--namelist", help="comma-separated internal mod names to fetch (also a quick existence check)")
    lst.add_argument("--page", type=int, default=1)
    lst.add_argument("--page-size", default="25", help="results per page, or `max` (default 25)")
    lst.add_argument("--sort", choices=SORT_KEYS, help="the portal sorts by these keys only (not by downloads)")
    lst.add_argument("--sort-order", choices=("asc", "desc"))
    lst.add_argument("--hide-deprecated", action="store_true")

    srch = sub.add_parser("search", help="full-text search (needs credentials)")
    srch.add_argument("text", help="search text, e.g. belt")
    srch.add_argument("--version", help="only mods with a release for this Factorio version")
    srch.add_argument("--page", type=int, default=1)
    srch.add_argument("--page-size", type=int, default=20)

    info = sub.add_parser("info", help="show one mod: licence, newest release, dependencies (no login)")
    info.add_argument("name", help="internal mod name, as in mods.factorio.com/mod/<name>")
    info.add_argument("--factorio-version", help="show the newest release for this Factorio version")
    info.add_argument("--releases", action="store_true", help="list every release")

    dl = sub.add_parser("download", help="download a release and unpack it (needs credentials)")
    dl.add_argument("name", help="internal mod name")
    dl.add_argument("--version", help="exact mod version (default: the newest matching release)")
    dl.add_argument("--factorio-version", help="newest release declaring this Factorio version, such as 2.0")
    dl.add_argument("--dest", required=True, type=Path, help="folder for the zip; the mod is unpacked to <dest>/<name>_<version>/")
    dl.add_argument("--force", action="store_true", help="replace an existing unpacked folder")

    for command in (srch, dl):
        command.add_argument(ALLOW_FLAG, action="store_true", dest="allow_player_data",
                             help="if FACTORIO_USERNAME/FACTORIO_TOKEN are unset, read the game's player-data.json; "
                             "only pass this after the user approved it")
    return parser


def run(args: argparse.Namespace, client: httpx2.Client) -> list[str]:
    portal = Portal(client)
    out: list[str] = []
    if args.command == "list":
        page_size: int | str = args.page_size if args.page_size == "max" else int(args.page_size)
        namelist = [n.strip() for n in args.namelist.split(",") if n.strip()] if args.namelist else None
        page = portal.list_mods(
            version=args.version, namelist=namelist, page=args.page, page_size=page_size,
            sort=args.sort, sort_order=args.sort_order, hide_deprecated=args.hide_deprecated,
        )
        out += page_lines(page)
    elif args.command == "search":
        creds = require_credentials(args.allow_player_data, "search")
        out += page_lines(portal.search(args.text, creds, version=args.version, page=args.page, page_size=args.page_size))
    elif args.command == "info":
        out += info_lines(portal.full(args.name), args.factorio_version, args.releases)
    else:
        mod = portal.full(args.name)
        release = pick_release(args.name, releases_of(mod), args.version, args.factorio_version)
        creds = require_credentials(args.allow_player_data, "download")
        result = portal.download(args.name, release, creds, args.dest, force=args.force)
        out += [
            f"downloaded: {result.zip_path} (sha1 ok)",
            f"unpacked: {result.unpacked} ({result.files} files)",
            f"release: {release.get('version')} (factorio {release.get('info_json', {}).get('factorio_version', '?')})",
            licence_line(mod),
            f"license files in the mod: {', '.join(result.licence_files) or 'none found'}",
        ]
    return out


def main(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(argv)
    with make_client(follow_redirects=True) as client:
        for line in run(args, client):
            print(line)
    return 0


if __name__ == "__main__":
    cli_main(main)
