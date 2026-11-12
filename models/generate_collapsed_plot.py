"""Blender 4.x: modular collapsed-building plot, exported as ONE GLB.
Five independent meshes: broken wall, three rubble piles, scorched ground.
"""
import bpy
import random
import math
import os
from mathutils import Vector

# ---- Parameters ----
width = 6.0
depth = 6.0
floors = 2                 # Compatibility with the building generator settings
seed = 1
lit_window_ratio = 0.0   # No intact windows in this ruined plot
damage = 0.8             # Controls rubble variation and soot intensity
wall_thickness = 0.5

assert width == 6.0 and depth == 6.0, 'This layout is designed for a 6x6 m plot.'
assert 0 <= damage <= 1 and 0 <= lit_window_ratio <= 1
random.seed(seed)

# ---- Clean scene ----
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for mat in list(bpy.data.materials):
    if mat.users == 0:
        bpy.data.materials.remove(mat)


def material(name, color, roughness=0.9):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    return mat

concrete = [
    material('Concrete pale', (0.39, 0.38, 0.35)),
    material('Concrete grey', (0.30, 0.30, 0.29)),
    material('Concrete dusty', (0.48, 0.44, 0.38)),
    material('Concrete charred', (0.12, 0.12, 0.115)),
]
soot = material('Soot black', (0.055, 0.052, 0.049))
ground_mat = material('Scorched ground', (0.105, 0.092, 0.078))
rebar_mat = material('Rusty rebar', (0.24, 0.105, 0.062), 0.75)


def mesh_object(name, verts, faces, mats, face_mats=None):
    mesh = bpy.data.meshes.new(name + '_mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.materials.clear()
    for mat in mats:
        mesh.materials.append(mat)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    if face_mats:
        for poly, index in zip(mesh.polygons, face_mats):
            poly.material_index = index
    return ob


def add_box(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)
    return ob


def join_parts(parts, name, origin):
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    # Set an explicit placement pivot, without changing world-space geometry.
    bpy.context.scene.cursor.location = origin
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return obj


# ---- Broken wall: 0.5 m thick, 4.6 m tall, jagged top ----
# The wall occupies the rear edge, leaving room for three movable rubble piles.
wall_x0, wall_x1 = -2.8, 2.8
wall_y0, wall_y1 = 2.25, 2.75
profile = [(-2.8, 0.0), (2.8, 0.0), (2.8, 3.75),
           (2.32, 4.05), (1.95, 3.78), (1.45, 4.65),
           (0.85, 4.12), (0.18, 4.88), (-0.35, 4.30),
           (-1.05, 5.05), (-1.55, 4.36), (-2.25, 4.70),
           (-2.8, 4.12)]
count = len(profile)
verts = [(x, wall_y0, z) for x, z in profile] + [(x, wall_y1, z) for x, z in profile]
faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, 2 * count))]
for i in range(count):
    j = (i + 1) % count
    faces.append((i, j, count + j, count + i))
wall = mesh_object('wall_core', verts, faces, concrete,
                   [0, 1] + [random.choice([0, 1, 2, 3]) for _ in range(count)])
wall_parts = [wall]
# Surface-mounted scorch strips on front face; no textures or booleans.
for i in range(6):
    x = -2.3 + i * 0.83
    h = random.uniform(0.45, 1.05) * (0.65 + damage * 0.4)
    z = random.uniform(2.4, 3.15)
    wall_parts.append(add_box('wall_soot', (x, wall_y0 - 0.012, z),
                              (random.uniform(0.12, 0.27), 0.016, h), soot))
# Rusted thin rebar protrudes from the jagged top, within 5.2 m total.
for x, z in [(-1.07, 5.05), (0.19, 4.88), (1.45, 4.65)]:
    rod_height = min(0.12, 5.19 - z)
    wall_parts.append(add_box('wall_rebar', (x, 2.48, z + rod_height / 2),
                              (0.025, 0.025, rod_height), rebar_mat))
wall_obj = join_parts(wall_parts, 'ruin_wall_s1', (0, 2.5, 0))


