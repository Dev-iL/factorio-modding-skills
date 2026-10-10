"""Look up one API entry (class, member, prototype, property, event, concept, define) and render it as text.

Every rendered block starts with `<stage> <kind> <qualified name>` so output can be grepped, and all lists
appear in declared (`order`) order, not the alphabetical order of the JSON.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from .apimodel import (
    ApiClass,
    Attribute,
    Concept,
    Define,
    Event,
    Method,
    Parameter,
    Property,
    Prototype,
    PrototypeDoc,
    RuntimeDoc,
    Stage,
    attribute_access,
    attribute_type,
    by_order,
    first_line,
    format_param,
    is_parameter,
    format_returns,
    format_type,
    method_params,
    method_signature,
    property_descriptor,
)
from .errors import ToolkitError

MEMBER_SEARCH_LIMIT = 25
QUERY_RE = re.compile(r"^([^.:\s]+)(?:(?:\.|::)(\S+))?$")


@dataclass(frozen=True)
class Docs:
    """The API documents for one version; either stage may be absent when the caller restricted `--stage`."""

    version: str
    runtime: RuntimeDoc | None = None
    prototype: PrototypeDoc | None = None

    def classes(self) -> dict[str, ApiClass]:
        return {c["name"]: c for c in (self.runtime or {}).get("classes", [])}

    def events(self) -> dict[str, Event]:
        return {e["name"]: e for e in (self.runtime or {}).get("events", [])}

    def concepts(self) -> dict[str, Concept]:
        return {c["name"]: c for c in (self.runtime or {}).get("concepts", [])}

    def prototypes(self) -> dict[str, Prototype]:
        return {p["name"]: p for p in (self.prototype or {}).get("prototypes", [])}

    def types(self) -> dict[str, Concept]:
        return {c["name"]: c for c in (self.prototype or {}).get("types", [])}

    def defines(self) -> list[tuple[Stage, Define]]:
        """Top-level defines; the runtime and prototype documents carry the same ones, so the first present is used."""
        if self.runtime and self.runtime.get("defines"):
            return [("runtime", d) for d in self.runtime["defines"]]
        if self.prototype and self.prototype.get("defines"):
            return [("prototype", d) for d in self.prototype["defines"]]
        return []


def indent(text: str, prefix: str) -> list[str]:
    return [prefix + line if line.strip() else "" for line in text.strip().splitlines()]


def description_lines(text: str, *, full: bool, prefix: str = "  ") -> list[str]:
    if not text.strip():
        return []
    return indent(text, prefix) if full else [prefix + first_line(text, 200)]


def chain_of[T: (ApiClass, Prototype)](name: str, index: Mapping[str, T]) -> list[T]:
    """`name` followed by its ancestors, nearest first (cycle-safe)."""
    out: list[T] = []
    seen: set[str] = set()
    current: str | None = name
    while current and current in index and current not in seen:
        seen.add(current)
        out.append(index[current])
        current = index[current].get("parent")
    return out


# ----------------------------------------------------------------------------------------------- rendering


def _tags(item: Mapping[str, object]) -> str:
    tags = []
    if item.get("abstract"):
        tags.append("abstract")
    if item.get("deprecated"):
        tags.append("deprecated")
    visibility = item.get("visibility")
    if isinstance(visibility, list):
        tags.append("requires " + ", ".join(str(v) for v in visibility))
    return f" [{'; '.join(tags)}]" if tags else ""


def render_method(owner: str, defined_in: str, m: Method, *, full: bool = True) -> list[str]:
    name = m.get("name", "")
    note = f"  [defined in {defined_in}]" if defined_in != owner else ""
    lines = [f"runtime method {owner}.{name}{note}{_tags(m)}", f"  signature: {method_signature(owner, m)}"]
    if m.get("description"):
        lines += ["  description:", *indent(m["description"], "    ")]
    params = by_order(m.get("parameters", []))
    if params:
        takes_table = m.get("format", {}).get("takes_table")
        lines.append("  parameters (declared order" + (", passed as one table" if takes_table else "") + "):")
        lines += _param_lines(params)
    for group in by_order(m.get("variant_parameter_groups", [])):
        lines.append(f"  parameters when {group.get('name', '')} (declared order):")
        lines += _param_lines(by_order(group.get("parameters", [])))
    variadic = m.get("variadic_parameter")
    if variadic:
        lines.append(f"  variadic: ...: {format_type(variadic.get('type', 'any'))} {first_line(variadic.get('description', ''))}".rstrip())
    returns = by_order(m.get("return_values", []))
    if returns:
        lines.append("  returns:")
        for i, r in enumerate(returns, 1):
            desc = first_line(r.get("description", ""), 300)
            lines.append(f"    {i}. {format_returns([r])}" + (f" - {desc}" if desc else ""))
    for raised in m.get("raises", []):
        lines.append(f"  raises: {raised.get('name', '')} ({raised.get('timeframe', '')}{', optional' if raised.get('optional') else ''})")
    return lines + _examples(m)


def _param_lines(params: Sequence[Parameter]) -> list[str]:
    lines = []
    for i, p in enumerate(params, 1):
        desc = first_line(p.get("description", ""), 300)
        lines.append(f"    {i}. {format_param(p)}" + (f" - {desc}" if desc else ""))
    return lines


def _examples(item: Mapping[str, object]) -> list[str]:
    examples = item.get("examples")
    if not isinstance(examples, list) or not examples:
        return []
    return ["  examples:", *[line for ex in examples for line in indent(str(ex), "    ")]]


def render_attribute(owner: str, defined_in: str, a: Attribute) -> list[str]:
    note = f"  [defined in {defined_in}]" if defined_in != owner else ""
    optional = "?" if a.get("optional") else ""
    lines = [
        f"runtime attribute {owner}.{a.get('name', '')}{note}{_tags(a)}",
        f"  signature: {owner}.{a.get('name', '')}: {attribute_type(a)}{optional} ({attribute_access(a)})",
    ]
    if a.get("description"):
        lines += ["  description:", *indent(a["description"], "    ")]
    for raised in a.get("raises", []):
        lines.append(f"  raises when written: {raised.get('name', '')} ({raised.get('timeframe', '')})")
    return lines + _examples(a)


def render_property(owner: str, defined_in: str, p: Property) -> list[str]:
    note = f"  [defined in {defined_in}]" if defined_in != owner else ""
    alt = f"  (also written `{p['alt_name']}`)" if p.get("alt_name") else ""
    lines = [f"prototype property {owner}.{p.get('name', '')}{note}{alt}{_tags(p)}", f"  type: {property_descriptor(p)}"]
    if p.get("description"):
        lines += ["  description:", *indent(p["description"], "    ")]
    return lines + _examples(p)


def render_event(e: Event) -> list[str]:
    lines = [f"runtime event {e.get('name', '')}"]
    lines += description_lines(e.get("description", ""), full=True)
    if e.get("filter"):
        lines.append(f"  filter: {e['filter']}  (the entry type of the `filters` argument of LuaBootstrap.on_event and set_event_filter)")
    lines.append("  data (declared order):")
    for i, p in enumerate(by_order(e.get("data", [])), 1):
        desc = first_line(p.get("description", ""), 300)
        lines.append(f"    {i}. {format_param(p)}" + (f" - {desc}" if desc else ""))
    return lines + _examples(e)


def render_class(cls: ApiClass, classes: Mapping[str, ApiClass], *, full: bool, inherited: bool) -> list[str]:
    name = cls.get("name", "")
    chain = chain_of(name, classes)
    ancestors = [c.get("name", "") for c in chain[1:]]
    extends = f"  extends {' -> '.join(ancestors)}" if ancestors else ""
    lines = [f"runtime class {name}{extends}{_tags(cls)}", *description_lines(cls.get("description", ""), full=True)]
    for source in (chain if inherited else chain[:1]):
        owner = name
        src = source.get("name", "")
        suffix = "" if src == name else f"  [from {src}]"
        for m in by_order(source.get("methods", [])):
            lines.append(f"runtime method {owner}.{m.get('name', '')}{method_params(m)}{_returns(m)}{suffix}" + _summary(m, full))
        for a in by_order(source.get("attributes", [])):
            lines.append(
                f"runtime attribute {owner}.{a.get('name', '')}: {attribute_type(a)}{'?' if a.get('optional') else ''}"
                f" ({attribute_access(a)}){suffix}" + _summary(a, full)
            )
    if not inherited:
        for source in chain[1:]:
            n_methods, n_attrs = len(source.get("methods", [])), len(source.get("attributes", []))
            lines.append(
                f"# inherited from {source.get('name', '')}: {n_methods} methods, {n_attrs} attributes "
                f"(`lookup {source.get('name', '')}` lists them, `--inherited` lists them here)"
            )
    for op in cls.get("operators", []):
        lines.append(f"runtime operator {name}.{op.get('name', '')}")
    return lines


def _returns(m: Method) -> str:
    returns = format_returns(m.get("return_values", []))
    return f" -> {returns}" if returns else ""


def _summary(item: Mapping[str, object], full: bool) -> str:
    desc = item.get("description")
    if not isinstance(desc, str) or not desc.strip():
        return ""
    return f"  - {' '.join(desc.split())}" if full else f"  - {first_line(desc, 100)}"


def render_prototype(proto: Prototype, prototypes: Mapping[str, Prototype], *, full: bool) -> list[str]:
    name = proto.get("name", "")
    chain = chain_of(name, prototypes)
    ancestors = [c.get("name", "") for c in chain[1:]]
    typename = f'  typename="{proto["typename"]}"' if proto.get("typename") else ""
    extends = f"  extends {' -> '.join(ancestors)}" if ancestors else ""
    lines = [f"prototype prototype {name}{typename}{extends}{_tags(proto)}", *description_lines(proto.get("description", ""), full=True)]
    if proto.get("instance_limit") is not None:
        lines.append(f"  instance limit: {proto['instance_limit']}")
    lines.append("  properties: own first, then inherited by ancestor; each group in declared order")
    seen: set[str] = set()
    for source in chain:
        src = source.get("name", "")
        suffix = "" if src == name else f"  [from {src}]"
        for p in by_order(source.get("properties", [])):
            if p.get("name", "") in seen:
                continue  # an override in a nearer class already shows it
            seen.add(p.get("name", ""))
            alt = f" (alt `{p['alt_name']}`)" if p.get("alt_name") else ""
            lines.append(f"prototype property {name}.{p.get('name', '')}{alt}: {property_descriptor(p)}{suffix}" + _summary(p, full))
    custom = proto.get("custom_properties")
    if custom:
        lines.append(f"  custom properties: {format_type(custom.get('key_type', '?'))} -> {format_type(custom.get('value_type', '?'))}")
    return lines + _examples(proto)


def _concept_fields(c: Concept) -> list[Property]:
    """Fields of a struct-like concept: its `properties`, or the parameters of its table type as properties."""
    if c.get("properties"):
        return c["properties"]
    t = c.get("type")
    if not (isinstance(t, dict) and t.get("complex_type") == "table"):
        return []
    return [
        Property(name=p.get("name", ""), order=p.get("order", 0), description=p.get("description", ""), type=p.get("type", "?"), optional=p.get("optional", False))
        for p in t.get("parameters", [])
        if is_parameter(p)
    ]


def render_concept(c: Concept, stage: Stage, *, full: bool) -> list[str]:
    name = c.get("name", "")
    kind = "concept" if stage == "runtime" else "type"
    t = c.get("type", "?")
    shown = "struct" if isinstance(t, dict) and t.get("complex_type") in ("struct", "table") else format_type(t)
    parent = f"  extends {c['parent']}" if c.get("parent") else ""
    lines = [f"{stage} {kind} {name}{parent}{_tags(c)}  = {shown}", *description_lines(c.get("description", ""), full=True)]
    fields = by_order(_concept_fields(c))
    if fields:
        lines.append("  fields (declared order):")
        lines += [f"{stage} field {name}.{f.get('name', '')}: {property_descriptor(f)}{_summary(f, full)}" for f in fields]
    return lines + _examples(c)


def render_define(path: str, d: Define) -> list[str]:
    lines = [f"runtime define {path}", *description_lines(d.get("description", ""), full=True)]
    for v in by_order(d.get("values", [])):
        lines.append(f"runtime define-value {path}.{v.get('name', '')}" + _summary(v, True))
    for sub in by_order(d.get("subkeys", [])):
        lines.append(f"runtime define {path}.{sub.get('name', '')}  (sub-define)")
    return lines


# ----------------------------------------------------------------------------------------------- lookup


def _walk_defines(docs: Docs) -> Iterator[tuple[str, Define]]:
    def rec(prefix: str, d: Define) -> Iterator[tuple[str, Define]]:
        path = f"{prefix}.{d.get('name', '')}"
        yield path, d
        for sub in d.get("subkeys", []):
            yield from rec(path, sub)

    for _, top in docs.defines():
        yield from rec("defines", top)


def _lookup_define(docs: Docs, query: str) -> list[str]:
    if query == "defines":
        return ["runtime define defines  (all top-level defines)"] + [f"runtime define defines.{d.get('name', '')}" for _, d in docs.defines()]
    by_path = dict(_walk_defines(docs))
    if query in by_path:
        return render_define(query, by_path[query])
    parent, _, leaf = query.rpartition(".")
    if parent in by_path and any(v.get("name") == leaf for v in by_path[parent].get("values", [])):
        value = next(v for v in by_path[parent]["values"] if v.get("name") == leaf)
        return [f"runtime define-value {query}", *description_lines(value.get("description", ""), full=True)]
    raise _miss(docs, query, list(by_path))


def _all_heads(docs: Docs) -> list[str]:
    names = [*docs.classes(), *docs.events(), *docs.concepts(), *docs.prototypes(), *docs.types()]
    names += [p["typename"] for p in docs.prototypes().values() if p.get("typename")]
    if docs.runtime:
        names += [g["name"] for g in docs.runtime.get("global_objects", [])] + [g["name"] for g in docs.runtime.get("global_functions", [])]
    return list(dict.fromkeys(names))


def _suggest(query: str, candidates: Sequence[str], count: int = 5) -> list[str]:
    lowered = {c.lower(): c for c in candidates}
    close = [lowered[m] for m in difflib.get_close_matches(query.lower(), list(lowered), n=count, cutoff=0.6)]
    substring = [c for low, c in lowered.items() if query.lower() in low and c not in close][:count]
    return [*close, *substring][: count + 2]


def _miss(docs: Docs, query: str, candidates: Sequence[str], what: str = "name") -> ToolkitError:
    suggestions = _suggest(query, candidates)
    hint = f"did you mean: {', '.join(suggestions)}?" if suggestions else "check the spelling, or search the docs at https://lua-api.factorio.com/."
    return ToolkitError(f"no API {what} {query!r} in Factorio {docs.version}.", hint)


def _all_members(docs: Docs) -> Iterator[tuple[str, str, str, str]]:
    """(member name, stage, kind, owner) for every class method/attribute and prototype property."""
    for cname, cls in docs.classes().items():
        for m in cls.get("methods", []):
            yield m.get("name", ""), "runtime", "method", cname
        for a in cls.get("attributes", []):
            yield a.get("name", ""), "runtime", "attribute", cname
    for pname, proto in docs.prototypes().items():
        for p in proto.get("properties", []):
            yield p.get("name", ""), "prototype", "property", pname


def _member_search(docs: Docs, name: str) -> list[str]:
    hits = [(st, kind, owner) for member, st, kind, owner in _all_members(docs) if member == name]
    if not hits:
        return []
    shown = [f"{st} {kind} {owner}.{name}" for st, kind, owner in hits[:MEMBER_SEARCH_LIMIT]]
    more = [f"# ... {len(hits) - MEMBER_SEARCH_LIMIT} more"] if len(hits) > MEMBER_SEARCH_LIMIT else []
    return [f"# no class, event, prototype or concept is named {name!r}; members with that name (look one up as Owner.{name}):", *shown, *more]


def _find_member_block(docs: Docs, head: str, member: str, full: bool) -> list[list[str]]:
    blocks: list[list[str]] = []
    classes, prototypes = docs.classes(), docs.prototypes()
    if head in classes:
        for source in chain_of(head, classes):
            src = source.get("name", "")
            for m in source.get("methods", []):
                if m.get("name") == member:
                    blocks.append(render_method(head, src, m))
            for a in source.get("attributes", []):
                if a.get("name") == member:
                    blocks.append(render_attribute(head, src, a))
            if blocks:
                break
    if head in prototypes:
        for proto_source in chain_of(head, prototypes):
            src = proto_source.get("name", "")
            found = [p for p in proto_source.get("properties", []) if member in (p.get("name"), p.get("alt_name"))]
            if found:
                blocks.append(render_property(head, src, found[0]))
                break
    if head in docs.events():
        for p in docs.events()[head].get("data", []):
            if p.get("name") == member:
                blocks.append([f"runtime event-field {head}.{member}", f"  type: {format_param(p)}", *description_lines(p.get("description", ""), full=True)])
    concept_tables: tuple[tuple[Stage, Mapping[str, Concept]], ...] = (("runtime", docs.concepts()), ("prototype", docs.types()))
    for stage, table in concept_tables:
        concept = table.get(head)
        if concept:
            for f in _concept_fields(concept):
                if f.get("name") == member:
                    blocks.append([f"{stage} field {head}.{member}", f"  type: {property_descriptor(f)}", *description_lines(f.get("description", ""), full=True)])
    return blocks


def _member_candidates(docs: Docs, head: str) -> list[str]:
    names: list[str] = []
    for source in chain_of(head, docs.classes()):
        names += [m.get("name", "") for m in source.get("methods", [])] + [a.get("name", "") for a in source.get("attributes", [])]
    for proto_source in chain_of(head, docs.prototypes()):
        names += [p.get("name", "") for p in proto_source.get("properties", [])]
    if head in docs.events():
        names += [p.get("name", "") for p in docs.events()[head].get("data", [])]
    for table in (docs.concepts(), docs.types()):
        if head in table:
            names += [f.get("name", "") for f in _concept_fields(table[head])]
    return names


def _head_blocks(docs: Docs, head: str, *, full: bool, inherited: bool) -> list[list[str]]:
    blocks: list[list[str]] = []
    classes, prototypes = docs.classes(), docs.prototypes()
    if head in classes:
        blocks.append(render_class(classes[head], classes, full=full, inherited=inherited))
    if head in docs.events():
        blocks.append(render_event(docs.events()[head]))
    stages: tuple[tuple[Stage, Mapping[str, Concept]], ...] = (("runtime", docs.concepts()), ("prototype", docs.types()))
    for stage, table in stages:
        if head in table:
            blocks.append(render_concept(table[head], stage, full=full))
    if head in prototypes:
        blocks.append(render_prototype(prototypes[head], prototypes, full=full))
    by_typename = [p for p in prototypes.values() if p.get("typename") == head]
    for proto in by_typename:
        blocks.append(render_prototype(proto, prototypes, full=full))
    if docs.runtime:
        for g in docs.runtime.get("global_objects", []):
            if g.get("name") == head:
                blocks.append([f"runtime global-object {head}: {format_type(g.get('type', '?'))}", *description_lines(g.get("description", ""), full=True)])
        for fn in docs.runtime.get("global_functions", []):
            if fn.get("name") == head:
                blocks.append([f"runtime global-function {head}{method_params(fn)}{_returns(fn)}", *description_lines(fn.get("description", ""), full=True)])
    return blocks


def lookup(query: str, docs: Docs, *, full: bool = False, inherited: bool = False) -> list[str]:
    """Render the API entry named by `query`, or raise a ToolkitError with "did you mean" suggestions.

    `query` is a bare name (`LuaEntity`, `AssemblingMachinePrototype`, `on_built_entity`, a prototype `typename`
    such as `assembling-machine`, a concept) or `Owner.member` / `Owner::member`, or a define path (`defines.inventory`).
    Members are found through the parent chain, so `LuaEntity.get_inventory` resolves to the method LuaControl declares.
    """
    query = query.strip()
    if query == "defines" or query.startswith("defines."):
        return _lookup_define(docs, query)
    match = QUERY_RE.match(query)
    if not match:
        raise ToolkitError(f"cannot parse {query!r} as an API name.", "use Name or Owner.member, e.g. LuaEntity.get_inventory.")
    head, member = match.group(1), match.group(2)
    if not _head_exists(docs, head):
        folded = {h.lower(): h for h in _all_heads(docs)}
        if head.lower() in folded:
            head = folded[head.lower()]
        elif member is None:
            found = _member_search(docs, head)
            if found:
                return found
            raise _miss(docs, head, _all_heads(docs))
        else:
            raise _miss(docs, head, _all_heads(docs))
    if member is None:
        return _join(_head_blocks(docs, head, full=full, inherited=inherited))
    blocks = _find_member_block(docs, head, member, full)
    if not blocks:
        raise _miss(docs, member, _member_candidates(docs, head), what=f"member of {head}")
    return _join(blocks)


def _head_exists(docs: Docs, head: str) -> bool:
    return bool(
        head in docs.classes()
        or head in docs.events()
        or head in docs.concepts()
        or head in docs.prototypes()
        or head in docs.types()
        or any(p.get("typename") == head for p in docs.prototypes().values())
        or (docs.runtime and any(g.get("name") == head for g in [*docs.runtime.get("global_objects", []), *docs.runtime.get("global_functions", [])]))
    )


def _join(blocks: Sequence[Sequence[str]]) -> list[str]:
    out: list[str] = []
    for i, block in enumerate(blocks):
        if i:
            out.append("")
        out += block
    return out
