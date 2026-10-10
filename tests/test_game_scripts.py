"""The game loop against the real local install: data-stage check, in-game tests, log scan, and what each reports.

These need Factorio (FACTORIO_PATH or a standard location) and are skipped without it.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterator
from pathlib import Path

import check_data
import pytest
import run_tests
import scan_log
from _lib import gamerun
from _lib.errors import ToolkitError
from _lib.paths import GameInstall, locate_game
from _lib.sandbox import sandbox

pytestmark = pytest.mark.game

MODS = Path(__file__).parent / "fixtures" / "mods"


@pytest.fixture(scope="module")
def install() -> GameInstall:
    try:
        return locate_game()
    except ToolkitError as exc:
        pytest.skip(f"no Factorio install: {exc.message}")


def tree_hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(autouse=True)
def install_is_left_as_found(install: GameInstall) -> Iterator[None]:
    before = (tree_hashes(install.mods_dir), tree_hashes(install.saves_dir))
    yield
    assert (tree_hashes(install.mods_dir), tree_hashes(install.saves_dir)) == before


def run_cli(module, argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = module.main(argv)
    return code, capsys.readouterr().out


def test_good_mod_passes_the_data_stage_and_exposes_its_prototype(install: GameInstall, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_cli(check_data, ["--mod", str(MODS / "fms-good"), "--expect", "item/fms-test-item"], capsys)
    assert code == 0, out
    assert out.startswith("PASS data stage: fms-good 0.1.0")


def test_missing_expected_prototype_fails(install: GameInstall, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_cli(check_data, ["--mod", str(MODS / "fms-good"), "--expect", "item/not-there"], capsys)
    assert code == 1 and "lacks: item/not-there" in out


def test_syntax_error_names_stage_file_and_log_excerpt(install: GameInstall, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_cli(check_data, ["--mod", str(MODS / "fms-broken-syntax")], capsys)
    assert code == 1
    assert "[data stage] fms-broken-syntax: data.lua:" in out and "log excerpt" in out and "'}' expected" in out


def test_invalid_prototype_value_names_the_prototype(install: GameInstall, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_cli(check_data, ["--mod", str(MODS / "fms-broken-prototype")], capsys)
    assert code == 1
    assert "[data stage] item prototype 'fms-broken-item' (ROOT.item.fms-broken-item.stack_size)" in out


def test_unknown_prototype_property_fails_unless_allowed(install: GameInstall, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = tmp_path / "fms-unknown-prop"
    mod.mkdir()
    (mod / "info.json").write_text('{"name": "fms-unknown-prop", "version": "0.1.0", "title": "t", "author": "a", "factorio_version": "2.1", "dependencies": ["base"]}', "utf-8")
    (mod / "data.lua").write_text(
        'data:extend({{type = "item", name = "x", icon = "__base__/graphics/icons/iron-plate.png", icon_size = 64, stack_size = 1, bogus = 1}})',
        "utf-8",
    )
    code, out = run_cli(check_data, ["--mod", str(mod)], capsys)
    assert code == 1 and "ROOT.item.x.bogus" in out
    assert run_cli(check_data, ["--mod", str(mod), "--allow-unused"], capsys)[0] == 0


def test_launch_logs_are_kept_in_log_dir_and_scan_clean(install: GameInstall, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    logs = tmp_path / "logs"
    assert run_cli(check_data, ["--mod", str(MODS / "fms-good"), "--log-dir", str(logs)], capsys)[0] == 0
    assert run_cli(run_tests, ["--mod", str(MODS / "fms-good"), "--log-dir", str(logs)], capsys)[0] == 0
    assert sorted(p.name for p in logs.iterdir()) == ["check-data.log", "run-tests-benchmark.log", "run-tests-create.log"]
    code, out = run_cli(scan_log, ["--log-dir", str(logs)], capsys)
    assert code == 0 and "PASS log scan" in out and "PASS test: item prototype exists at map creation" in out


def test_in_game_test_passes_without_a_window(install: GameInstall, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_cli(run_tests, ["--mod", str(MODS / "fms-good")], capsys)
    assert code == 0, out
    assert "PASS test: item prototype exists at map creation" in out and "PASS test: item prototype exists while ticking" in out


def test_failing_runtime_assertion_is_a_control_stage_failure(install: GameInstall, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_cli(run_tests, ["--mod", str(MODS / "fms-broken-runtime")], capsys)
    assert code == 1
    assert "[control stage] fms-broken-runtime: control.lua:2" in out and "fms-does-not-exist" in out


def test_mod_that_reports_no_tests_fails(install: GameInstall, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = tmp_path / "fms-silent"
    mod.mkdir()
    (mod / "info.json").write_text('{"name": "fms-silent", "version": "0.1.0", "title": "t", "author": "a", "factorio_version": "2.1", "dependencies": ["base"]}', "utf-8")
    (mod / "control.lua").write_text("-- no test hooks", "utf-8")
    code, out = run_cli(run_tests, ["--mod", str(mod)], capsys)
    assert code == 1 and "reported no results" in out


def test_no_sandbox_is_left_behind_and_links_are_gone(install: GameInstall, tmp_path: Path) -> None:
    with sandbox(install, [MODS / "fms-good"]) as (box, _):
        root = box.root
        result = gamerun.run_game(install, box, ["--version"])
        assert result.exit_code == 0
    assert not root.exists()
    assert (MODS / "fms-good" / "info.json").exists()


def test_game_timeout_is_a_clear_error(install: GameInstall, monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("factorio", 1)

    monkeypatch.setattr(gamerun.subprocess, "run", hang)
    with sandbox(install, [MODS / "fms-good"]) as (box, _), pytest.raises(ToolkitError) as err:
        gamerun.run_game(install, box, ["--dump-data"], timeout=1)
    assert "did not exit within" in err.value.message and "--timeout" in (err.value.hint or "")
