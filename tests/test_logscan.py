"""Log parsing: errors get a stage and a location, test marks are collected, noise is ignored."""

from __future__ import annotations

from _lib.logscan import format_finding, scan_log

HEAD = """\
   0.100 Loading mod base 2.1.21 (data.lua)
   1.556 Loading mod fms-x 0.1.0 (data.lua)
"""


def test_data_stage_syntax_error_names_file_and_line() -> None:
    log = HEAD + """\
   1.578 Error Util.cpp:81: Failed to load mod "fms-x": __fms-x__/data.lua:5: '}' expected near <eof>
   1.584 Goodbye
"""
    result = scan_log(log)
    [finding] = result.errors
    assert finding.stage == "data"
    assert finding.where == "fms-x: data.lua:5"
    assert result.finished


def test_invalid_prototype_value_names_prototype_and_property() -> None:
    log = HEAD + """\
   1.328 Error Util.cpp:81: Error while loading item prototype "x" (item): Value must be a unsigned integer in property tree at ROOT.item.x.stack_size
Modifications: P
"""
    [finding] = scan_log(log).errors
    assert finding.stage == "data"
    assert finding.where == "item prototype 'x' (ROOT.item.x.stack_size)"
    assert "Modifications: P" in finding.excerpt


def test_runtime_error_is_control_stage_and_headline_is_the_lua_error() -> None:
    log = HEAD + """\
   2.095 Factorio initialised
   2.555 Error Util.cpp:81: The mod P (0.1.0) caused a non-recoverable error.
Please report this error to the mod author.

Error while running event fms-x::on_nth_tick(1)
__fms-x__/control.lua:2: boom
stack traceback:
\t[C]: in function 'assert'
"""
    [finding] = scan_log(log).errors
    assert finding.stage == "control"
    assert finding.where == "fms-x: control.lua:2"
    assert finding.message == "__fms-x__/control.lua:2: boom"
    assert "stack traceback:" in format_finding(finding)


def test_unused_prototype_value_warning_is_an_error_unless_allowed() -> None:
    log = HEAD + "   1.503 Warning PrototypeLoader.cpp:200: Value ROOT.item.x.bogus_prop was not used.\n"
    [finding] = scan_log(log).errors
    assert finding.where == "ROOT.item.x.bogus_prop"
    assert "unknown or misspelt" in finding.message
    relaxed = scan_log(log, unused_is_error=False)
    assert not relaxed.errors and not relaxed.warnings


def test_other_warnings_do_not_fail_the_scan() -> None:
    result = scan_log(HEAD + "   1.600 Warning Something.cpp:1: deprecated thing\n")
    assert not result.errors
    assert [w.message for w in result.warnings] == ["deprecated thing"]


def test_test_marks_are_collected_from_script_lines_only() -> None:
    log = HEAD + """\
   2.690 Script @__fms-x__/control.lua:1: [FMS-TEST] PASS item exists
   2.691 Script @__fms-x__/control.lua:2: [FMS-TEST] FAIL inserter bonus: expected 2 got 1
   2.692 Info Other.cpp:1: [FMS-TEST] PASS not-from-a-script
"""
    tests = scan_log(log).tests
    assert [(t.name, t.passed) for t in tests] == [("item exists", True), ("inserter bonus: expected 2 got 1", False)]


def test_error_without_a_file_is_data_stage_before_initialisation_and_control_after() -> None:
    before = scan_log("   0.500 Error Foo.cpp:1: mystery\n")
    after = scan_log("   0.500 Factorio initialised\n   0.600 Error Foo.cpp:1: mystery\n")
    assert before.errors[0].stage == "data" and after.errors[0].stage == "control"


def test_error_in_a_required_data_module_is_data_stage() -> None:
    log = HEAD + """   1.700 Error Util.cpp:81: Failed to load mod "fms-x": __fms-x__/prototypes/item.lua:2: boom
"""
    [finding] = scan_log(log).errors
    assert finding.stage == "data" and finding.where == "fms-x: prototypes/item.lua:2"


def test_error_in_a_required_runtime_module_is_control_stage() -> None:
    log = (
        "   0.500 Factorio initialised\n"
        "   0.900 Error Util.cpp:81: The mod X caused a non-recoverable error.\n"
        "__fms-x__/boost.lua:9: boom\n"
    )
    [finding] = scan_log(log).errors
    assert finding.stage == "control"
