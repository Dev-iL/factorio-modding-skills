---
name: design-mod
description: Turn a Factorio mod idea, or an existing mod from the portal or a local folder, into a scored design and a manifest that the develop-mod skill can build. Use it when the user wants to plan a new Factorio mod, find out whether something like it already exists, weigh feasibility, fun and effort before any code, or plan changes to another author's mod.
argument-hint: '<idea text | portal mod name | path to a mod folder> [--design-doc] [--autonomous]'
---

# Design a Factorio mod

Planning and grilling are done by the `manifest-dev` plugin; this skill adds what only a Factorio modder knows: what the portal
already has, whether the game's API supports the idea, and gates that run the real game. Load the `factorio-toolkit` skill first, then run its `preflight.py`
and stop on any failure (it names the fix). The mod gets built later by `develop-mod`; do not write mod code here.

## Pick the mode

- **Existing mod**: the argument is a folder containing `info.json`, or a name `portal.py info` finds on the portal.
- **New idea**: anything else.

`--design-doc` writes a design document (see Design document). `--autonomous` is passed through to `figure-out` and `define`.

## New idea

1. **Search the portal for similar mods** with `portal.py search` using several phrasings of the idea. If credentials are
   missing the script says so and how to set them; say that to the user, then fall back to `portal.py list` filtered by the
   game version and read names and summaries yourself. Keep each similar mod's name, URL (`https://mods.factorio.com/mod/<name>`),
   download count and one line on how it differs. If a result already does the idea, that is the most likely recommendation: say so.
2. Continue at **Grill**.

## Existing mod

1. Get the mod: `portal.py download <name> --dest <work folder>` (needs credentials) or use the local folder.
2. **Read its licence before making any plan** (`portal.py info` for the portal's licence field, and the mod's own `LICENSE`
   file). Take the branch in [licensing.md](../factorio-toolkit/references/licensing.md): restrictive or missing licence means a
   separate patch mod that depends on the original, never copying its graphics, and reusing logic only after a rewrite.
   Plan a fork or republish only under a permissive licence or when the user says they have permission.
3. **Map the mod**: list its prototypes (type and name from its `data*.lua`), its control scripts and the events they handle,
   its graphics files, its locale and its settings. Record the map in the design notes; it is what the plan is built against.
4. Search the portal for similar mods as in New idea step 1, then continue at **Grill**.

## Grill

Invoke the `manifest-dev:figure-out` skill (Claude Code: `/manifest-dev:figure-out`) on the idea or the mod, carrying the portal
findings and the map. Press on: where it enters progression, what is fun on a second playthrough, which prototype types and events
it needs and whether `api.py lookup` confirms they exist in the installed game version, and for each asset which graphics rung applies
([graphics-ladder.md](../factorio-toolkit/references/graphics-ladder.md)). Pass `--autonomous` when it was given to this skill.

## Score it

Score feasibility, fun and effort from 1 to 5 with evidence for each, as defined in
[design-scorecard.md](../factorio-toolkit/references/design-scorecard.md). The fun evidence states all three of progression (where
the mod enters the game), replayability (what changes on a second playthrough) and novelty against the named similar mods; the
effort evidence states counts and the graphics rung per asset. Write the scorecard in the final answer, not only in notes. Show it to the user. When it recommends not building
(a duplicate exists, feasibility is 1 or 2), say that plainly and stop without writing a manifest, unless the user asks to continue.

## Design document (only with `--design-doc`)

Before the manifest, write `design-<mod-name>.md` in the working directory: the idea, similar mods, the scorecard with evidence,
the design (prototypes, scripts, graphics with rung per asset, locale), risks, and what is out of scope. Without the flag write no
design document; the manifest is the only output.

## Manifest

Invoke the `manifest-dev:define` skill (`--autonomous` passed through if given) with the shared understanding. The manifest must name the
mod folder (default `./<mod-name>` in the working directory) and its deliverables must cover prototypes, control scripts, graphics
with a rung chosen per asset, locale and tests. Add the gates from [factorio-gates.md](../factorio-toolkit/references/factorio-gates.md), with absolute
toolkit paths filled in. Existing-mod mode adds its licence rule as a global invariant.

Finish by giving the manifest path, the scorecard and the next step: run `develop-mod` on the manifest.
