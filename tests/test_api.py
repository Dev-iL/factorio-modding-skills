from __future__ import annotations

from pathlib import Path

import api
import httpx2
import pytest
from _lib.errors import ToolkitError
from _lib.http import make_client

from api_docs import FakeSite, site_with_versions


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeSite:
    fake = site_with_versions()
    monkeypatch.setenv("FM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(api, "make_client", lambda **kw: make_client(transport=httpx2.MockTransport(fake), **kw))
    return fake


def test_lookup_prints_the_signature_and_description(site: FakeSite, capsys: pytest.CaptureFixture[str]) -> None:
    assert api.main(["lookup", "LuaEntity.get_inventory", "--version", "1.0.0"]) == 0
    out = capsys.readouterr().out
    assert "signature: LuaEntity.get_inventory(inventory: defines.inventory) -> LuaInventory?" in out
    assert "Get an inventory belonging to this entity." in out


def test_diff_prints_grep_friendly_lines(site: FakeSite, capsys: pytest.CaptureFixture[str]) -> None:
    assert api.main(["diff", "1.0.0", "2.0.0"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert "REMOVED runtime class LuaGone" in out


def test_a_second_run_does_not_download_again(site: FakeSite, capsys: pytest.CaptureFixture[str]) -> None:
    api.main(["--verbose", "lookup", "LuaEntity", "--version", "1.0.0"])
    first = len(site.requests)
    api.main(["--verbose", "lookup", "LuaEntity", "--version", "1.0.0"])
    assert len(site.requests) == first == 2
    assert "cache hit" in capsys.readouterr().err


def test_stage_restricts_what_is_downloaded(site: FakeSite) -> None:
    api.main(["--stage", "prototype", "lookup", "AssemblingMachinePrototype", "--version", "1.0.0"])
    assert site.requests == ["/1.0.0/prototype-api.json"]


def test_a_missing_entry_raises_a_toolkit_error_with_suggestions(site: FakeSite) -> None:
    with pytest.raises(ToolkitError) as info:
        api.main(["lookup", "LuaEntty", "--version", "1.0.0"])
    assert "did you mean" in (info.value.hint or "")


def test_help_works(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        api.main(["--help"])
    assert exit_info.value.code == 0
    assert "lookup" in capsys.readouterr().out


@pytest.mark.network
def test_live_lookup_of_a_member_inherited_from_the_parent_class(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FM_CACHE_DIR", str(tmp_path / "cache"))
    assert api.main(["lookup", "LuaEntity.get_inventory", "--version", "2.1.21"]) == 0
    assert "LuaInventory?" in capsys.readouterr().out
    assert api.main(["lookup", "AssemblingMachinePrototype", "--version", "2.1.21"]) == 0
    assert "fixed_recipe" in capsys.readouterr().out
