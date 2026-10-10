from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx2
import pytest
from _lib.creds import Credentials
from _lib.errors import ToolkitError
from _lib.http import RetryPolicy, make_client
from _lib.portalapi import Portal, newest_release, pick_release, releases_of, unpack_zip

from portal_site import NEW_RELEASE, OLD_RELEASE, TOKEN, USERNAME, FakePortal, make_zip, mod_full

CREDS = Credentials(USERNAME, TOKEN)


def portal_for(site: FakePortal, slept: list[float] | None = None) -> Portal:
    client = make_client(transport=httpx2.MockTransport(site), follow_redirects=True)
    return Portal(client, RetryPolicy(sleep=(slept if slept is not None else []).append, rng=lambda: 0.0))


def test_newest_release_is_by_version_not_by_position_and_honours_the_factorio_filter() -> None:
    releases = releases_of(mod_full())  # listed as 1.0.0 (1.1), 2.1.0 (2.1), 2.0.2 (2.0)
    newest, newest_for_2_0 = newest_release(releases), newest_release(releases, "2.0")
    assert newest is not None and newest["version"] == "2.1.0"
    assert newest_for_2_0 is not None and newest_for_2_0["version"] == "2.0.2"
    assert newest_release(releases, "0.17") is None


def test_pick_release_explains_what_exists() -> None:
    releases = [OLD_RELEASE, NEW_RELEASE]
    with pytest.raises(ToolkitError, match="no release 9.9.9") as info:
        pick_release("tiny-mod", releases, "9.9.9", None)
    assert "1.0.0, 2.0.2" in (info.value.hint or "")
    with pytest.raises(ToolkitError, match="no release for Factorio 2.1") as info:
        pick_release("tiny-mod", releases, None, "2.1")
    assert "1.1, 2.0" in (info.value.hint or "")


def test_list_sends_the_filters_as_query_parameters() -> None:
    site = FakePortal()
    page = portal_for(site).list_mods(version="2.0", page=3, page_size=5, sort="updated_at", sort_order="desc", hide_deprecated=True)
    params = site.requests[0].url.params
    assert (params["version"], params["page"], params["page_size"], params["sort"], params["sort_order"], params["hide_deprecated"]) == ("2.0", "3", "5", "updated_at", "desc", "true")
    assert "token" not in str(site.requests[0].url)
    assert page.results[0]["name"] == "tiny-mod" and page.count == 1


def test_an_invalid_version_filter_shows_the_portals_message() -> None:
    with pytest.raises(ToolkitError, match="Invalid factorio version"):
        portal_for(FakePortal()).list_mods(version="9.9")


def test_search_puts_credentials_in_the_body_not_the_url() -> None:
    site = FakePortal()
    page = portal_for(site).search("belt", CREDS)
    request = site.requests[0]
    assert request.method == "POST" and TOKEN not in str(request.url)
    assert TOKEN.encode() in request.content
    assert page.results[0]["latest_release_version"] == "2.1.0"


def test_search_with_wrong_credentials_is_explained_without_leaking_them() -> None:
    with pytest.raises(ToolkitError) as info:
        portal_for(FakePortal()).search("belt", Credentials(USERNAME, "fake-wrong-9999"))
    text = info.value.render()
    assert "Invalid username or token" in text and "fake-wrong-9999" not in text


def test_429_is_retried_with_exponential_backoff_then_succeeds() -> None:
    site = FakePortal()
    answers = iter([429, 429, 200])

    def flaky(request: httpx2.Request) -> httpx2.Response:
        status = next(answers)
        return httpx2.Response(429, headers={}) if status == 429 else site(request)

    slept: list[float] = []
    client = make_client(transport=httpx2.MockTransport(flaky))
    page = Portal(client, RetryPolicy(sleep=slept.append, rng=lambda: 0.0)).list_mods()
    assert page.count == 1 and slept == [1.0, 2.0]


def test_a_missing_mod_says_how_to_check_the_name() -> None:
    with pytest.raises(ToolkitError) as info:
        portal_for(FakePortal()).full("no-such-mod")
    assert "'no-such-mod' was not found" in info.value.message and "mods.factorio.com/mod/<name>" in (info.value.hint or "")


def test_a_mod_name_with_path_characters_is_refused_before_any_request() -> None:
    site = FakePortal()
    with pytest.raises(ToolkitError, match="not a valid mod name"):
        portal_for(site).full("../../etc/passwd")
    assert site.requests == []


def test_download_follows_the_redirect_verifies_sha1_and_unpacks(tmp_path: Path) -> None:
    site = FakePortal()
    result = portal_for(site).download("tiny-mod", NEW_RELEASE, CREDS, tmp_path)
    assert result.zip_path == tmp_path / "tiny-mod_2.0.2.zip"
    assert result.unpacked == tmp_path / "tiny-mod_2.0.2" and (result.unpacked / "info.json").is_file()
    assert not (result.unpacked / "tiny-mod_2.0.2").exists()  # the zip's top-level folder was stripped
    assert result.licence_files == ["LICENSE"]
    first = site.requests[0]
    assert first.url.params["username"] == USERNAME and first.url.params["token"] == TOKEN  # sent to the portal ...
    assert all(TOKEN not in str(r.url) for r in site.requests[1:])  # ... but not to the CDN it redirects to


def test_download_refuses_a_bad_checksum_and_html_answers(tmp_path: Path) -> None:
    site = FakePortal()
    site.download_body = make_zip() + b"tampered"
    with pytest.raises(ToolkitError, match="does not match the portal's sha1"):
        portal_for(site).download("tiny-mod", NEW_RELEASE, CREDS, tmp_path)
    site.download_body = b"<html>log in</html>"
    with pytest.raises(ToolkitError, match="not a zip file") as info:
        portal_for(site).download("tiny-mod", NEW_RELEASE, CREDS, tmp_path / "other")
    assert "credentials" in (info.value.hint or "")


def test_download_with_wrong_credentials_is_refused_and_leaves_nothing(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as info:
        portal_for(FakePortal()).download("tiny-mod", NEW_RELEASE, Credentials(USERNAME, "fake-wrong-9999"), tmp_path)
    assert "HTTP 403" in info.value.message and "fake-wrong-9999" not in info.value.render()
    assert list(tmp_path.iterdir()) == []


def test_download_does_not_overwrite_without_force(tmp_path: Path) -> None:
    portal = portal_for(FakePortal())
    portal.download("tiny-mod", NEW_RELEASE, CREDS, tmp_path)
    with pytest.raises(ToolkitError, match="already exists"):
        portal.download("tiny-mod", NEW_RELEASE, CREDS, tmp_path)
    portal.download("tiny-mod", NEW_RELEASE, CREDS, tmp_path, force=True)


def test_unpack_handles_a_zip_without_a_top_level_folder(tmp_path: Path) -> None:
    assert unpack_zip(make_zip(top=None), tmp_path / "m") == 3
    assert (tmp_path / "m" / "info.json").is_file()


def test_unpack_refuses_paths_that_escape_the_target(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mod/info.json", "{}")
        archive.writestr("mod/../../evil.txt", "x")
    with pytest.raises(ToolkitError, match="unsafe path"):
        unpack_zip(buffer.getvalue(), tmp_path / "m")
    assert not (tmp_path / "evil.txt").exists()
