"""Download, validate and cache the runtime and prototype API JSON per game version.

The files live at https://lua-api.factorio.com/<version>/runtime-api.json and prototype-api.json. A downloaded
file is cached under `<cache_dir>/api/<version>/` and never fetched again; `latest` and `installed` are resolved
to a concrete version first (`latest` through a pointer file that expires after a day, since it moves).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

import httpx2

from . import paths
from .apimodel import API_VERSION, STAGES, PrototypeDoc, RuntimeDoc, Stage
from .errors import ToolkitError
from .http import DEFAULT_POLICY, RetryPolicy, cached_download, fail, parse_json_bytes, send, write_atomic

BASE_URL = "https://lua-api.factorio.com"
LATEST_TTL_SECONDS = 24 * 3600
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _check_document(data: bytes, stage: Stage, what: str) -> None:
    doc = parse_json_bytes(data, what)
    if doc.get("api_version") != API_VERSION or doc.get("stage") != stage:
        raise fail(
            f"{what} is not an api_version {API_VERSION} {stage} document "
            f"(api_version={doc.get('api_version')!r}, stage={doc.get('stage')!r}).",
            "the service may have changed its JSON format; report this, or pick a game version from 2.0 onward.",
        )


class ApiStore:
    """Per-version cache of the API JSON, backed by lua-api.factorio.com."""

    def __init__(
        self,
        client: httpx2.Client,
        cache_root: Path | None = None,
        *,
        policy: RetryPolicy = DEFAULT_POLICY,
        log: Callable[[str], None] = lambda _: None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._client = client
        self._root = (cache_root or paths.cache_dir()) / "api"
        self._policy = policy
        self._log = log
        self._now = now

    def path(self, version: str, stage: Stage) -> Path:
        return self._root / version / f"{stage}-api.json"

    def resolve(self, spec: str, *, refresh: bool = False) -> str:
        """Turn `latest`, `installed` or a literal `X.Y.Z` into a concrete version."""
        if VERSION_RE.match(spec):
            return spec
        if spec == "installed":
            install = paths.locate_game()
            version = paths.game_version(install)
            self._log(f"installed game version: {version} ({install.root})")
            return version
        if spec == "latest":
            return self._resolve_latest(refresh)
        raise ToolkitError(
            f"{spec!r} is not a Factorio version.",
            "use X.Y.Z (for example 2.1.21), `latest`, or `installed` for the version of your local game.",
        )

    def _resolve_latest(self, refresh: bool) -> str:
        pointer = self._root / "latest.json"
        if pointer.is_file() and not refresh:
            try:
                info = json.loads(pointer.read_text("utf-8"))
                if self._now() - float(info["fetched_at"]) < LATEST_TTL_SECONDS and VERSION_RE.match(info["version"]):
                    self._log(f"cache hit: `latest` is {info['version']} (pointer {pointer})")
                    return str(info["version"])
            except (OSError, ValueError, KeyError, TypeError):
                pass  # unreadable pointer: fall through and refetch it
        url = f"{BASE_URL}/latest/runtime-api.json"
        self._log(f"downloading {url}")
        data = send(self._client, "GET", url, what="the latest runtime API JSON", policy=self._policy).content
        _check_document(data, "runtime", url)
        version = str(parse_json_bytes(data, url).get("application_version", ""))
        if not VERSION_RE.match(version):
            raise fail(f"{url} reports application_version {version!r}.", "run with an explicit version such as 2.1.21.")
        runtime = self.path(version, "runtime")
        if not runtime.is_file():
            write_atomic(runtime, data)
        write_atomic(pointer, json.dumps({"version": version, "fetched_at": self._now()}).encode("utf-8"))
        return version

    def fetch(self, version: str, stage: Stage, *, refresh: bool = False) -> Path:
        """Make sure the JSON for `version`/`stage` is cached and return its path."""
        dest = self.path(version, stage)
        url = f"{BASE_URL}/{version}/{stage}-api.json"
        what = f"the {stage} API JSON for Factorio {version}"
        if dest.is_file() and not refresh:
            self._log(f"cache hit: {dest}")
            return dest
        self._log(f"downloading {url}")
        cached_download(
            self._client,
            url,
            dest,
            what=what,
            validate=lambda data: _check_document(data, stage, url),
            force=refresh,
            policy=self._policy,
            not_found_hint=(
                f"check that {version} is a released Factorio version; {BASE_URL}/ lists the versions with docs "
                "(the oldest releases have no machine-readable docs)."
            ),
        )
        return dest

    def _load(self, version: str, stage: Stage, refresh: bool) -> bytes:
        path = self.fetch(version, stage, refresh=refresh)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise fail(f"could not read {path}: {exc.strerror or exc}.", "delete the cache folder and run again.") from exc

    def runtime(self, version: str, *, refresh: bool = False) -> RuntimeDoc:
        return cast(RuntimeDoc, parse_json_bytes(self._load(version, "runtime", refresh), str(self.path(version, "runtime"))))

    def prototype(self, version: str, *, refresh: bool = False) -> PrototypeDoc:
        return cast(PrototypeDoc, parse_json_bytes(self._load(version, "prototype", refresh), str(self.path(version, "prototype"))))


__all__ = ["ApiStore", "BASE_URL", "STAGES", "version_key"]
