# Factorio gate templates for the manifest

Give `/manifest-dev:define` these gates, adapted to the mod, as Acceptance Criteria or Global Invariants. Replace `<mod>`
with the absolute mod folder and `<toolkit>` with the absolute path of this skill's `scripts` folder. Verifiers run these commands later and may not know where
the plugin is installed, so write real absolute paths, not placeholders. Run commands as `uv run --script <toolkit>/<name>.py ...`.

Each template names its kind; `define` requires one on every gate.

## Per deliverable

**Prototypes** (deterministic). Run `check_data.py --mod <mod> --expect <type>/<name> ...` listing every new prototype, plus `--graphics`
when the mod ships any sprite or icon. Done when it exits 0. Unknown prototype properties and wrong value types fail it.

**Control scripts** (deterministic). Run `run_tests.py --mod <mod>`. Done when it exits 0 and prints one `PASS test:` line per
behaviour the manifest lists. Each behaviour has a test that logs `[FMS-TEST] PASS|FAIL <name>` (see the toolkit's
`references/in-game-testing.md`); a deliverable with runtime logic and no such test is unfinished.

**Log scan** (deterministic). Run `check_data.py` and `run_tests.py` with `--log-dir <logs>`, then `scan_log.py --log-dir <logs> --warnings`.
Done when the scan exits 0 and prints no `Warning` that names the mod.

**Graphics** (judgment, one gate covering every asset). Each asset names its rung: 1 = recolour or compose base-game
sprites, 2 = Blender render of an agent-built model, 3 = user-supplied `.blend`; user-supplied art is also allowed. Done when each
icon is a 64 px PNG whose mipmap declaration matches the file, each rendered sheet has the dimensions the tool reported and
stays within the size limit in the toolkit's `references/graphics-ladder.md`, a shadow layer exists for rung 2 and 3 entities,
and the data stage loads. No AI-generated image appears anywhere.

**Locale** (judgment). Every new prototype has a name, and every item or entity a description, in `locale/en`; no key
is unused or missing.

## Global invariants worth including

- **Licence rule** (judgment, only when building on another author's mod): the source licence was read before the plan; a
  restrictive or missing licence means a separate patch mod that depends on the original; none of that mod's graphics files
  are copied into this mod; logic is reused only after a rewrite (clean-room for a strict licence); a fork or republish only under a
  permissive licence or with the user's stated permission.
- **No portal writes** (deterministic): nothing in the deliverable uploads or edits anything on the mod portal.
- **Install untouched** (deterministic): the user's `mods\` and `saves\` hold the same entries and hashes before and after verification.

## Test layout

The mod's test hooks live in its own `control.lua` (or a `tests.lua` it requires) and report through `log()`. Keep
test code in the mod folder; `check_data.py` and `run_tests.py` link only that folder.
