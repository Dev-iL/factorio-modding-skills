"""locate_game prints the resolved layout and fails clearly when nothing is found."""

from __future__ import annotations

import json
from pathlib import Path

import locate_game
import pytest
from _lib.errors import ToolkitError


def make_install(root: Path) -> Path:
    (root / "bin" / "x64").mkdir(parents=True)
    (root / "bin" / "x64" / "factorio.exe").write_bytes(b"")
    (root / "config-path.cfg").write_text("use-system-read-write-data-directories=false\n", "utf-8")
    return root


def test_missing_install_without_path_names_the_fix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for var in ("FACTORIO_PATH",):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path))
    with pytest.raises(ToolkitError) as err:
        locate_game.main([])
    assert "FACTORIO_PATH" in (err.value.hint or "")


def test_prints_layout_with_log_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_install(tmp_path / "factorio")
    monkeypatch.setattr(locate_game, "game_version", lambda install: "2.1.21")
    assert locate_game.main(["--path", str(root), "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["version"] == "2.1.21" and info["layout"] == "portable"
    assert Path(info["log"]) == root / "factorio-current.log"
