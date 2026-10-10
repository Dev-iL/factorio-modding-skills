# Minimal mod skeleton for Factorio 2.1

Source: "Mod Structure" in the 2.1.21 auxiliary docs, https://lua-api.factorio.com/2.1.21/auxiliary/mod-structure.html.
The mandatory-key list was also checked by removing each key in turn and running `check_data.py` against 2.1.21 (build 87673).

## `info.json`

A mod is a folder named `{mod-name}` or `{mod-name}_{version}` that holds `info.json`, the only mandatory file.
Mandatory keys: `name`, `version` (`number.number.number`), `title` and `author`. Removing any of them makes the game
refuse the mod (for example `Key "title" not found in property tree at ROOT`).

`factorio_version` is the major version only, such as `"2.1"` (the experimental line) or `"2.0"` (stable). A third number
makes the portal reject the mod. It is technically optional but defaults to `"0.12"`, so omitting it makes a modern game
reject the mod as incompatible. `dependencies` defaults to `["base"]`; `description` is optional.

Dependency strings are `"<prefix> name <op> version"`. Prefixes: none = hard requirement, `?` optional, `(?)` hidden
optional, `+` recommended, `~` required without affecting load order, `!` incompatible. The official DLC mods are
`space-age`, `quality`, `elevated-rails` and `recycler`; depend on one only when the mod needs its content.

## Files and where they run

| File | Stage | Notes |
|---|---|---|
| `settings.lua`, `settings-updates.lua`, `settings-final-fixes.lua` | settings | Declares mod settings. |
| `data.lua`, `data-updates.lua`, `data-final-fixes.lua` | data | Defines and edits prototypes in `data.raw`. The log shows `Loading mod <name> <version> (data.lua)`. |
| `control.lua` | control | Runtime scripts. |
| `locale/<lang>/*.cfg` | | Translations, e.g. `[item-name]` and `[item-description]` sections. |
| `migrations/`, `scenarios/`, `thumbnail.png`, `changelog.txt` | | Recognised by the game; see the source page. |

Mod files are addressed as `__<mod-name>__/path`; base game files as `__base__/graphics/...`.
The stages and what each can touch are explained in [data-vs-control-stage.md](data-vs-control-stage.md).

## Quirks that cost a run

- A misspelt or unknown prototype property is silently ignored by the game; `check_data.py` reports it (see
  [in-game-testing.md](in-game-testing.md)).
- A sprite or icon file that does not exist is not caught by the data stage alone (see [graphics-ladder.md](graphics-ladder.md)).
