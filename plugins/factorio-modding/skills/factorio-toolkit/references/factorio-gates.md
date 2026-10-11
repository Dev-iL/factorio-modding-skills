# Factorio gate templates for the manifest

Give `/manifest-dev:define` these gates, adapted to the mod. Replace `<mod>` with the absolute mod folder and `<toolkit>` with the
absolute path of this skill's `scripts` folder. Verifiers run these commands later and may not know where the plugin is
installed, so write real absolute paths, not placeholders. Run commands as `uv run --script <toolkit>/<name>.py ...`.

These terms come from manifest-dev:

- A gate is one check that must pass before a deliverable or the whole mod counts as done.
- A deterministic gate is decided by a command's exit code.
- A judgment gate is decided by a reviewer who reads the evidence.
- An acceptance criterion is a gate on one deliverable. A global invariant is a gate on the whole mod.
- A verifier is the agent that runs a gate.

Each template names its kind, deterministic or judgment; `define` requires one on every gate.

## Per deliverable

**Prototypes** (deterministic). Run `check_data.py --mod <mod> --expect <type>/<name> ...` listing every new prototype, plus `--graphics`
when the mod ships any sprite or icon. Done when it exits 0. Unknown prototype properties and wrong value types fail it.

**Control scripts** (deterministic). Run `run_tests.py --mod <mod>`. Done when it exits 0 and prints one `PASS test:` line per
behaviour the manifest lists. Each behaviour has a test that logs `[FMS-TEST] PASS|FAIL <name>` (see
[in-game-testing.md](in-game-testing.md)); a deliverable with runtime logic and no such test is unfinished.

**Log scan** (deterministic). Run `check_data.py` and `run_tests.py` with `--log-dir <logs>`, then `scan_log.py --log-dir <logs> --warnings`.
Done when the scan exits 0 and prints no `Warning` that names the mod.

**Graphics** (judgment, one gate covering every asset). Each asset names its rung: 1 is recolour or compose base-game sprites, 2 is a
Blender render of an agent-built model, and 3 is a user-supplied `.blend`. User-supplied art is also allowed. Done when each icon is a
64 px PNG whose mipmap declaration matches the file. Each rendered sheet must have the dimensions the tool reported and stay within the
size limit in [graphics-ladder.md](graphics-ladder.md). Rung 2 and 3 entities need a shadow layer, and the data stage must load.
No AI-generated image appears anywhere.

**Locale** (judgment). Every new prototype has a name, and every item or entity a description, in `locale/en`; no key
is unused or missing.

## Global invariants worth including

- **Licence rule** (judgment, only when building on another author's mod):
  - The source licence was read before the plan.
  - A restrictive or missing licence means a separate patch mod that depends on the original.
  - None of that mod's graphics files are copied into this mod.
  - Logic is reused only after a rewrite, which is clean-room for a strict licence.
  - A fork or republish happens only under a permissive licence or with the user's stated permission.
- **No portal writes** (deterministic): nothing in the deliverable uploads or edits anything on the mod portal.
- **Install untouched** (deterministic): the user's `mods\` and `saves\` hold the same entries and hashes before and after verification.

## Test layout

The mod's test hooks live in its own `control.lua` (or a `tests.lua` it requires) and report through `log()`. Keep
test code in the mod folder; `check_data.py` and `run_tests.py` link only that folder.
