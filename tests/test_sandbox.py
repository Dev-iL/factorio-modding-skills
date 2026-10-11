"""The sandbox isolates runs from the user's install and cleans up only what it created."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from _lib.errors import ToolkitError
from _lib.paths import GameInstall
from _lib.sandbox import enabled_mod_names, read_mod_info, remove_link, sandbox


def fake_install(root: Path, write_data: Path | None = None) -> GameInstall:
    (root / "data").mkdir(parents=True)
    for name, deps in {
        "space-age": ["base", "elevated-rails >= 2.0.0", "quality >= 2.0.0"],
        "quality": ["base"],
        "elevated-rails": ["base"],
        "recycler": ["base"],
    }.items():
        (root / "data" / name).mkdir()
        (root / "data" / name / "info.json").write_text(json.dumps({"name": name, "dependencies": deps}), "utf-8")
    return GameInstall(root=root, exe=root / "bin" / "x64" / "factorio.exe", read_data=root / "data",
                       write_data=write_data or root, config_ini=None, portable=True)


def make_mod(path: Path, name: str, dependencies: list[str]) -> Path:
    path.mkdir(parents=True)
    (path / "info.json").write_text(json.dumps({"name": name, "version": "1.2.3", "dependencies": dependencies}), "utf-8")
    (path / "data.lua").write_text("-- data", "utf-8")
    return path


def test_mod_info_requires_info_json(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as err:
        read_mod_info(tmp_path)
    assert "info.json" in err.value.message


def test_only_depended_on_dlc_is_enabled_with_its_own_requirements(tmp_path: Path) -> None:
    install = fake_install(tmp_path / "game")
    plain = read_mod_info(make_mod(tmp_path / "a", "plain", ["base"]))
    aged = read_mod_info(make_mod(tmp_path / "b", "aged", ["base", "? space-age", "! recycler"]))
    assert enabled_mod_names(install, [plain]) == ["base", "plain"]
    assert enabled_mod_names(install, [aged]) == ["base", "elevated-rails", "quality", "space-age", "aged"]
    assert enabled_mod_names(install, [plain], extra=["recycler"]) == ["base", "recycler", "plain"]


def test_sandbox_links_mod_writes_mod_list_and_cleans_up(tmp_path: Path) -> None:
    install = fake_install(tmp_path / "game")
    mod = make_mod(tmp_path / "src" / "mymod", "mymod", ["base"])
    with sandbox(install, [mod]) as (box, infos):
        link = box.mods_dir / "mymod"
        assert os.path.isjunction(link) or link.is_symlink()
        assert (link / "data.lua").read_text("utf-8") == "-- data"
        listing = {m["name"]: m["enabled"] for m in json.loads((box.mods_dir / "mod-list.json").read_text("utf-8"))["mods"]}
        assert listing == {"base": True, "mymod": True, "elevated-rails": False, "quality": False, "space-age": False, "recycler": False}
        assert f"write-data={box.write_data}" in box.config_ini.read_text("utf-8")
        assert infos[0].version == "1.2.3"
        root = box.root
    assert not root.exists()
    assert (mod / "data.lua").exists() and (mod / "info.json").exists()


def test_sandbox_cleans_up_when_the_body_raises(tmp_path: Path) -> None:
    install = fake_install(tmp_path / "game")
    mod = make_mod(tmp_path / "mymod", "mymod", ["base"])
    with pytest.raises(RuntimeError), sandbox(install, [mod]) as (box, _):
        root = box.root
        raise RuntimeError("test body failed")
    assert not root.exists() and (mod / "info.json").exists()


def test_keep_leaves_the_sandbox_but_removes_links(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    install = fake_install(tmp_path / "game")
    mod = make_mod(tmp_path / "mymod", "mymod", ["base"])
    with sandbox(install, [mod], keep=True) as (box, _):
        root = box.root
    try:
        assert root.exists() and not (root / "mods" / "mymod").exists()
        assert str(root) in capsys.readouterr().out
    finally:
        import shutil

        shutil.rmtree(root)


def test_duplicate_mod_names_are_rejected(tmp_path: Path) -> None:
    install = fake_install(tmp_path / "game")
    a = make_mod(tmp_path / "a", "same", ["base"])
    b = make_mod(tmp_path / "b", "same", ["base"])
    with pytest.raises(ToolkitError), sandbox(install, [a, b]):
        pass


def test_remove_link_leaves_real_directories_alone(tmp_path: Path) -> None:
    real = make_mod(tmp_path / "real", "real", ["base"])
    remove_link(real)
    assert (real / "info.json").exists()


def test_a_link_that_cannot_be_removed_keeps_the_sandbox_and_the_mod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    install = fake_install(tmp_path / "game")
    mod = make_mod(tmp_path / "mymod", "mymod", ["base"])

    def refuse(link: Path) -> None:
        raise PermissionError("in use")

    monkeypatch.setattr("_lib.sandbox.remove_link", refuse)
    with sandbox(install, [mod]) as (box, _):
        root = box.root
    try:
        assert root.exists(), "never rmtree a sandbox whose link is still in place"
        assert (mod / "info.json").exists() and (mod / "data.lua").exists()
        assert "could not remove link" in capsys.readouterr().err
    finally:
        monkeypatch.undo()
        remove_link(root / "mods" / "mymod")
        import shutil

        shutil.rmtree(root)


def test_sandbox_refuses_to_sit_inside_the_games_own_data_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_root = tmp_path / "temp"
    tmp_root.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(tmp_root))
    install = fake_install(tmp_path / "game", write_data=tmp_root)
    mod = make_mod(tmp_path / "mymod", "mymod", ["base"])
    with pytest.raises(ToolkitError, match="inside the game's own data folder"), sandbox(install, [mod]):
        pass
    assert not list(tmp_root.glob("fm-sandbox-*"))
