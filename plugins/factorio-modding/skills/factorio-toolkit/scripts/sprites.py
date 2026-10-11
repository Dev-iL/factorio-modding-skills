#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["pillow"]
# ///
"""Graphics for a mod without AI image generation: recolour or compose base-game sprites, or render a Blender model.

  tint    recolour a base-game PNG (multiplies the colour channels)
  icon    composite a 64px icon from a base icon plus a badge overlay
  render  headless Blender: model (or .blend) -> N directions x M frames -> sheet + shadow sheet + Lua snippet

For an entity, the prototype `tint` field on a base-game sprite is usually better than a new PNG:
  picture = { filename = "__base__/graphics/entity/wooden-chest/wooden-chest.png", width = 62, height = 72,
              scale = 0.5, tint = {r = 0.4, g = 0.7, b = 1} }
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from PIL import Image

from _lib.blender import find_blender
from _lib.errors import ToolkitError, cli_main

# Sprite limits, Factorio 2.1.21 prototype docs (https://lua-api.factorio.com/2.1.21/):
#   one frame/sprite: width and height 0-4096 px  (types/SpriteSource.html#width, types/AnimationParameters.html#width)
#   one input file:   8192 px wide                (types/AnimationParameters.html#line_length)
# The docs state no height limit for a file (the 0.17.0 changelog names a 'spritesheet' limit without an axis);
# MAX_SHEET_SIDE is applied to the height too as a conservative choice, not a documented fact.
MAX_FRAME_SIDE = 4096
MAX_SHEET_SIDE = 8192

TILE_PX_AT_SCALE_1 = 32  # `scale = 1` draws one tile as 32 px; 2.x sprites are high resolution, so 64 px/tile uses scale 0.5
DIRECTION_KEYS: Mapping[int, tuple[str, ...]] = {
    1: ("",),
    4: ("north", "east", "south", "west"),
    8: ("north", "north_east", "east", "south_east", "south", "south_west", "west", "north_west"),
}
BLENDER_SCENE = Path(__file__).resolve().parent / "blender" / "blender_scene.py"
ALPHA_THRESHOLD = 16  # alpha at or above this counts as "the object" when measuring extents


# --- rung 1: tint and icon ------------------------------------------------------------------------------------------

def parse_color(text: str) -> tuple[int, int, int]:
    """`#rrggbb`, `rrggbb` or `r,g,b` (0-255) -> RGB ints."""
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", text.strip())
    if match:
        value = match.group(1)
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    parts = text.split(",")
    if len(parts) == 3 and all(p.strip().isdigit() and int(p) <= 255 for p in parts):
        r, g, b = (int(p) for p in parts)
        return r, g, b
    raise ToolkitError(f"cannot read colour {text!r}.", "use #rrggbb (e.g. #ff8800) or r,g,b with 0-255 values.")


def tint_image(image: Image.Image, rgb: tuple[int, int, int]) -> Image.Image:
    """Multiply the colour channels by `rgb`/255 and keep alpha: what the game's `tint` field does at draw time."""
    rgba = image.convert("RGBA")
    red, green, blue, alpha = rgba.split()
    channels = [c.point(lambda v, k=k: round(v * k / 255)) for c, k in zip((red, green, blue), rgb, strict=True)]
    return Image.merge("RGBA", (*channels, alpha))


def first_level(image: Image.Image, size: int) -> Image.Image:
    """Top-left square of a base-game icon file (those hold the mipmap levels side by side), scaled to `size`."""
    if image.width < image.height:
        raise ToolkitError(
            f"icon image is {image.width}x{image.height}; an icon file is as wide as it is tall (or wider, with mipmaps).",
            "pass the icon PNG, e.g. __base__/graphics/icons/iron-plate.png from the game's data folder.",
        )
    level = image.convert("RGBA").crop((0, 0, image.height, image.height))
    return level if level.width == size else level.resize((size, size), Image.Resampling.LANCZOS)


