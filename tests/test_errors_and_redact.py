"""The CLI wrapper prints one clear message instead of a traceback; secrets never survive redaction."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest
from _lib.errors import EXIT_INTERNAL, EXIT_USAGE, ToolkitError, cli_main
from _lib.redact import REDACTED, redact


def run(monkeypatch: pytest.MonkeyPatch, main: Callable[[Sequence[str]], int]) -> int:
    monkeypatch.setattr("sys.argv", ["script"])
    with pytest.raises(SystemExit) as exit_info:
        cli_main(main)
    return exit_info.value.code


def test_toolkit_error_prints_cause_and_next_step(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def main(argv: Sequence[str]) -> int:
        raise ToolkitError("the game is missing", "set FACTORIO_PATH")

    assert run(monkeypatch, main) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "error: the game is missing" in err and "next step: set FACTORIO_PATH" in err
    assert "Traceback" not in err


def test_unexpected_exception_is_summarised_not_dumped(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("FM_DEBUG", raising=False)

    def main(argv: Sequence[str]) -> int:
        raise ValueError("boom")

    assert run(monkeypatch, main) == EXIT_INTERNAL
    err = capsys.readouterr().err
    assert "unexpected ValueError: boom" in err and "Traceback" not in err


def test_debug_flag_shows_traceback(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("FM_DEBUG", "1")

    def main(argv: Sequence[str]) -> int:
        raise ValueError("boom")

    run(monkeypatch, main)
    assert "Traceback" in capsys.readouterr().err


def test_return_value_becomes_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(monkeypatch, lambda argv: 3) == 3


def test_download_url_credentials_are_redacted() -> None:
    url = "https://mods.factorio.com/download/belt/abc?username=alice&token=s3cret-value"
    text = redact(f"GET {url} failed")
    assert "alice" not in text and "s3cret-value" not in text and text.count(REDACTED) == 2


def test_json_credential_fields_and_env_token_are_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTORIO_TOKEN", "tok-1234567890")
    text = redact('{"service-token": "abcdef", "service-username": "alice"} and tok-1234567890')
    assert "abcdef" not in text and "alice" not in text and "tok-1234567890" not in text
