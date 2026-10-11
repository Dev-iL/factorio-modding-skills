# Graphics ladder

Give each asset the lowest rung that looks right, and name the rung in the manifest. Every rung produces files the game
loads like any other sprite; none involves an AI image model. Another mod's graphics are never a source (see
[licensing.md](licensing.md)).

| Rung | Use it when | How |
|---|---|---|
| 1. Reuse, tint, compose | A base-game sprite looks close enough. **The default.** | Reference the base-game file with a `tint`; `sprites.py tint`, `sprites.py icon` |
| 2. Agent-modelled Blender render | Nothing in the base game looks alike. | `sprites.py render --model <script>` |
| 3. User-supplied `.blend` | The user has a model. | `sprites.py render --blend <file>` |
| User-supplied art | The user has finished PNGs. | Use them as given; read the frame size from the file |

## Rung 1: reuse, tint, compose

For an entity, keep the base-game file and set `tint` on the layer that should change. Leave the shadow layer alone.
Copying the whole prototype with `table.deepcopy` keeps the sprite rectangles correct (see [graveyard.md](graveyard.md), item 5):

```lua
local chest = table.deepcopy(data.raw["container"]["wooden-chest"])
chest.name = "my-chest"
chest.minable.result = "my-chest"
chest.picture.layers[1].tint = { r = 0.4, g = 0.7, b = 1.0 }   -- layers[2] is the shadow
```

`sprites.py tint in.png out.png --color "#66b3ff"` writes a recoloured PNG instead, for when a new file is wanted; it multiplies the
colour channels and keeps alpha. Compare it with the in-game `tint` before relying on the two matching.

