"""Game-loop scripts: log scanning and argument errors, none of which need the game."""

from __future__ import annotations

from pathlib import Path

import check_data
import pytest
import scan_log
from _lib.errors import ToolkitError


def test_scan_log_reports_errors_in_a_given_log_and_exits_non_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = tmp_path / "factorio-current.log"
    log.write_text('   1.500 Error Util.cpp:81: Failed to load mod "m": __m__/data.lua:3: oops\n', "utf-8")
    assert scan_log.main(["--log", str(log)]) == 1
    out = capsys.readouterr().out
    assert "[data stage] m: data.lua:3" in out and "FAIL log scan" in out
    log.write_text("   1.500 Factorio initialised\n   1.600 Goodbye\n", "utf-8")
    assert scan_log.main(["--log", str(log)]) == 0
    assert "PASS log scan" in capsys.readouterr().out


def test_scan_log_without_a_log_says_what_to_do(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as err:
        scan_log.main(["--log", str(tmp_path / "missing.log")])
    assert "no log file" in err.value.message


def test_missing_mod_folder_is_a_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "game"
    (root / "bin" / "x64").mkdir(parents=True)
    (root / "bin" / "x64" / "factorio.exe").write_bytes(b"")
    with pytest.raises(ToolkitError) as err:
        check_data.main(["--path", str(root), "--mod", str(tmp_path / "nope")])
    assert "does not exist" in err.value.message


def test_scan_log_dir_scans_every_saved_log(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "check-data.log").write_text("   1.500 Factorio initialised\n", "utf-8")
    (tmp_path / "run-tests-create.log").write_text('   1.500 Error Util.cpp:81: Failed to load mod "m": __m__/control.lua:3: oops\n', "utf-8")
    assert scan_log.main(["--log-dir", str(tmp_path)]) == 1
    assert "m: control.lua:3" in capsys.readouterr().out


def test_scan_log_dir_without_logs_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as err:
        scan_log.main(["--log-dir", str(tmp_path)])
    assert "--log-dir" in (err.value.hint or "")
