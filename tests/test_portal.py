from __future__ import annotations

from pathlib import Path

import httpx2
import portal
import pytest
from _lib.errors import ToolkitError
from _lib.http import make_client

from portal_site import CUSTOM, MIT, TOKEN, USERNAME, FakePortal


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch) -> FakePortal:
    fake = FakePortal(licence=MIT)
    monkeypatch.setattr(portal, "make_client", lambda **kw: make_client(transport=httpx2.MockTransport(fake), **kw))
    monkeypatch.setenv("FACTORIO_USERNAME", USERNAME)
    monkeypatch.setenv("FACTORIO_TOKEN", TOKEN)
    return fake


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    assert portal.main(list(argv)) == 0
    return capsys.readouterr().out


def test_list_prints_one_grep_friendly_line_per_mod_and_needs_no_credentials(
    site: FakePortal, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("FACTORIO_TOKEN")
    out = run(capsys, "list", "--version", "2.0")
    assert out.splitlines()[0] == "tiny-mod  downloads=12  latest=2.0.2  factorio=2.0  owner=someone-else  A tiny mod."
    assert out.splitlines()[-1].startswith("# page 1/1: 1 mods match")


def test_list_by_name_handles_the_releases_shape(site: FakePortal, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(capsys, "list", "--namelist", "tiny-mod").startswith("tiny-mod  downloads=12  latest=2.0.2  factorio=2.0")


def test_search_without_credentials_stops_and_says_how_to_set_them(
    site: FakePortal, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FACTORIO_USERNAME")
    monkeypatch.delenv("FACTORIO_TOKEN")
    with pytest.raises(ToolkitError) as info:
        portal.main(["search", "belt"])
    assert "search needs mod portal credentials" in info.value.message
    hint = info.value.hint or ""
    assert "~/.claude/settings.json" in hint and "shell_environment_policy" in hint
    assert site.requests == []


def test_search_prints_name_downloads_versions_and_summary(site: FakePortal, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "search", "tiny")
    assert out.splitlines()[0] == "tiny-mod  downloads=12  latest=2.1.0  factorio=2.0,2.1  owner=someone-else  A tiny mod"
    assert TOKEN not in out


def test_info_shows_the_licence_and_the_newest_release_for_a_factorio_version(site: FakePortal, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "info", "tiny-mod", "--factorio-version", "2.0")
    assert "license: MIT (default_mit) https://opensource.org/licenses/MIT" in out
    assert "newest for Factorio 2.0 release: 2.0.2 (factorio 2.0)" in out
    assert "releases: 3 (factorio 1.1: 1, factorio 2.0: 1, factorio 2.1: 1)" in out


def test_info_flags_a_missing_licence(site: FakePortal, capsys: pytest.CaptureFixture[str]) -> None:
    site.licence = None
    assert "license: none declared on the portal (treat as all rights reserved" in run(capsys, "info", "tiny-mod")


def test_info_prints_the_text_of_a_custom_licence(site: FakePortal, capsys: pytest.CaptureFixture[str]) -> None:
    site.licence = CUSTOM
    out = run(capsys, "info", "tiny-mod")
    assert "license: Own terms (custom_0123)" in out
    assert "license text (author's own wording, read it before planning): Free to use. No commercial use. No modified versions." in out


def test_download_reports_the_unpacked_folder_and_licence_files_without_leaking_credentials(
    site: FakePortal, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = run(capsys, "download", "tiny-mod", "--factorio-version", "2.0", "--dest", str(tmp_path))
    assert "(sha1 ok)" in out and "license files in the mod: LICENSE" in out and "license: MIT" in out
    assert TOKEN not in out and USERNAME not in out
    assert (tmp_path / "tiny-mod_2.0.2" / "data.lua").is_file()


def test_download_of_an_unknown_mod_fails_with_the_404_message(site: FakePortal, tmp_path: Path) -> None:
    with pytest.raises(ToolkitError, match="'ghost-mod' was not found"):
        portal.main(["download", "ghost-mod", "--dest", str(tmp_path)])


def test_download_without_credentials_stops_before_downloading(
    site: FakePortal, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FACTORIO_TOKEN")
    with pytest.raises(ToolkitError, match="download needs mod portal credentials"):
        portal.main(["download", "tiny-mod", "--factorio-version", "2.0", "--dest", str(tmp_path)])
    assert not any(r.url.path.startswith("/download/") for r in site.requests)


def test_help_works(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        portal.main(["download", "--help"])
    assert exit_info.value.code == 0
    assert "--dest" in capsys.readouterr().out


@pytest.mark.network
def test_live_anonymous_list_and_info(capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "list", "--version", "2.0", "--page-size", "3")
    assert out.count("downloads=") == 3
    info = run(capsys, "info", "belt-visualizer")
    assert "license:" in info


@pytest.mark.network
def test_live_search_with_the_credentials_from_the_environment(capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "search", "belt", "--page-size", "3")
    assert out.count("downloads=") == 3 and "# page 1/" in out


@pytest.mark.network
def test_live_unknown_mod_is_a_clear_404() -> None:
    with pytest.raises(ToolkitError, match="was not found"):
        portal.main(["info", "no-such-mod-zzzz-0000"])


def test_list_page_size_must_be_a_positive_number_or_max(site: FakePortal, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as bad:
        portal.main(["list", "--page-size", "abc"])
    assert bad.value.code == 2 and "not a positive number or `max`" in capsys.readouterr().err
    assert "# page" in run(capsys, "list", "--page-size", "max")


def test_download_into_a_path_that_is_a_file_names_the_cause(site: FakePortal, tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("occupied", "utf-8")
    with pytest.raises(ToolkitError, match="could not save the download") as err:
        portal.main(["download", "tiny-mod", "--factorio-version", "2.0", "--dest", str(blocker)])
    assert "--dest" in (err.value.hint or "")
