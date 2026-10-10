# This script runs INSIDE Blender's bundled Python (`blender -b --python blender_scene.py -- params.json`).
# It imports `bpy`, so it is exempt from the uv / Python 3.15 rules; `sprites.py render` is its launcher.
"""Build (or open) a model, then render it from a fixed orthographic camera: N directions x M frames.

Model contract (rung 2): the model script defines `build()` and, optionally, `animate(t)`.
  - Geometry sits on the z=0 ground plane, centred on the origin, front facing +Y ("north" on screen).
    Give materials a `diffuse_color`; the Workbench renderer shows exactly that colour, shaded.
  - `animate(t)` poses the parts for loop position t in [0, 1); frame i of M gets t = i / M. The poses are
    baked into keyframes so a saved .blend replays the same animation (rung 3).
Rung 3 opens a .blend as-is: the pipeline replaces its cameras and lights and samples its frame range.

Direction d rotates the model about z by -360/N * d degrees (clockwise from above), so north, east, south,
west for N=4. The camera and lighting never move, so shading and the shadow stay consistent between directions.
Shadow: a second pass draws every mesh flattened onto the ground along a fixed light direction (a point at height z
moves by (reach_x * z, reach_y * z) on the ground), in solid black, from the same camera.
Output: d{direction}_f{frame}.png and s{direction}_f{frame}.png (shadow), RGBA with a transparent background, plus
result.json in the output directory.
"""

import json
import math
import os
import runpy
import sys

import bpy
from mathutils import Matrix, Vector

CAMERA_DISTANCE = 40.0


def load_params():
    with open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8") as handle:
        return json.load(handle)


def keyable_objects():
    return [o for o in bpy.context.scene.objects if o.type in {"MESH", "EMPTY", "CURVE", "SURFACE", "META", "FONT"}]


def bake_animation(animate, frames):
    scene = bpy.context.scene
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "CONSTANT"  # discrete poses, not a sweep
    scene.frame_start, scene.frame_end = 1, max(frames, 1)
    for i in range(frames):
        scene.frame_set(i + 1)
        animate(i / frames)
        for obj in keyable_objects():
            for path in ("location", "rotation_euler", "scale"):
                obj.keyframe_insert(path, frame=i + 1)


def clear_cameras_and_lights():
    for obj in list(bpy.data.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)


def parent_under_root(scene):
    root = bpy.data.objects.new("fms_root", None)
    scene.collection.objects.link(root)
    for obj in list(scene.objects):
        if obj is not root and obj.parent is None:
            obj.parent = root
    return root


def model_height(scene, frame_numbers):
    """Highest z of any mesh over the sampled frames, in world space."""
    top = 0.0
    for frame in frame_numbers:
        scene.frame_set(frame)
        for obj in scene.objects:
            if obj.type == "MESH":
                top = max(top, max((obj.matrix_world @ Vector(c)).z for c in obj.bound_box))
    return top


def add_camera(scene, frame_px, px_per_tile, elevation_deg, target_z):
    elevation = math.radians(elevation_deg)
    cam_data = bpy.data.cameras.new("fms_camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = frame_px / px_per_tile
    cam_data.clip_start, cam_data.clip_end = 0.1, 200.0
    cam = bpy.data.objects.new("fms_camera", cam_data)
    scene.collection.objects.link(cam)
    view = Vector((0.0, math.cos(elevation), -math.sin(elevation)))
    cam.location = Vector((0.0, 0.0, target_z)) - view * CAMERA_DISTANCE
    cam.rotation_euler = (math.radians(90.0 - elevation_deg), 0.0, 0.0)
    scene.camera = cam


def configure_render(scene, frame_px):
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = frame_px
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.dither_intensity = 0.0
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.display.render_aa = "8"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    shading.use_world_space_lighting = True
    shading.show_shadows = False
    shading.show_cavity = False


def render_shadow(scene, reach, path):
    """Render the ground projection of the posed model as a black silhouette."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    flatten = Matrix(((1, 0, reach[0], 0), (0, 1, reach[1], 0), (0, 0, 0, 0), (0, 0, 0, 1)))
    black = bpy.data.materials.new("fms_shadow")
    black.diffuse_color = (0.0, 0.0, 0.0, 1.0)
    originals = [o for o in scene.objects if o.type == "MESH"]
    shadows = []
    for obj in originals:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated)
        mesh.transform(flatten @ evaluated.matrix_world)
        mesh.materials.clear()
        mesh.materials.append(black)
        shadow = bpy.data.objects.new("fms_shadow_" + obj.name, mesh)
        scene.collection.objects.link(shadow)
        shadows.append(shadow)
        obj.hide_render = True
    scene.display.shading.light = "FLAT"  # studio lighting adds specular highlights to black
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    scene.display.shading.light = "STUDIO"
    for obj in originals:
        obj.hide_render = False
    for shadow in shadows:
        mesh = shadow.data
        bpy.data.objects.remove(shadow, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    bpy.data.materials.remove(black)


def main():
    params = load_params()
    out_dir = params["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    frames, directions = params["frames"], params["directions"]

    if params.get("blend"):
        bpy.ops.wm.open_mainfile(filepath=params["blend"])
        clear_cameras_and_lights()
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        namespace = runpy.run_path(params["model"])
        if "build" not in namespace:
            raise RuntimeError("the model script must define build()")
        namespace["build"]()
        if "animate" in namespace:
            bake_animation(namespace["animate"], frames)
        if params.get("save_blend"):
            bpy.ops.wm.save_as_mainfile(filepath=params["save_blend"], copy=True)

    scene = bpy.context.scene
    start, end = scene.frame_start, scene.frame_end
    span = end - start + 1
    sampled = [start + (i * span) // frames for i in range(frames)]
    root = parent_under_root(scene)
    height = model_height(scene, sampled)
    target_z = params["center_z"] if params.get("center_z") is not None else height / 2.0

    configure_render(scene, params["frame_px"])
    add_camera(scene, params["frame_px"], params["px_per_tile"], params["elevation_deg"], target_z)
    for d in range(directions):
        root.rotation_euler = (0.0, 0.0, -math.radians(360.0 / directions * d))
        for f, frame in enumerate(sampled):
            scene.frame_set(frame)
            scene.render.filepath = os.path.join(out_dir, f"d{d}_f{f}.png")
            bpy.ops.render.render(write_still=True)
            if params.get("shadow_reach"):
                render_shadow(scene, params["shadow_reach"], os.path.join(out_dir, f"s{d}_f{f}.png"))

    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as handle:
        json.dump({"model_height": height, "center_z": target_z, "frames": frames, "directions": directions,
                   "blender": bpy.app.version_string}, handle)


main()