`sprites.py icon base.png badge.png out.png --mod-name <mod>` composites a 64 px icon: the base icon with the badge in a corner,
and prints the `icon`/`icon_size` lines for the prototype. Base-game icon files are strips of mipmap levels
(`iron-plate.png` is 120x64: 64, 32, 16 and 8 px side by side), so the tool takes the first level of each input. The prototype can also
layer icons itself with `icons = {{icon = ..., icon_size = 64}, {icon = ..., icon_size = 64, scale = 0.5, shift = {8, 8}}}`
([IconData](https://lua-api.factorio.com/2.1.21/types/IconData.html)); use that when no new file is needed.

Icon mipmaps in 2.x: there is no `icon_mipmaps` field (removed in 2.0.7: "Mipmap count will be inferred from icon_size and actual
dimensions of the source image", `data/changelog.txt`; absent from the 2.1.21 `prototype-api.json`). The file declares its own
levels: each is half the previous, laid left to right from the top-left corner with no padding, so a file with N levels is
`sum(icon_size >> i)` wide and `icon_size` high ([IconData](https://lua-api.factorio.com/2.1.21/types/IconData.html), "icon mipmaps").
The game generates mipmaps itself for a plain 64x64 file, which is what `icon` writes by default. `--mipmaps 4` writes a 120x64 strip
like the base game's; the tool resamples the levels from the composite, so it adds nothing over the generated ones.

## Rung 2: an agent-modelled Blender render

Write a model script (copy `scripts/blender/example_model.py`) and run:

```
sprites.py render --model model.py --name rotor --mod-name my-mod --out <mod>/graphics/entity \
    --directions 4 --frames 2 --frame-size 320 --save-blend model.blend
```

The model script runs inside Blender with `bpy` and defines `build()` and optionally `animate(t)`: geometry on the z=0 ground
plane, centred on the origin, front facing +Y (north); `t` in [0, 1) is the loop position of each frame. Give materials a
`diffuse_color`; the fast Workbench renderer uses it as the base colour and shades it with fixed studio lighting, so it renders darker than the swatch. The tool renders every direction by turning the model, keeping
the orthographic camera and the lighting fixed, so all directions are shaded consistently. A second pass flattens the model onto
the ground along a fixed light direction (`--shadow-x`, `--shadow-y`; right and down on screen) into solid black.

The output is `<name>.png` (frames across, directions down, in Factorio's order north, east, south, west; 8 directions use
north, north_east, east, ...), `<name>-shadow.png` with the same layout, and `<name>.lua`: an `Animation4Way`-shaped table whose
two layers use `x`/`y` to select each direction's block, with `draw_as_shadow = true` on the shadow layer. The same table with
`north` ... `west` keys fits any `Animation4Way` or (single frame) `Sprite4Way` property, for example an assembling machine's
`graphics_set.animation` (`WorkingVisualisations::animation` is an `Animation4Way`). The tool also prints the layout (frame size, columns, rows, sheet size), a warning if the model
or shadow touches the frame edge (raise `--frame-size`), and the shadow's centroid relative to the model.

Facts the emitted Lua relies on, all from the 2.1.21 prototype docs ([Sprite](https://lua-api.factorio.com/2.1.21/types/SpriteParameters.html),
[Animation](https://lua-api.factorio.com/2.1.21/types/AnimationParameters.html)) unless noted:

- `hr_version` is gone; graphics are always high definition (2.0.7 changelog). The base game draws 64 px per tile at `scale = 0.5`
  (`wooden-chest.png` is 62x72 px at `scale = 0.5` in `data/base/prototypes/entity/entities.lua`), so the tool renders 64 px per tile
  and writes `scale = 0.5`.
- `width`/`height` are one frame; `x`/`y` locate the first frame in the file; `frame_count` frames run left to right and wrap after
  `line_length` per row.
- `shift` is in tiles. The tool aims the camera at half the model's height, so the point under the entity's centre is
  `center_z * cos(elevation)` below the frame centre; it writes that as the `shift` on both layers.
- `draw_as_shadow` marks a layer as a shadow. The base game draws its shadow as a separate layer; here the shadow shares the main
  layer's frame, `shift` and `scale` because both are rendered from the same camera.
- `animation_speed` of 1 is one frame per tick; the tool writes `--animation-speed` (default 0.5).

The camera elevation (60 degrees) and the shadow direction are the tool's own choices, not Factorio's; tune `--elevation`,
`--shadow-x` and `--shadow-y` against a neighbouring base-game entity.

## Rung 3: a user-supplied `.blend`

`sprites.py render --blend model.blend ...` takes the same options. The tool deletes the file's cameras and lights, uses its own
(so the look matches rung 2), and samples `--frames` frames evenly from the file's frame range. Orient the model as in rung 2.
`--save-blend` on a rung 2 run keeps the model, animation baked into keyframes, for a later `--blend` run.

## Limits

| Limit | Value | Source |
|---|---|---|
| One sprite or animation frame, width and height | 0 to 4096 px | [SpriteSource `width`](https://lua-api.factorio.com/2.1.21/types/SpriteSource.html), [AnimationParameters `width`](https://lua-api.factorio.com/2.1.21/types/AnimationParameters.html) ("from 0-4096") |
| One input file, width | 8192 px ("the game engine's width limit of 8192px per input file ... to be compatible with most graphics cards") | AnimationParameters `line_length` |
| One input file, height | not stated per axis | The 0.17.0 changelog says "Increased limit for size of spritesheet to 8196px" without naming an axis; the tool applies 8192 to the height as a conservative choice. |

`sprites.py render` wraps frames after `8192 // frame_width` columns, and refuses with the numbers when a frame is over 4096 or
the sheet is over 8192 high. Do not use the "2048px normal / 4096px high resolution" single-sprite limit from the same 0.17.0 entry: 2.x has no normal-resolution sprites and the 2.1.21 docs state 4096.

## Prove the graphics load

Run `check_data.py --mod <dir> --graphics` (see [in-game-testing.md](in-game-testing.md)): the plain data-stage check never reads
sprite files, so a missing PNG or an out-of-range sprite rectangle only shows with `--graphics`.
