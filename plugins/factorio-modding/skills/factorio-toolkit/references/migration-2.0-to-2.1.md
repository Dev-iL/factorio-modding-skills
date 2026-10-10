<!-- Adapted in part from Jaer985/factorio-modding-skill, references/factorio-2.1-breaking-changes.md (https://github.com/Jaer985/factorio-modding-skill), MIT licence, Copyright (c) 2026 gentleman-programming. -->
<!-- Every item was re-checked against the Factorio 2.1.21 API JSON and its data/changelog.txt; items that could not be re-checked were dropped. See THIRD_PARTY_NOTICES.md. -->
# Migrating a mod from Factorio 2.0 to 2.1

What breaks, and what silently changes meaning, when a 2.0 mod runs on 2.1. Checked on 2026-10-10 against the
runtime and prototype API JSON of 2.0.77 and 2.1.21 (`api.py diff 2.0.77 2.1.21`) and the `data/changelog.txt` of the
2.1.21 install (`changelog.py 2.0.77 2.1.21 --section Modding --section Scripting`). The changelog lists every 2.1
change under 2.1.7 (its first 2.1 entry) unless a later version is given in the "Since" column. 2.1 is the experimental
branch: later 2.1 releases may add rows, so re-run both commands for the target version before trusting this page.

## Declare the new version

- `info.json` `factorio_version` takes one major version, so a mod written for `"2.0"` must say `"2.1"` to load on 2.1.
  A mod cannot declare both (Mod structure page, [lua-api.factorio.com](https://lua-api.factorio.com/2.1.21/auxiliary/mod-structure.html)).
  Keeping one code base for both versions therefore means two releases with different `info.json` files.
- New in `info.json`: the `+` dependency prefix (optional but recommended, enabled by default; 2.1.7) and
  `migrates_from` (lets a mod take over the storage, script inventories, GUI elements and render objects of a removed
  mod; 2.1.18).

## Data stage (prototypes)

| 2.0 | 2.1 | Since |
|---|---|---|
| `RecipePrototype.category`, `additional_categories` | `categories` (array, default `{"crafting"}`) | 2.1.7 |
| compound recipe categories `basic-crafting`, `recycling-or-hand-crafting`, `chemistry-or-cryogenics`, `pressing`, `crafting-with-fluid-or-metallurgy`, `metallurgy-or-assembling`, `organic-or-hand-crafting`, `organic-or-assembling`, `organic-or-chemistry`, `electronics-or-assembling`, `electronics`, `electronics-with-fluid`, `cryogenics-or-assembling` | removed; list several categories on the recipe or machine instead. `hand-crafting` is new | 2.1.7 |
| `recycling` recipe category, defined in base | defined by the recycler mod (`data/recycler`) | 2.1.7 |
| product `probability` (`ItemProductPrototype`, `FluidProductPrototype`) | `independent_probability` on `ProductPrototypeBase`; `shared_probability` is new | 2.1.7 |
| `RecipePrototype.result_is_always_fresh`, `reset_freshness_on_craft` | `ItemProductPrototype.always_fresh`, `reset_freshness_on_craft` | 2.1.7 |
| `RecipePrototype.always_show_products`, `show_amount_in_title` | removed | 2.1.7 |
| `ItemProductPrototype.show_details_in_recipe_tooltip` (and fluid) | `ProductPrototypeBase.show_details_in_recipe_tooltip` | 2.1.7 |
| `ItemPrototype.fuel_category` | `fuel_categories` (array) | 2.1.20 |
| `VehiclePrototype.braking_power`, `friction` | `braking_force`, `friction_force` | 2.1.7 |
| `CraftingMachinePrototype.forced_symmetry` | `use_mirroring` | 2.1.7 |
| `AssemblingMachinePrototype.enable_logistic_control_behavior` | entity flag `"no-logistic-connection"` | 2.1.7 |
| `AsteroidPrototype.mass` | `damage_per_hp` | 2.1.7 |
| `DeconstructionItemPrototype.tile_filter_count`, `entity_filter_count` | removed (filter counts are dynamic) | 2.1.7 |
| `EntityPrototype.build_base_evolution_requirement` | removed | 2.1.7 |
| `EntityWithHealthPrototype.loot` is an array of `LootItem` | array of `ItemProductPrototype` | 2.1.7 |
| `MineEntityTechnologyTrigger.entity` | `entities` (array) | 2.1.7 |
| `AmbientSound.planet` | `planets` | 2.1.7 |
| `CargoLandingPadPrototype` and `LogisticContainerPrototype`: `robot_animation` / `animation`, `landing_location_offset`, `robot_opened_duration` / `opened_duration`, `robot_animation_sound` / `animation_sound` | grouped in `robot_door` | 2.1.7 |
| `GeneratorPrototype.horizontal_animation`, `vertical_animation`, `horizontal_frozen_patch`, `vertical_frozen_patch` | `pictures` | 2.1.7 |
| `MiningDrillPrototype.base_picture`, `base_render_layer` | `working_visualisations` | 2.1.7 |
| `PumpPrototype.fluid_wagon_connector_graphics`, `fluid_wagon_connector_alignment_tolerance` | `wagon_connection_graphics` and related new properties | 2.1.7 |
| `SpacePlatformHubPrototype.surface_render_parameters` (Space Age) | `SpaceLocationPrototype.platform_surface_render_parameters` | 2.1.7 |
| `ContainerPrototype.circuit_connector` is one definition | an array; `direction_count` is new (`ProxyContainerPrototype` follows in 2.1.21) | 2.1.7, 2.1.21 |
| circuit connector layer set on the entity: `LoaderPrototype.circuit_connector_layer`, `RailSignalPictureSet.circuit_connector_render_layer`, `CraftingMachineGraphicsSet` and `MiningDrillGraphicsSet` `circuit_connector_layer` / `circuit_connector_secondary_draw_order` | `CircuitConnectorSprites.render_layer`, `secondary_draw_order` | 2.1.15 |
| `UtilityConstants.max_fluid_flow`, `MapSettings.steering`, `PollutionSettings.max_pollution_to_restore_trees` | removed (steering moved to `UnitPrototype`, `SpiderUnitPrototype`) | 2.1.7, 2.1.18 |
| `FluidBox.hide_connection_info` | `PipeConnectionDefinition.hide_connection_info` | 2.1.7 |
| `[space-age]` recipes `molten-iron`, `molten-copper` | `iron-ore-melting`, `copper-ore-melting` | 2.1.7 |

Also from the 2.1.7 entry: science packs are plain items, and `TechnologyPrototype` and `LabPrototype` accept any
item as a research ingredient, so code that tests `type == "tool"` to find science packs misses them.

`assembler2pipepictures` and `assembler3pipepictures` are fields of the table in
`data/base/prototypes/entity/assembler-pictures.lua` (line 104 in 2.1.21), not functions. The base game reaches them with
`require("prototypes.entity.assembler-pictures").assembler2pipepictures` (`entities.lua`, line 3279); from another mod
the path needs the `__base__/` prefix: `require("__base__/prototypes/entity/assembler-pictures")`. The 2.0 form was
reported by Jaer985's notes and not checked here.

## Runtime API (control stage)

| 2.0 | 2.1 | Since |
|---|---|---|
| `LuaEntity.fluidbox` and the class `LuaFluidBox` | removed; use `LuaEntity` methods such as `get_fluid`, `set_fluid`, `add_fluid`, `clear_fluid(s)`, `get_fluid_capacity`, `get_fluid_filter` (all take a `FluidStorageIndex`) | 2.1.7 |
| `LuaEntity.neighbours` | `fluidbox_neighbours`, `underground_belt_neighbour`, `wall_neighbours`, `cliff_neighbours`, `neighbour_connectable_connections`, plus the existing `belt_neighbours`, `heat_neighbours` | 2.1.7 |
| `LuaEntity.pump_rail_target` | `pump_input_rail_targets`, `pump_output_rail_targets` | 2.1.7 |
| writing `LuaEntity.active`, `LuaEntity.minable` (reads remain) | write `disabled_by_script`, `minable_flag` | 2.1.7 |
| `LuaRecipe.category`, `additional_categories`; same on `LuaRecipePrototype` | `categories` (array) | 2.1.7 |
| `LuaRecipePrototype.always_show_products`, `show_amount_in_title`, `result_is_always_fresh`, `reset_freshness_on_craft` | removed; `is_parameter` is replaced by `LuaPrototypeBase.parameter` | 2.1.7 |
| `LuaGroup` | `LuaItemGroup`, `LuaItemSubGroup` (`prototypes.item_group`, `prototypes.item_subgroup`, `LuaRecipe.group` and the filters change type) | 2.1.15 |
| `LuaItemPrototype.fuel_category` | `fuel_categories` | 2.1.20 |
| `LuaItemPrototype.inventory_size` | `get_inventory_size(quality)` | 2.1.7 |
| `LuaEntityPrototype.fluid_usage_per_tick`, `max_power_output`, `pumping_speed` | `get_fluid_usage_per_tick()`, `get_max_power_output()`, `get_pumping_speed()` | 2.1.7 |
| `LuaFluidBoxPrototype.volume` | `get_volume(quality)` | 2.1.7 |
| `LuaEntityPrototype.building_grid_bit_shift` | `build_grid_size` | 2.1.21 |
| `LuaEntityPrototype.fixed_recipe` returns a string | returns a `LuaRecipePrototype` | 2.1.7 |
| `LuaEntityPrototype.build_base_evolution_requirement` | removed | 2.1.7 |
| `LuaItemPrototype.tile_filter_slots`, `entity_filter_slots` | removed | 2.1.7 |
| `LuaGameScript.create_profiler()` | `LuaHelpers.create_profiler()` | 2.1.7 |
| `LuaPlayer.pipette_entity()` | `pipette()` | 2.1.7 |
| `LuaPlayer.spectator` | removed (it did nothing) | 2.1.20 |
| `LuaRecord.is_blueprint_preview` | `is_preview` | 2.1.7 |
| `LuaEntity.mining_progress` | declared on `LuaControl` and now writable (still reachable as `entity.mining_progress`) | 2.1.7 |
| `LuaAssemblingMachineControlBehavior.include_fuel`, `LuaFurnaceControlBehavior.include_fuel` | `read_fuel` | 2.1.7 |
| `circuit_exclusive_mode_of_operation` on the logistic container and cargo landing pad control behaviours | removed; use `set_requests` and `read_contents` | 2.1.7 |
| `LuaDisplayPanelControlBehavior.messages`, `get_message`, `set_message` | `records`, `get_record`, `set_record`, `add_record`, `remove_record`, `move_record` | 2.1.7 |
| `defines.inventory.assembling_machine_input`, `furnace_source`, `rocket_silo_input` | `crafter_input` | 2.1.7 |
| `defines.inventory.assembling_machine_output`, `furnace_result`, `rocket_silo_output` | `crafter_output` | 2.1.7 |
| `defines.inventory.assembling_machine_modules`, `furnace_modules`, `rocket_silo_modules` | `crafter_modules` | 2.1.7 |
| `defines.inventory.assembling_machine_trash`, `furnace_trash` | `crafter_trash` | 2.1.7 |
| `defines.control_behavior.type.storage_tank` | `single_fluid_box` | 2.1.7 |
| `defines.default_icon_size` | `defines.constant.default_icon_size` | 2.1.7 |
| `defines.relative_gui_type.storage_tank_gui`, `defines.input_action.translate_string` | removed | 2.1.7 |
| `LuaSimulation.get_widget_position()` took data strings and 0-based positions | no data arguments, 1-based positions | 2.1.15 |
| boiler fluid filters adjustable at runtime | no longer adjustable | 2.1.21 |

The class `LuaStorageTankControlBehavior` was removed in the same release that added `LuaSingleFluidBoxControlBehavior`
(`api.py lookup LuaSingleFluidBoxControlBehavior`); the changelog does not state the mapping, so check a storage-tank mod's code by hand.

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
  draw order. A connector can now draw behind or above entities it did not before (2.1.15). Check by looking at it.
- Reactors no longer connect to neighbours merely because their edges touch (`ReactorPrototype.neighbour_connectable`).
- `LuaEntity.display_panel_text` no longer accepts a `LocalisedString`; `inserter_spoil_priority` returns dashes where it returned underscores.

## Already in 2.0.77: adopt the new name now

These replacements exist in both versions (checked in both JSON files), so a mod can switch to them without a version
split: `defines.inventory.crafter_input`, `crafter_output`, `crafter_modules`, `crafter_trash`;
`LuaHelpers.create_profiler`; `LuaPlayer.pipette`; `LuaRecord.is_preview`; `LuaPrototypeBase.parameter`.

## Finding the affected code in a mod

```
grep -rnE "\.category\b|additional_categories|probability|fuel_category|forced_symmetry|braking_power|\bfriction\b" --include=*.lua .
grep -rnE "fluidbox|remove_fluid|set_fluid|LuaGroup|prototypes\.(item_)?(sub)?group|create_profiler|pipette_entity|assembling_machine_(input|output|modules|trash)|furnace_(source|result|modules|trash)|rocket_silo_(input|output|modules)|default_icon_size|\.active *=|\.minable *=" --include=*.lua .
grep -rnE "circuit_connector_(layer|render_layer|secondary_draw_order)|assembler[23]pipepictures" --include=*.lua .
```

`api.py diff` lists the exact members and types; read the `REMOVED`, `CHANGED` and `MOVED` lines against the mod's own
prototype and class names. A hit is not proof of a bug (`category` also names unrelated fields such as a technology's
`research_category` or a recipe-category prototype), so confirm each in context.
