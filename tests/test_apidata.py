from __future__ import annotations

import json
from pathlib import Path

import httpx2
import pytest
from _lib.apidata import ApiStore
from _lib.errors import ToolkitError
from _lib.http import RetryPolicy, make_client
from _lib.paths import GameInstall

from api_docs import FakeSite, prototype_old, runtime_old


def store_for(site: FakeSite, root: Path, now: float = 1000.0) -> ApiStore:
    client = make_client(transport=httpx2.MockTransport(site))
    return ApiStore(client, root, policy=RetryPolicy(sleep=lambda _: None), now=lambda: now)


def doc(version: str, stage: str) -> bytes:
    base = dict(runtime_old() if stage == "runtime" else prototype_old())
    base["application_version"] = version
    return json.dumps(base).encode()


def site_for(version: str) -> FakeSite:
    return FakeSite({f"/{version}/runtime-api.json": doc(version, "runtime"), f"/{version}/prototype-api.json": doc(version, "prototype")})


def test_each_document_is_downloaded_once_per_version(tmp_path: Path) -> None:
    site = site_for("2.0.0")
    store = store_for(site, tmp_path)
    for _ in range(2):
        assert store.runtime("2.0.0")["classes"]
        assert store.prototype("2.0.0")["prototypes"]
    assert site.requests == ["/2.0.0/runtime-api.json", "/2.0.0/prototype-api.json"]


def test_refresh_downloads_again(tmp_path: Path) -> None:
    site = site_for("2.0.0")
    store = store_for(site, tmp_path)
    store.runtime("2.0.0")
    store.runtime("2.0.0", refresh=True)
    assert len(site.requests) == 2


def test_a_cache_hit_is_logged(tmp_path: Path) -> None:
    messages: list[str] = []
    client = make_client(transport=httpx2.MockTransport(site_for("2.0.0")))
    store = ApiStore(client, tmp_path, log=messages.append)
    store.runtime("2.0.0")
    store.runtime("2.0.0")
    assert messages[0].startswith("downloading https://lua-api.factorio.com/2.0.0/runtime-api.json")
    assert messages[1].startswith("cache hit:")


def test_an_html_error_page_is_never_cached(tmp_path: Path) -> None:
    site = FakeSite({"/2.0.0/runtime-api.json": b"<html>Service unavailable</html>"})
    store = store_for(site, tmp_path)
    with pytest.raises(ToolkitError, match="not valid JSON"):
        store.runtime("2.0.0")
    assert not store.path("2.0.0", "runtime").exists()


def test_a_document_of_another_api_version_is_rejected(tmp_path: Path) -> None:
    old_format = json.dumps({"api_version": 5, "stage": "runtime"}).encode()
    store = store_for(FakeSite({"/1.1.0/runtime-api.json": old_format}), tmp_path)
    with pytest.raises(ToolkitError, match="api_version 6"):
        store.runtime("1.1.0")


def test_an_unknown_version_says_so(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as info:
        store_for(FakeSite({}), tmp_path).runtime("9.9.9")
    assert "was not found" in info.value.message and "9.9.9" in info.value.message


def test_latest_is_resolved_to_a_concrete_version_and_reused_for_a_day(tmp_path: Path) -> None:
    site = site_for("2.5.0")
    site.documents["/latest/runtime-api.json"] = doc("2.5.0", "runtime")
    assert store_for(site, tmp_path, now=1000.0).resolve("latest") == "2.5.0"
    assert store_for(site, tmp_path, now=1000.0 + 3600).resolve("latest") == "2.5.0"
    assert site.requests == ["/latest/runtime-api.json"]
    assert store_for(site, tmp_path, now=1000.0 + 3600).runtime("2.5.0")["classes"]  # filled from the `latest` download
    assert site.requests == ["/latest/runtime-api.json"]
    store_for(site, tmp_path, now=1000.0 + 25 * 3600).resolve("latest")
    assert site.requests == ["/latest/runtime-api.json"] * 2


def test_installed_uses_the_local_games_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install = GameInstall(root=tmp_path, exe=tmp_path / "factorio.exe", read_data=tmp_path, write_data=tmp_path, config_ini=None, portable=True)
    monkeypatch.setattr("_lib.apidata.paths.locate_game", lambda: install)
    monkeypatch.setattr("_lib.apidata.paths.game_version", lambda install: "2.1.21")
    assert store_for(FakeSite({}), tmp_path).resolve("installed") == "2.1.21"


def test_a_malformed_version_is_explained(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError, match="not a Factorio version"):
        store_for(FakeSite({}), tmp_path).resolve("two-point-one")