def mip_strip_width(size: int, levels: int) -> int:
    """Width of an icon file holding `levels` levels, each half the previous, laid out left to right (height = size)."""
    return sum(size >> i for i in range(levels))


def mip_strip(level0: Image.Image, levels: int) -> Image.Image:
    size = level0.width
    if levels < 1 or (size >> (levels - 1)) < 1:
        raise ToolkitError(f"cannot hold {levels} mipmap levels in a {size}px icon.", f"use 1 to {size.bit_length()}.")
    strip = Image.new("RGBA", (mip_strip_width(size, levels), size))
    x = 0
    for i in range(levels):
        side = size >> i
        strip.paste(level0 if i == 0 else level0.resize((side, side), Image.Resampling.LANCZOS), (x, 0))
        x += side
    return strip


def compose_icon(base: Image.Image, badge: Image.Image, size: int, badge_scale: float, corner: str, levels: int) -> Image.Image:
    """Base icon with the badge in a corner, as a file of `levels` mipmap levels (1 = just the `size` x `size` image)."""
    if not 0 < badge_scale <= 1:
        raise ToolkitError(f"badge scale {badge_scale} is outside (0, 1].", "use a fraction of the icon size, e.g. 0.5.")
    icon = first_level(base, size).copy()
    side = max(1, round(size * badge_scale))
    mark = first_level(badge, side) if badge.height >= side else badge.convert("RGBA").resize((side, side), Image.Resampling.LANCZOS)
    vertical, horizontal = corner.split("-")
    x = size - side if horizontal == "right" else 0
    y = size - side if vertical == "bottom" else 0
    icon.alpha_composite(mark, (x, y))
    return mip_strip(icon, levels)


def icon_lua(filename: str, size: int, levels: int) -> str:
    if levels == 1:
        note = "-- one level: the game generates the mipmaps itself"
    else:
        note = f"-- the file holds {levels} mipmap levels ({mip_strip_width(size, levels)}x{size}); the game infers the count from the width"
    return f'icon = "{filename}",\nicon_size = {size},  {note}\n-- 2.x has no icon_mipmaps field (removed in 2.0.7, data/changelog.txt)'


# --- rung 2/3: sheet layout, shadow, Lua -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Layout:
    """Frames run left to right and wrap after `columns`; each direction owns `rows_per_direction` rows, stacked down."""

    frame_w: int
    frame_h: int
    frames: int
    directions: int
    columns: int

    @property
    def rows_per_direction(self) -> int:
        return math.ceil(self.frames / self.columns)

    @property
    def sheet_size(self) -> tuple[int, int]:
        return self.columns * self.frame_w, self.directions * self.rows_per_direction * self.frame_h

    def cell(self, direction: int, frame: int) -> tuple[int, int]:
        row = direction * self.rows_per_direction + frame // self.columns
        return (frame % self.columns) * self.frame_w, row * self.frame_h

    def direction_origin(self, direction: int) -> tuple[int, int]:
        return self.cell(direction, 0)


