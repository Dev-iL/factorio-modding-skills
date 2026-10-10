# Rapid iteration without restarting the game

Restarting Factorio takes 20-60 s with Space Age. These techniques shorten the loop for some changes. Each is marked
with how well it is established. "Confirmed by the user" means the repository owner reported it working; "verified here"
means it was run headless against Factorio 2.1.21 (build 87673) while building this plugin; "unconfirmed" means it is
believed from documentation or reasoning and has not been tried. Treat unconfirmed items as hypotheses.

## What needs a restart

Prototype and graphics changes need a full restart: the data stage runs once at startup and builds the prototype
list for the whole session (see [data-vs-control-stage.md](data-vs-control-stage.md)). That claim is the user's and matches how
`--dump-data` behaves (it runs the data stage and exits); it has not been tried against `game.reload_mods()` here.

## Edit a save in place, then reload the save

A save is a zip file. Besides the map data it contains the scenario's `control.lua` (run as `__level__`) and a
`locale/` folder. Both can be edited after unzipping and take effect when the save is loaded again.

| Component in the save | Status |
|---|---|
| `locale/<lang>/*.cfg` | Confirmed by the user: unzip `saves\example_save.zip`, edit `locale\he\freeplay.cfg`, reload the save. |
| Scenario `control.lua` (`__level__`) | Verified here: a log line appended to an unzipped save's `control.lua` ran when the folder was loaded with `--benchmark`, and again after re-zipping it. This reloads the game process each time, so it shows the edit is picked up, not that a running game needs no restart. |
| A mod's own `control.lua` or locale | Unconfirmed. Mods are read from the mods folder, not from the save; whether the running game re-reads a changed mod file on "load save" has not been tried. |
| Prototypes, graphics, `settings.lua` | Need a restart (see above). |

Use the headless runner instead when the goal is a pass/fail result rather than looking at the game: `run_tests.py`
starts in about 5 s without Space Age (see [in-game-testing.md](in-game-testing.md)).

## `game.reload_mods()` for the control stage

`LuaGameScript.reload_mods()` "forces a reload of all mods" and "will act like saving and loading from the mod(s)
perspective"; it does nothing in multiplayer and disables the replay if one is enabled (runtime API, `LuaGameScript.reload_mods`,
2.1.21; added in the changelog entry "Added LuaGameScript::reload_mods()"). Call it from the console in a single-player
game after editing `control.lua`. Status: unconfirmed here. Because it behaves like a save and load, expect `on_load`
to run rather than `on_init`, and expect `storage` to be kept.

## Which technique to use

1. Changing data stage (prototypes, graphics, settings): run `check_data.py`, then restart the game.
2. Changing control-stage logic you want to see in the game: try `game.reload_mods()`; fall back to a restart.
3. Changing locale: edit the save's `locale/` and reload the save.
4. Checking logic without looking at the game: `run_tests.py`.
