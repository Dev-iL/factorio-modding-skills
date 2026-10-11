"""update-mod refuses downgrades and sources older than 2.0.77 before any analysis, and lets a 2.0 mod go to 2.1.21."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "plugins" / "factorio-modding" / "skills" / "update-mod" / "scripts" / "version_gate.py"


@pytest.fixture(scope="module")
def version_gate():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import version_gate as module
    finally:
        sys.path.pop(0)
    return module


def make_mod(tmp_path: Path, declared: str | None) -> Path:
    info: dict[str, str] = {"name": "m", "version": "1.0.0"}
    if declared is not None:
        info["factorio_version"] = declared
    (tmp_path / "info.json").write_text(json.dumps(info), "utf-8")
    return tmp_path


def run(mod: Path, target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--mod", str(mod), "--target", target], capture_output=True, text=True, check=False
    )


def test_downgrade_is_refused_and_says_so(tmp_path: Path) -> None:
    result = run(make_mod(tmp_path, "2.1"), "2.0.77")
    assert result.returncode == 2
    assert "downgrades are not yet supported" in result.stderr and "not yet supported" in result.stderr


def test_older_source_is_refused_as_not_yet_supported(tmp_path: Path) -> None:
    result = run(make_mod(tmp_path, "1.1"), "2.1.21")
    assert result.returncode == 2
    assert "not yet supported" in result.stderr and "1.1" in result.stderr and "downgrade" not in result.stderr


def test_missing_declared_version_counts_as_an_old_source(tmp_path: Path) -> None:
    assert run(make_mod(tmp_path, None), "2.1.21").returncode == 2


def test_two_zero_mod_proceeds_to_2_1_21_with_the_2_0_77_baseline(tmp_path: Path) -> None:
    result = run(make_mod(tmp_path, "2.0"), "2.1.21")
    assert result.returncode == 0
    assert "diff from 2.0.77" in result.stdout and "target 2.1.21" in result.stdout


def test_same_series_update_proceeds_from_the_first_published_2_1_release(tmp_path: Path) -> None:
    result = run(make_mod(tmp_path, "2.1"), "2.1.21")
    assert result.returncode == 0 and "diff from 2.1.7" in result.stdout


def test_target_below_the_series_floor_is_refused_with_the_floor_named(version_gate) -> None:
    with pytest.raises(version_gate.Refused, match=r"targets older than 2\.0\.77 are not yet supported"):
        version_gate.check("2.0", "2.0.50")
    with pytest.raises(version_gate.Refused, match=r"targets older than 2\.1\.7 are not yet supported"):
        version_gate.check("2.1", "2.1.3")


def test_two_one_mod_gets_the_first_published_baseline(version_gate) -> None:
    assert version_gate.check("2.1", "2.1.21").source_baseline == (2, 1, 7)


def test_bad_input_is_explained(tmp_path: Path, version_gate) -> None:
    with pytest.raises(version_gate.Refused, match="cannot read"):
        version_gate.check("two", "2.1.21")
    result = run(tmp_path, "2.1.21")  # no info.json
    assert result.returncode == 2 and "info.json" in result.stderr


def test_json_output(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--mod", str(make_mod(tmp_path, "2.0")), "--target", "2.1.21", "--json"],
        capture_output=True, text=True, check=False,
    )
    assert json.loads(result.stdout) == {"source_series": "2.0", "source_baseline": "2.0.77", "target": "2.1.21"}