# ---- Rubble piles: independent movable objects, each under 800 triangles ----
# Dimensions of the pile envelopes (X, Y, Z), all inside the 6x6 plot.
piles = [
    ('rubble_s1', (-1.65, -1.65), (2.3, 2.1, 1.05)),
    ('rubble_s2', (1.52, -1.55), (2.5, 2.3, 1.40)),
    ('rubble_s3', (0.0, 0.65), (2.0, 1.55, 0.82)),
]

for name, (cx, cy), (sx, sy, sz) in piles:
    parts = []
    # A chunky irregular stack: boxy stones with visible flat faces.
    # Keep every block inside the declared pile envelope.
    for layer, n in [(0, 8), (1, 5), (2, 3)]:
        layer_scale = [1.0, 0.72, 0.42][layer]
        for _ in range(n):
            bx = random.uniform(0.25, 0.65) * layer_scale
            by = random.uniform(0.25, 0.65) * layer_scale
            bz = random.uniform(0.18, 0.35) * layer_scale
            xlim = sx * layer_scale / 2 - bx / 2
            ylim = sy * layer_scale / 2 - by / 2
            x = cx + random.uniform(-max(0, xlim), max(0, xlim))
            y = cy + random.uniform(-max(0, ylim), max(0, ylim))
            z0 = [0, sz * 0.32, sz * 0.65][layer]
            z = min(sz - bz / 2, z0 + bz / 2)
            block = add_box('broken_concrete', (x, y, z), (bx, by, bz),
                            random.choice(concrete))
            block.rotation_euler[2] = random.uniform(-0.22, 0.22)
            # Limit rotated corners to the pile envelope.
            # Conservative clamp using the rotated XY bounding half-extents.
            a = block.rotation_euler[2]
            hx = (abs(math.cos(a)) * bx + abs(math.sin(a)) * by) / 2
            hy = (abs(math.sin(a)) * bx + abs(math.cos(a)) * by) / 2
            block.location.x = min(cx + sx / 2 - hx, max(cx - sx / 2 + hx, x))
            block.location.y = min(cy + sy / 2 - hy, max(cy - sy / 2 + hy, y))
            parts.append(block)
    pile = join_parts(parts, name, (cx, cy, 0))

# ---- Scorched ground: a thin slab inside the footprint ----
# The slab is a separate prop so it can be hidden or repositioned in-game.
ground = add_box('scorched_ground_s1', (0, 0, 0.015),
                 (width, depth, 0.03), ground_mat)
bpy.context.scene.cursor.location = (0, 0, 0)
bpy.ops.object.select_all(action='DESELECT')
ground.select_set(True)
bpy.context.view_layer.objects.active = ground
bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

# ---- Validate bounds and mesh budgets ----
expected = {'ruin_wall_s1', 'rubble_s1', 'rubble_s2', 'rubble_s3',
            'scorched_ground_s1'}
assert {o.name for o in bpy.context.scene.objects if o.type == 'MESH'} == expected
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH':
        continue
    world_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = [min(p[i] for p in world_corners) for i in range(3)]
    maxs = [max(p[i] for p in world_corners) for i in range(3)]
    assert mins[0] >= -width / 2 - 1e-5 and maxs[0] <= width / 2 + 1e-5, obj.name
    assert mins[1] >= -depth / 2 - 1e-5 and maxs[1] <= depth / 2 + 1e-5, obj.name
    assert mins[2] >= -1e-5 and maxs[2] <= 5.2 + 1e-5, obj.name
    triangles = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    assert triangles < 800, f'{obj.name}: {triangles} triangles exceeds prop budget'
    print(f'{obj.name}: {triangles} triangles; bounds {mins} -> {maxs}')

# ---- Export all FIVE separate mesh nodes in one binary glTF ----
output_dir = (os.path.dirname(bpy.data.filepath)
              if bpy.data.filepath else os.path.expanduser('~'))
output_path = os.path.join(output_dir, f'collapsed_plot_6x6_s{seed}.glb')
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=output_path,
                          export_format='GLB',
                          use_selection=True,
                          export_yup=True,
                          export_apply=True,
                          export_materials='EXPORT')
print('Exported:', output_path)
