#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = []
# ///
"""Check that everything the factorio-modding skills need is present, and say how to fix what is not.

Checks: uv and Python 3.15, the Factorio install, the manifest-dev plugin (asked of the host's own CLI,
never by reading config files), Blender (with --sprites), and whether portal credentials are set (never their values).
Exits 0 when every required check passes, 2 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from _lib.errors import EXIT_USAGE, ToolkitError, cli_main
from _lib.paths import game_version, locate_game

MANIFEST_DEV_REPO = "doodledood/manifest-dev"
MIN_UV = (0, 13, 0)  # first uv that ships Python 3.15 final
CLAUDE_INSTALL = f"claude plugin marketplace add {MANIFEST_DEV_REPO}  then  claude plugin install manifest-dev@manifest-dev"
CODEX_INSTALL = f"codex plugin marketplace add {MANIFEST_DEV_REPO}  then  codex plugin add manifest-dev@manifest-dev"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""
    required: bool = True


def _run(command: Sequence[str], env: Mapping[str, str], timeout: float = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False, env=dict(env))


def check_uv(env: Mapping[str, str]) -> Check:
    uv = env.get("FM_UV", "uv")
    exe = shutil.which(uv)
    if exe is None:
        return Check("uv", False, f"`{uv}` was not found on PATH", "install uv (https://docs.astral.sh/uv/) and restart the agent")
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", _run([exe, "--version"], env).stdout)
    if not match:
        return Check("uv", False, f"`{uv} --version` printed no version", "reinstall uv")
    version = tuple(int(g) for g in match.groups())
    pretty = ".".join(match.groups())
    if version < MIN_UV:
        return Check("uv", False, f"uv {pretty} is too old to know Python 3.15", "run `uv self update` (needs uv 0.13.0 or newer)")
    return Check("uv", True, f"uv {pretty}")


def check_python(env: Mapping[str, str]) -> Check:
    uv = shutil.which(env.get("FM_UV", "uv"))
    if uv is None:
        return Check("Python 3.15", False, "cannot ask uv: it is missing", "install uv first")
    # Ask about uv's installed interpreters, not the virtual environment this script itself runs in.
    clean_env = {k: v for k, v in env.items() if k != "VIRTUAL_ENV"}
    found = _run([uv, "python", "find", "3.15", "--no-python-downloads", "--system", "--no-project"], clean_env)
    if found.returncode != 0:
        return Check("Python 3.15", False, "uv has no Python 3.15 installed", "run `uv python install 3.15` (needs uv 0.13.0 or newer)")
    return Check("Python 3.15", True, found.stdout.strip())


def check_game(path: str | None, env: Mapping[str, str]) -> Check:
    try:
        install = locate_game(path, env)
        version = game_version(install)
    except ToolkitError as exc:
        return Check("Factorio", False, exc.message, exc.hint or "")
    return Check("Factorio", True, f"{version} at {install.root} ({'portable' if install.portable else 'system'} data; log {install.log_path})")


def detect_host(requested: str, env: Mapping[str, str]) -> str:
    """Which agent host is running this: explicit choice, then `CLAUDECODE`, then Codex's variables, then whichever CLI exists."""
    if requested != "auto":
        return requested
    if env.get("CLAUDECODE"):
        return "claude"
    if any(key.startswith("CODEX_") for key in env):
        return "codex"
    return "claude" if shutil.which("claude") else "codex"


def _manifest_dev_in_claude(env: Mapping[str, str]) -> bool:
    out = _run([shutil.which("claude") or "claude", "plugin", "list", "--json"], env)
    if out.returncode != 0:
        raise ToolkitError(f"`claude plugin list --json` failed: {out.stderr.strip() or out.stdout.strip()}", "update Claude Code, then re-run.")
    try:
        plugins = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise ToolkitError(f"`claude plugin list --json` printed invalid JSON ({exc}).", "update Claude Code, then re-run.") from exc
    return any(str(p.get("id", "")).startswith("manifest-dev@") and p.get("enabled") for p in plugins)


