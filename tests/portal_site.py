"""A fake mod portal for the portal tests: serves canned JSON and a mod zip, and records every request."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

import httpx2

TOKEN = "fake-token-0000"
USERNAME = "someone"

OLD_RELEASE = {
    "download_url": "/download/tiny-mod/aaa111",
    "file_name": "tiny-mod_1.0.0.zip",
    "info_json": {"factorio_version": "1.1", "dependencies": ["base >= 1.1"]},
    "released_at": "2023-01-01T00:00:00.000000Z",
    "version": "1.0.0",
    "sha1": "",
}


def make_zip(top: str | None = "tiny-mod_2.0.2") -> bytes:
    buffer = io.BytesIO()
    prefix = f"{top}/" if top else ""
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{prefix}info.json", json.dumps({"name": "tiny-mod", "version": "2.0.2", "factorio_version": "2.0"}))
        archive.writestr(f"{prefix}data.lua", "-- data stage\n")
        archive.writestr(f"{prefix}LICENSE", "MIT License\n")
    return buffer.getvalue()


ZIP_BYTES = make_zip()

NEW_RELEASE = {
    "download_url": "/download/tiny-mod/bbb222",
    "file_name": "tiny-mod_2.0.2.zip",
    "info_json": {"factorio_version": "2.0", "dependencies": ["base >= 2.0.0"]},
    "released_at": "2024-10-22T00:00:00.000000Z",
    "version": "2.0.2",
    "sha1": hashlib.sha1(ZIP_BYTES).hexdigest(),
}
NEWEST_FOR_2_1 = {
    "download_url": "/download/tiny-mod/ccc333",
    "file_name": "tiny-mod_2.1.0.zip",
    "info_json": {"factorio_version": "2.1"},
    "released_at": "2026-07-01T00:00:00.000000Z",
    "version": "2.1.0",
    "sha1": "",
}


def mod_full(license_: dict[str, str] | None = None) -> dict[str, object]:
    full: dict[str, object] = {
        "name": "tiny-mod",
        "title": "Tiny Mod",
        "owner": "someone-else",
        "summary": "A tiny mod.\r\nWith two lines.",
        "category": "utilities",
        "tags": ["logistics"],
        "downloads_count": 12,
        "source_url": "https://example.test/src",
        "homepage": "",
        # deliberately not in version order: the 2.1 release comes before the newer 2.0 one
        "releases": [OLD_RELEASE, NEWEST_FOR_2_1, NEW_RELEASE],
    }
    if license_:
        full["license"] = license_
    return full


MIT = {"id": "default_mit", "name": "mit", "title": "MIT", "url": "https://opensource.org/licenses/MIT"}


class FakePortal:
    """Handler for `httpx2.MockTransport`. Set `licence` to None to model a mod with no declared licence."""

    def __init__(self, licence: dict[str, str] | None = None) -> None:
        self.licence = licence
        self.requests: list[httpx2.Request] = []
        self.download_body: bytes = ZIP_BYTES

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/mods":
            page = {"count": 1, "page": 1, "page_count": 1, "page_size": 25, "links": {"first": None, "next": None, "prev": None, "last": None}}
            entry = {
                "name": "tiny-mod", "title": "Tiny Mod", "owner": "someone-else", "summary": "A tiny\r\nmod.", "downloads_count": 12,
                "latest_release": NEW_RELEASE,
            }
            if "namelist" in request.url.params:
                entry = {k: v for k, v in entry.items() if k != "latest_release"} | {"releases": [OLD_RELEASE, NEW_RELEASE]}
            if request.url.params.get("version") == "9.9":
                return httpx2.Response(400, json={"message": "Invalid factorio version"})
            return httpx2.Response(200, json={"pagination": page, "results": [entry]})
        if path == "/api/search":
            body = json.loads(request.content)
            if body.get("token") != TOKEN or body.get("username") != USERNAME:
                return httpx2.Response(403, json={"message": "Invalid username or token"})
            pagination = {"count": 1, "page": 1, "page_count": 1, "page_size": 20}
            hit = {
                "name": "tiny-mod", "owner": "someone-else", "summary": "A tiny mod", "downloads_count": 12,
                "factorio_versions": ["2.0", "2.1"], "latest_release": "bbb222", "latest_release_version": "2.1.0", "requires_space_age": False,
            }
            return httpx2.Response(200, json={"category_hits": {}, "expansion_hits": {}, "pagination": pagination, "results": [hit], "tag_hits": {}})
        if path == "/api/mods/tiny-mod/full":
            return httpx2.Response(200, json=mod_full(self.licence))
        if path.startswith("/api/mods/"):
            return httpx2.Response(404, json={"message": "Mod not found"})
        if path == "/download/tiny-mod/bbb222":
            if request.url.params.get("token") != TOKEN:
                return httpx2.Response(403, headers={"content-type": "text/html"}, text="<html>forbidden</html>")
            return httpx2.Response(302, headers={"location": "https://dl-mod.example.test/files/ab/cdef"})
        if request.url.host == "dl-mod.example.test":
            return httpx2.Response(200, content=self.download_body)
        return httpx2.Response(404, json={"message": "not found"})
