---
name: factorio-toolkit
description: Shared tools and reference notes for working on Factorio mods against the game version the user actually runs. Load it before writing or changing mod Lua, checking whether a mod loads, looking up the Factorio API, searching or downloading from the mod portal, or making sprites. The design-mod, develop-mod and update-mod skills depend on it.
user-invocable: false
---

# Factorio toolkit

A coding agent working on a Factorio mod tends to go wrong in four ways: it writes Lua against a half-remembered API from
an older Factorio version, it never starts the game so a broken prototype is found by the user, it builds something the mod portal
already has (or reuses someone's code or art without checking the licence), and it skips graphics or reaches for AI images
that cannot become a consistent multi-direction sheet.

## How to run the scripts

The scripts are in `scripts/` next to this file. Run each as `uv run --script ${CLAUDE_SKILL_DIR}/scripts/<name>.py ...`
(Claude Code fills in `${CLAUDE_SKILL_DIR}`; in Codex use the folder of the SKILL.md you loaded). They need `uv` 0.13 or later;
uv fetches Python 3.15 and the dependencies by itself. Every script has `--help`. The checks (`preflight.py`, `check_data.py`, `run_tests.py`, `scan_log.py`) end with a `PASS` or `FAIL` line;
a failure of any script is a plain error with the next step, never a traceback.

If `uv run` itself fails before any output (uv missing, uv older than 0.13, no Python 3.15), the toolkit cannot report it:
tell the user to install uv from https://docs.astral.sh/uv/ or run `uv self update`, then `uv python install 3.15`.

## Rules

1. **Run preflight first** in a new session: `preflight.py`. It checks uv, Python 3.15, the Factorio install, that `manifest-dev` is
   installed in this host, and with `--sprites` Blender. Fix what it reports before doing anything else.
2. **Look the API up; never write it from memory.** `api.py lookup <name>` answers for the installed game version
   (`locate_game.py` prints it). Parameter order in the output is the declared one. Use `api.py diff` and `changelog.py` for what changed between versions.
3. **Prove it loads before saying it works.** After any data-stage change run `check_data.py`; for runtime behaviour run
   `run_tests.py`. Never report a mod as working because the Lua reads correctly. Read the log once after a run
   (`scan_log.py`); never tail it.
4. **Check the portal before designing**, and read the licence of any mod you build on (`portal.py`, [licensing.md](references/licensing.md)).
5. **Credentials** are `FACTORIO_USERNAME` and `FACTORIO_TOKEN`. The portal search and download need them. If they are unset the script says
   so; offer the user the two setup routes it prints. Never read the game's `player-data.json` yourself; the scripts do it only with
   `--allow-player-data`, which you may pass only after asking the user in this conversation, each time. Never print a token or a
   download URL that carries one.
6. **Graphics**: use the ladder in [graphics-ladder.md](references/graphics-ladder.md). Never generate images with an AI model, and
   never copy another mod's graphics.
7. **Publishing is out of scope.** Nothing here uploads or edits anything on the portal; do not offer to.
8. **Do not touch the user's `mods\` or `saves\`.** The runners use a sandbox; keep it that way.

## Scripts

Each script and what it is for:

| Script | Use it to |
|---|---|
| `preflight.py` | Check the environment and name what is missing. |
| `locate_game.py` | Print the install, version, write-data, mods, saves and log paths. |
| `check_data.py` | Validate the data stage (`--dump-data`) of a mod. |
| `run_tests.py` | Run a mod's in-game tests headless. |
| `scan_log.py` | Read a game log once and list errors by stage. |
| `api.py` | `lookup` a class, prototype, event or member; `diff` two API versions. |
| `changelog.py` | Print the "Modding:" sections of the game's changelog between two versions. |
| `portal.py` | `list`, `search`, `info` and `download` mods from the mod portal. |
| `sprites.py` | `tint` and `icon` for base-game graphics; `render` a Blender model into a sprite sheet. |

## References

Load a reference when its situation comes up; they are not needed for every task.

| File | Load it when |
|---|---|
| [mod-skeleton.md](references/mod-skeleton.md) | creating a mod from scratch: `info.json` keys, files, stages |
| [data-vs-control-stage.md](references/data-vs-control-stage.md) | deciding where logic belongs, or hitting a stage error |
| [in-game-testing.md](references/in-game-testing.md) | writing or running tests against the game |
| [install-paths-and-logs.md](references/install-paths-and-logs.md) | a path or log is not where expected, or the install is portable vs system |
| [rapid-iteration.md](references/rapid-iteration.md) | the user wants a faster loop than restarting the game |
| [graphics-ladder.md](references/graphics-ladder.md) | an entity or item needs graphics |
| [licensing.md](references/licensing.md) | building on, patching or porting another author's mod |
| [migration-2.0-to-2.1.md](references/migration-2.0-to-2.1.md) | porting or reading 2.0-era code |
| [design-scorecard.md](references/design-scorecard.md) | scoring an idea or a gameplay proposal |
| [factorio-gates.md](references/factorio-gates.md) | writing a manifest for a mod: gate templates that run the game |
| [graveyard.md](references/graveyard.md) | before trying an unusual approach; it lists ones known to fail |