def _manifest_dev_in_codex(env: Mapping[str, str]) -> bool:
    out = _run([shutil.which("codex") or "codex", "plugin", "list"], env)
    if out.returncode != 0:
        raise ToolkitError(f"`codex plugin list` failed: {out.stderr.strip() or out.stdout.strip()}", "update Codex, then re-run.")
    return re.search(r"^\s*manifest-dev@\S+\s+installed,\s*enabled\b", out.stdout, re.M) is not None


def check_manifest_dev(host: str, env: Mapping[str, str]) -> Check:
    cli = "claude" if host == "claude" else "codex"
    install = CLAUDE_INSTALL if host == "claude" else CODEX_INSTALL
    if shutil.which(cli) is None:
        return Check("manifest-dev", False, f"the `{cli}` CLI is not on PATH, so the plugin list cannot be read", f"put `{cli}` on PATH")
    try:
        present = _manifest_dev_in_claude(env) if host == "claude" else _manifest_dev_in_codex(env)
    except ToolkitError as exc:
        return Check("manifest-dev", False, exc.message, exc.hint or "")
    if not present:
        return Check("manifest-dev", False, f"the manifest-dev plugin is not installed and enabled in {host}", install)
    return Check("manifest-dev", True, f"installed and enabled in {host}")


def check_blender(env: Mapping[str, str]) -> Check:
    path = env.get("BLENDER_PATH") or shutil.which("blender")
    candidates = [path] if path else []
    for root in (env.get("ProgramFiles", r"C:\Program Files"),):
        base = os.path.join(root, "Blender Foundation")
        if os.path.isdir(base):
            candidates += [os.path.join(base, d, "blender.exe") for d in sorted(os.listdir(base), reverse=True)]
    found = next((c for c in candidates if c and os.path.isfile(c)), None)
    if found is None:
        return Check("Blender", False, "no Blender found", "install Blender or set BLENDER_PATH to blender.exe (only needed for rendered sprites)")
    return Check("Blender", True, found)


def check_credentials(env: Mapping[str, str]) -> Check:
    have = [name for name in ("FACTORIO_USERNAME", "FACTORIO_TOKEN") if env.get(name)]
    if len(have) == 2:
        return Check("portal credentials", True, "FACTORIO_USERNAME and FACTORIO_TOKEN are set", required=False)
    return Check(
        "portal credentials", False, "FACTORIO_USERNAME / FACTORIO_TOKEN are not both set (portal search and download need them)",
        "set both in ~/.claude/settings.json `env` (Claude Code) or `[shell_environment_policy] set` in ~/.codex/config.toml (Codex)",
        required=False,
    )


def run_checks(path: str | None, host: str, sprites: bool, env: Mapping[str, str]) -> list[Check]:
    checks = [check_uv(env), check_python(env), check_game(path, env), check_manifest_dev(detect_host(host, env), env)]
    if sprites:
        checks.append(check_blender(env))
    checks.append(check_credentials(env))
    return checks


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", help="Factorio install folder; default: FACTORIO_PATH, then common locations")
    parser.add_argument("--host", choices=("auto", "claude", "codex"), default="auto", help="agent host to check manifest-dev in (default: detect)")
    parser.add_argument("--sprites", action="store_true", help="also require Blender (for rendered sprites)")
    args = parser.parse_args(argv)

    checks = run_checks(args.path, args.host, args.sprites, os.environ)
    for check in checks:
        status = "ok  " if check.ok else ("FAIL" if check.required else "note")
        print(f"[{status}] {check.name}: {check.detail}")
        if not check.ok and check.fix:
            print(f"       fix: {check.fix}")
    failed = [c for c in checks if c.required and not c.ok]
    if failed:
        print(f"PREFLIGHT FAILED: {', '.join(c.name for c in failed)}")
        return EXIT_USAGE
    print("PREFLIGHT PASSED")
    return 0


if __name__ == "__main__":
    cli_main(main)
