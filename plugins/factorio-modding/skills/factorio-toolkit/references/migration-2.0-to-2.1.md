<!-- Adapted in part from Jaer985/factorio-modding-skill, references/factorio-2.1-breaking-changes.md (https://github.com/Jaer985/factorio-modding-skill), MIT licence, Copyright (c) 2026 gentleman-programming. -->
<!-- Every item was re-checked against the Factorio 2.1.21 API JSON and its data/changelog.txt; items that could not be re-checked were dropped. See THIRD_PARTY_NOTICES.md. -->
# Migrating a mod from Factorio 2.0 to 2.1

The changes most likely to hit an ordinary mod, and the ones the API diff cannot explain (renames with a new shape,
names that survive with a new meaning). Checked on 2026-10-10 against the API JSON of 2.0.77 and 2.1.21 and the
2.1.21 install's `data/changelog.txt`. For the complete list run `api.py diff 2.0.77 2.1.21` and
`changelog.py 2.0.77 2.1.21 --section Modding --section Scripting`; 2.1 is the experimental branch, so run them for the target version too.
Unless a version is given, a change entered in 2.1.7, the first 2.1 entry in the changelog.

## Declare the new version

- `info.json` `factorio_version` takes one major version: a mod written for `"2.0"` must say `"2.1"` to load on 2.1, and
  cannot declare both (Mod structure page, [lua-api.factorio.com](https://lua-api.factorio.com/2.1.21/auxiliary/mod-structure.html)).
  One code base for both versions means two releases with different `info.json` files.
- New in `info.json`: the `+` dependency prefix (recommended dependency) and `migrates_from` (a mod takes over the storage and
  GUI elements of a removed mod; 2.1.18).

## Data stage (prototypes)

| 2.0 | 2.1 |
|---|---|
| `RecipePrototype.category`, `additional_categories` | `categories` (array, default `{"crafting"}`) |
| compound recipe categories such as `basic-crafting`, `chemistry-or-cryogenics`, `organic-or-assembling` | removed: list several categories on the recipe or machine. `hand-crafting` is new |
| `recycling` category defined in base | defined by the recycler mod (`data/recycler`) |
| product `probability` | `independent_probability` (`shared_probability` is new) |
| `RecipePrototype.result_is_always_fresh`, `reset_freshness_on_craft` | `ItemProductPrototype.always_fresh`, `reset_freshness_on_craft` |
| `ItemPrototype.fuel_category` (2.1.20) | `fuel_categories` (array) |
| `CraftingMachinePrototype.forced_symmetry` | `use_mirroring` |
| `VehiclePrototype.braking_power`, `friction` | `braking_force`, `friction_force` |
| `MineEntityTechnologyTrigger.entity` | `entities` (array) |
| `ContainerPrototype.circuit_connector` (one definition) | an array; `direction_count` is new (`ProxyContainerPrototype` follows in 2.1.21) |
| `circuit_connector_layer` and similar fields on the entity | `CircuitConnectorSprites.render_layer`, `secondary_draw_order` (2.1.15) |

Science packs are plain items and `TechnologyPrototype` and `LabPrototype` accept any item as a research ingredient, so code that
tests `type == "tool"` to find science packs misses them (2.1.7 changelog).

## Runtime API (control stage)

| 2.0 | 2.1 |
|---|---|
| `LuaEntity.fluidbox` and the class `LuaFluidBox` | removed; use `LuaEntity` methods such as `get_fluid`, `set_fluid`, `add_fluid`, `clear_fluid(s)`, `get_fluid_capacity`, `get_fluid_filter` (all take a `FluidStorageIndex`) |
| `LuaEntity.neighbours` | `fluidbox_neighbours`, `underground_belt_neighbour`, `wall_neighbours`, `cliff_neighbours`, `neighbour_connectable_connections` |
| writing `LuaEntity.active`, `LuaEntity.minable` | write `disabled_by_script`, `minable_flag` (reads remain) |
| `LuaRecipe.category`, `additional_categories` | `categories` (array) |
| `LuaGroup` (2.1.15) | `LuaItemGroup`, `LuaItemSubGroup`; `prototypes.item_group`, `item_subgroup`, `LuaRecipe.group` and the filters change type |
| `LuaItemPrototype.fuel_category` (2.1.20) | `fuel_categories` |
| `LuaItemPrototype.inventory_size` | `get_inventory_size(quality)` |
| `LuaEntityPrototype.fixed_recipe` returns a string | returns a `LuaRecipePrototype` |
| `LuaGameScript.create_profiler()` | `LuaHelpers.create_profiler()` |
| `LuaPlayer.pipette_entity()` | `pipette()` |
| `defines.inventory.assembling_machine_input`, `furnace_source`, `rocket_silo_input` | `crafter_input` (likewise `_output`, `_modules`, `_trash` -> `crafter_output`, `crafter_modules`, `crafter_trash`) |
| `defines.default_icon_size` | `defines.constant.default_icon_size` |
| `defines.control_behavior.type.storage_tank` | `single_fluid_box` (the class `LuaStorageTankControlBehavior` was removed in the same release; the changelog gives no mapping, so check such code by hand) |

## Names that survive with a new meaning

These do not fail on load or on a name lookup; they run and do something else. Search for them by hand.

- `LuaEntity.remove_fluid`: the 2.0 method took a table `{name, amount, ...}` and returned the amount removed. In 2.1 the
  same name takes `(index, amount)` and returns a `Fluid`. The old behaviour is `extract_fluid`. `set_fluid` now requires its second
  argument and returns a `FluidAmount` instead of a `Fluid`.
- Quality: effect values in prototype definitions were divided by 10, and `next_probability` was multiplied by 10,
  so a 100% effect now guarantees a quality step. Module effects resolve to 0.01%. Values copied from a 2.0 mod keep
  their number and change their effect (2.1.7 changelog).
- `SelectionModeFlags` `"blueprint"`, `"deconstruct"`, `"cancel-deconstruct"`, `"upgrade"`, `"cancel-upgrade"`, `"downgrade"` no longer
  imply `"any-entity"` or `"any-tile"`, so a selection tool that relied on that selects less.
- Circuit connectors on inserters, train stops, asteroid collectors and rocket silos no longer have their old default render layer or
  draw order; a connector can draw behind or above entities it did not before (2.1.15). Check by looking at it.
- Reactors no longer connect to neighbours merely because their edges touch (`ReactorPrototype.neighbour_connectable`).
- `LuaEntity.display_panel_text` no longer accepts a `LocalisedString`; `inserter_spoil_priority` returns dashes where it returned underscores.

## Already in 2.0.77: adopt the new name now

These replacements exist in both versions (checked in both JSON files), so a mod can switch without a version split:
`defines.inventory.crafter_input`, `crafter_output`, `crafter_modules`, `crafter_trash`; `LuaHelpers.create_profiler`;
`LuaPlayer.pipette`; `LuaRecord.is_preview`; `LuaPrototypeBase.parameter`.

## Finding the affected code in a mod

```
grep -rnE "\.category\b|additional_categories|probability|fuel_category|forced_symmetry|braking_power|\bfriction\b" --include=*.lua .
grep -rnE "fluidbox|remove_fluid|set_fluid|LuaGroup|create_profiler|pipette_entity|assembling_machine_(input|output|modules|trash)|furnace_(source|result|modules|trash)|default_icon_size|\.active *=|\.minable *=" --include=*.lua .
```

A hit is not proof of a bug (`category` also names unrelated fields such as a technology's `research_category`), so confirm each
in context against the `REMOVED`, `CHANGED` and `MOVED` lines of `api.py diff`.
