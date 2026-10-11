"""What a failed game launch prints when the log scanner finds nothing it recognises."""

from __future__ import annotations

from _lib.gamerun import GameResult, describe_unrecognised_exit
from _lib.logscan import format_finding, format_log_tail, scan_console


def test_log_tail_quotes_the_last_lines_only() -> None:
    assert format_log_tail("a\nb\nc", lines=2) == "    | b\n    | c"


def test_unrecognised_exit_prefers_the_console_output_over_the_log() -> None:
    result = GameResult(args=("--create", "x.zip"), exit_code=1, output="mod X failed to load: boom\n", log="   1.000 Info nothing\n")
    text = describe_unrecognised_exit(result)
    assert "exited with code 1 (--create)" in text
    assert "mod X failed to load: boom" in text
    assert "Info nothing" not in text


def test_unrecognised_exit_falls_back_to_the_log_when_the_console_is_empty() -> None:
    quiet = GameResult(args=("--benchmark", "x.zip"), exit_code=2, output="  \n", log="   1.000 Info last line\n")
    assert "Info last line" in describe_unrecognised_exit(quiet)


CONSOLE_REQUIRE = """\
   2.917 Checksum for script __level__/control.lua: 3704017257
Error: fms-x 0.1.0 errored when running a required file.

__fms-x__/boost.lua:1: boom from boost
stack traceback:
\t[C]: in function 'error'
"""

CONSOLE_EVENT = """\
Error while running event fms-x::on_init()
__fms-x__/lib/helper.lua:2: attempt to index local 't' (a nil value)
stack traceback:
\t__fms-x__/lib/helper.lua:2: in function <__fms-x__/lib/helper.lua:1>
"""


def test_console_only_load_error_is_a_control_stage_finding_with_its_file() -> None:
    [finding] = scan_console(CONSOLE_REQUIRE)
    assert finding.stage == "control" and finding.where == "fms-x: boost.lua:1"
    assert finding.message == "__fms-x__/boost.lua:1: boom from boost"
    assert "console output" in format_finding(finding)


def test_console_event_error_names_the_helper_file() -> None:
    [finding] = scan_console(CONSOLE_EVENT)
    assert finding.stage == "control" and finding.where == "fms-x: lib/helper.lua:2"


def test_console_output_without_errors_yields_nothing() -> None:
    assert scan_console("Performed 5 updates in 1.692 ms\navg: 0.338 ms\n") == []


def test_core_frames_do_not_hide_the_mods_own_frame() -> None:
    text = "Error: Invalid array of prototypes\n__core__/lualib/dataloader.lua:23: bad\n__fms-x__/data.lua:1: in main chunk\n"
    [finding] = scan_console(text)
    assert finding.where == "fms-x: data.lua:1" and finding.stage == "data"


CONSOLE_CRASH = """\
Error: The mod fms-x (0.1.0) caused a non-recoverable error.
Please report this error to the mod author.

Error while running event fms-x::on_init()
__fms-x__/control.lua:1: attempt to index local 't' (a nil value)
stack traceback:
\t__fms-x__/control.lua:1: in function <__fms-x__/control.lua:1>
"""


def test_a_crash_printed_as_several_error_lines_is_one_finding() -> None:
    [finding] = scan_console(CONSOLE_CRASH)
    assert finding.where == "fms-x: control.lua:1" and "attempt to index" in finding.message
