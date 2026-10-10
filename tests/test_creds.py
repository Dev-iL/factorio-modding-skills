from __future__ import annotations

import json
from pathlib import Path

import pytest
from _lib.creds import get_credentials
from _lib.errors import ToolkitError

ENV = {"FACTORIO_USERNAME": "someone", "FACTORIO_TOKEN": "fake-token-0000"}


def write_player_data(path: Path, **fields: str) -> Path:
    path.write_text(json.dumps(fields), "utf-8")
    return path


def test_environment_variables_are_used() -> None:
    creds = get_credentials(env=ENV)
    assert (creds.username, creds.token) == ("someone", "fake-token-0000")


def test_token_is_not_in_repr() -> None:
    assert "fake-token-0000" not in repr(get_credentials(env=ENV))


def test_missing_variables_explain_how_to_set_them_for_both_hosts() -> None:
    with pytest.raises(ToolkitError) as info:
        get_credentials(env={"FACTORIO_USERNAME": "someone"})
    assert "FACTORIO_TOKEN" in info.value.message and "FACTORIO_USERNAME" not in info.value.message
    hint = info.value.hint or ""
    assert "~/.claude/settings.json" in hint and "shell_environment_policy" in hint and "--allow-player-data" in hint


def test_player_data_is_not_touched_without_the_flag(tmp_path: Path) -> None:
    pd = write_player_data(tmp_path / "player-data.json", **{"service-username": "x", "service-token": "y"})
    with pytest.raises(ToolkitError):
        get_credentials(allow_player_data=False, player_data_path=pd, env={})


def test_player_data_fallback_when_approved(tmp_path: Path) -> None:
    pd = write_player_data(tmp_path / "player-data.json", **{"service-username": "alice", "service-token": "fake-token-1111"})
    creds = get_credentials(allow_player_data=True, player_data_path=pd, env={})
    assert (creds.username, creds.token) == ("alice", "fake-token-1111")


def test_environment_wins_over_player_data_even_when_approved(tmp_path: Path) -> None:
    missing = tmp_path / "absent.json"  # would raise if it were read
    assert get_credentials(allow_player_data=True, player_data_path=missing, env=ENV).username == "someone"


def test_player_data_without_login_is_explained(tmp_path: Path) -> None:
    pd = write_player_data(tmp_path / "player-data.json", **{"latest-multiplayer-connections": "[]"})
    with pytest.raises(ToolkitError, match="not logged in"):
        get_credentials(allow_player_data=True, player_data_path=pd, env={})
