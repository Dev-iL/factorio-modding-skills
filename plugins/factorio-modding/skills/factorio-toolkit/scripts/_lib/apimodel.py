"""Typed view of lua-api.factorio.com's machine-readable JSON (api_version 6) and one-line renderings of it.

Structure source: https://lua-api.factorio.com/latest/auxiliary/json-docs-runtime.html and json-docs-prototype.html.
Two format rules matter here: every list in the JSON is sorted alphabetically, and the order shown on the website
is the `order` field of each member, so everything user-facing is re-sorted with `by_order`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Literal, TypedDict, TypeIs

API_VERSION = 6
type Stage = Literal["runtime", "prototype"]
STAGES: tuple[Stage, ...] = ("runtime", "prototype")

type Scalar = str | int | float | bool
type TypeExpr = str | ComplexType


class Parameter(TypedDict, total=False):
    name: str
    order: int
    description: str
    type: TypeExpr
    optional: bool


class ParameterGroup(TypedDict, total=False):
    name: str
    order: int
    description: str
    parameters: list[Parameter]


class ComplexType(TypedDict, total=False):
    complex_type: str
    value: TypeExpr | int | float | bool
    key: TypeExpr
    options: list[TypeExpr]
    full_format: bool
    parameters: list[Parameter | TypeExpr]  # table: named parameters; function: bare types
    variant_parameter_groups: list[ParameterGroup]
    values: list[TypeExpr]
    attributes: list[Attribute]
    description: str


class MethodFormat(TypedDict, total=False):
    takes_table: bool
    table_optional: bool


class VariadicParameter(TypedDict, total=False):
    type: TypeExpr
    description: str


class EventRaised(TypedDict, total=False):
    name: str
    order: int
    description: str
    timeframe: str
    optional: bool


class Member(TypedDict, total=False):
    """Fields shared by methods, attributes and operators (`BasicMember` in the format docs)."""

    name: str
    order: int
    description: str
    lists: list[str]
    examples: list[str]
    visibility: list[str]
    subclasses: list[str]
    raises: list[EventRaised]


class Method(Member, total=False):
    parameters: list[Parameter]
    variant_parameter_groups: list[ParameterGroup]
    variant_parameter_description: str
    variadic_parameter: VariadicParameter
    format: MethodFormat
    return_values: list[Parameter]


class Attribute(Member, total=False):
    read_type: TypeExpr
    write_type: TypeExpr
    optional: bool


class ApiClass(TypedDict, total=False):
    name: str
    order: int
    description: str
    lists: list[str]
    examples: list[str]
    visibility: list[str]
    parent: str
    abstract: bool
    methods: list[Method]
    attributes: list[Attribute]
    operators: list[Method | Attribute]


class Event(TypedDict, total=False):
    name: str
    order: int
    description: str
    lists: list[str]
    examples: list[str]
    data: list[Parameter]
    filter: str


class Concept(TypedDict, total=False):
    name: str
    order: int
    description: str
    lists: list[str]
    examples: list[str]
    type: TypeExpr
    parent: str
    abstract: bool
    inline: bool
    properties: list[Property]


class DefineValue(TypedDict, total=False):
    name: str
    order: int
    description: str


class Define(TypedDict, total=False):
    name: str
    order: int
    description: str
    values: list[DefineValue]
    subkeys: list[Define]


class Property(TypedDict, total=False):
    name: str
    order: int
    description: str
    lists: list[str]
    examples: list[str]
    visibility: list[str]
    alt_name: str
    override: bool
    type: TypeExpr
    optional: bool
    default: str | ComplexType


class CustomProperties(TypedDict, total=False):
    description: str
    key_type: TypeExpr
    value_type: TypeExpr


class Prototype(TypedDict, total=False):
    name: str
    order: int
    description: str
    lists: list[str]
    examples: list[str]
    visibility: list[str]
    parent: str
    abstract: bool
    typename: str
    instance_limit: int
    deprecated: bool
    properties: list[Property]
    custom_properties: CustomProperties


class RuntimeDoc(TypedDict, total=False):
    application_version: str
    api_version: int
    stage: str
    classes: list[ApiClass]
    events: list[Event]
    concepts: list[Concept]
    defines: list[Define]
    global_objects: list[Parameter]
    global_functions: list[Method]


class PrototypeDoc(TypedDict, total=False):
    application_version: str
    api_version: int
    stage: str
    prototypes: list[Prototype]
    types: list[Concept]
    defines: list[Define]


def by_order[T: Member | Parameter | Property | DefineValue | Define | ParameterGroup](items: Iterable[T]) -> list[T]:
    """Sort into declared order: the website's order, which is not the JSON's alphabetical order."""
    return sorted(items, key=lambda item: (item.get("order", 0), item.get("name", "")))


def format_type(t: TypeExpr | int | float | bool) -> str:
    """Render a type expression on one line, e.g. `array[LuaEntity]`, `string | nil`, `{x: double, y?: double}`."""
    if isinstance(t, str):
        return t
    if isinstance(t, (bool, int, float)):
        return json.dumps(t)
    kind = t.get("complex_type", "")
    match kind:
        case "array":
            return f"array[{format_type(t['value'])}]"
        case "dictionary" | "LuaCustomTable":
            name = "dict" if kind == "dictionary" else kind
            return f"{name}[{format_type(t['key'])}, {format_type(t['value'])}]"
        case "union":
            return " | ".join(format_type(o) for o in t.get("options", []))
        case "tuple":
            return f"tuple[{', '.join(format_type(v) for v in t.get('values', []))}]"
        case "table":
            return _format_table(t)
        case "type":
            return format_type(t["value"])
        case "literal":
            return json.dumps(t["value"])
        case "function":
            params = [p for p in t.get("parameters", []) if not _is_parameter(p)]
            return f"function({', '.join(format_type(p) for p in params)})"
        case "LuaLazyLoadedValue":
            return f"LuaLazyLoadedValue[{format_type(t['value'])}]"
        case "LuaStruct":
            return "LuaStruct{" + ", ".join(format_attribute_field(a) for a in by_order(t.get("attributes", []))) + "}"
        case "struct" | "builtin":
            return kind
        case _:
            return f"<{kind or 'unknown'}: {json.dumps(t, sort_keys=True)[:80]}>"


def _is_parameter(value: Parameter | TypeExpr) -> TypeIs[Parameter]:
    return isinstance(value, dict) and "name" in value


def _format_table(t: ComplexType) -> str:
    params = [p for p in t.get("parameters", []) if _is_parameter(p)]
    text = ", ".join(format_param(p) for p in by_order(params))
    for group in by_order(t.get("variant_parameter_groups", [])):
        text += f"; {group.get('name', '')}: " + ", ".join(format_param(p) for p in by_order(group.get("parameters", [])))
    return "{" + text + "}"


def format_param(p: Parameter) -> str:
    """`name: type`, with `?` after the name for optional parameters."""
    return f"{p.get('name', '')}{'?' if p.get('optional') else ''}: {format_type(p.get('type', '?'))}"


def format_attribute_field(a: Attribute) -> str:
    return f"{a.get('name', '')}: {format_type(a.get('read_type') or a.get('write_type') or '?')}"


def format_returns(values: Sequence[Parameter]) -> str:
    parts = [format_type(v.get("type", "?")) + ("?" if v.get("optional") else "") for v in by_order(values)]
    return ", ".join(parts)


def method_params(m: Method) -> str:
    """The parameter list of a method, with the call brackets: `(a: T, b?: U)` or `{a: T, b?: U}` for table calls."""
    params = ", ".join(format_param(p) for p in by_order(m.get("parameters", [])))
    for group in by_order(m.get("variant_parameter_groups", [])):
        params += f"; {group.get('name', '')}: " + ", ".join(format_param(p) for p in by_order(group.get("parameters", [])))
    variadic = m.get("variadic_parameter")
    if variadic:
        params += (", " if params else "") + f"...: {format_type(variadic.get('type', 'any'))}"
    fmt = m.get("format", {})
    if fmt.get("takes_table"):
        return "{" + params + "}" + ("?" if fmt.get("table_optional") else "")
    return "(" + params + ")"


def method_signature(owner: str, m: Method) -> str:
    """`Owner.name(a: T) -> R`; table-taking methods are written `Owner.name{a: T}`."""
    returns = format_returns(m.get("return_values", []))
    return f"{owner}.{m.get('name', '')}{method_params(m)}" + (f" -> {returns}" if returns else "")


def attribute_access(a: Attribute) -> str:
    """`read`, `write` or `read-write`, from which of read_type / write_type are present."""
    has_read, has_write = "read_type" in a, "write_type" in a
    return "read-write" if has_read and has_write else "write" if has_write else "read"


def attribute_type(a: Attribute) -> str:
    """The attribute's type; when reading and writing differ, `read T / write U`."""
    read, write = a.get("read_type"), a.get("write_type")
    if read is not None and write is not None and format_type(read) != format_type(write):
        return f"read {format_type(read)} / write {format_type(write)}"
    return format_type(read if read is not None else write if write is not None else "?")


def format_default(value: str | ComplexType | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value or '""'
    return format_type(value)


def property_descriptor(p: Property) -> str:
    """Type, optionality and default of a prototype property, e.g. `uint32 (optional, default 1)`."""
    flags = ["optional"] if p.get("optional") else []
    if "default" in p:
        flags.append(f"default {format_default(p['default'])}")
    return format_type(p.get("type", "?")) + (f" ({', '.join(flags)})" if flags else "")


def first_line(text: str, limit: int = 140) -> str:
    """The first sentence-ish chunk of a description on one line, shortened to `limit` characters."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"
