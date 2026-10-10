"""Read-only client for the Factorio mod portal.

Endpoints used (all but the last two work without credentials):
  GET  /api/mods               list and filter (version, namelist, page, page_size, sort, sort_order, hide_deprecated)
  GET  /api/mods/<name>/full   one mod with all releases and its licence
  POST /api/search             full-text search; username and token go in the JSON body
  GET  /download/<name>/<id>   a release zip; username and token go in the query string, the answer is a redirect
Source: https://wiki.factorio.com/Mod_portal_API, checked against live responses on 2026-10-10.
The portal's result shape differs per endpoint: a list gives `latest_release` as an object, a `namelist` query gives
`releases`, and search gives `latest_release` as an id with `latest_release_version`.
"""

from __future__ import annotations

import hashlib
import io
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TypedDict, cast

import httpx2

from .creds import ENV_TOKEN, ENV_USERNAME, Credentials
from .errors import ToolkitError
from .http import DEFAULT_POLICY, JsonObject, RetryPolicy, fail, json_object, send, write_atomic

BASE_URL = "https://mods.factorio.com"
AUTH_HINT = (
    f"check {ENV_USERNAME} and {ENV_TOKEN}: the token is the API token from your factorio.com profile page, not your password."
)
NAME_RE = re.compile(r"^[\w .\-]{1,100}$")


class ReleaseInfo(TypedDict, total=False):
    factorio_version: str
    dependencies: list[str]


class Release(TypedDict, total=False):
    download_url: str
    file_name: str
    info_json: ReleaseInfo
    released_at: str
    version: str
    sha1: str


class License(TypedDict, total=False):
    description: str
    id: str
    name: str
    title: str
    url: str


class ModEntry(TypedDict, total=False):
    """A mod as returned by list, namelist, search or `/full` (each fills a different subset)."""

    name: str
    title: str
    owner: str
    summary: str
    category: str
    tags: list[str]
    downloads_count: int
    deprecated: bool
    requires_space_age: bool
    factorio_versions: list[str]
    latest_release: Release | str
    latest_release_version: str
    releases: list[Release]
    license: License
    source_url: str
    homepage: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ModPage:
    results: list[ModEntry]
    count: int
    page: int
    page_count: int
    page_size: int


@dataclass(frozen=True)
class Downloaded:
    mod: str
    release: Release
    zip_path: Path
    unpacked: Path
    files: int
    licence_files: list[str]


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) if part.isdigit() else 0 for part in re.split(r"[.\-]", version))


def releases_of(mod: ModEntry) -> list[Release]:
    """Every release the entry carries: `releases`, or the single `latest_release` object."""
    if mod.get("releases"):
        return mod["releases"]
    latest = mod.get("latest_release")
    return [latest] if isinstance(latest, dict) else []


def newest_release(releases: list[Release], factorio_version: str | None = None) -> Release | None:
    """The highest mod version, optionally only among releases declaring `factorio_version` (such as `2.0`)."""
    pool = [r for r in releases if factorio_version is None or r.get("info_json", {}).get("factorio_version") == factorio_version]
    return max(pool, key=lambda r: (version_key(r.get("version", "0")), r.get("released_at", "")), default=None)


def pick_release(mod: str, releases: list[Release], version: str | None, factorio_version: str | None) -> Release:
    """Choose the release to download, or explain what exists."""
    if version:
        for release in releases:
            if release.get("version") == version:
                return release
        have = ", ".join(r.get("version", "?") for r in sorted(releases, key=lambda r: version_key(r.get("version", "0")))[-8:])
        raise ToolkitError(f"mod {mod!r} has no release {version}.", f"releases include: {have}. Omit --version for the newest.")
    chosen = newest_release(releases, factorio_version)
    if chosen is None:
        declared = sorted({r.get("info_json", {}).get("factorio_version", "?") for r in releases})
        raise ToolkitError(
            f"mod {mod!r} has no release for Factorio {factorio_version}.",
            f"its releases declare Factorio {', '.join(declared)}; pick one with --factorio-version, or omit it.",
        )
    return chosen


def _page(body: JsonObject) -> ModPage:
    pagination = body.get("pagination")
    results = body.get("results")
    if not isinstance(results, list) or not isinstance(pagination, dict):
        raise fail(
            f"the portal's answer has no results/pagination (keys: {', '.join(sorted(body))}).",
            f"{body.get('message') or 'the API may have changed'}; check the arguments.",
        )

    def num(key: str) -> int:
        value = pagination.get(key)
        return value if isinstance(value, int) else 0

    return ModPage(cast(list[ModEntry], results), num("count"), num("page"), num("page_count"), num("page_size"))


