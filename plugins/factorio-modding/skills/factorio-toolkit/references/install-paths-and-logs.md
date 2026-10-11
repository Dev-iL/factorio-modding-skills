# Where Factorio keeps its files: portable and system installs

This plugin supports standalone Windows installs only: the zip package (portable) and the standalone installer
(system). Steam, Linux, and macOS layouts differ and are not supported. All facts on this page were read from an install of
Factorio 2.1.21 and its `config-path.cfg`, whose own comments describe the two modes.

## Two layouts

The two layouts differ in where the game writes its data:

| Item | Portable (zip package) | System (installer) |
|---|---|---|
| `config-path.cfg` | `use-system-read-write-data-directories=false` | `use-system-read-write-data-directories=true` |
| Read data (`data\`) | `<install>\data` | `<install>\data` |
| Write data (mods, saves, log, script-output, `player-data.json`) | `<install>` itself | `%APPDATA%\Factorio` |
| Config file | `<install>\config\config.ini` | `%APPDATA%\Factorio\config\config.ini` |

`config-path.cfg` sits in the install root. Its `config-path=__PATH__executable__/../../config` line says where
`config.ini` is, and the `[path]` section of that file (`read-data`, `write-data`) is what the game actually uses. After
`config.ini` exists, the `use-system-...` setting no longer changes anything, so read `config.ini` first.
`locate_game.py` does this and prints the resolved paths; do not guess them.

## Log location

The log is `<write-data>\factorio-current.log`: next to the executable's install root on a portable install, and
`%APPDATA%\Factorio\factorio-current.log` on a system install. The previous launch's log is renamed
`factorio-previous.log` at the next start (pass `--no-log-rotation` to prevent that). Each launch therefore overwrites the
log, so scan it after the launch you care about, before starting another.

`--dump-data` writes `script-output\data-raw-dump.json` under write-data. It exits with code 0 on success
and 1 when the data stage fails.

## Test runs and the user's install

`check_data.py` and `run_tests.py` never use the install's own write-data folder. They start the game with:

- `-c <temp>\config.ini`, whose `[path]` has `read-data` pointing at the install's `data` folder and `write-data` at a
  temp folder, so the log, saves, script output, and a fresh `player-data.json` all land in the temp folder;
- `--mod-directory <temp>\mods`, holding a directory junction to each mod under test and a generated `mod-list.json`.

The user's own mods and saves are not loaded and are never modified. Official DLC mods (the downloadable expansions) are enabled
only when the mod under test depends on them, which also makes data-stage checks faster: about 4 s without Space Age against 22 s with it.
