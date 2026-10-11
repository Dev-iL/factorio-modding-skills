# AGENTS.md

Guidance for anyone, human or agent, changing this repository. It holds one plugin, `factorio-modding`,
that installs into both Claude Code and Codex.

## Layout

- `.claude-plugin/marketplace.json` lists the plugin for Claude Code. `.agents/plugins/marketplace.json` lists it for Codex.
- `plugins/factorio-modding/` is the single plugin. It has `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`
  and exactly one `skills/` tree that both hosts read. Do not add symlinks (Windows checks them out as text files)
  and do not copy a skill file into a second place.
- `plugins/factorio-modding/skills/factorio-toolkit/` is the shared layer: `scripts/` (the Python tools) and `references/`
  (what agents get wrong). `design-mod`, `develop-mod`, and `update-mod` are the workflows. They call the toolkit and hand
  planning and execution to the `manifest-dev` plugin (`/manifest-dev:figure-out`, `/manifest-dev:define`, `/manifest-dev:do`).
- `tests/` holds the pytest suite. `tests/fixtures/` holds small hand-written mods used by the in-game tests.

## Run the tests

```
uv run --python 3.15 pytest
```

Tests marked `game` need the local Factorio install (`FACTORIO_PATH` or a standard location). Tests marked `blender`
need Blender (`BLENDER_PATH` or a standard location). Tests marked `network` hit the live portal or lua-api.factorio.com.
Everything else mocks the network. Deselect a group with `-m "not game"`.

## Try the plugin locally

- Claude Code, one session, no install: `claude --plugin-dir plugins/factorio-modding` (needs `manifest-dev` installed too).
  To run a skill non-interactively, use `claude -p "/factorio-modding:design-mod <idea> --autonomous" --plugin-dir plugins/factorio-modding`.
- Claude Code, installed: `claude plugin marketplace add <path to this repo>` then
  `claude plugin install factorio-modding@factorio-modding-skills`. Point `CLAUDE_CONFIG_DIR` at an empty folder to keep your own setup out of it.
- Codex: `codex plugin marketplace add <path to this repo>` then `codex plugin add factorio-modding@factorio-modding-skills`.
  Install `manifest-dev` first (see the README section "Codex setup"). Point `CODEX_HOME` at an empty folder for a clean install.
- The scripts run on their own: `uv run --script plugins/factorio-modding/skills/factorio-toolkit/scripts/preflight.py`.
  Set `FACTORIO_PATH` to your Factorio folder for anything that starts the game.

## Conventions

- Scripts are single-file `uv run --script` programs with a PEP 723 header and `requires-python = ">=3.15"`.
  Shared code lives in `scripts/_lib/` and is imported as `_lib` (uv puts the script's directory on `sys.path`).
  The exception is the scripts in `scripts/blender/`, which run inside Blender's bundled Python (`blender -b --python`);
  they import `bpy` and have no uv header.
- HTTP goes through `httpx2` only: no `requests`, `urllib.request`, `urllib3`, `aiohttp` or plain `httpx`.
- Script names use underscores so tests can import them. Every script module has a test.
- Every failure a user can hit raises `ToolkitError` (cause plus next step); scripts never show a raw traceback.
  The exception is `plugins/factorio-modding/skills/update-mod/scripts/version_gate.py`: it is stdlib-only so that it runs
  without the toolkit, so it raises its own `Refused` with the same cause-plus-next-step wording and never shows a traceback.
- Credentials come from `FACTORIO_USERNAME` and `FACTORIO_TOKEN`. Nothing reads `player-data.json` unless the
  user approved it in the current conversation and the script was given the explicit flag. Nothing prints a
  credential; run any text that might carry one through `_lib.redact.redact`.
- The plugin never uploads, publishes or edits anything on the mod portal.
- No AI image generation anywhere in a graphics path.
- Do not add a `CLAUDE.md`; this file is the single instruction file for both hosts.
