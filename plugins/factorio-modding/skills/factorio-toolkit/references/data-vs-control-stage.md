# Data stage and control stage

Where logic belongs. The stage order, the three files per stage, load order, and the `storage` table are explained on the official
2.1.21 pages: [Data lifecycle](https://lua-api.factorio.com/2.1.21/auxiliary/data-lifecycle.html),
[Storage](https://lua-api.factorio.com/2.1.21/auxiliary/storage.html), and [Mod structure](https://lua-api.factorio.com/2.1.21/auxiliary/mod-structure.html).
Read them for those facts. One consequence they leave an agent to trip over: an ordinary Lua variable in `control.lua` is lost on
load and differs between a joining client and the host, so anything that must survive a save or agree across players goes into `storage`.

## When to prefer the data stage

Choose the data stage whenever the result can be expressed as a prototype property, a recipe, a technology effect, a tint, or a
locale string. Write `control.lua` only for behaviour that must react to something happening in a game. A data-stage mod costs
nothing per tick, holds no state that can desync, and is validated in seconds by `check_data.py` (`factorio --dump-data`, see
[in-game-testing.md](in-game-testing.md)). A control-stage mistake only shows when its code path runs, so it needs a map and a test.

The following table maps what you want to the stage that provides it:

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
