from __future__ import annotations

from _lib.apimodel import Method, by_order, format_type, method_params


def test_every_complex_type_renders_on_one_line() -> None:
    assert format_type("uint32") == "uint32"
    assert format_type({"complex_type": "array", "value": "LuaEntity"}) == "array[LuaEntity]"
    assert format_type({"complex_type": "dictionary", "key": "string", "value": "double"}) == "dict[string, double]"
    assert format_type({"complex_type": "LuaCustomTable", "key": "string", "value": "LuaForce"}) == "LuaCustomTable[string, LuaForce]"
    union = {"complex_type": "union", "options": ["string", {"complex_type": "array", "value": "string"}], "full_format": False}
    assert format_type(union) == "string | array[string]"
    assert format_type({"complex_type": "tuple", "values": ["double", "double"]}) == "tuple[double, double]"
    assert format_type({"complex_type": "type", "value": "string", "description": "Described."}) == "string"
    assert format_type({"complex_type": "literal", "value": "north"}) == '"north"'
    assert format_type({"complex_type": "literal", "value": 2}) == "2"
    assert format_type({"complex_type": "function", "parameters": ["EventData"]}) == "function(EventData)"
    assert format_type({"complex_type": "LuaLazyLoadedValue", "value": "LuaEntity"}) == "LuaLazyLoadedValue[LuaEntity]"
    assert format_type({"complex_type": "struct"}) == "struct"
    assert format_type({"complex_type": "LuaStruct", "attributes": [{"name": "a", "order": 0, "read_type": "double"}]}) == "LuaStruct{a: double}"


def test_table_type_lists_fields_in_declared_order_with_optional_marks() -> None:
    table = {
        "complex_type": "table",
        "parameters": [
            {"name": "y", "order": 1, "type": "double", "optional": True},
            {"name": "x", "order": 0, "type": "double", "optional": False},
        ],
    }
    assert format_type(table) == "{x: double, y?: double}"


def test_unknown_complex_type_falls_back_to_something_readable() -> None:
    assert format_type({"complex_type": "hologram"}).startswith("<hologram:")


def test_by_order_ignores_alphabetical_json_order() -> None:
    items = [{"name": "a", "order": 2}, {"name": "b", "order": 0}, {"name": "c", "order": 1}]
    assert [i["name"] for i in by_order(items)] == ["b", "c", "a"]


def test_table_methods_are_written_with_braces() -> None:
    method: Method = {
        "parameters": [{"name": "p", "order": 0, "type": "string"}],
        "format": {"takes_table": True, "table_optional": True},
    }
    assert method_params(method) == "{p: string}?"
