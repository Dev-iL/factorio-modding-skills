# Scoring a mod idea or a gameplay proposal

Score every idea (and every gameplay proposal in update-mod) on three dimensions from 1 to 5, and write the evidence
next to each number. A score with no evidence is a guess and is not recorded.

| Dimension | 5 means | 1 means | Evidence to cite |
|---|---|---|---|
| Feasibility | Every needed prototype type, property and event exists in the target game version and nothing known blocks it. | Needs an engine capability the API does not expose. | `api.py lookup` output for each load-bearing prototype, property or event; a [graveyard.md](graveyard.md) entry if one applies. |
| Fun | Fills a real gap in a stage of the game, adds choices worth revisiting, and is new next to similar mods. | Duplicates what the base game or a popular mod already does, or adds a chore. | Where it enters progression (which science pack, planet or tech), what changes on a second playthrough, and the named similar mods from the portal search. |
| Effort | Small: a few prototypes, no runtime script, rung 1 graphics. | Large: many entities, control-stage logic, custom rendered sprites, migration risk. | Counts of prototypes, scripts and assets; the graphics rung per asset ([graphics-ladder.md](graphics-ladder.md)). |

Effort is scored so that 5 is cheap: a higher total is always better. Report the three numbers with their evidence and a recommendation: build, build a reduced version, use an existing mod, or do not build. A low feasibility or fun score
is a real answer; do not inflate it to reach a manifest.
