<!-- Adapted in part from Jaer985/factorio-modding-skill, references/factorio-2.1-breaking-changes.md (https://github.com/Jaer985/factorio-modding-skill), MIT licence, Copyright (c) 2026 gentleman-programming. -->
<!-- Every item was re-checked against the Factorio 2.1.21 API JSON and its data/changelog.txt; items that could not be re-checked were dropped. See THIRD_PARTY_NOTICES.md. -->
# Migration from Factorio 2.0 to 2.1

The complete list of changes comes from `api.py diff 2.0.77 2.1.21` and
`changelog.py 2.0.77 2.1.21 --section Modding --section Scripting`; 2.1 is the experimental branch, so run both for the target
version too. This page keeps only what those commands cannot explain: names that survive with a new meaning, and the
`info.json` change. It was checked on 2026-10-10 against the API JSON of 2.0.77 and 2.1.21 and the 2.1.21 install's
`data/changelog.txt`. A change without a version entered the changelog in 2.1.7, the first 2.1 entry.

## Declare the new version

- `info.json` `factorio_version` takes one major version: a mod written for `"2.0"` must say `"2.1"` to load on 2.1, and
  cannot declare both (Mod structure page, [lua-api.factorio.com](https://lua-api.factorio.com/2.1.21/auxiliary/mod-structure.html)).
  One code base for both versions means two releases with different `info.json` files.
- New in `info.json`: the `+` dependency prefix (recommended dependency) and `migrates_from`, which lets a mod take over the
  storage and GUI elements of a removed mod (2.1.18).

## Names that survive with a new meaning

These do not fail on load or on a name lookup; they run and do something else. Search for them by hand.

- `LuaEntity.remove_fluid`: the 2.0 method took a table `{name, amount, ...}` and returned the amount removed. In 2.1 the
  same name takes `(index, amount)` and returns a `Fluid`. The old behaviour is `extract_fluid`. `set_fluid` now requires its second
  argument and returns a `FluidAmount` instead of a `Fluid`.
- Science packs are plain items, and `TechnologyPrototype` and `LabPrototype` accept any item as a research ingredient. Code that
  tests `type == "tool"` to find science packs misses them (2.1.7 changelog).
- Quality: effect values in prototype definitions were divided by 10, and `next_probability` was multiplied by 10,
  so a 100% effect now guarantees a quality step. Module effects resolve to 0.01%. Values copied from a 2.0 mod keep
  their number and change their effect (2.1.7 changelog).
- `SelectionModeFlags` `"blueprint"`, `"deconstruct"`, `"cancel-deconstruct"`, `"upgrade"`, `"cancel-upgrade"`, `"downgrade"` no longer
  imply `"any-entity"` or `"any-tile"`, so a selection tool that relied on that selects less.
- Circuit connectors on inserters, train stops, asteroid collectors, and rocket silos no longer have their old default render layer
  or draw order, so a connector can draw behind or above entities it did not before (2.1.15). Check by looking at it.
- Reactors no longer connect to neighbours merely because their edges touch (`ReactorPrototype.neighbour_connectable`).
- `LuaEntity.display_panel_text` no longer accepts a `LocalisedString`. `inserter_spoil_priority` returns dashes where it
  returned underscores.

## Removal with no replacement

The class `LuaStorageTankControlBehavior` is removed, and the changelog gives no mapping. Check any code that uses it by hand.

## Replacements already in 2.0.77

These replacements exist in both versions (checked in both JSON files), so a mod can switch to the new name without a version split:
`defines.inventory.crafter_input`, `crafter_output`, `crafter_modules`, and `crafter_trash`; `LuaHelpers.create_profiler`;
`LuaPlayer.pipette`; `LuaRecord.is_preview`; `LuaPrototypeBase.parameter`.
