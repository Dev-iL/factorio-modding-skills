# Data stage vs control stage

A Factorio mod runs its code at two different times, with different tools available at each. Writing runtime code
(`game`, `script`, `LuaEntity`) in a data-stage file, or trying to edit a prototype from a control-stage file, is
the most common structural mistake agents make. This page says what runs when and which stage to choose.

Sources, named where they are used: the official [Data lifecycle](https://lua-api.factorio.com/2.1.21/auxiliary/data-lifecycle.html),
[Storage](https://lua-api.factorio.com/2.1.21/auxiliary/storage.html) and
[Mod structure](https://lua-api.factorio.com/2.1.21/auxiliary/mod-structure.html) pages (read for 2.1.21), and the wiki's
[Command line parameters](https://wiki.factorio.com/Command_line_parameters) page.

## Terms

- **Prototype**: the definition of a game thing (an item, recipe, entity, technology, tile ...) as a Lua table with a
  `type` and a `name`. The prototype API docs list every type and its properties.
- **`data.raw`**: the Lua table in which all prototypes collect during the data stage.
- **Stage**: one of the three points at which the game runs mod code.
- **`storage`**: the per-mod table that the game saves with a map (named `global` before 2.0, per the Storage page).

## The three stages

| Stage | Files that run (in this order, for every mod) | Available | Ends |
|---|---|---|---|
| Settings | `settings.lua`, `settings-updates.lua`, `settings-final-fixes.lua` | `data` (for setting prototypes), `mods` | the player's choices are read from `mod-settings.dat` |
| Data (also called prototype stage) | `data.lua`, `data-updates.lua`, `data-final-fixes.lua` | `data` (all prototypes), `mods`, `settings` (startup settings) | all prototypes are built; the game reaches the main menu |
| Control (runtime) | `control.lua`, then the event handlers it registers | the runtime API: `game`, `script`, `storage`, LuaObjects | when the save is closed |

Source: Data lifecycle. The rules that follow come from the same page unless another source is named.

## What that means in practice

**Data stage**
- No game exists yet: the runtime API (`game`, `script`, `LuaEntity` and so on) is not available.
- All mods share one Lua state per stage, and the game discards it when the stage ends. A variable or function defined
  in `data.lua` does not exist in `control.lua`, and any property the game does not recognise is dropped. Prototypes are
  the only data that survives into the control stage.
- Each stage makes three passes over all mods: first every mod's `data.lua`, then every mod's `data-updates.lua`, then
  every mod's `data-final-fixes.lua`. Because of that, a mod can adjust someone else's prototype without being loaded after it.
  Put your own prototypes in `data.lua`; put edits to prototypes owned by the base game or another mod in
  `data-updates.lua`; keep `data-final-fixes.lua` for corrections that must win over every other mod, since nothing runs after it.
- Mods load in order of dependency-chain depth (shallower first), then by name. When your code needs another mod's
  prototypes to exist already, list that mod in `info.json` `dependencies` (a `?` prefix makes it optional; Mod structure page).
- `mods` maps every enabled mod's name to its version, which is how data-stage code adapts to other mods.

**Control stage**
- `control.lua` runs on every save creation and every save load. Prototypes can no longer be changed and `data` no longer exists.
- `on_init` runs when the mod is new to the save, `on_load` when it was already part of it, and `on_configuration_changed`
  (for every mod at once) when the game or any mod changed version, mods were added or removed, a startup setting differs,
  or prototypes were added or removed. A client joining a multiplayer game runs only `control.lua` and `on_load`, so
  those two must rebuild exactly the state the other players already have. Writing to `storage` inside `on_load` is an
  error (Data lifecycle and Storage pages).
- State that must survive a save and load goes into `storage`. It accepts strings, numbers, booleans, nil, tables and
  LuaObject references; functions are an error (Storage page). Anything kept in an ordinary variable is lost on load
  and differs between a joining client and the host.

## When to prefer the data stage

Choose the data stage whenever the result can be expressed as a prototype property, a recipe, a technology effect, a
tint or a locale string, and write `control.lua` only for behaviour that has to react to something happening in a game.

- A data-stage mod costs nothing per tick and holds no state that can desync.
- The game validates every prototype while loading. `factorio --dump-data` loads all mods' prototypes, writes `data.raw`
  as JSON to the script-output folder and exits (Command line parameters page), so a data-stage mistake shows up
  within seconds without a map. The toolkit's `check_data.py` wraps this.
- A control-stage mistake only shows up when the code path runs, so it needs a map and a test that triggers the path
  (see [in-game-testing.md](in-game-testing.md)).

| You want | Stage |
|---|---|
| New or changed items, recipes, entities, technologies, tints, sounds | data |
| A stat change on an existing entity (speed, stack size, energy use) | data (`data-updates.lua`) |
| A new setting the player picks at startup | settings, read back in the data stage through `settings.startup` |
| Text shown in the game | `locale/<language>/*.cfg` files, no code |
| Reacting to a build, a death, a research, a tick; GUI; per-save state | control |
| Changing the behaviour of one entity depending on where it is or who owns it | control |

When a feature needs both (a data-stage entity plus control-stage logic that moves items), build the prototype first and
get `check_data.py` passing before writing any runtime code.

## Which restart each change needs

Prototype and graphics changes need a game restart because the data stage runs once at startup; see
[rapid-iteration.md](rapid-iteration.md) for what can be reloaded without one.
