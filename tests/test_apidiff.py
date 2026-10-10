from __future__ import annotations

from _lib.apidiff import diff_docs

from api_docs import prototype_new, prototype_old, runtime_new, runtime_old


def lines() -> list[str]:
    return diff_docs("1.0.0", "2.0.0", runtime_old(), runtime_new(), prototype_old(), prototype_new())


def test_added_removed_changed_and_moved_are_reported_one_per_line() -> None:
    out = lines()
    assert "REMOVED runtime class LuaGone" in out
    assert "ADDED runtime class LuaNew" in out
    assert "ADDED runtime method LuaEntity.explode: ()" in out
    assert (
        "CHANGED runtime method LuaControl.get_inventory: (inventory: defines.inventory) -> LuaInventory?"
        " -> (inventory: defines.inventory.kind) -> LuaInventory?"
    ) in out
    assert "ADDED prototype property AssemblingMachinePrototype.animation_random_start_frame: boolean (optional, default false)" in out
    assert "CHANGED prototype property CraftingMachinePrototype.energy_usage: Energy -> Energy | double" in out


def test_a_member_that_moved_to_a_parent_is_not_reported_as_removed() -> None:
    out = lines()
    assert "MOVED runtime method LuaMover.shift: now inherited from LuaControl" in out
    assert not any(line.startswith("REMOVED") and "LuaMover.shift" in line for line in out)
    assert "CHANGED runtime class LuaMover: (none) -> extends LuaControl" in out


def test_members_of_an_added_class_are_not_listed_separately() -> None:
    assert not any("LuaNew.fresh" in line for line in lines())


def test_output_is_grouped_by_status_and_starts_with_a_summary() -> None:
    out = lines()
    assert out[0].startswith("# API diff 1.0.0 -> 2.0.0:")
    statuses = [line.split()[0] for line in out if not line.startswith("#")]
    assert statuses == sorted(statuses, key=["ADDED", "REMOVED", "MOVED", "CHANGED"].index)


def test_identical_versions_produce_only_the_header() -> None:
    out = diff_docs("1", "1", runtime_old(), runtime_old(), prototype_old(), prototype_old())
    assert all(line.startswith("#") for line in out)
