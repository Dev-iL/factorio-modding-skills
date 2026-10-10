"""Preflight names what is missing and how to fix it; manifest-dev is read from the host CLI, not config files."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence

import pytest
import preflight

CODEX_LIST = """\
Marketplace `manifest-dev`
PLUGIN                           STATUS              VERSION  SOURCE
manifest-dev@manifest-dev        installed, enabled  12.7.0   somewhere
manifest-dev-tools@manifest-dev  installed, enabled  6.5.1    somewhere
"""


def fake_run(outputs: Mapping[tuple[str, ...], tuple[int, str]]):
    def run(command: Sequence[str], env: Mapping[str, str], timeout: float = 60) -> subprocess.CompletedProcess[str]:
        key = tuple(command[1:])
        code, out = next((v for k, v in outputs.items() if key[: len(k)] == k), (1, "unknown command"))
        return subprocess.CompletedProcess(command, code, out, "")

    return run


@pytest.fixture(autouse=True)
def tools_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda name: f"/bin/{name}")


def test_old_uv_is_rejected_with_the_upgrade_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "_run", fake_run({("--version",): (0, "uv 0.10.10 (abc 2026-03-13)")}))
    check = preflight.check_uv({})
    assert not check.ok and "uv self update" in check.fix


def test_missing_uv_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight.shutil, "which", lambda name: None)
    check = preflight.check_uv({"FM_UV": "no-such-uv"})
    assert not check.ok and "no-such-uv" in check.detail


def test_python_315_missing_says_how_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "_run", fake_run({("python", "find"): (2, "")}))
    check = preflight.check_python({})
    assert not check.ok and "uv python install 3.15" in check.fix


def test_claude_host_reads_plugin_list_json(monkeypatch: pytest.MonkeyPatch) -> None:
    present = json.dumps([{"id": "manifest-dev@manifest-dev", "enabled": True}])
    absent = json.dumps([{"id": "other@market", "enabled": True}, {"id": "manifest-dev@manifest-dev", "enabled": False}])
    monkeypatch.setattr(preflight, "_run", fake_run({("plugin", "list", "--json"): (0, present)}))
    assert preflight.check_manifest_dev("claude", {}).ok
    monkeypatch.setattr(preflight, "_run", fake_run({("plugin", "list", "--json"): (0, absent)}))
    check = preflight.check_manifest_dev("claude", {})
    assert not check.ok and "claude plugin install manifest-dev@manifest-dev" in check.fix


def test_codex_host_reads_plugin_list_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "_run", fake_run({("plugin", "list"): (0, CODEX_LIST)}))
    assert preflight.check_manifest_dev("codex", {}).ok
    monkeypatch.setattr(preflight, "_run", fake_run({("plugin", "list"): (0, CODEX_LIST.replace("installed, enabled", "not installed", 1))}))
    check = preflight.check_manifest_dev("codex", {})
    assert not check.ok and "codex plugin add manifest-dev@manifest-dev" in check.fix


def test_host_cli_failure_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "_run", fake_run({("plugin", "list", "--json"): (1, "boom")}))
    check = preflight.check_manifest_dev("claude", {})
    assert not check.ok and "failed" in check.detail


def test_host_detection_prefers_explicit_then_claudecode_then_codex_vars() -> None:
    assert preflight.detect_host("codex", {"CLAUDECODE": "1"}) == "codex"
    assert preflight.detect_host("auto", {"CLAUDECODE": "1"}) == "claude"
    assert preflight.detect_host("auto", {"CODEX_HOME": "x"}) == "codex"


def test_credentials_are_noted_but_never_required_or_printed() -> None:
    check = preflight.check_credentials({"FACTORIO_USERNAME": "alice"})
    assert not check.ok and not check.required and "alice" not in check.detail
    assert preflight.check_credentials({"FACTORIO_USERNAME": "a", "FACTORIO_TOKEN": "t"}).ok


def test_main_exits_2_and_lists_each_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(preflight, "run_checks", lambda *a: [
        preflight.Check("uv", True, "uv 0.13.0"),
        preflight.Check("Factorio", False, "not found", "set FACTORIO_PATH"),
    ])
    assert preflight.main([]) == 2
    out = capsys.readouterr().out
    assert "[FAIL] Factorio: not found" in out and "fix: set FACTORIO_PATH" in out and "PREFLIGHT FAILED: Factorio" in out
