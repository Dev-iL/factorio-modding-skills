# Licensing: building on another author's mod

Rules for any plan that starts from a mod somebody else wrote: porting it to a new game version, extending it, or
borrowing an idea. They are the project owner's rulings. This page is not legal advice; when a licence is unclear,
choose the more restrictive reading and tell the user.

## The rules

1. **Read the source mod's licence before making any plan.** Check both places: the portal's licence field and the
   licence file inside the mod. Record the licence and the branch chosen in rules 2, 4, and 5 in the manifest.
2. **A restrictive or missing licence means a separate patch mod.** Do not copy and edit the original. Make a new
   mod that lists the original in `info.json` `dependencies` (for example `"original-mod >= 1.2.0"`) and changes the original's
   prototypes from `data-updates.lua` or `data-final-fixes.lua`. A dependency loads first, so its prototypes exist by
   then (Data lifecycle and Mod structure pages; see [data-vs-control-stage.md](data-vs-control-stage.md)).
3. **Another mod's graphics files are never copied into the mod you produce.** Pointing at them in place is allowed. With the
   original as a dependency, a prototype can use `__original-mod__/graphics/x.png`, because the path format `__<mod-name>__`
   addresses the root of any active mod (`FileName` type, prototype API docs for 2.1.21).
4. **Logic is reused only after a thorough rewrite.** Reading the source to understand what it does is fine; pasting or lightly
   rephrasing its functions is not. When the licence is strict (see The portal's licence field), rewrite clean-room. One pass
   writes a description of the behaviour (inputs, outputs, rules, edge cases) without code from the source. A second pass, which
   does not read the source, writes the implementation from that description.
5. **A fork or republished copy is planned only under a permissive licence, or when the user says they have permission
   from the author.** Even then the licence's own conditions apply (an MIT licence, for instance, requires keeping its
   copyright notice). Base-game files (`__base__`, `__space-age__`) are not another mod's graphics. Reusing them by path with a tint
   is the normal first step of the graphics ladder (see [graphics-ladder.md](graphics-ladder.md)).

Publishing a mod is outside this plugin: it never uploads anything to the mod portal. If the user publishes the result themselves,
these rules still decide what may be in it.

## The portal's licence field

`portal.py info <name>` prints it, and `portal.py download` prints it again with any licence file found in the zip. It comes
from the `license` object of `GET /api/mods/<name>/full` ([Mod portal API](https://wiki.factorio.com/Mod_portal_API)), whose
fields are `id`, `name`, `title`, `url`, and `description`.

On 2026-10-10 a sample of 47 portal mods (the 40 most recently updated 2.0 mods and 7 well-known ones) showed these `id` values:

| `id` | Meaning | Treat as |
|---|---|---|
| `default_mit` | MIT | permissive |
| `default_unlicense` | Unlicense (public-domain dedication) | permissive |
| `default_gnugplv3`, `default_gnulgplv3` | GNU GPL v3, GNU LGPL v3 | copyleft: a copy or derivative must stay under the same licence with source available. A fork is possible; a patch mod is simpler |
| `default_mozilla2` | Mozilla Public License 2.0 | copyleft at file level; treat like the GNU licences |
| `custom_<hex>` | The author's own terms | restrictive until read; the text is in `description`, or the `url` points to a standard one such as CC BY-SA 4.0 or CC BY-NC-ND 4.0. `portal.py info` prints this text |
| no `license` key (not seen in the sample) | Nothing declared | restrictive: all rights remain with the author |

Custom terms in the sample ranged from CC BY-SA 4.0 to "no commercial use, no modified versions". Read each one. The
table is only a starting point, and the portal may offer more default licences than the sample showed.

## The licence file inside the mod

Look in the unpacked mod for `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING`, or a licence section in the `README`. Check the
`info.json` fields `homepage` and `contact` for a source repository. `portal.py download` lists the licence files it found.
A source repository may carry a different licence from the portal listing, and graphics in a mod can have a
different licence from its code (a `graphics/LICENSE` file, or a credits note). When two statements disagree, follow the
stricter one for the part concerned, and ask the user.

## What to record in the manifest

- Source mod name, version, and URL (`https://mods.factorio.com/mod/<name>`).
- Licence `id` and the licence file's name, quoted.
- The branch taken: patch mod (rule 2), clean-room rewrite (rule 4), or fork with the permission or licence that allows it (rule 5).
- That no graphics file of the source was copied (rule 3).
