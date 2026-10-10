"""Run the Factorio executable inside a sandbox and collect what it logged."""

from __future__ import annotations

import subprocess
from pathlib import Path
from collections.abc import Sequence
from dataclasses import dataclass

from .errors import ToolkitError
from .paths import GameInstall
from .sandbox import Sandbox

DEFAULT_TIMEOUT = 600


@dataclass(frozen=True)
class GameResult:
    """One game launch: its exit code, console output and the log it wrote (read once, after exit)."""

    args: tuple[str, ...]
    exit_code: int
    output: str
    log: str


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
    log = box.log_path.read_text("utf-8", errors="replace") if box.log_path.is_file() else ""
    return GameResult(args=tuple(args), exit_code=proc.returncode, output=proc.stdout + proc.stderr, log=log)


def save_log(directory: Path | None, label: str, result: GameResult) -> None:
    """Keep a launch's log after the sandbox is deleted: `<directory>/<label>.log` (no-op without a directory)."""
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{label}.log").write_text(result.log, "utf-8")
