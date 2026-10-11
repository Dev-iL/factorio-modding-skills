"""Run the Factorio executable inside a sandbox and collect what it logged."""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import ToolkitError
from .logscan import format_log_tail
from .paths import GameInstall
from .sandbox import Sandbox

DEFAULT_TIMEOUT = 600
_ERROR_LINE = re.compile(r"^\s*\d+\.\d{3} Error ", re.M)


@dataclass(frozen=True)
class GameResult:
    """One game launch: its exit code, console output and the log it wrote (read once, after exit)."""

    args: tuple[str, ...]
    exit_code: int
    output: str
    log: str
    timed_out: bool = False


def _read_log(box: Sandbox) -> str:
    return box.log_path.read_text("utf-8", errors="replace") if box.log_path.is_file() else ""


def run_game(install: GameInstall, box: Sandbox, args: Sequence[str], timeout: float = DEFAULT_TIMEOUT) -> GameResult:
    """Launch the game headless with the sandbox's config and mod directory, wait for it to exit, read its log."""
    command = [str(install.exe), "-c", str(box.config_ini), "--mod-directory", str(box.mods_dir), *args]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ToolkitError(
            f"Factorio did not exit within {timeout:.0f}s ({' '.join(args)}).",
            "check for a mod that loops forever in its data or control script, or raise --timeout.",
        ) from exc
    except OSError as exc:
        raise ToolkitError(f"could not start {install.exe}: {exc}", "check FACTORIO_PATH and that the executable is not blocked by antivirus.") from exc
    return GameResult(args=tuple(args), exit_code=proc.returncode, output=proc.stdout + proc.stderr, log=_read_log(box))


def run_game_until_error(install: GameInstall, box: Sandbox, args: Sequence[str], timeout: float, done_marker: str | None = None) -> GameResult:
    """Launch the game with a window and stop it as soon as its log shows an error, shows `done_marker`, or after `timeout`.

    A sprite error leaves the game on a dialog that nobody will click, so waiting for an exit would only burn the timeout.
    The result has `timed_out=True` when the game was stopped for running too long.
    """
    command = [str(install.exe), "-c", str(box.config_ini), "--mod-directory", str(box.mods_dir), *args]
    try:
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        raise ToolkitError(f"could not start {install.exe}: {exc}", "check FACTORIO_PATH and that the executable is not blocked by antivirus.") from exc
    deadline = time.monotonic() + timeout
    timed_out = False
    try:
        while proc.poll() is None:
            log = _read_log(box)
            if _ERROR_LINE.search(log) or (done_marker and done_marker in log):
                break
            if time.monotonic() > deadline:
                timed_out = True
                break
            time.sleep(1)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
    exit_code = proc.returncode if not timed_out and proc.returncode is not None else -1
    return GameResult(args=tuple(args), exit_code=exit_code, output="", log=_read_log(box), timed_out=timed_out)


def describe_unrecognised_exit(result: GameResult) -> str:
    """Say that the game exited non-zero with nothing the log scanner recognises, and show what it printed.

    A mod that fails while the map loads can report its error on the console only, so the console output wins over the log.
    """
    text = result.output if result.output.strip() else result.log
    return f"game exited with code {result.exit_code} ({result.args[0]}) without a recognised error; end of its output:\n{format_log_tail(text)}"


def save_log(directory: Path | None, label: str, result: GameResult) -> None:
    """Keep a launch's log after the sandbox is deleted: `<directory>/<label>.log` (no-op without a directory)."""
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{label}.log").write_text(result.log, "utf-8")
