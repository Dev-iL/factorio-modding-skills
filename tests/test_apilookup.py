from __future__ import annotations

import pytest
from _lib.apilookup import Docs, lookup
from _lib.errors import ToolkitError

from api_docs import prototype_old, runtime_old

DOCS = Docs("1.0.0", runtime_old(), prototype_old())


def text(query: str, *, inherited: bool = False) -> str:
    return "\n".join(lookup(query, DOCS, inherited=inherited))


def test_member_is_found_through_the_parent_chain_and_says_where_it_is_defined() -> None:
    out = text("LuaEntity.get_inventory")
    first = out.splitlines()[0]
    assert first.startswith("runtime method LuaEntity.get_inventory") and "[defined in LuaControl]" in first
    assert "signature: LuaEntity.get_inventory(inventory: defines.inventory) -> LuaInventory?" in out
    assert "Get an inventory belonging to this entity." in out
    assert "1. inventory: defines.inventory" in out


def test_double_colon_form_works_like_the_dot_form() -> None:
    assert text("LuaEntity::get_inventory") == text("LuaEntity.get_inventory")


def test_table_taking_method_lists_parameters_in_declared_not_alphabetical_order() -> None:
    out = text("LuaEntity.create_thing")
    assert "LuaEntity.create_thing{amount?: uint32, name: string, force: string}" in out
    numbered = [line.strip().split(":")[0] for line in out.splitlines() if line.strip()[:2] in ("1.", "2.", "3.")]
    assert numbered == ["1. amount?", "2. name", "3. force"]


def test_event_data_is_in_declared_order_with_its_filter() -> None:
    out = text("on_built_entity")
    fields = [line.split()[1].rstrip(":") for line in out.splitlines() if line.strip()[:2] in ("1.", "2.", "3.", "4.")]
    assert fields == ["entity", "player_index", "name", "tick"]
    assert "filter: LuaPlayerBuiltEntityEventFilter" in out


def test_prototype_lists_own_properties_first_then_inherited_each_in_declared_order() -> None:
    lines = [line for line in lookup("AssemblingMachinePrototype", DOCS) if line.startswith("prototype property")]
    names = [line.split()[2].split(".")[1].rstrip(":") for line in lines]
    assert names == ["circuit_connector", "fixed_recipe", "crafting_speed", "energy_usage"]
    assert "[from CraftingMachinePrototype]" in lines[-1]
    assert 'default ""' in lines[1]


def test_prototype_is_found_by_its_typename_string() -> None:
    assert text("assembling-machine").startswith('prototype prototype AssemblingMachinePrototype  typename="assembling-machine"')


def test_inherited_prototype_property_is_found_on_the_child() -> None:
    assert "[defined in CraftingMachinePrototype]" in text("AssemblingMachinePrototype.energy_usage")


def test_class_listing_summarises_parents_unless_asked() -> None:
    compact = text("LuaEntity")
    assert "runtime method LuaEntity.create_thing" in compact and "LuaEntity.get_inventory" not in compact
    assert "# inherited from LuaControl: 1 methods, 1 attributes" in compact
    assert "runtime method LuaEntity.get_inventory" in text("LuaEntity", inherited=True)


def test_concept_fields_and_define_values_in_declared_order() -> None:
    fields = [line.split()[2] for line in lookup("SimplePoint", DOCS) if line.startswith("runtime field")]
    assert fields == ["SimplePoint.x:", "SimplePoint.y:"]
    values = [line.split()[2] for line in lookup("defines.inventory", DOCS) if line.startswith("runtime define-value")]
    assert values == ["defines.inventory.chest", "defines.inventory.furnace_source"]


def test_a_miss_suggests_close_names() -> None:
    with pytest.raises(ToolkitError) as info:
        lookup("LuaEntty", DOCS)
    assert "LuaEntity" in (info.value.hint or "")


def test_a_member_miss_suggests_members_of_that_owner() -> None:
    with pytest.raises(ToolkitError) as info:
        lookup("LuaEntity.get_inventry", DOCS)
    assert "member of LuaEntity" in info.value.message and "get_inventory" in (info.value.hint or "")


def test_a_bare_member_name_lists_the_owners_that_declare_it() -> None:
    assert "runtime method LuaControl.get_inventory" in text("get_inventory")
