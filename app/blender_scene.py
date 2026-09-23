"""Blender background entrypoint for constrained, animated chemistry scenes.

Called only by app.renderer with a server-written JSON specification after `--`.
This file runs inside Blender's Python and intentionally has no project imports.
"""

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def material(name, rgb, metallic=0.08, glow=0.0):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*rgb, 1)
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*rgb, 1)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = 0.27
    if glow and "Emission Color" in shader.inputs:
        shader.inputs["Emission Color"].default_value = (*rgb, 1)
        shader.inputs["Emission Strength"].default_value = glow
    return result


def sphere(name, where, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=where)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def rod(name, start, end, radius, mat):
    start, end = Vector(start), Vector(end)
    direction = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=direction.length,
                                        location=(start + end) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def ring(name, where, radius, thickness, mat):
    bpy.ops.mesh.primitive_torus_add(major_segments=48, minor_segments=8,
                                     major_radius=radius, minor_radius=thickness, location=where)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def move(obj, points):
    for frame, where in points:
        obj.location = where
        obj.keyframe_insert(data_path="location", frame=frame)


def scale(obj, points):
    for frame, value in points:
        obj.scale = (value, value, value)
        obj.keyframe_insert(data_path="scale", frame=frame)


def atom_material(label, fallback):
    label = label.lower()
    if any(x in label for x in ("oxygen", "oxide")):
        return RED
    if "hydrogen" in label:
        return WHITE
    if any(x in label for x in ("chlor", "cl−", "cl-")):
        return GREEN
    if any(x in label for x in ("sodium", "na+", "na⁺")):
        return BLUE
    if "carbon" in label:
        return GRAY
    return fallback


def stage():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    world = bpy.data.worlds.new("Deep navy studio")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.012, 0.025, 0.056, 1)
    background.inputs["Strength"].default_value = 0.6

    floor = material("studio floor", (0.019, 0.043, 0.084), metallic=0.32)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -2.0))
    bpy.context.object.data.materials.append(floor)
    for x in (-4, 0, 4):
        ring("stage marker", (x, 0, -1.96), 1.65, 0.012, GRID)

    bpy.ops.object.camera_add(location=(0, -13.5, 4.1))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 10.8
    scene.camera = camera
    for where, power, size in [((-5, -6, 8), 1400, 7), ((5, 2, 7), 1100, 6)]:
        bpy.ops.object.light_add(type="AREA", location=where)
        light = bpy.context.object
        light.data.energy = power
        light.data.shape = "DISK"
        light.data.size = size
    return scene


