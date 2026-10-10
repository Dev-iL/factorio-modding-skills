---
name: develop-mod
description: Build the Factorio mod that a manifest from design-mod describes, and prove it loads and passes its tests in the real game. Use it when the user has a manifest for a Factorio mod and wants it implemented, or wants an existing mod changed under a manifest.
argument-hint: '<manifest path> [options passed through to /manifest-dev:do]'
---

# Develop a Factorio mod

This is a thin wrapper: execution, verification and completion are done by `manifest-dev`. It exists so that every run starts
from a working environment and a modder's defaults.

1. Load the `factorio-toolkit` skill. Run its `preflight.py` (add `--sprites` when the manifest has a rung 2 or 3 graphics asset)
   and stop on any failure; the output says how to fix it.
2. Read the manifest. If it has no gate that runs the toolkit's `check_data.py` and `run_tests.py`, note in the final report that
   it was not written by `design-mod` and its gates do not prove the mod loads; carry on without changing the manifest.
3. Invoke the `manifest-dev:do` skill (Claude Code: `/manifest-dev:do`) with the manifest path and any options the user supplied.
   Do not restate or reimplement its procedure.
4. While it runs, apply these defaults when the manifest leaves a choice open:
   - Look every API name up with `api.py lookup` before using it; the installed game version is in `locate_game.py`.
   - Graphics: rung 1 by default (recolour or compose base-game sprites, preferring the prototype `tint` field); rung 2 (a Blender
     render of a model you build, `sprites.py render`) only when nothing in the base game looks alike; rung 3 when the user supplied
     a `.blend`. Never generate images with an AI model and never copy another mod's graphics
     ([graphics-ladder.md](../factorio-toolkit/references/graphics-ladder.md)).
   - Run `check_data.py` after each data-stage change and `run_tests.py` after each runtime change, as you go.
5. When `manifest-dev:do` finishes, report the mod folder and what was verified. If it ends blocked or escalated, report that
   as it stands.
