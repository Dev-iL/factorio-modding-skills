# Data stage vs control stage

Where logic belongs, and the stage rules that cost agents runs. Stage order, the three files per stage and the
`storage` table are explained on the official pages for 2.1.21: [Data lifecycle](https://lua-api.factorio.com/2.1.21/auxiliary/data-lifecycle.html),
[Storage](https://lua-api.factorio.com/2.1.21/auxiliary/storage.html) and [Mod structure](https://lua-api.factorio.com/2.1.21/auxiliary/mod-structure.html);
the rules below come from those pages unless another source is named.

## Rules that bite

**Data stage** (`data.lua`, `data-updates.lua`, `data-final-fixes.lua`)
- No game exists yet: `game`, `script` and `LuaEntity` are not available. Code written for them here fails at load.
- All mods share one Lua state per stage and it is discarded when the stage ends. A variable defined in `data.lua` does not
  exist in `control.lua`; prototypes are the only data that survives, and a property the game does not recognise is dropped.
- Each stage makes three passes over all mods: every `data.lua`, then every `data-updates.lua`, then every `data-final-fixes.lua`.
  Put your own prototypes in `data.lua`, edits to prototypes owned by the base game or another mod in `data-updates.lua`, and
  corrections that must win over every other mod in `data-final-fixes.lua`.
- Mods load by dependency-chain depth (shallower first), then by name. If your code needs another mod's prototypes to exist,
  list that mod in `info.json` `dependencies`.
- `mods` maps each enabled mod name to its version, which is how data-stage code adapts to other mods.

**Control stage** (`control.lua` and the handlers it registers)
- `control.lua` runs on every save creation and every save load; prototypes can no longer be changed.
- `on_init` runs when the mod is new to the save, `on_load` when it was already part of it, `on_configuration_changed` when the
  game or any mod changed version, mods were added or removed, a startup setting differs, or prototypes changed. A client joining
  a multiplayer game runs only `control.lua` and `on_load`, so those must rebuild exactly the state the other players have.
  Writing to `storage` inside `on_load` is an error.
- State that must survive a save goes into `storage` (strings, numbers, booleans, nil, tables, LuaObject references; functions are an
  error). An ordinary variable is lost on load and differs between a joining client and the host.

## When to prefer the data stage

Choose the data stage whenever the result can be expressed as a prototype property, a recipe, a technology effect, a tint or a
locale string; write `control.lua` only for behaviour that must react to something happening in a game. A data-stage mod costs
nothing per tick, holds no state that can desync, and is validated in seconds by `check_data.py` (`factorio --dump-data`, see
[in-game-testing.md](in-game-testing.md)); a control-stage mistake only shows when its code path runs, so it needs a map and a test.

| You want | Stage |
|---|---|
| New or changed items, recipes, entities, technologies, tints, sounds | data |
| A stat change on an existing entity (speed, stack size, energy use) | data (`data-updates.lua`) |
| A setting the player picks at startup | settings, read back in the data stage through `settings.startup` |
| Text shown in the game | `locale/<language>/*.cfg`, no code |
| Reacting to a build, a death, a research, a tick; GUI; per-save state | control |
| One entity behaving differently depending on where it is or who owns it | control |

When a feature needs both, build the prototype first and get `check_data.py` passing before writing runtime code. Prototype and
graphics changes need a game restart (see [rapid-iteration.md](rapid-iteration.md)).
