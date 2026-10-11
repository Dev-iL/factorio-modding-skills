---
name: update-mod
description: Port a Factorio 2.0 mod to a newer game version (2.1) and propose gameplay changes that the new version makes possible. Use it when the user wants a mod brought up to date, wants to know what the new Factorio version breaks in a mod, or wants ideas for using new game features in an existing mod. Works from a portal mod name or a local mod folder.
argument-hint: '<portal mod name | path to a mod folder> [--from <series>] [--target <version>] [--plan-only] [--autonomous]'
---

# Update a Factorio mod

Planning and execution are done by `manifest-dev`; this skill adds the version arithmetic, the API and changelog diff, and the
gameplay proposals. Load the `factorio-toolkit` skill first and run its `preflight.py`; stop on any failure.

Supported today: a mod declaring `factorio_version` 2.0 or newer, ported to the same or a newer game version. Downgrades and
sources older than 2.0.77 are refused. `--autonomous` is passed through to `define` and also means no user will pick proposals:
adopt none. `--plan-only` stops after the manifest is written.

## Steps

1. **Get the mod**: `portal.py download <name> --dest <work folder>` (needs credentials), adding `--factorio-version <series>` when `--from` names the series to port from (for example `--from 2.0` when the newest release already targets 2.1), or use the local folder. Read its `info.json`.
2. **Resolve the target** Y: `--target` if given, otherwise the installed game version from `locate_game.py`.
3. **Check the versions first**: run `${CLAUDE_SKILL_DIR}/scripts/version_gate.py --mod <mod folder> --target <Y> --json`
   (in Codex, the `scripts/` folder of this skill). If it exits 2, print its message to the user as written and stop; run no
   analysis and write no plan. Otherwise it prints the baseline version to diff from (2.0.77 for a 2.0 mod).
4. **Read the licence before planning** (`portal.py info`, the mod's `LICENSE` file) and take the branch in
   [licensing.md](../factorio-toolkit/references/licensing.md). A restrictive or missing licence means the plan is a separate patch mod
   that depends on the original; do not edit or republish the original's files.
5. **Find what changes**: run `api.py diff <baseline> <Y>` and `changelog.py <baseline> <Y>`; for each change search the mod's code and
   prototypes for the affected name. Read [migration-2.0-to-2.1.md](../factorio-toolkit/references/migration-2.0-to-2.1.md) for known pitfalls.
   Write a compatibility report listing each change that touches the mod with its `file:line` in the mod, what the change is, and the fix.
   Changes that touch nothing in the mod are not listed.
6. **Propose gameplay changes**: from the changelog's new features in the target version (its "Features" and "Modding" entries),
   propose the ones that fit this mod, each scored with the fun, effort and feasibility notes of
   [design-scorecard.md](../factorio-toolkit/references/design-scorecard.md). Adoption is opt-in: ask the user which, if any, to adopt.
   With `--autonomous` or no user present adopt none and record every proposal as a declined option in the manifest.
7. **Write the manifest**: invoke the `manifest-dev:define` skill (`--autonomous` passed through if given). Required deliverable: the mechanical port
   (every item of the compatibility report). One optional deliverable per adopted proposal. Use the gates in
   [factorio-gates.md](../factorio-toolkit/references/factorio-gates.md) so the port is proved by `check_data.py`, `run_tests.py` and the log scan, and
   add the licence rule as a global invariant. Include the compatibility report and the declined proposals in the manifest's context.
8. **Hand off**: unless `--plan-only` was given, run the `develop-mod` skill on the manifest, which executes it through `manifest-dev:do`.
   With `--plan-only`, report the manifest path and stop.
