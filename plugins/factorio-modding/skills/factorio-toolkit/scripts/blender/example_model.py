# Example rung-2 model script: runs inside Blender via `sprites.py render --model blender/example_model.py`.
# A 3x3-tile machine with a front marker and a rotating arm. Copy it and change the geometry.
"""A model script defines build() and optionally animate(t); see blender_scene.py for the contract."""

import math

import bpy


def material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1.0)  # the Workbench renderer uses this as the base colour
    return mat


def box(name, size, location, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name, obj.scale = name, size
    obj.data.materials.append(mat)
    return obj


parts = {}


def build():
    steel, paint, accent = material("steel", (0.55, 0.57, 0.6)), material("paint", (0.78, 0.55, 0.12)), material("front", (0.8, 0.1, 0.1))
    box("base", (2.7, 2.7, 0.7), (0, 0, 0.35), steel)
    box("front_marker", (1.0, 0.25, 0.3), (0, 1.25, 0.85), accent)  # +Y is the entity's front (north)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.6, location=(0, 0, 1.0))
    pedestal = bpy.context.active_object
    pedestal.name = "pedestal"
    pedestal.data.materials.append(paint)
    parts["arm"] = box("arm", (2.0, 0.4, 0.3), (0, 0, 1.45), paint)


def animate(t):
    parts["arm"].rotation_euler = (0.0, 0.0, t * math.pi / 2)  # the arm is symmetric every 90 degrees, so the loop closes
