# Graveyard: approaches that fail

Things an agent tends to try and that do not work. Each entry says what fails, the evidence (checked in this project on
2026-10-10 against Factorio 2.1.21 and the live services unless another source is named), and what to do instead.
The idea of keeping such a list comes from TalShar783/Factorio-Modding-Skill; the entries are this project's own.

## 1. Reading a method's `parameters` array in the order the JSON gives

`runtime-api.json` sorts every list alphabetically, and says so: the order on the website is each member's `order` field
(JSON docs, https://lua-api.factorio.com/latest/auxiliary/json-docs-runtime.html). The list for `script.on_nth_tick` reads
`handler, tick`, but the declared order is `tick, handler`; `LuaBootstrap.register_metatable` reads `metatable, name` and is
declared `name, metatable`. A positional call written from the alphabetical list passes each argument in the wrong
slot. (Methods that take a single table, such as `LuaSurface.can_fast_replace`, name their arguments and are not
affected.) The same holds for event data and prototype properties. Use `api.py lookup`, which prints declared order, or
sort by `order` yourself.

## 2. Assuming a name that still exists behaves as before

An API diff that only shows removed names misses a method whose signature changed under the same name. In 2.1,
`LuaEntity.remove_fluid` changed from `{name, amount, ...}` returning the amount removed to `(index, amount)` returning a
`Fluid`; the old behaviour is now `extract_fluid` (2.1.7 changelog; `api.py diff` shows it as `CHANGED`). Read the
`CHANGED` lines of the diff as well as `REMOVED`, and see [migration-2.0-to-2.1.md](migration-2.0-to-2.1.md).

## 3. Writing 2.x code from memory of 1.1 or 2.0

The model's recall of the API is older than the game. Known traps: `global` became `storage` in 2.0 (Storage page);
`hr_version` was removed from graphics definitions in 2.0 ("The graphics are now always considered to be in high
definition", `data/changelog.txt` under 2.0.7); recipe `category` became `categories` in 2.1. Look the member up with
`api.py lookup` for the target version before using it, and run `check_data.py` after every prototype edit.

## 4. Treating a passing data-stage check as proof that graphics load

`--dump-data` does not read sprite files, so a wrong `filename` or sprite size passes it
(see [in-game-testing.md](in-game-testing.md)). Check the file paths and dimensions separately, and prove the graphics
by loading the mod in the game.

## 5. Tailing the game log or waiting on a game window

An agent command that never returns blocks the whole session. The game is started with a timeout and without a window,
and its log is read once, after the process has exited (`scan_log.py`). The game rotates its log on each start unless
`--no-log-rotation` is given (Command line parameters page), so read the log of the run you just made, not an earlier one.

## 6. Letting a test run use the player's `mods` folder

The player's own mods would load into the test, and the game may rewrite `mod-list.json` in whichever mods folder it is
pointed at. Tests run with `--mod-directory` pointing at a throwaway folder
(see [install-paths-and-logs.md](install-paths-and-logs.md)).

## 7. Mod portal calls that look right and quietly are not

Each of these was observed on live responses from `mods.factorio.com`:

- `GET /api/mods?sort=downloads_count` is accepted and ignored: the result is ordered by name, descending. Only `name`,
  `created_at` and `updated_at` sort. Rank by download count client-side, from the `downloads_count` field.
- `pagination.links.next` drops the `version` filter. Request page *n* by number with the same parameters.
- With a `version` filter, `latest_release` is the newest release for that Factorio version, not the newest overall, and
  a mod appears if any of its releases matches (a mod whose newest release is 2.1 is listed under `version=2.0` if it also
  has a 2.0 release). `2.0.77` is accepted and treated as `2.0`.
- `POST /api/search` without `username` and `token` in the JSON body answers `Missing data for required field.`. Search
  has no anonymous mode; listing and `/api/mods/<name>/full` do.
- Download links (`/download/<name>/<id>`) answer 403 without `?username=&token=`, and 403 with a wrong token, as an HTML page.
  A valid request answers 302 to a CDN, so the client must follow redirects.
- Search results hold `latest_release` as an id string; list results hold it as an object; `namelist` results hold
  `releases` and no `latest_release`. Do not index into one shape with another's keys.

`portal.py` handles each of these.

## 8. Generating sprites with an AI image model

An image model cannot produce the same object from four or eight directions with a consistent shadow, scale and
animation frames, which a Factorio sprite sheet needs. Jaer985/factorio-modding-skill records that its author tried AI
icon generation and discarded it (`references/dmr-icon-assets-generation.md`, MIT). This project has ruled AI image
generation out; use base-game sprites with a tint, Blender renders of a model built for the task, or art the user
supplies (see [graphics-ladder.md](graphics-ladder.md)).

## 9. Hard-coding the pixel rectangle of a base-game sprite

Jaer985/factorio-modding-skill reports (MIT, `references/factorio-2.1-breaking-changes.md`; not reproduced here) that
copying an assembling machine's sprite rectangle from a clean `data.raw` dump loaded fine on a clean game and failed when
an overhaul mod replaced or resized the same sheet. Reference the base-game graphics by path with a tint and let the
engine read their size, or ship your own sprite whose size you control.

## 10. Copying another mod's graphics or code into yours

Not a technical failure but a licensing one: a mod's files belong to its author, and a missing or restrictive licence gives
you no right to reuse them. See [licensing.md](licensing.md) for what is allowed.
