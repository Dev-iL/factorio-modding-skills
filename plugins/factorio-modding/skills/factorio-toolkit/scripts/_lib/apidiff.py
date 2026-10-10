"""Diff two versions of the API JSON into grep-friendly lines.

Each line is `<STATUS> <stage> <kind> <qualified name>[: detail]`, with STATUS one of ADDED, REMOVED, MOVED
(the member left this class but is still reachable through its new parents) or CHANGED (`old -> new`).
Descriptions are not compared, only structure: types, optionality, defaults, parents, visibility.
Members of an added or removed class, event, concept, prototype or define are not listed separately.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .apimodel import (
    Concept,
    Define,
    Property,
    PrototypeDoc,
    RuntimeDoc,
    Stage,
    attribute_access,
    attribute_type,
    format_param,
    format_returns,
    format_type,
    is_parameter,
    method_params,
    property_descriptor,
)

STATUS_ORDER = {"ADDED": 0, "REMOVED": 1, "MOVED": 2, "CHANGED": 3}
CONTAINER_OF = {
    "method": "class",
    "attribute": "class",
    "event-field": "event",
    "concept-field": "concept",
    "property": "prototype",
    "type-field": "type",
}
CONTAINER_KINDS = frozenset(CONTAINER_OF.values()) | {"define"}


@dataclass(frozen=True)
class Entry:
    stage: Stage
    kind: str
    name: str
    detail: str
    container: str | None = None  # qualified name of the owner for members, in the same stage


type Entries = dict[tuple[Stage, str, str], Entry]


def _tags(item: Mapping[str, object]) -> list[str]:
    tags = []
    if item.get("abstract"):
        tags.append("abstract")
    if item.get("deprecated"):
        tags.append("deprecated")
    visibility = item.get("visibility")
    if isinstance(visibility, list) and visibility:
        tags.append("requires " + "+".join(str(v) for v in visibility))
    return tags


def _add(out: Entries, stage: Stage, kind: str, name: str, detail: str = "", owner: str | None = None) -> None:
    out[(stage, kind, name)] = Entry(stage, kind, name, detail, owner)


def _concept_entries(out: Entries, stage: Stage, kind: str, field_kind: str, concept: Concept) -> None:
    name = concept.get("name", "")
    t = concept.get("type", "?")
    is_struct = isinstance(t, dict) and t.get("complex_type") in ("struct", "table")
    parts = [] if is_struct else [format_type(t)]
    if concept.get("parent"):
        parts.append(f"extends {concept['parent']}")
    _add(out, stage, kind, name, "; ".join(parts + _tags(concept)))
    fields: list[Property] = list(concept.get("properties", []))
    if isinstance(t, dict) and t.get("complex_type") == "table":
        fields += [
            Property(name=p.get("name", ""), type=p.get("type", "?"), optional=p.get("optional", False))
            for p in t.get("parameters", [])
            if is_parameter(p)
        ]
    for f in fields:
        _add(out, stage, field_kind, f"{name}.{f.get('name', '')}", property_descriptor(f), owner=name)


def _define_entries(out: Entries, stage: Stage, prefix: str, d: Define) -> None:
    path = f"{prefix}.{d.get('name', '')}"
    _add(out, stage, "define", path, owner=prefix if prefix != "defines" else None)
    for v in d.get("values", []):
        _add(out, stage, "define-value", f"{path}.{v.get('name', '')}", owner=path)
    for sub in d.get("subkeys", []):
        _define_entries(out, stage, path, sub)


def flatten_runtime(doc: RuntimeDoc) -> Entries:
    out: Entries = {}
    for cls in doc.get("classes", []):
        cname = cls.get("name", "")
        parts = ([f"extends {cls['parent']}"] if cls.get("parent") else []) + _tags(cls)
        _add(out, "runtime", "class", cname, "; ".join(parts))
        for m in cls.get("methods", []):
            returns = format_returns(m.get("return_values", []))
            detail = method_params(m) + (f" -> {returns}" if returns else "")
            _add(out, "runtime", "method", f"{cname}.{m.get('name', '')}", " ".join([detail, *[f"[{t}]" for t in _tags(m)]]), owner=cname)
        for a in cls.get("attributes", []):
            detail = f"{attribute_type(a)}{'?' if a.get('optional') else ''} ({attribute_access(a)})"
            _add(out, "runtime", "attribute", f"{cname}.{a.get('name', '')}", " ".join([detail, *[f"[{t}]" for t in _tags(a)]]), owner=cname)
    for e in doc.get("events", []):
        ename = e.get("name", "")
        _add(out, "runtime", "event", ename, f"filter {e['filter']}" if e.get("filter") else "")
        for p in e.get("data", []):
            _add(out, "runtime", "event-field", f"{ename}.{p.get('name', '')}", format_param(p).split(": ", 1)[1] + ("?" if p.get("optional") else ""), owner=ename)
    for c in doc.get("concepts", []):
        _concept_entries(out, "runtime", "concept", "concept-field", c)
    for d in doc.get("defines", []):
        _define_entries(out, "runtime", "defines", d)
    for g in doc.get("global_objects", []):
        _add(out, "runtime", "global-object", g.get("name", ""), format_type(g.get("type", "?")))
    for fn in doc.get("global_functions", []):
        _add(out, "runtime", "global-function", fn.get("name", ""), method_params(fn))
    return out


def flatten_prototype(doc: PrototypeDoc) -> Entries:
    out: Entries = {}
    for proto in doc.get("prototypes", []):
        pname = proto.get("name", "")
        parts = [f"typename {proto['typename']}"] if proto.get("typename") else []
        parts += ([f"extends {proto['parent']}"] if proto.get("parent") else []) + _tags(proto)
        _add(out, "prototype", "prototype", pname, "; ".join(parts))
        for p in proto.get("properties", []):
            alt = f" (alt {p['alt_name']})" if p.get("alt_name") else ""
            _add(out, "prototype", "property", f"{pname}.{p.get('name', '')}", property_descriptor(p) + alt, owner=pname)
    for c in doc.get("types", []):
        _concept_entries(out, "prototype", "type", "type-field", c)
    return out


type AncestorFinder = Callable[[str, str], str | None]


def _ancestor_finder(parents: Mapping[str, str | None], declared: Mapping[str, set[str]]) -> AncestorFinder:
    """`find(owner, member)`: the nearest ancestor of `owner` that declares `member`, or None."""

    def find(owner: str, member: str) -> str | None:
        seen = {owner}
        current = parents.get(owner)
        while current and current not in seen:
            seen.add(current)
            if member in declared.get(current, set()):
                return current
            current = parents.get(current)
        return None

    return find


def runtime_ancestors(doc: RuntimeDoc) -> AncestorFinder:
    classes = doc.get("classes", [])
    declared = {c.get("name", ""): {m.get("name", "") for m in (*c.get("methods", []), *c.get("attributes", []))} for c in classes}
    return _ancestor_finder({c.get("name", ""): c.get("parent") for c in classes}, declared)


def prototype_ancestors(doc: PrototypeDoc) -> AncestorFinder:
    protos = doc.get("prototypes", [])
    declared = {p.get("name", ""): {q.get("name", "") for q in p.get("properties", [])} for p in protos}
    return _ancestor_finder({p.get("name", ""): p.get("parent") for p in protos}, declared)


def diff_entries(old: Entries, new: Entries, find_in_new_parents: AncestorFinder) -> list[tuple[str, Entry, str]]:
    """Return `(status, entry, detail)` triples, unsorted. `find_in_new_parents` powers the MOVED check."""
    added = {k for k in new if k not in old}
    removed = {k for k in old if k not in new}
    gone_containers = {(k[0], k[2]) for k in removed if k[1] in CONTAINER_KINDS}
    new_containers = {(k[0], k[2]) for k in added if k[1] in CONTAINER_KINDS}
    results: list[tuple[str, Entry, str]] = []
    for key in added:
        entry = new[key]
        if entry.container and (entry.stage, entry.container) in new_containers:
            continue
        results.append(("ADDED", entry, entry.detail))
    for key in removed:
        entry = old[key]
        if entry.container and (entry.stage, entry.container) in gone_containers:
            continue
        if entry.kind in ("method", "attribute", "property") and entry.container:
            member = entry.name.split(".", 1)[1]
            source = find_in_new_parents(entry.container, member)
            if source:
                results.append(("MOVED", entry, f"now inherited from {source}"))
                continue
        results.append(("REMOVED", entry, entry.detail))
    for key, entry in new.items():
        if key in old and old[key].detail != entry.detail:
            results.append(("CHANGED", entry, f"{old[key].detail or '(none)'} -> {entry.detail or '(none)'}"))
    return results


def render_diff(old_version: str, new_version: str, results: list[tuple[str, Entry, str]]) -> list[str]:
    results.sort(key=lambda r: (STATUS_ORDER[r[0]], r[1].stage != "runtime", r[1].kind, r[1].name))
    counts: dict[str, int] = {}
    for status, _, _ in results:
        counts[status] = counts.get(status, 0) + 1
    summary = ", ".join(f"{counts.get(s, 0)} {s}" for s in STATUS_ORDER)
    lines = [
        f"# API diff {old_version} -> {new_version}: {summary}",
        "# line format: STATUS stage kind name[: detail]; MOVED = left this class but still reachable via its parents;",
        "# members of added or removed classes/events/concepts/prototypes/defines are not listed separately; descriptions are not compared.",
    ]
    for status, entry, detail in results:
        lines.append(f"{status} {entry.stage} {entry.kind} {entry.name}" + (f": {detail}" if detail else ""))
    return lines


def diff_docs(
    old_version: str,
    new_version: str,
    old_runtime: RuntimeDoc | None,
    new_runtime: RuntimeDoc | None,
    old_prototype: PrototypeDoc | None,
    new_prototype: PrototypeDoc | None,
) -> list[str]:
    """Diff whichever stages are present on both sides and render the result."""
    results: list[tuple[str, Entry, str]] = []
    if old_runtime is not None and new_runtime is not None:
        results += diff_entries(flatten_runtime(old_runtime), flatten_runtime(new_runtime), runtime_ancestors(new_runtime))
    if old_prototype is not None and new_prototype is not None:
        results += diff_entries(flatten_prototype(old_prototype), flatten_prototype(new_prototype), prototype_ancestors(new_prototype))
    return render_diff(old_version, new_version, results)
