"""One-shot parsing of a Factorio log: errors with their stage and location, warnings, and in-game test results."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Stage = Literal["data", "control", "unknown"]

_ENTRY = re.compile(r"^\s*(\d+\.\d{3}) (.*)$")
_LEVEL = re.compile(r"^(Error|Warning)\b[^:]*:\d+: (.*)$", re.S)
_SCRIPT_LINE = re.compile(r"^Script @(__[^\s:]+\.lua):(\d+): (.*)$", re.S)
_TEST_MARK = re.compile(r"\[FMS-TEST\]\s+(PASS|FAIL)\s+(.+?)\s*$", re.M)
_FILE = re.compile(r"__(?P<mod>[\w.\-]+)__/(?P<file>[^\s:]+\.lua):(?P<line>\d+)")
_PROTOTYPE = re.compile(r'(?:loading|load)\s+(?P<kind>\S+)\s+prototype\s+"(?P<name>[^"]+)"')
_PROPERTY = re.compile(r"(?:property tree at |Value )ROOT\.(?P<path>[\w.\-]+)")
_DATA_FILES = ("data.lua", "data-updates.lua", "data-final-fixes.lua", "settings.lua", "settings-updates.lua", "settings-final-fixes.lua")
_EXCERPT_LINES = 14


@dataclass(frozen=True)
class Finding:
    """One error or warning from the log."""

    severity: Literal["error", "warning"]
    stage: Stage
    message: str
    where: str
    excerpt: tuple[str, ...]
    log_time: float


@dataclass(frozen=True)
class TestResult:
    """One `[FMS-TEST] PASS|FAIL <name>[: detail]` line written by a mod's test hook."""

    name: str
    passed: bool


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    tests: list[TestResult] = field(default_factory=list)
    initialised: bool = False
    finished: bool = False

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]


def _split_entries(text: str) -> list[tuple[float, str]]:
    """Group the log into (seconds, text) entries; lines without a timestamp continue the previous entry."""
    entries: list[tuple[float, list[str]]] = []
    for line in text.splitlines():
        match = _ENTRY.match(line)
        if match:
            entries.append((float(match[1]), [match[2]]))
        elif entries:
            entries[-1][1].append(line)
    return [(t, "\n".join(lines).rstrip()) for t, lines in entries]


def _locate(body: str) -> tuple[str, Stage]:
    """Name where a problem is (file:line in a mod, or the prototype) and which stage it belongs to."""
    file_match = _FILE.search(body)
    where = ""
    stage: Stage = "unknown"
    if file_match:
        where = f"{file_match['mod']}: {file_match['file']}:{file_match['line']}"
        top_level = file_match["file"].rsplit("/", 1)[-1] if "/" not in file_match["file"] else ""
        # A required module (`prototypes/item.lua`) can run in either stage: leave it to the caller's initialised check.
        stage = "data" if top_level in _DATA_FILES else ("control" if top_level == "control.lua" else "unknown")
    proto = _PROTOTYPE.search(body)
    if proto:
        where = f"{proto['kind']} prototype '{proto['name']}'"
        prop = _PROPERTY.search(body)
        if prop:
            where += f" (ROOT.{prop['path']})"
        stage = "data"
    elif not file_match and (prop := _PROPERTY.search(body)):
        where = f"ROOT.{prop['path']}"
        stage = "data"
    return where, stage


def _headline(body: str) -> str:
    """The line that says what went wrong: for a mod crash, the Lua error line rather than the boilerplate above it."""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if "caused a non-recoverable error" in body:
        return next((ln for ln in lines if _FILE.search(ln)), lines[0])
    return lines[0] if lines else body.strip()


def scan_log(text: str, *, unused_is_error: bool = True) -> ScanResult:
    """Scan a whole log once. Unused-prototype-value warnings count as errors unless `unused_is_error` is off."""
    result = ScanResult()
    for seconds, body in _split_entries(text):
        if "Factorio initialised" in body:
            result.initialised = True
        if body.startswith("Goodbye"):
            result.finished = True
        level = _LEVEL.match(body)
        if level:
            detail = level[2]
            where, stage = _locate(detail)
            if stage == "unknown":
                stage = "control" if result.initialised else "data"
            severity: Literal["error", "warning"] = "error" if level[1] == "Error" else "warning"
            if severity == "warning" and "was not used" in detail:
                if not unused_is_error:
                    continue
                severity = "error"
                detail = f"{_headline(detail)} - unknown or misspelt prototype property"
            excerpt = tuple(detail.splitlines()[:_EXCERPT_LINES])
            result.findings.append(Finding(severity, stage, _headline(detail), where, excerpt, seconds))
            continue
        script = _SCRIPT_LINE.match(body)
        if script:
            for mark in _TEST_MARK.finditer(script[3]):
                result.tests.append(TestResult(name=mark[2], passed=mark[1] == "PASS"))
    return result


def format_finding(finding: Finding, log_name: str = "factorio-current.log") -> str:
    """Render a finding as stage, location and the relevant log excerpt."""
    head = f"{finding.severity.upper()} [{finding.stage} stage] {finding.where or 'unlocated'}: {finding.message}"
    body = "\n".join(f"    | {line}" for line in finding.excerpt)
    return f"{head}\n  log excerpt ({log_name} @ {finding.log_time:.3f}s):\n{body}"
