"""What a failed game launch prints when the log scanner finds nothing it recognises."""

from __future__ import annotations

from _lib.gamerun import GameResult, describe_unrecognised_exit
from _lib.logscan import format_log_tail


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
