# Graveyard: approaches that fail

Things an agent tends to try and that do not work. Each entry says what fails, the evidence (checked in this project on
2026-10-10 against Factorio 2.1.21 and the live services unless another source is named), and what to do instead.

## Alphabetical parameter order in the API JSON

`runtime-api.json` sorts every list alphabetically, and says so: the order on the website is each member's `order` field
([JSON docs](https://lua-api.factorio.com/latest/auxiliary/json-docs-runtime.html)). The list for `script.on_nth_tick` reads
`handler, tick`, but the declared order is `tick, handler`. `LuaBootstrap.register_metatable` reads `metatable, name` and is
declared `name, metatable`. A positional call written from the alphabetical list passes each argument in the wrong slot.
Methods that take a single table, such as `LuaSurface.can_fast_replace`, name their arguments and are not affected. The same
holds for event data and prototype properties. Use `api.py lookup`, which prints declared order, or sort by `order` yourself.

## Lua code written from memory of 1.1 or 2.0

The model's recall of the API is older than the game. Known traps: `global` became `storage` in 2.0 (Storage page);
`hr_version` was removed from graphics definitions in 2.0 ("The graphics are now always considered to be in high
definition", `data/changelog.txt` under 2.0.7); recipe `category` became `categories` in 2.1. Look the member up with
`api.py lookup` for the target version before using it, and run `check_data.py` after every prototype edit.

## Mod portal calls that look right and quietly are not

Each of these was observed on live responses from `mods.factorio.com`:

- `GET /api/mods?sort=downloads_count` is accepted and ignored: the portal falls back to name order (with
  `sort_order=desc` the result came back in reverse alphabetical order). Only `name`, `created_at`, and `updated_at` sort.
  Rank by download count on the client, from the `downloads_count` field.
- `pagination.links.next` drops the `version` filter. Request page *n* by number with the same parameters.
- With a `version` filter, `latest_release` is the newest release for that Factorio version, not the newest overall. A mod appears
  if any of its releases matches: a mod whose newest release is 2.1 is listed under `version=2.0` if it also has a 2.0 release.
  `2.0.77` is accepted and treated as `2.0`.
- `POST /api/search` without `username` and `token` in the JSON body answers `Missing data for required field.`. Search
  has no anonymous mode; listing and `/api/mods/<name>/full` do.
- Download links (`/download/<name>/<id>`) answer 403 with a wrong `?username=&token=`, and the body is an HTML page. A valid
  request answers 302 to a content delivery network, so the client must follow redirects.
- Search results hold `latest_release` as an id string; list results hold it as an object; `namelist` results hold
  `releases` and no `latest_release`. Do not index into one shape with another's keys.

`portal.py` handles each of these.

## AI-generated sprites

An image model cannot produce the same object from four or eight directions with a consistent shadow, scale, and
animation frames, which a Factorio sprite sheet needs. Jaer985/factorio-modding-skill records that its author tried AI
icon generation and discarded it (`references/dmr-icon-assets-generation.md`, MIT). This project has ruled AI image
generation out. Use base-game sprites with a tint, Blender renders of a model built for the task, or art the user
supplies (see [graphics-ladder.md](graphics-ladder.md)).

## Hard-coded pixel rectangles for base-game sprites

Jaer985/factorio-modding-skill reports (MIT, `references/factorio-2.1-breaking-changes.md`; not reproduced here) that
copying an assembling machine's sprite rectangle from a clean `data.raw` dump loaded fine on a clean game and failed when
an overhaul mod replaced or resized the same sheet. Reference the base-game graphics by path with a tint and let the
engine read their size, or ship your own sprite whose size you control.
