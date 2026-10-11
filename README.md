# factorio-modding-skills

Skills that let a coding agent design, build, and port Factorio mods against the game version you actually run, and
prove each change in the real game instead of guessing.

The repository is a **marketplace** (a catalogue an agent host installs from) holding one **plugin**, `factorio-modding`.
A plugin bundles **skills**: instruction files plus helper scripts that an agent loads when a task matches. It installs into
both Claude Code and OpenAI Codex, the two supported **hosts**. The skills hand planning and execution to a second plugin,
[manifest-dev](https://github.com/doodledood/manifest-dev). In manifest-dev, `/figure-out` interviews you about a problem,
`/define` writes a **manifest** (a checklist of deliverables and the checks that prove each one), and `/do` carries the manifest out.

## What you get

The plugin provides four skills:

| Skill | Use it to |
|---|---|
| `design-mod` | Turn an idea, or an existing mod, into a scored design and a manifest. It searches the mod portal for similar mods, interviews you, scores feasibility, fun, and effort from 1 to 5 with evidence, and writes a manifest whose checks run the real game. |
| `develop-mod` | Build the mod a manifest describes and verify it loads and passes its tests in Factorio. |
| `update-mod` | Port a 2.0 mod to 2.1: compare the two API versions and changelogs, list what breaks with file and line, and propose optional gameplay changes the new version allows. |
| `factorio-toolkit` | Shared by the other three, not run by you: API lookup, version diff, mod portal client, game launcher, log scanner, and sprite tools. |

A run goes like this. The toolkit's scripts start Factorio headless (with no window) in a throwaway **sandbox**: a temporary
data folder with its own log, and a temporary mod folder that links only the mod under test. Your own mods, saves, and settings are
neither loaded nor changed. The scripts check the **data stage**, where prototypes are defined, with `factorio --dump-data`. They
check the **control stage**, the runtime scripts, by creating a map and running it for a few ticks.

## Supported and not supported

Supported:

- Factorio **standalone Windows installs**: the zip package (portable) and the standalone installer. Steam, Linux, and macOS layouts are not supported.
- Experimental 2.1 (developed against 2.1.21) and stable 2.0.
- `update-mod` ports mods built for Factorio 2.0.77 or later (`factorio_version` 2.0 or later).

Not supported:

- Downgrades, such as a mod for 2.1 targeted at 2.0.
- Source mods built for a Factorio version older than 2.0.77, including all 1.1 mods.
- Linux and macOS.
- Publishing. The plugin never uploads or edits anything on the mod portal; it only reads from it.

## Requirements

- Windows with Factorio installed as described in Supported and not supported.
- Claude Code, tested with 2.1.296, or Codex, tested with 0.159.3 and 0.162.1.
- [uv](https://docs.astral.sh/uv/) 0.13 or later, the first release whose default Python is 3.15 ([uv 0.13.0 release notes](https://github.com/astral-sh/uv/releases/tag/0.13.0)). The scripts are single-file Python
  programs run with `uv run --script`; uv downloads Python 3.15 and their dependencies on first use.
- [Blender](https://www.blender.org/) 5.x, only for rendered sprites (`sprites.py render`).
- Mod portal credentials, only for portal search and download (see Mod portal credentials).

## Install: Claude Code

```
claude plugin marketplace add doodledood/manifest-dev
claude plugin marketplace add Dev-iL/factorio-modding-skills
claude plugin install factorio-modding@factorio-modding-skills
```

The first command lets Claude Code find manifest-dev; the install then pulls it in as a dependency. `claude plugin list` shows
both `factorio-modding@factorio-modding-skills` and `manifest-dev@manifest-dev` as enabled. Restart Claude Code, then start the
skills with `/factorio-modding:design-mod`, `/factorio-modding:develop-mod`, or `/factorio-modding:update-mod`.

## Codex setup

The Codex [plugin build guide](https://developers.openai.com/codex/plugins/build) documents no way to declare a dependency on another plugin, so install manifest-dev yourself first:

```
codex plugin marketplace add doodledood/manifest-dev
codex plugin add manifest-dev@manifest-dev
codex plugin marketplace add Dev-iL/factorio-modding-skills
codex plugin add factorio-modding@factorio-modding-skills
```

`codex plugin list` shows both as "installed, enabled". In a Codex session, ask for a skill by name, for example "use the
design-mod skill to plan a mod that adds a new fluid".

Codex limits what its commands may write and reach, which can block uv from writing its cache; this happened in this repository's own test run. If `uv run` fails with "Access is denied", allow Codex to write the uv cache folder and to reach the network. The sites to allow are lua-api.factorio.com and the mod portal. Alternatively, point
`UV_CACHE_DIR` and `FM_CACHE_DIR` (the toolkit's API cache) at a folder that Codex may write.

## Point the plugin at your game

The scripts look for Factorio in `FACTORIO_PATH`, then in common standalone locations. Set `FACTORIO_PATH` to the folder that contains
`bin\x64\factorio.exe`. For a single run, pass `--path` to a script.

- Claude Code: add it to the `env` block of `~/.claude/settings.json`:
  ```json
  { "env": { "FACTORIO_PATH": "C:\\Games\\Factorio" } }
  ```
- Codex: add it to `~/.codex/config.toml`:
  ```toml
  [shell_environment_policy]
  set = { FACTORIO_PATH = "C:\\Games\\Factorio" }
  ```

  In TOML, write each Windows backslash twice, or use forward slashes.

## Mod portal credentials

Searching and downloading from the mod portal needs your Factorio username and API token; listing and viewing mods does not.
The token is stored in the `player-data.json` file in your Factorio user data folder
([Mod portal API](https://wiki.factorio.com/Mod_portal_API)). That page does not name the fields. The toolkit reads
`service-username` and `service-token`, the field names this repository observed in a Factorio 2.1.21 install. Copy the two values
yourself into the same files as `FACTORIO_PATH`, under the names `FACTORIO_USERNAME` and `FACTORIO_TOKEN`:

- Claude Code: `"env": { "FACTORIO_USERNAME": "...", "FACTORIO_TOKEN": "..." }` in `~/.claude/settings.json`.
- Codex: `set = { FACTORIO_USERNAME = "...", FACTORIO_TOKEN = "..." }` under `[shell_environment_policy]` in `~/.codex/config.toml`.

The scripts never print these values and redact them from download URLs. They never read `player-data.json` on their own.
If the variables are missing, the agent may ask whether to read the file once, and the scripts read it only with an explicit
`--allow-player-data` flag.

## First run: preflight

Ask the agent to run the toolkit's preflight, or run it yourself from the installed plugin's `skills/factorio-toolkit/scripts`
folder. Claude Code shows the plugin's folder as `installPath` in `claude plugin list --json`; Codex prints it as "Installed
plugin root" when you run `codex plugin add`. Set `FACTORIO_PATH` in that shell, then run:

```
uv run --script preflight.py
```

Preflight checks uv and Python 3.15, finds Factorio and reports its version, confirms manifest-dev is installed in your host,
and notes whether credentials are set. Each failure names what is missing and the fix. Add `--sprites` to also require Blender.

## Layout and contributing

See [AGENTS.md](AGENTS.md) for the repository layout, how to run the tests, and the conventions. Attribution for the projects this
one learned from is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The code and prose in this repository are MIT licensed (see `LICENSE`).
