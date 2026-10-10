from __future__ import annotations

from pathlib import Path

import changelog
import pytest
from _lib.errors import ToolkitError

SAMPLE = """\
---------------------------------------------------------------------------------------------------
Version: 2.1.21
Date: 06. 10. 2026
  Bugfixes:
    - Fixed a thing.
  Modding:
    - Added CraftingMachinePrototype::animation_random_start_frame.
    - Added ProxyContainerPrototype::direction_count. Changed ProxyContainerPrototype::circuit_connector into an array.
  Scripting:
    - Added LuaEntity::get_signals_changed().
---------------------------------------------------------------------------------------------------
Version: 2.1.9
Date: 01. 09. 2026
  Modding:
    - Wrapped entry that continues
      on a second line.
---------------------------------------------------------------------------------------------------
Version: 2.0.77
Date: 05. 08. 2026
  Modding:
    - Not part of a 2.0.77 -> x range.
---------------------------------------------------------------------------------------------------
Version: 2.0.10
Date: 01. 01. 2026
  Modding:
    - Older, and sorted after 2.0.9 by number not by text.
"""


@pytest.fixture
def changelog_file(tmp_path: Path) -> Path:
    path = tmp_path / "changelog.txt"
    path.write_text(SAMPLE, "utf-8")
    return path


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> list[str]:
    assert changelog.main(list(argv)) == 0
    return capsys.readouterr().out.splitlines()


def test_prints_modding_entries_after_the_lower_bound_up_to_the_upper_bound(changelog_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "2.0.77", "2.1.21", "--file", str(changelog_file))
    assert "2.1.21 Modding: Added CraftingMachinePrototype::animation_random_start_frame." in out
    assert not any("2.0.77 Modding" in line or "Scripting" in line or "Bugfixes" in line for line in out)
    assert out[0].startswith("# changelog 2.0.77 (excluded) -> 2.1.21: 2 versions")


def test_versions_are_compared_as_numbers(changelog_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "2.0.9", "2.1.9", "--file", str(changelog_file))
    assert any(line.startswith("2.0.10 Modding:") for line in out)  # 2.0.10 > 2.0.9 although "10" < "9" as text
    assert out.index("## 2.0.10 (01. 01. 2026)") < out.index("## 2.0.77 (05. 08. 2026)") < out.index("## 2.1.9 (01. 09. 2026)")


def test_wrapped_entries_are_joined_and_keep_their_version_prefix(changelog_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "2.1.0", "2.1.21", "--file", str(changelog_file))
    assert "2.1.9 Modding: Wrapped entry that continues on a second line." in out


def test_other_sections_can_be_requested(changelog_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = run(capsys, "2.1.9", "2.1.21", "--file", str(changelog_file), "--section", "Scripting")
    assert "2.1.21 Scripting: Added LuaEntity::get_signals_changed()." in out
    assert not any("Modding" in line for line in out[1:])


def test_a_reversed_range_is_refused(changelog_file: Path) -> None:
    with pytest.raises(ToolkitError, match="must be lower"):
        changelog.main(["2.1.21", "2.0.77", "--file", str(changelog_file)])


def test_a_missing_changelog_names_the_ways_to_provide_one(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as info:
        changelog.main(["2.0.77", "2.1.21", "--file", str(tmp_path / "nope.txt")])
    assert "--file" in (info.value.hint or "") and "FACTORIO_PATH" in (info.value.hint or "")


def test_without_a_game_or_a_file_the_error_offers_both_ways_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FACTORIO_PATH", str(tmp_path / "no-game-here"))
    with pytest.raises(ToolkitError) as info:
        changelog.main(["2.0.77", "2.1.21"])
    assert "FACTORIO_PATH" in (info.value.hint or "") and "--file" in (info.value.hint or "")


def test_a_changelog_older_than_the_target_is_flagged(changelog_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert changelog.main(["2.0.77", "2.9.0", "--file", str(changelog_file)]) == 0
    assert "ends at 2.1.21" in capsys.readouterr().err


def test_continuation_lines_stay_with_their_entry() -> None:
    releases = changelog.parse_changelog(SAMPLE)
    assert [r.version for r in releases] == ["2.1.21", "2.1.9", "2.0.77", "2.0.10"]
    assert releases[0].sections["Modding"][1].endswith("into an array.")
