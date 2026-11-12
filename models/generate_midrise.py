"""Blender 4.x: three lightweight, mid-rise post-apocalyptic buildings.
Each GLB contains one mesh, local origin at bottom center, exact footprint/height.
"""
import bpy
import random
import math
import os
from mathutils import Vector

# ===== PARAMETERS =====
width = 6.0
depth = 6.0
floors = 3
seed = 17
lit_window_ratio = 0.27
damage = 0.5
roof_height = 8.7
floor_height = 2.9
footprints = [(6.0, 6.0), (6.0, 13.0), (13.0, 13.0)]
spacing = 20.0

random.seed(seed)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)


def mat(name, color, roughness=0.9, metallic=0, emission=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Metallic'].default_value = metallic
    if emission:
        bs.inputs['Emission Color'].default_value = (*color, 1)
        bs.inputs['Emission Strength'].default_value = emission
    return m

concrete = mat('Concrete faded grey', (.39, .39, .37))
plaster = mat('Faded plaster', (.53, .51, .46))
band = mat('Concrete horizontal bands', (.26, .27, .27))
char = mat('Burned black concrete', (.055, .05, .047))
soot = mat('Soot stains', (.095, .085, .077))
crack = mat('Dark structural cracks', (.11, .105, .10))
frame = mat('Dark metal window frames', (.11, .115, .12), .6)
glass = mat('Unlit glass', (.018, .022, .027), .16, .1)
lit = mat('Lit windows #FF9A3A', (1.0, .6039, .22745), .35, 0, 3)
empty = mat('Burned-out black window void', (.009, .009, .01))
rust = mat('Rusty fire escape', (.29, .16, .105), .8, .1)
metal = mat('AC and elevator metal', (.36, .39, .40), .65, .35)
roof = mat('Flat roof', (.21, .22, .22))


def cube(name, loc, size, material, parts):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    parts.append(o)
    return o


def add_window(axis, side, along, z, w, d, parts, burned=False):
    # All window details sit INSIDE the exact footprint boundary.
    depth_inset = .025
    if axis == 'Y':
        y = side * (d / 2 - depth_inset)
        cube('Window frame', (along, y, z), (.89, .048, 1.25), frame, parts)
        cube('Window glass', (along, y + side * .018, z), (.72, .012, 1.08), empty if burned else (lit if random.random() < lit_window_ratio else glass), parts)
        # Crossbar in burnt windows suggests broken/empty glazing.
        if burned:
            cube('Charred window crossbar', (along, y + side * .035, z + .02), (.75, .016, .038), char, parts)
    else:
        x = side * (w / 2 - depth_inset)
        cube('Window frame', (x, along, z), (.048, .89, 1.25), frame, parts)
        cube('Window glass', (x + side * .018, along, z), (.012, .72, 1.08), empty if burned else (lit if random.random() < lit_window_ratio else glass), parts)
        if burned:
            cube('Charred window crossbar', (x + side * .035, along, z + .02), (.016, .75, .038), char, parts)


def wall_soot(axis, side, along, z, w, d, parts):
    # Flat, uneven vertical stains rise from some window openings.
    length = random.uniform(.5, 1.05)
    breadth = random.uniform(.14, .32)
    if axis == 'Y':
        cube('Soot rising from window', (along, side * (d / 2 - .009), z + .73 + length / 2), (breadth, .013, length), soot, parts)
    else:
        cube('Soot rising from window', (side * (w / 2 - .009), along, z + .73 + length / 2), (.013, breadth, length), soot, parts)


def fire_escape(w, d, parts):
    # 0.11m facade relief, drawn as thin ladder and landings; not a usable balcony.
    y = -d / 2 + .064
    x = w / 2 - .75
    for dx in (-.31, .31):
        cube('Fire escape vertical rail', (x + dx, y, 4.35), (.035, .08, 7.7), rust, parts)
    for i in range(19):
        cube('Fire escape ladder rung', (x, y - .014, .65 + i * .38), (.66, .035, .035), rust, parts)
    for z in (2.86, 5.76):
        cube('Fire escape landing', (x, y, z), (1.10, .11, .065), rust, parts)
        cube('Fire escape guard', (x, y, z + .38), (1.1, .035, .04), rust, parts)


def ac_units(w, d, parts):
    # Compact facade units entirely within the collision footprint.
    for i, z in enumerate((2.1, 4.95)):
        x = -w / 2 + .78 + i * 1.12
        y = d / 2 - .08
        cube('Wall mounted AC case', (x, y, z), (.66, .15, .42), metal, parts)
        for j in range(3):
            cube('AC vent grille', (x, y + .068, z - .105 + j * .09), (.51, .008, .022), frame, parts)


def burned_corner(w, d, parts):
    # Scorched upper corner, not a geometry subtraction (low poly, collision friendly).
    cube('Burned top floor front corner', (w / 2 - .68, -d / 2 + .008, 7.32), (1.35, .014, 2.53), char, parts)
    cube('Burned top floor side corner', (w / 2 - .008, -d / 2 + .68, 7.32), (.014, 1.35, 2.53), char, parts)
    for i in range(4):
        xx = w / 2 - .12 - i * .22
        cube('Scorch irregular edge', (xx, -d / 2 + .012, 6.02 + i * .14), (.12, .018, .26 + i * .09), soot, parts)


def roof_details(w, d, parts):
    # Roof top is exactly 8.7m: equipment is represented as flush roof access.
    cube('Flat walkable roof', (0, 0, 8.665), (w, d, .07), roof, parts)
    cube('Elevator access hatch', (-w / 2 + 1.15, d / 2 - 1.2, 8.694), (1.35, 1.55, .012), metal, parts)
    cube('Elevator hatch seam', (-w / 2 + 1.15, d / 2 - 1.2, 8.6995), (.025, 1.45, .001), frame, parts)
    cube('Roof drain grate', (w / 2 - .55, -d / 2 + .55, 8.699), (.40, .40, .002), band, parts)


def make_building(w, d, variant_seed):
    random.seed(variant_seed)
    parts = []
    body_mat = concrete if random.random() < .5 else plaster
    cube('Solid building shell', (0, 0, 4.32), (w, d, 8.64), body_mat, parts)
    # Horizontal floor bands remain inside the building's footprint.
    for z in (2.9, 5.8):
        cube('Front floor band', (0, -d / 2 + .014, z), (w, .028, .105), band, parts)
        cube('Rear floor band', (0, d / 2 - .014, z), (w, .028, .105), band, parts)
        for side in (-1, 1):
            cube('Side floor band', (side * (w / 2 - .014), 0, z), (.028, d, .105), band, parts)
    # Two windows per approximately 3m, with reserved fire-escape area.
    for floor in range(floors):
        z = floor * floor_height + 1.55
        for axis, length in [('Y', w), ('X', d)]:
            count = max(2, round(length / 3 * 2))
            positions = [-length / 2 + (i + .5) * length / count for i in range(count)]
            for side in (-1, 1):
                for pos in positions:
                    if axis == 'Y' and side == -1 and pos > w / 2 - 1.3:
                        continue  # fire escape
                    burned = damage >= .3 and floor == floors - 1 and ((axis == 'Y' and side == -1 and pos > w / 2 - 2.0) or (axis == 'X' and side == 1 and pos < -d / 2 + 1.8))
                    add_window(axis, side, pos, z, w, d, parts, burned)
                    if not burned and random.random() < damage * .48 and floor < floors - 1:
                        wall_soot(axis, side, pos, z, w, d, parts)
    burned_corner(w, d, parts)
    fire_escape(w, d, parts)
    ac_units(w, d, parts)
    roof_details(w, d, parts)
    # Narrow black fracture marks on the scorched facade.
    for i in range(max(2, round(damage * 7))):
        zz = 6.05 + i * .29
        cube('Corner fracture', (w / 2 - .015, -d / 2 + .2 + i * .14, zz), (.012, .13, .025), crack, parts)

    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    asset = bpy.context.object
    asset.name = 'building_mid_%sx%s_s%s' % (int(w), int(d), variant_seed)
    # Local origin at (0,0,0), despite Blender's default center origin.
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # Exact geometry checks, including all facade attachments.
    corners = [asset.matrix_world @ Vector(v) for v in asset.bound_box]
    low = [min(v[i] for v in corners) for i in range(3)]
    high = [max(v[i] for v in corners) for i in range(3)]
    assert all(abs(low[i] - target) < 1e-4 for i, target in enumerate((-w/2, -d/2, 0))), (asset.name, low)
    assert all(abs(high[i] - target) < 1e-4 for i, target in enumerate((w/2, d/2, roof_height))), (asset.name, high)
    tri_count = sum(len(p.vertices) - 2 for p in asset.data.polygons)
    print(asset.name, 'triangles:', tri_count)
    if tri_count >= 3000:
        print('WARNING: triangle budget exceeded:', asset.name)
    return asset


outdir = bpy.path.abspath('//') if bpy.data.filepath else os.path.expanduser('~')
assets = []
for index, (width, depth) in enumerate(footprints):
    obj = make_building(width, depth, seed + index)
    assets.append(obj)
    # Export with origin at zero; then position the objects for Blender overview.
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    export_path = os.path.join(outdir, obj.name + '.glb')
    bpy.ops.export_scene.gltf(filepath=export_path, export_format='GLB', use_selection=True,
                              export_apply=True, export_materials='EXPORT',
                              export_yup=True)
    print('Exported:', export_path)
    obj.location.x = index * spacing

bpy.ops.object.select_all(action='DESELECT')
for obj in assets:
    obj.select_set(True)
bpy.context.view_layer.objects.active = assets[0]
print('Finished three mid-rise assets.')