def electron_share(last, labels):
    left = sphere("first atom", (-2.3, 0, 0), 0.78, atom_material(labels[0], CYAN))
    right = sphere("second atom", (2.3, 0, 0), 0.78, atom_material(labels[-1], PURPLE))
    move(left, [(1, (-2.3, 0, 0)), (last, (-1.55, 0, 0))])
    move(right, [(1, (2.3, 0, 0)), (last, (1.55, 0, 0))])
    bond = rod("forming covalent bond", (-0.9, 0, 0), (0.9, 0, 0), 0.11, WHITE)
    scale(bond, [(1, 0.01), (last // 2, 0.01), (last, 1)])
    for i, z in enumerate((-0.3, 0.3)):
        dot = sphere("shared electron", (-1.2 if i == 0 else 1.2, -0.35, z), 0.15, GOLD)
        move(dot, [(1, dot.location.copy()), (last // 2, (0, -0.35, z)),
                   (last, ((-0.22 if i == 0 else 0.22), -0.35, z))])
    ring("shared orbital", (0, 0, 0), 1.65, 0.025, GRID)


def electron_transfer(last, labels):
    left = sphere("electron donor", (-2.35, 0, 0), 0.8, atom_material(labels[0], BLUE))
    right = sphere("electron acceptor", (2.35, 0, 0), 0.8, atom_material(labels[-1], GREEN))
    dot = sphere("transferred electron", (-1.58, -0.3, 0.65), 0.18, GOLD)
    move(dot, [(1, (-1.58, -0.3, 0.65)), (last // 2, (0, -0.25, 1.45)),
               (last, (1.58, -0.3, 0.65))])
    move(left, [(1, (-2.35, 0, 0)), (last, (-1.9, 0, 0))])
    move(right, [(1, (2.35, 0, 0)), (last, (1.9, 0, 0))])
    attraction = rod("ionic attraction", (-1.0, 0, 0), (1.0, 0, 0), 0.045, GOLD)
    scale(attraction, [(1, 0.01), (int(last * 0.7), 0.01), (last, 1)])
    for x, mat in [(-2.35, CYAN), (2.35, GREEN)]:
        ring("charge field", (x, 0, 0), 1.12, 0.018, mat)


def molecule_assembly(last, labels):
    center = sphere("central atom", (0, 0, 0), 0.8, atom_material(labels[0], RED))
    left = sphere("left atom", (-3.1, 0, -0.2), 0.48, atom_material(labels[1] if len(labels) > 1 else "hydrogen", WHITE))
    right = sphere("right atom", (3.1, 0, -0.2), 0.48, atom_material(labels[-1], WHITE))
    move(left, [(1, (-3.1, 0, -0.2)), (last, (-1.4, 0, -0.4))])
    move(right, [(1, (3.1, 0, -0.2)), (last, (1.4, 0, -0.4))])
    for sign in (-1, 1):
        bond = rod("molecular bond", (sign * 0.45, 0, -0.1), (sign * 1.12, 0, -0.34), 0.10, WHITE)
        scale(bond, [(1, 0.01), (last // 2, 0.01), (last, 1)])
    ring("molecular field", (0, 0, 0), 2.05, 0.018, GRID)


def water_molecule(where, number, last, destination, target_ion, positive_ion):
    origin, final = Vector(where), Vector(destination)
    toward = Vector(target_ion) - final
    toward.y = 0
    toward.normalize()
    side = Vector((-toward.z, 0, toward.x))
    # Water's negative oxygen faces cations; its positive hydrogens face anions.
    hydrogen_side = -1 if positive_ion else 1
    offsets = [Vector((0, 0, 0)),
               0.31 * hydrogen_side * toward + 0.16 * side,
               0.31 * hydrogen_side * toward - 0.16 * side]
    parts = [sphere(f"water oxygen {number}", origin, 0.22, RED)]
    for hydrogen in (1, 2):
        position = origin + offsets[hydrogen]
        parts.append(sphere(f"water hydrogen {number}{hydrogen}", position, 0.12, WHITE))
        bond = rod(f"water bond {number}{hydrogen}", origin, position, 0.035, WHITE)
        move(bond, [(1, bond.location.copy()), (last, bond.location + final - origin)])
    for obj, offset in zip(parts, offsets):
        move(obj, [(1, origin + offset), (last, final + offset)])


def dissolve_ions(last, labels):
    ions = []
    targets = []
    for row in range(2):
        for col in range(3):
            positive = (row + col) % 2 == 0
            loc = ((col - 1) * 0.82, row * 0.82 - 0.4, (row - 0.5) * 0.75)
            obj = sphere("sodium ion" if positive else "chloride ion", loc, 0.36, BLUE if positive else GREEN)
            ions.append((obj, loc, positive))
    for idx, (obj, loc, positive) in enumerate(ions):
        angle = idx * math.tau / len(ions)
        target = (2.3 * math.cos(angle), loc[1], 1.15 * math.sin(angle))
        targets.append(target)
        move(obj, [(1, loc), (last // 3, loc), (last, target)])
        ring(f"hydration field {idx}", target, 0.52, 0.017, CYAN)
    water_paths = [
        (0, (4.1, -0.45, 0), (2.9, -0.45, 0)),
        (3, (-4.1, -0.45, 0), (-3.1, -0.45, 0)),
        (1, (0.2, -0.45, 2.4), (0.2, -0.45, 1.7)),
        (4, (-0.3, -0.45, -2.4), (-0.3, -0.45, -1.7)),
    ]
    for number, (ion_index, initial, final) in enumerate(water_paths):
        water_molecule(initial, number, last, final, targets[ion_index], ions[ion_index][2])


def beaker(x, number):
    for z in (-1.3, 0.45):
        ring(f"beaker rim {number}", (x, 0, z), 0.84, 0.045, GLASS)
    for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        px, py = x + 0.84 * math.cos(angle), 0.84 * math.sin(angle)
        rod(f"beaker wall {number}", (px, py, -1.3), (px, py, 0.45), 0.033, GLASS)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.75, depth=0.13, location=(x, 0, -0.9))
    bpy.context.object.name = f"water in beaker {number}"
    bpy.context.object.data.materials.append(WATER)


def concentration(last, labels):
    rng = random.Random(13)
    for idx, (x, count) in enumerate(((-2.1, 10), (2.1, 1))):
        beaker(x, idx)
        for n in range(count):
            px = x + rng.uniform(-0.56, 0.56)
            py = rng.uniform(-0.5, 0.5)
            z = rng.uniform(-1.2, 0.1)
            ion = sphere(f"hydrogen ion {idx}-{n}", (px, py, z), 0.11, RED)
            move(ion, [(1, (px, py, z)), (last // 2, (px, py, z + 0.11)),
                       (last, (px, py, z + 0.02))])
    # A moving 3D indicator reinforces the change in concentration.
    arrow = sphere("moving concentration indicator", (-2.1, -1.2, 0.8), 0.15, GOLD)
    move(arrow, [(1, (-2.1, -1.2, 0.8)), (last, (2.1, -1.2, 0.8))])


def compare_bonds(last, labels):
    for center, mats in [(-2.6, (BLUE, GREEN)), (2.6, (CYAN, PURPLE))]:
        sphere("left bonded atom", (center - 0.83, 0, 0), 0.52, mats[0])
        sphere("right bonded atom", (center + 0.83, 0, 0), 0.52, mats[1])
    transfer = sphere("ionic transferred electron", (-3.15, -0.35, 0.7), 0.12, GOLD)
    move(transfer, [(1, (-3.15, -0.35, 0.7)), (last // 2, (-2.6, -0.35, 1.05)),
                    (last, (-2.05, -0.35, 0.7))])
    for z in (-0.2, 0.2):
        shared = sphere("covalent shared electron", (2.6, -0.3, z), 0.12, GOLD)
        move(shared, [(1, (2.6, -0.3, z)), (last // 2, (2.8, -0.3, z)),
                      (last, (2.6, -0.3, z))])
    rod("covalent bond", (2.0, 0, 0), (3.2, 0, 0), 0.065, WHITE)
    rod("comparison divider", (0, -0.1, -1.45), (0, -0.1, 1.35), 0.025, GRID)


def atomic_structure(last, labels):
    for idx, where in enumerate(((-0.3, 0, 0), (0.3, 0, 0), (0, 0.3, 0.2))):
        sphere("nucleus particle", where, 0.34, RED if idx % 2 else BLUE)
    for radius in (1.15, 1.7):
        ring("electron shell", (0, 0, 0), radius, 0.016, GRID)
    for idx in range(4):
        angle = idx * math.tau / 4
        obj = sphere("orbiting electron", (1.15 * math.cos(angle), 1.15 * math.sin(angle), 0), 0.15, GOLD)
        for frame, offset in [(1, 0), (last // 2, math.pi), (last, math.tau)]:
            theta = angle + offset
            obj.location = (1.15 * math.cos(theta), 1.15 * math.sin(theta), 0)
            obj.keyframe_insert(data_path="location", frame=frame)


def particle_diffusion(last, labels):
    rng = random.Random(5)
    for idx in range(18):
        angle = idx * math.tau / 18
        start = (0.4 * math.cos(angle), rng.uniform(-0.3, 0.3), 0.4 * math.sin(angle))
        end = (3.5 * math.cos(angle), rng.uniform(-0.8, 0.8), 1.25 * math.sin(angle))
        obj = sphere("diffusing particle", start, 0.18, CYAN if idx % 2 else GOLD)
        move(obj, [(1, start), (last, end)])
    ring("reaction vessel", (0, 0, 0), 3.9, 0.018, GLASS)


def reaction(last, labels):
    for idx, (x, mat) in enumerate(((-2.8, CYAN), (-1.8, WHITE), (1.8, PURPLE), (2.8, GREEN))):
        obj = sphere("reactant" if idx < 2 else "product", (x, 0, 0), 0.49, mat)
        target = (-1.0 if idx < 2 else 1.0) + (idx % 2) * 0.35
        move(obj, [(1, (x, 0, 0)), (last // 2, (target, 0, 0)),
                   (last, (x * 0.7, 0, (0.35 if idx % 2 else -0.35)))])
    ring("reaction center", (0, 0, 0), 1.35, 0.025, GOLD)


def phase_change(last, labels):
    rng = random.Random(6)
    for row in range(3):
        for col in range(4):
            idx = row * 4 + col
            start = ((col - 1.5) * 0.7, 0, (row - 1) * 0.7)
            end = (start[0] + rng.uniform(-1.2, 1.2), rng.uniform(-0.7, 0.7),
                   start[2] + rng.uniform(-0.6, 0.6))
            obj = sphere("changing-state particle", start, 0.22, CYAN if idx % 2 else PURPLE)
            move(obj, [(1, start), (last // 2, start), (last, end)])


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    spec = json.loads(Path(args[0]).read_text())
    global BLUE, GREEN, RED, WHITE, CYAN, PURPLE, GOLD, GRAY, GRID, GLASS, WATER
    BLUE = material("sodium blue", (0.14, 0.42, 0.92))
    GREEN = material("chloride green", (0.12, 0.76, 0.53))
    RED = material("oxygen red", (0.9, 0.17, 0.28))
    WHITE = material("hydrogen white", (0.8, 0.9, 1))
    CYAN = material("cyan", (0.04, 0.72, 0.85))
    PURPLE = material("purple", (0.53, 0.31, 0.94))
    GOLD = material("electron gold", (1.0, 0.61, 0.1), glow=0.45)
    GRAY = material("carbon graphite", (0.22, 0.28, 0.36))
    GRID = material("guide blue", (0.08, 0.31, 0.48), glow=0.15)
    GLASS = material("glass rim", (0.28, 0.75, 0.91), metallic=0.45)
    WATER = material("water", (0.06, 0.38, 0.65), metallic=0.25)
    scene = stage()
    scene.render.resolution_x = int(spec.get("width", 960))
    scene.render.resolution_y = int(spec.get("height", 540))
    scene.render.resolution_percentage = 100
    scene.render.fps = int(spec.get("fps", 15))
    scene.frame_start = 1
    scene.frame_end = max(2, round(float(spec["duration"]) * scene.render.fps))
    scene.render.filepath = str(Path(spec["frames_dir"]) / "frame_")
    labels = spec.get("labels") or ["atom", "electron", "atom"]
    mode = spec["mode"]
    renderers = {
        "share_electrons": electron_share,
        "transfer_electron": electron_transfer,
        "molecule_assembly": molecule_assembly,
        "dissolve_ions": dissolve_ions,
        "concentration": concentration,
        "compare_bonds": compare_bonds,
        "atomic_structure": atomic_structure,
        "particle_diffusion": particle_diffusion,
        "reaction": reaction,
        "phase_change": phase_change,
        "reversible_reaction": reaction,
    }
    renderers.get(mode, molecule_assembly)(scene.frame_end, labels)
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
