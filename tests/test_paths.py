"""Locating the install and resolving where it keeps data, for portable and system layouts."""

from __future__ import annotations

from pathlib import Path

import pytest
from _lib.errors import ToolkitError
from _lib.paths import cache_dir, locate_game, resolve_install

PORTABLE_CFG = "config-path=__PATH__executable__/../../config\nuse-system-read-write-data-directories=false\n"


def make_install(root: Path, config_path_cfg: str, config_ini: str | None = None) -> Path:
    (root / "bin" / "x64").mkdir(parents=True)
    (root / "bin" / "x64" / "factorio.exe").write_bytes(b"")
    (root / "data").mkdir()
    (root / "config-path.cfg").write_text(config_path_cfg, "utf-8")
    if config_ini is not None:
        (root / "config").mkdir()
        (root / "config" / "config.ini").write_text(config_ini, "utf-8")
    return root


def test_portable_install_keeps_everything_under_the_root(tmp_path: Path) -> None:
    ini = "[path]\nread-data=__PATH__executable__\\..\\..\\data\nwrite-data=__PATH__executable__\\..\\..\n"
    root = make_install(tmp_path / "f", PORTABLE_CFG, ini)
    install = locate_game(root, {})
    assert install.portable
    assert install.write_data == root
    assert install.read_data == root / "data"
    assert install.log_path == root / "factorio-current.log"
    assert install.mods_dir == root / "mods" and install.saves_dir == root / "saves"


def test_system_install_writes_under_appdata(tmp_path: Path) -> None:
    root = make_install(tmp_path / "f", "use-system-read-write-data-directories=true\n")
    install = resolve_install(root, {"APPDATA": str(tmp_path / "roaming")})
    assert not install.portable
    assert install.write_data == tmp_path / "roaming" / "Factorio"
    assert install.log_path == tmp_path / "roaming" / "Factorio" / "factorio-current.log"


def test_config_ini_overrides_write_data(tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    root = make_install(tmp_path / "f", PORTABLE_CFG, f"[path]\nwrite-data={other}\n")
    assert resolve_install(root, {}).write_data == other


def test_factorio_path_may_name_the_exe_or_its_folder(tmp_path: Path) -> None:
    root = make_install(tmp_path / "f", PORTABLE_CFG)
    assert locate_game(None, {"FACTORIO_PATH": str(root / "bin" / "x64" / "factorio.exe")}).root == root
    assert locate_game(None, {"FACTORIO_PATH": str(root / "bin" / "x64")}).root == root


def test_explicit_path_beats_environment(tmp_path: Path) -> None:
    root = make_install(tmp_path / "f", PORTABLE_CFG)
    assert locate_game(root, {"FACTORIO_PATH": str(tmp_path / "nope")}).root == root


def test_bad_factorio_path_names_variable_and_fix(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as err:
        locate_game(None, {"FACTORIO_PATH": str(tmp_path / "nope")})
    assert "FACTORIO_PATH" in err.value.message and "factorio.exe" in (err.value.hint or "")


def test_common_locations_are_searched_when_nothing_is_set(tmp_path: Path) -> None:
    home = tmp_path / "home"
    root = make_install(home / "Factorio", PORTABLE_CFG)
    assert locate_game(None, {"USERPROFILE": str(home), "ProgramFiles": str(tmp_path / "pf")}).root == root


def test_nothing_found_tells_the_user_to_set_factorio_path(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as err:
        locate_game(None, {"USERPROFILE": str(tmp_path), "ProgramFiles": str(tmp_path)})
    assert "FACTORIO_PATH" in (err.value.hint or "")


def test_cache_dir_honours_override(tmp_path: Path) -> None:
    assert cache_dir({"FM_CACHE_DIR": str(tmp_path)}) == tmp_path
    assert cache_dir({"LOCALAPPDATA": str(tmp_path)}) == tmp_path / "factorio-modding-skills"