class Portal:
    def __init__(self, client: httpx2.Client, policy: RetryPolicy = DEFAULT_POLICY, base_url: str = BASE_URL) -> None:
        self._client = client
        self._policy = policy
        self._base = base_url

    def list_mods(
        self,
        *,
        version: str | None = None,
        namelist: list[str] | None = None,
        page: int = 1,
        page_size: int | str = 25,
        sort: str | None = None,
        sort_order: str | None = None,
        hide_deprecated: bool = False,
    ) -> ModPage:
        """Anonymous listing. The portal's own `links.next` drops the filters, so pages are requested by number."""
        params: dict[str, str | int] = {"page": page, "page_size": page_size}
        if version:
            params["version"] = version
        if namelist:
            params["namelist"] = ",".join(namelist)
        if sort:
            params["sort"] = sort
        if sort_order:
            params["sort_order"] = sort_order
        if hide_deprecated:
            params["hide_deprecated"] = "true"
        response = send(
            self._client, "GET", f"{self._base}/api/mods", what="the mod list", params=params, policy=self._policy,
            not_found_hint="the portal has no such list; try again later.",
        )
        return _page(json_object(response, "the mod list"))

    def search(self, query: str, creds: Credentials, *, version: str | None = None, page: int = 1, page_size: int = 20) -> ModPage:
        """Full-text search. Credentials go in the POST body, as the portal requires."""
        body: dict[str, str | int] = {"query": query, "username": creds.username, "token": creds.token, "page": page, "page_size": page_size}
        if version:
            body["version"] = version
        response = send(
            self._client, "POST", f"{self._base}/api/search", what=f"search {query!r}", json_body=body,
            policy=self._policy, auth_hint=AUTH_HINT, secrets=[creds.token],
        )
        return _page(json_object(response, "the search results", secrets=[creds.token]))

    def full(self, name: str) -> ModEntry:
        if not NAME_RE.match(name):
            raise ToolkitError(f"{name!r} is not a valid mod name.", "use the internal name from the mod page URL, e.g. `belt-visualizer`.")
        response = send(
            self._client, "GET", f"{self._base}/api/mods/{name.replace(' ', '%20')}/full", what=f"mod {name!r}", policy=self._policy,
            not_found_hint="use the internal name from the mod page URL (mods.factorio.com/mod/<name>); `portal.py list --namelist` checks names.",
        )
        return cast(ModEntry, json_object(response, f"mod {name!r}"))

    def download(self, mod: str, release: Release, creds: Credentials, dest: Path, *, force: bool = False) -> Downloaded:
        """Download `release`, check its sha1, save the zip under `dest` and unpack it to `dest/<mod>_<version>/`."""
        version = release.get("version", "")
        target = dest / f"{re.sub(r'[^\w.\-]', '_', mod)}_{version}"
        if target.exists() and not force:
            raise ToolkitError(f"{target} already exists.", "delete it, pick another --dest, or pass --force to replace it.")
        url = release.get("download_url", "")
        if not url.startswith("/download/"):
            raise fail(f"release {version} of {mod!r} has no usable download_url ({url!r}).", "run `portal.py info` and report the release data.")
        response = send(
            self._client, "GET", f"{self._base}{url}", what=f"the download of {mod} {version}",
            params=creds.as_query(), policy=self._policy, auth_hint=AUTH_HINT, secrets=[creds.token],
            not_found_hint="the release may have been removed; run `portal.py info` for the current releases.",
        )
        data = response.content
        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise fail(
                f"the portal's answer for {mod} {version} is not a zip file (it starts with {data[:40]!r}).",
                f"the portal usually answers like this when the credentials are wrong. {AUTH_HINT}", secrets=[creds.token],
            )
        expected = release.get("sha1", "")
        if expected and hashlib.sha1(data).hexdigest() != expected:
            raise ToolkitError(f"the downloaded zip of {mod} {version} does not match the portal's sha1.", "run the download again.")
        dest.mkdir(parents=True, exist_ok=True)
        zip_path = dest / Path(release.get("file_name") or f"{mod}_{version}.zip").name
        write_atomic(zip_path, data)
        if target.exists():
            shutil.rmtree(target)
        files = unpack_zip(data, target)
        licences = sorted(p.name for p in target.iterdir() if p.is_file() and re.match(r"(?i)(licen[sc]e|copying|copyright)", p.name))
        return Downloaded(mod, release, zip_path, target, files, licences)


def unpack_zip(data: bytes, target: Path) -> int:
    """Extract a mod zip into `target`, dropping the single top-level folder most mod zips have.

    Refuses entries that would land outside `target` and symbolic links. Returns the number of files written.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [(info, PurePosixPath(info.filename.replace("\\", "/"))) for info in archive.infolist()]
        for info, path in entries:
            if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
                raise ToolkitError(f"the zip contains an unsafe path {info.filename!r}.", "do not use this download; report the mod.")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ToolkitError(f"the zip contains a symbolic link {info.filename!r}.", "do not use this download; report the mod.")
        file_parts = [p.parts for info, p in entries if not info.is_dir()]
        tops = {parts[0] for parts in file_parts}
        strip = 1 if len(tops) == 1 and all(len(parts) > 1 for parts in file_parts) else 0
        target.mkdir(parents=True, exist_ok=True)
        root = target.resolve()
        written = 0
        for info, path in entries:
            parts = path.parts[strip:]
            if not parts:
                continue
            out = (target.joinpath(*parts)).resolve()
            if root not in out.parents and out != root:
                raise ToolkitError(f"the zip entry {info.filename!r} would leave the target folder.", "do not use this download; report the mod.")
            if info.is_dir():
                out.mkdir(parents=True, exist_ok=True)
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(archive.read(info))
            written += 1
    return written
