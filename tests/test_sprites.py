"""Tests for scripts/sprites.py: tint, icon, sheet layout and limits, shadow, Lua, Blender launcher, and a real render."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageChops

import sprites
from _lib.errors import ToolkitError

SCRIPTS = Path(sprites.__file__).resolve().parent


def solid(size: tuple[int, int], rgba: tuple[int, int, int, int]) -> Image.Image:
    return Image.new("RGBA", size, rgba)


def png(path: Path, image: Image.Image) -> Path:
    image.save(path)
    return path


# --- tint -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [("#ff8000", (255, 128, 0)), ("00ff10", (0, 255, 16)), ("10, 20,30", (10, 20, 30))])
def test_parse_color(text: str, expected: tuple[int, int, int]) -> None:
    assert sprites.parse_color(text) == expected


@pytest.mark.parametrize("text", ["red", "#12345", "1,2", "300,0,0"])
def test_parse_color_rejects_garbage(text: str) -> None:
    with pytest.raises(ToolkitError, match="cannot read colour"):
        sprites.parse_color(text)


def test_tint_multiplies_colour_and_keeps_alpha() -> None:
    out = sprites.tint_image(solid((2, 2), (200, 100, 50, 128)), (255, 128, 0))
    assert out.getpixel((0, 0)) == (200, 50, 0, 128)


def test_tint_cli_writes_png_and_prints_lua_alternative(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = png(tmp_path / "in.png", solid((4, 3), (255, 255, 255, 255)))
    assert sprites.main(["tint", str(src), str(tmp_path / "out.png"), "--color", "#ff0000"]) == 0
    assert Image.open(tmp_path / "out.png").getpixel((1, 1)) == (255, 0, 0, 255)
    assert "tint = {r = 1.0, g = 0.0, b = 0.0}" in capsys.readouterr().out


def test_missing_input_names_the_path(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError, match="nope.png does not exist"):
        sprites.main(["tint", str(tmp_path / "nope.png"), str(tmp_path / "o.png"), "--color", "#fff"])


# --- icon -------------------------------------------------------------------------------------------------------------

def base_icon_with_mipmaps() -> Image.Image:
    """Like a base-game icon file: 64px level 0 (red) then 32/16/8px levels (blue) side by side, 120x64."""
    strip = Image.new("RGBA", (120, 64))
    strip.paste(solid((64, 64), (255, 0, 0, 255)), (0, 0))
    strip.paste(solid((56, 64), (0, 0, 255, 255)), (64, 0))
    return strip


def test_first_level_ignores_mipmaps_in_the_file() -> None:
    level = sprites.first_level(base_icon_with_mipmaps(), 64)
    assert level.size == (64, 64) and level.getpixel((63, 63)) == (255, 0, 0, 255)


def test_first_level_rejects_a_tall_image() -> None:
    with pytest.raises(ToolkitError, match="as wide as it is tall"):
        sprites.first_level(solid((8, 16), (0, 0, 0, 255)), 64)


def test_compose_places_badge_in_corner_and_file_is_64x64() -> None:
    badge = solid((64, 64), (0, 255, 0, 255))
    icon = sprites.compose_icon(base_icon_with_mipmaps(), badge, 64, 0.5, "bottom-right", 1)
    assert icon.size == (64, 64)
    assert icon.getpixel((10, 10)) == (255, 0, 0, 255)
    assert icon.getpixel((50, 50)) == (0, 255, 0, 255)


@pytest.mark.parametrize("levels", [1, 2, 4, 5])
def test_mip_strip_width_is_sum_of_halvings_and_height_is_icon_size(levels: int) -> None:
    icon = sprites.compose_icon(solid((64, 64), (9, 9, 9, 255)), solid((16, 16), (1, 1, 1, 255)), 64, 0.25, "top-left", levels)
    assert icon.size == (sum(64 >> i for i in range(levels)), 64)
    assert icon.size == (sprites.mip_strip_width(64, levels), 64)


def test_vanilla_four_level_icon_is_120_wide() -> None:
    assert sprites.mip_strip_width(64, 4) == 120  # base/graphics/icons/iron-plate.png is 120x64


def test_icon_lua_declares_what_the_file_holds() -> None:
    assert "icon_size = 64" in sprites.icon_lua("__m__/i.png", 64, 1)
    assert "4 mipmap levels (120x64)" in sprites.icon_lua("__m__/i.png", 64, 4)
    assert "icon_mipmaps =" not in sprites.icon_lua("__m__/i.png", 64, 4).replace("no icon_mipmaps field", "")


def test_icon_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = png(tmp_path / "base.png", base_icon_with_mipmaps())
    badge = png(tmp_path / "badge.png", solid((32, 32), (0, 255, 0, 255)))
    out = tmp_path / "icons" / "x.png"
    assert sprites.main(["icon", str(base), str(badge), str(out), "--mod-name", "m", "--mipmaps", "4"]) == 0
    assert Image.open(out).size == (120, 64)
    assert 'icon = "__m__/graphics/icons/x.png"' in capsys.readouterr().out


def test_icon_rejects_bad_badge_scale(tmp_path: Path) -> None:
    base = png(tmp_path / "b.png", solid((64, 64), (0, 0, 0, 255)))
    with pytest.raises(ToolkitError, match="badge scale"):
        sprites.main(["icon", str(base), str(base), str(tmp_path / "o.png"), "--mod-name", "m", "--badge-scale", "2"])


# --- layout and limits ----------------------------------------------------------------------------------------------

def test_layout_single_row_directions_stacked() -> None:
    layout = sprites.plan_layout(256, 256, 2, 4)
    assert (layout.columns, layout.rows_per_direction, layout.sheet_size) == (2, 1, (512, 1024))
    assert layout.cell(2, 1) == (256, 512)
    assert layout.direction_origin(3) == (0, 768)


def test_layout_wraps_frames_at_the_sheet_width_limit() -> None:
    layout = sprites.plan_layout(1024, 100, 20, 1)
    assert layout.columns == 8 and layout.rows_per_direction == 3
    assert layout.sheet_size == (8192, 300)
    assert layout.cell(0, 9) == (1024, 100)


def test_frame_over_4096_is_refused() -> None:
    with pytest.raises(ToolkitError, match="4096px limit"):
        sprites.plan_layout(4097, 64, 1, 1)


def test_sheet_over_8192_high_is_refused_naming_the_numbers() -> None:
    with pytest.raises(ToolkitError, match=r"4 directions x 80 frames of 512x512 px need a 8192x10240 px sheet"):
        sprites.plan_layout(512, 512, 80, 4)


def test_unsupported_direction_count() -> None:
    with pytest.raises(ToolkitError, match="3 directions is not supported"):
        sprites.plan_layout(64, 64, 1, 3)


def test_pack_sheet_puts_each_frame_in_its_cell() -> None:
    layout = sprites.plan_layout(4, 4, 2, 4)
    colours = [[(d * 60, f * 100, 7, 255) for f in range(2)] for d in range(4)]
    sheet = sprites.pack_sheet([[solid((4, 4), c) for c in row] for row in colours], layout)
    assert sheet.size == layout.sheet_size == (8, 16)
    for d in range(4):
        for f in range(2):
            x, y = layout.cell(d, f)
            assert sheet.getpixel((x + 1, y + 1)) == colours[d][f]


def test_pack_sheet_rejects_wrong_frame_size() -> None:
    with pytest.raises(ToolkitError, match="expected 4x4"):
        sprites.pack_sheet([[solid((5, 4), (0, 0, 0, 255))]], sprites.plan_layout(4, 4, 1, 1))


# --- frame checks -----------------------------------------------------------------------------------------------------

def test_shadow_centroid_is_measured_in_pixels_from_top_left() -> None:
    left, right = Image.new("RGBA", (10, 10)), Image.new("RGBA", (10, 10))
    left.paste(solid((2, 2), (0, 0, 0, 255)), (0, 0))
    right.paste(solid((2, 2), (0, 0, 0, 255)), (6, 4))
    (lx, ly), (rx, ry) = sprites.alpha_centroid([[left]]), sprites.alpha_centroid([[right]])
    assert (rx - lx, ry - ly) == pytest.approx((6, 4))


def test_empty_render_is_reported() -> None:
    with pytest.raises(ToolkitError, match="render is empty"):
        sprites.require_drawn([[Image.new("RGBA", (8, 8))]])


def test_clipped_frames_flags_content_on_the_edge() -> None:
    edge = Image.new("RGBA", (8, 8))
    edge.paste(solid((8, 2), (0, 0, 0, 255)), (0, 0))
    assert sprites.clipped_frames([[edge, Image.new("RGBA", (8, 8))]]) == [(0, 0)]


# --- Lua --------------------------------------------------------------------------------------------------------------

def test_lua_for_a_four_way_animation_with_shadow() -> None:
    layout = sprites.plan_layout(256, 256, 2, 4)
    lua = sprites.render_lua("box", layout, "__m__/graphics/entity/box.png", "__m__/graphics/entity/box-shadow.png", (0, -0.4), 0.5, 0.5)
    assert lua.startswith("local box_animation = {")
    for key in ("north", "east", "south", "west"):
        assert f"  {key} = {{" in lua
    assert "y = 768" in lua  # west block starts three direction-rows down
    assert 'filename = "__m__/graphics/entity/box.png", priority = "high", width = 256, height = 256, x = 0, y = 256, frame_count = 2, line_length = 2' in lua
    assert "shift = {0, -0.4}" in lua and "scale = 0.5" in lua
    assert lua.count("draw_as_shadow = true") == 4 and lua.count("box-shadow.png") == 4


def test_lua_for_a_single_static_sprite_has_no_animation_fields() -> None:
    lua = sprites.render_lua("box", sprites.plan_layout(64, 64, 1, 1), "__m__/a.png", None, (0, 0), 0.5, 1)
    assert lua.startswith("local box_sprite = {") and "layers = {" in lua
    assert "frame_count" not in lua and "draw_as_shadow" not in lua and "north" not in lua


def test_lua_eight_way_uses_factorio_direction_order() -> None:
    lua = sprites.render_lua("t", sprites.plan_layout(8, 8, 1, 8), "__m__/a.png", None, (0, 0), 0.5, 1)
    order = [lua.index(f"  {k} = {{") for k in ("north", "north_east", "east", "south_east", "south", "south_west", "west", "north_west")]
    assert order == sorted(order)


# --- Blender discovery and launcher ----------------------------------------------------------------------------------

def test_find_blender_honours_blender_path(tmp_path: Path) -> None:
    exe = tmp_path / "blender.exe"
    exe.write_text("")
    assert sprites.find_blender({"BLENDER_PATH": str(exe)}) == exe
    assert sprites.find_blender({"BLENDER_PATH": str(tmp_path)}) == exe


def test_find_blender_bad_blender_path_is_named(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError, match="BLENDER_PATH is .*not a Blender executable"):
        sprites.find_blender({"BLENDER_PATH": str(tmp_path / "gone.exe")})


def test_find_blender_picks_newest_standard_install(tmp_path: Path) -> None:
    for version in ("Blender 4.2", "Blender 5.2", "Blender 5.10"):
        exe = tmp_path / "Blender Foundation" / version / "blender.exe"
        exe.parent.mkdir(parents=True)
        exe.write_text("")
    found = sprites.find_blender({"ProgramFiles": str(tmp_path), "PATH": ""})
    assert found.parent.name == "Blender 5.10"


def test_missing_blender_message_names_the_fix(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError) as caught:
        sprites.find_blender({"PATH": "", "ProgramFiles": str(tmp_path)})
    assert "BLENDER_PATH" in str(caught.value.hint) and "blender.org" in str(caught.value.hint)


def test_blender_crash_becomes_an_error_with_the_output_excerpt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def crash(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 1, "", "Traceback (most recent call last):\nRuntimeError: the model script must define build()")

    monkeypatch.setattr(sprites.subprocess, "run", crash)
    with pytest.raises(ToolkitError, match=r"(?s)exited with code 1.*must define build"):
        sprites.run_blender(Path("blender.exe"), {"frames": 1}, tmp_path, 5)


def test_blender_that_exits_zero_without_result_is_still_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sprites.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 0, "ok", ""))
    with pytest.raises(ToolkitError, match="before finishing the render"):
        sprites.run_blender(Path("blender.exe"), {}, tmp_path, 5)


def test_blender_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired("blender", 5)

    monkeypatch.setattr(sprites.subprocess, "run", hang)
    with pytest.raises(ToolkitError, match="did not finish within 5s"):
        sprites.run_blender(Path("blender.exe"), {}, tmp_path, 5)


# --- render argument errors (no Blender needed) ------------------------------------------------------------------------

def render_args(tmp_path: Path, *extra: str) -> list[str]:
    return ["render", "--name", "box", "--mod-name", "m", "--out", str(tmp_path / "out"), *extra]


def test_render_needs_exactly_one_input(tmp_path: Path) -> None:
    with pytest.raises(ToolkitError, match="exactly one of --model"):
        sprites.main(render_args(tmp_path))


def test_render_refuses_oversize_job_before_starting_blender(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model = tmp_path / "m.py"
    model.write_text("")
    monkeypatch.setattr(sprites, "find_blender", lambda *_: pytest.fail("Blender must not be looked up for a refused job"))
    with pytest.raises(ToolkitError, match="need a .* sheet"):
        sprites.main(render_args(tmp_path, "--model", str(model), "--frames", "80", "--frame-size", "512"))


@pytest.mark.parametrize("flag", ["--shadow-x", "--shadow-y"])
def test_shadow_must_point_bottom_right(tmp_path: Path, flag: str) -> None:
    model = tmp_path / "m.py"
    model.write_text("")
    with pytest.raises(ToolkitError, match="must be greater than 0"):
        sprites.main(render_args(tmp_path, "--model", str(model), flag, "-0.2"))


def test_save_blend_requires_a_model(tmp_path: Path) -> None:
    blend = tmp_path / "a.blend"
    blend.write_text("")
    with pytest.raises(ToolkitError, match="--save-blend saves a model"):
        sprites.main(render_args(tmp_path, "--blend", str(blend), "--save-blend", str(tmp_path / "b.blend")))


# --- real Blender -----------------------------------------------------------------------------------------------------

@pytest.mark.blender
def test_render_model_then_rerender_saved_blend(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    common = ["--mod-name", "m", "--directions", "4", "--frames", "2", "--frame-size", "96", "--px-per-tile", "32"]
    saved = tmp_path / "model.blend"
    first, second = tmp_path / "a", tmp_path / "b"
    model = SCRIPTS / "blender" / "example_model.py"
    assert sprites.main(["render", "--name", "box", "--out", str(first), "--model", str(model), "--save-blend", str(saved), *common]) == 0
    assert saved.is_file()
    sheet = Image.open(first / "box.png")
    assert sheet.size == (2 * 96, 4 * 96)
    assert Image.open(first / "box-shadow.png").size == sheet.size
    lua = (first / "box.lua").read_text("utf-8")
    assert "frame_count = 2" in lua and "draw_as_shadow = true" in lua
    out = capsys.readouterr().out
    assert "shadow centroid vs model: +" in out and "px right, +" in out  # right of and below the model
    shadow = Image.open(first / "box-shadow.png")
    alpha, red = shadow.getchannel("A"), shadow.getchannel("R")
    assert alpha.getextrema()[1] > 200 and ImageChops.multiply(red, alpha.point(lambda a: 255 if a else 0)).getextrema() == (0, 0)  # solid black

    assert sprites.main(["render", "--name", "box", "--out", str(second), "--blend", str(saved), *common]) == 0
    assert Image.open(second / "box.png").tobytes() == sheet.tobytes()  # the saved model replays the same pictures


@pytest.mark.blender
def test_model_script_error_surfaces_as_toolkit_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def build():\n    raise RuntimeError('boom from the model')\n")
    with pytest.raises(ToolkitError, match="boom from the model"):
        sprites.main(render_args(tmp_path, "--model", str(bad), "--frame-size", "32", "--px-per-tile", "32"))