def plan_layout(frame_w: int, frame_h: int, frames: int, directions: int) -> Layout:
    """Choose the sheet layout, or refuse with the limit that is exceeded."""
    if directions not in DIRECTION_KEYS:
        raise ToolkitError(f"{directions} directions is not supported.", f"use one of {sorted(DIRECTION_KEYS)}.")
    if frames < 1 or frame_w < 1 or frame_h < 1:
        raise ToolkitError("frames and frame size must be at least 1.", "check --frames and --frame-size.")
    if max(frame_w, frame_h) > MAX_FRAME_SIDE:
        raise ToolkitError(
            f"a {frame_w}x{frame_h} px frame exceeds Factorio's {MAX_FRAME_SIDE}px limit per sprite or frame.",
            "lower --frame-size (see references/graphics-ladder.md, Limits).",
        )
    columns = min(frames, MAX_SHEET_SIDE // frame_w)
    layout = Layout(frame_w, frame_h, frames, directions, columns)
    sheet_w, sheet_h = layout.sheet_size
    if sheet_h > MAX_SHEET_SIDE:
        raise ToolkitError(
            f"{directions} directions x {frames} frames of {frame_w}x{frame_h} px need a {sheet_w}x{sheet_h} px sheet; "
            f"the limit is {MAX_SHEET_SIDE}px per side.",
            "reduce --frames or --frame-size, or render the directions as separate sheets in separate runs.",
        )
    return layout


def pack_sheet(frames: Sequence[Sequence[Image.Image]], layout: Layout) -> Image.Image:
    """`frames[direction][frame]` -> one sheet image laid out as `layout` describes."""
    sheet = Image.new("RGBA", layout.sheet_size)
    for d, row in enumerate(frames):
        for f, frame in enumerate(row):
            if frame.size != (layout.frame_w, layout.frame_h):
                raise ToolkitError(f"frame d{d} f{f} is {frame.width}x{frame.height}, expected {layout.frame_w}x{layout.frame_h}.", "re-run the render.")
            sheet.paste(frame, layout.cell(d, f))
    return sheet


def _opaque_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    return image.getchannel("A").point(lambda a: 255 if a >= ALPHA_THRESHOLD else 0).getbbox()


def require_drawn(frames: Sequence[Sequence[Image.Image]]) -> None:
    if not any(_opaque_bbox(f) for row in frames for f in row):
        raise ToolkitError("the render is empty: nothing was drawn in any frame.", "check that build() creates visible geometry on the ground plane in front of the camera.")


def alpha_centroid(frames: Sequence[Sequence[Image.Image]]) -> tuple[float, float]:
    """Alpha-weighted centre of mass of all frames, in pixels from the frame's top-left."""
    total = sx = sy = 0.0
    for row in frames:
        for frame in row:
            width = frame.width
            data = frame.getchannel("A").tobytes()
            for i, a in enumerate(data):
                if a:
                    total += a
                    sx += a * (i % width)
                    sy += a * (i // width)
    return (sx / total, sy / total) if total else (0.0, 0.0)


def clipped_frames(frames: Sequence[Sequence[Image.Image]]) -> list[tuple[int, int]]:
    """(direction, frame) of frames whose opaque pixels touch the frame edge, i.e. that were probably cut off."""
    clipped = []
    for d, row in enumerate(frames):
        for f, frame in enumerate(row):
            box = _opaque_bbox(frame)
            if box and (box[0] == 0 or box[1] == 0 or box[2] == frame.width or box[3] == frame.height):
                clipped.append((d, f))
    return clipped


def _lua_number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") if value else "0"


def _lua_layer(layout: Layout, filename: str, origin: tuple[int, int], shift: tuple[float, float], scale: float, speed: float, shadow: bool) -> str:
    fields = [f'filename = "{filename}"', 'priority = "high"', f"width = {layout.frame_w}", f"height = {layout.frame_h}", f"x = {origin[0]}", f"y = {origin[1]}"]
    if layout.frames > 1:
        fields += [f"frame_count = {layout.frames}", f"line_length = {layout.columns}", f"animation_speed = {_lua_number(speed)}"]
    fields += [f"scale = {_lua_number(scale)}", f"shift = {{{_lua_number(shift[0])}, {_lua_number(shift[1])}}}"]
    if shadow:
        fields.append("draw_as_shadow = true")
    return "{ " + ", ".join(fields) + " }"


def render_lua(
    name: str, layout: Layout, main_file: str, shadow_file: str | None, shift: tuple[float, float], scale: float, speed: float
) -> str:
    """A `Sprite4Way`/`Animation4Way`-shaped table (a single sprite or animation for one direction) with the shadow layer."""
    kind = "animation" if layout.frames > 1 else "sprite"
    var = f"{re.sub(r'[^0-9A-Za-z_]', '_', name)}_{kind}"  # `name` may be hyphenated; Lua identifiers cannot be
    lines = [f"local {var} = {{"]
    for d, key in enumerate(DIRECTION_KEYS[layout.directions]):
        origin = layout.direction_origin(d)
        layers = [_lua_layer(layout, main_file, origin, shift, scale, speed, False)]
        if shadow_file:
            layers.append(_lua_layer(layout, shadow_file, origin, shift, scale, speed, True))
        indent = "    " if key else "  "  # a direction key opens one more table level
        block = [f"{indent}layers = {{", *(f"{indent}  {layer}," for layer in layers), f"{indent}}},"]
        lines += [f"  {key} = {{", *block, "  },"] if key else block
    lines.append("}")
    return "\n".join(lines)


# --- Blender ---------------------------------------------------------------------------------------------------------

class RenderInfo(TypedDict):
    """What blender_scene.py reports in result.json."""

    model_height: float
    center_z: float
    frames: int
    directions: int
    blender: str


def run_blender(blender: Path, params: Mapping[str, object], work: Path, timeout: float) -> RenderInfo:
    """Run `blender_scene.py` headless once for the whole job; return its result.json."""
    work.mkdir(parents=True, exist_ok=True)
    params_file = work / "params.json"
    params_file.write_text(json.dumps({**params, "out_dir": str(work)}), "utf-8")
    command = [str(blender), "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(BLENDER_SCENE), "--", str(params_file)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ToolkitError(f"Blender did not finish within {timeout:.0f}s.", "reduce --frames/--frame-size or raise --timeout.") from exc
    except OSError as exc:
        raise ToolkitError(f"could not start {blender}: {exc}", "check BLENDER_PATH and that the executable is not blocked by antivirus.") from exc
    result_file = work / "result.json"
    if proc.returncode != 0 or not result_file.is_file():
        excerpt = "\n".join(f"    | {line}" for line in (proc.stdout + proc.stderr).strip().splitlines()[-15:])
        raise ToolkitError(
            f"Blender exited with code {proc.returncode} before finishing the render. Last output:\n{excerpt}",
            "fix the error shown above (a model-script exception names its line); re-run with the same arguments.",
        )
    info: RenderInfo = json.loads(result_file.read_text("utf-8"))
    return info


# --- subcommands ---------------------------------------------------------------------------------------------------------

def load_frames(directory: Path, prefix: str, directions: int, frames: int) -> list[list[Image.Image]]:
    """Read Blender's `<prefix><direction>_f<frame>.png` files into memory (the temp folder is deleted afterwards)."""
    return [[Image.open(directory / f"{prefix}{d}_f{f}.png").convert("RGBA") for f in range(frames)] for d in range(directions)]


def _open_png(path: Path) -> Image.Image:
    if not path.is_file():
        raise ToolkitError(f"{path} does not exist.", "check the path; base-game icons live under <game>/data/base/graphics/icons/.")
    try:
        return Image.open(path)
    except OSError as exc:
        raise ToolkitError(f"{path} is not a readable image ({exc}).", "pass a PNG file.") from exc


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")


def cmd_tint(args: argparse.Namespace) -> int:
    source = _open_png(args.input)
    rgb = parse_color(args.color)
    result = tint_image(source, rgb)
    _save(result, args.output)
    r, g, b = (round(c / 255, 3) for c in rgb)
    print(f"wrote {args.output} ({result.width}x{result.height})")
    print(f"in-prototype alternative (no new file): tint = {{r = {r}, g = {g}, b = {b}}} on the base-game sprite")
    return 0


def cmd_icon(args: argparse.Namespace) -> int:
    icon = compose_icon(_open_png(args.base), _open_png(args.badge), args.size, args.badge_scale, args.corner, args.mipmaps)
    _save(icon, args.output)
    filename = f"__{args.mod_name}__/{args.lua_dir}/{args.output.name}"
    print(f"wrote {args.output} ({icon.width}x{icon.height}, {args.mipmaps} mipmap level(s))")
    print(icon_lua(filename, args.size, args.mipmaps))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    if bool(args.model) == bool(args.blend):
        raise ToolkitError("give exactly one of --model (a model script) or --blend (an existing .blend file).", "see --help for both.")
    source = args.model or args.blend
    if not source.is_file():
        raise ToolkitError(f"{source} does not exist.", "check the path.")
    if args.save_blend and not args.model:
        raise ToolkitError("--save-blend saves a model built by --model; there is nothing to save with --blend.", "drop --save-blend.")
    if not args.no_shadow and (args.shadow_x <= 0 or args.shadow_y <= 0):
        raise ToolkitError("--shadow-x and --shadow-y must be greater than 0.", "the shadow is cast toward the bottom-right; use e.g. 0.4 and 0.15, or --no-shadow.")
    layout = plan_layout(args.frame_size, args.frame_size, args.frames, args.directions)  # refuse oversize jobs before the 10 s Blender start
    blender = find_blender()
    params = {
        "model": str(args.model.resolve()) if args.model else None,
        "blend": str(args.blend.resolve()) if args.blend else None,
        "save_blend": str(args.save_blend.resolve()) if args.save_blend else None,
        "directions": args.directions, "frames": args.frames, "frame_px": args.frame_size,
        "px_per_tile": args.px_per_tile, "elevation_deg": args.elevation, "center_z": args.center_z,
        "shadow_reach": None if args.no_shadow else [args.shadow_x, -args.shadow_y],  # world +y is up-screen, so down is negative
    }
    if args.save_blend:
        args.save_blend.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fm-render-") as tmp:
        info = run_blender(blender, params, Path(tmp), args.timeout)
        main_frames = load_frames(Path(tmp), "d", args.directions, args.frames)
        shadow_frames = [] if args.no_shadow else load_frames(Path(tmp), "s", args.directions, args.frames)
    scale = TILE_PX_AT_SCALE_1 / args.px_per_tile
    center_z = info["center_z"]
    shift = (0.0, -center_z * math.cos(math.radians(args.elevation)))  # ground point under the entity sits this far below frame centre

    require_drawn(main_frames)
    out_main = args.out / f"{args.name}.png"
    _save(pack_sheet(main_frames, layout), out_main)
    lines = [f"frame {layout.frame_w}x{layout.frame_h} px; {args.directions} direction(s) x {args.frames} frame(s)",
             f"layout: {layout.columns} column(s) x {layout.rows_per_direction} row(s) per direction, directions stacked down; "
             f"sheet {layout.sheet_size[0]}x{layout.sheet_size[1]} px (limits: {MAX_FRAME_SIDE} per frame, {MAX_SHEET_SIDE} per sheet side)",
             f"main sheet: {out_main}"]
    shadow_file: str | None = None
    if not args.no_shadow:
        out_shadow = args.out / f"{args.name}-shadow.png"
        _save(pack_sheet(shadow_frames, layout), out_shadow)
        shadow_file = f"__{args.mod_name}__/{args.lua_dir}/{out_shadow.name}"
        (cx, cy), (sx, sy) = alpha_centroid(main_frames), alpha_centroid(shadow_frames)
        lines += [f"shadow sheet: {out_shadow}", f"shadow centroid vs model: {sx - cx:+.1f} px right, {sy - cy:+.1f} px down"]
        lines += [f"warning: shadow of d{d} f{f} is cut off by the frame edge; raise --frame-size" for d, f in clipped_frames(shadow_frames)[:3]]
    lines += [f"warning: model of d{d} f{f} is cut off by the frame edge; raise --frame-size" for d, f in clipped_frames(main_frames)[:3]]
    lua = render_lua(args.name, layout, f"__{args.mod_name}__/{args.lua_dir}/{out_main.name}", shadow_file, shift, scale, args.animation_speed)
    lua_file = args.out / f"{args.name}.lua"
    lua_file.write_text(lua + "\n", "utf-8")
    lines += [f"camera: orthographic, elevation {args.elevation} deg, {args.px_per_tile} px/tile -> scale {_lua_number(scale)}, "
              f"model height {info['model_height']:.2f} tiles",
              f"lua: {lua_file}", "", lua]
    print("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    tint = sub.add_parser("tint", help="recolour a PNG (multiply)")
    tint.add_argument("input", type=Path, help="source PNG, e.g. a sprite from <game>/data/base/graphics")
    tint.add_argument("output", type=Path)
    tint.add_argument("--color", required=True, help="#rrggbb or r,g,b (0-255)")
    tint.set_defaults(handler=cmd_tint)

    icon = sub.add_parser("icon", help="composite an icon from a base icon and a badge")
    icon.add_argument("base", type=Path, help="base icon PNG (its first mipmap level is used)")
    icon.add_argument("badge", type=Path, help="badge PNG drawn over a corner (e.g. another base icon)")
    icon.add_argument("output", type=Path)
    icon.add_argument("--mod-name", required=True, help="mod name, for the __mod__/ path in the Lua snippet")
    icon.add_argument("--lua-dir", default="graphics/icons", help="folder of the output inside the mod (default: %(default)s)")
    icon.add_argument("--size", type=int, default=64, help="icon size in px (default: %(default)s)")
    icon.add_argument("--badge-scale", type=float, default=0.5, help="badge size as a fraction of the icon (default: %(default)s)")
    icon.add_argument("--corner", choices=["top-left", "top-right", "bottom-left", "bottom-right"], default="bottom-right")
    icon.add_argument("--mipmaps", type=int, default=1, help="mipmap levels stored in the file, 1 = plain icon (base-game icons use 4; default: %(default)s)")
    icon.set_defaults(handler=cmd_icon)

    render = sub.add_parser("render", help="render a Blender model to a sheet and a shadow sheet, and print the Lua")
    render.add_argument("--model", type=Path, help="model script run inside Blender (defines build() and optionally animate(t)); see blender/example_model.py")
    render.add_argument("--blend", type=Path, help="an existing .blend file to render instead (rung 3)")
    render.add_argument("--save-blend", type=Path, help="save the built model here so it can be re-rendered later with --blend")
    render.add_argument("--name", required=True, help="sprite name: files <name>.png, <name>-shadow.png, <name>.lua")
    render.add_argument("--mod-name", required=True, help="mod name, for the __mod__/ paths in the Lua")
    render.add_argument("--out", type=Path, required=True, help="folder for the PNGs; this should be the mod folder + --lua-dir")
    render.add_argument("--lua-dir", default="graphics/entity", help="folder of the PNGs inside the mod (default: %(default)s)")
    render.add_argument("--directions", type=int, default=4, choices=sorted(DIRECTION_KEYS), help="1, 4 (N,E,S,W) or 8 (default: %(default)s)")
    render.add_argument("--frames", type=int, default=1, help="animation frames per direction (default: %(default)s)")
    render.add_argument("--frame-size", type=int, default=256, help="square frame side in px; must fit the model and its shadow (default: %(default)s)")
    render.add_argument("--px-per-tile", type=int, default=64, help="render resolution; 64 matches base-game 2.x sprites at scale 0.5 (default: %(default)s)")
    render.add_argument("--elevation", type=float, default=60.0, help="camera angle above the horizon in degrees (default: %(default)s)")
    render.add_argument("--center-z", type=float, help="world height the camera looks at (default: half the model height)")
    render.add_argument("--shadow-x", type=float, default=0.4, help="shadow reach to the right, in tiles per tile of height (default: %(default)s)")
    render.add_argument("--shadow-y", type=float, default=0.15, help="shadow reach down the screen, in tiles per tile of height (default: %(default)s)")
    render.add_argument("--no-shadow", action="store_true", help="skip the shadow sheet")
    render.add_argument("--animation-speed", type=float, default=0.5, help="animation_speed written to the Lua (default: %(default)s)")
    render.add_argument("--timeout", type=float, default=600, help="seconds to wait for Blender (default: %(default)s)")
    render.set_defaults(handler=cmd_render)
    return parser


def main(argv: Sequence[str]) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    cli_main(main)
