import bpy
import random
import math
import os
from mathutils import Vector

# ---------------- PARAMETERS ----------------
width = 6.0
depth = 6.0
floors = 2
seed = 41
lit_window_ratio = 0.35  # 0..1
damage = 0.30            # 0..1
ROOF_HEIGHT = 5.6
FLOOR_HEIGHT = 2.9
PRESETS = [(6.0, 6.0), (6.0, 13.0), (13.0, 13.0)]
SPACING = 20.0          # Center-to-center spacing

# Reset scene and ensure deterministic generation.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(seed)


def material(name, color, metallic=0.0, roughness=0.85, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = emission
    return mat


brick = material('Brick red', (0.37, 0.16, 0.12))
beige = material('Dirty beige', (0.48, 0.43, 0.32))
trim = material('Concrete edges', (0.28, 0.27, 0.24))
roof = material('Flat dark roof', (0.18, 0.19, 0.18))
glass = material('Near black glossy windows', (0.018, 0.023, 0.025), roughness=0.13)
# #FF9A3A in sRGB, using the requested color values.
lit = material('Emissive orange #FF9A3A', (1.0, 154/255, 58/255), emission=3.0)
rust = material('Rusty steel', (0.34, 0.17, 0.10), metallic=0.45)
steel = material('Dark steel', (0.15, 0.17, 0.17), metallic=0.45)
soot = material('Soot', (0.075, 0.064, 0.056))
missing = material('Missing brick recess', (0.17, 0.12, 0.10))
shard = material('Broken glass fragments', (0.16, 0.23, 0.24), metallic=0.2, roughness=0.24)


def cube(parts, name, center, scale, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)
    parts.append(ob)
    return ob


def wall_window(parts, x, y, z, horizontal, mat, w=0.78, h=1.05):
    # Windows sit in a dark recess; all geometry remains inside the footprint.
    if horizontal:  # Wall parallel to X
        cube(parts, 'Window recess', (x, y, z), (w+0.13, 0.045, h+0.13), trim)
        cube(parts, 'Window pane', (x, y-0.027 if y < 0 else y+0.027, z),
             (w, 0.028, h), mat)
        cube(parts, 'Window mullion', (x, y-0.047 if y < 0 else y+0.047, z),
             (0.035, 0.035, h), steel)
    else:  # Wall parallel to Y
        cube(parts, 'Window recess', (x, y, z), (0.045, w+0.13, h+0.13), trim)
        cube(parts, 'Window pane', (x-0.027 if x < 0 else x+0.027, y, z),
             (0.028, w, h), mat)
        cube(parts, 'Window mullion', (x-0.047 if x < 0 else x+0.047, y, z),
             (0.035, 0.035, h), steel)


def build_building(w, d, index):
    global width, depth
    width, depth = w, d
    rng = random.Random(seed + index * 1009)
    parts = []
    wall_mat = brick if index != 1 else beige
    # Solid volume for simple box collision; roof at exactly 5.6m.
    cube(parts, 'Building core', (0, 0, ROOF_HEIGHT/2),
         (w, d, ROOF_HEIGHT), wall_mat)
    # Roof is visually flat; inset roof fixtures are flush with its top.
    cube(parts, 'Roof membrane', (0, 0, ROOF_HEIGHT-0.015),
         (w-0.20, d-0.20, 0.03), roof)
    # Floor band is below the 2.9m floor datum.
    cube(parts, 'Floor division front', (0, -d/2+0.028, FLOOR_HEIGHT),
         (w-0.12, 0.055, 0.10), trim)
    cube(parts, 'Floor division back', (0, d/2-0.028, FLOOR_HEIGHT),
         (w-0.12, 0.055, 0.10), trim)

    # 2 windows per 3m of wall, distributed with a small edge margin.
    # Ground floor front reserves space for shop and front entrance.
    for floor in range(floors):
        z = (1.65 if floor == 0 else 4.23)
        nx = max(2, round(w * 2 / 3))
        ny = max(2, round(d * 2 / 3))
        for side in (-1, 1):
            y = side * (d/2 - 0.055)
            for j in range(nx):
                x = -w/2 + (j+0.5)*w/nx
                if floor == 0 and side == -1 and abs(x) < min(2.0, w*0.36):
                    continue  # Shop and door occupy the front center.
                m = lit if rng.random() < lit_window_ratio else glass
                wall_window(parts, x, y, z, True, m)
                if rng.random() < damage * 0.55:
                    cube(parts, 'Soot above window', (x, y, z+0.66),
                         (0.62, 0.013, 0.20), soot)
        for side in (-1, 1):
            x = side * (w/2 - 0.055)
            for j in range(ny):
                y = -d/2 + (j+0.5)*d/ny
                m = lit if rng.random() < lit_window_ratio else glass
                wall_window(parts, x, y, z, False, m)
                if rng.random() < damage * 0.45:
                    cube(parts, 'Soot side', (x, y, z+0.65),
                         (0.013, 0.60, 0.17), soot)

    # Shop front on the front wall: damaged glazing and shutter.
    front_y = -d/2 + 0.038
    shop_x = -w*0.20
    shop_w = min(1.95, w*0.36)
    cube(parts, 'Shop frame', (shop_x, front_y, 1.15),
         (shop_w, 0.06, 2.20), steel)
    cube(parts, 'Shop dark display', (shop_x, front_y-0.025, 1.14),
         (shop_w-0.14, 0.025, 1.96), glass)
    # Angular broken-glass look using a few sparse shard bars.
    for k in range(3):
        sx = shop_x - shop_w*0.35 + k*shop_w*0.30
        ob = cube(parts, 'Broken shop glass', (sx, front_y-0.052, 0.43+k*0.12),
                  (0.10, 0.025, 0.54), shard)
        ob.rotation_euler[1] = (k-1)*0.27
    # Shutter occupies the right half of the display, rusty slats.
    for k in range(9):
        cube(parts, 'Rusty shutter slat', (shop_x+shop_w*0.23, front_y-0.075,
             1.30+k*0.105), (shop_w*0.45, 0.045, 0.08), rust)
    # Front door to the right of shop.
    door_x = min(w/2-0.58, w*0.23)
    cube(parts, 'Front door frame', (door_x, front_y, 1.02),
         (0.91, 0.07, 2.04), trim)
    cube(parts, 'Front door', (door_x, front_y-0.043, 0.98),
         (0.78, 0.032, 1.88), steel)
    cube(parts, 'Door handle', (door_x+0.27, front_y-0.070, 1.0),
         (0.06, 0.025, 0.10), rust)

    # Recessed rooftop details: top never rises above Z=5.6.
    # They are represented as flush service covers with raised-looking trim.
    vent_x, vent_y = -w*0.25, d*0.20
    cube(parts, 'Recessed vent top', (vent_x, vent_y, ROOF_HEIGHT-0.012),
         (0.75, 0.65, 0.024), steel)
    for k in range(3):
        cube(parts, 'Vent grille', (vent_x-0.22+k*0.22, vent_y, ROOF_HEIGHT),
             (0.045, 0.47, 0.001), rust)
    tank_x, tank_y = w*0.22, d*0.20
    cube(parts, 'Recessed tank access', (tank_x, tank_y, ROOF_HEIGHT-0.012),
         (0.90, 0.90, 0.024), rust)
    cube(parts, 'Tank hatch', (tank_x, tank_y, ROOF_HEIGHT),
         (0.53, 0.53, 0.001), steel)

    # Stylized chipped bricks and cracked corner, no displacement beyond box.
    for k in range(round(damage * 16)):
        x = rng.uniform(-w/2+0.3, w/2-0.3)
        z = rng.uniform(0.45, ROOF_HEIGHT-0.4)
        cube(parts, 'Missing brick mark', (x, -d/2+0.008, z),
             (rng.uniform(0.12, 0.28), 0.012, 0.09), missing)
    for k in range(5):
        z = 0.4 + k*0.36
        cube(parts, 'Corner crack', (-w/2+0.012, -d/2+0.012, z),
             (0.018, 0.018, 0.22), soot)

    # Join one object and put its local origin at bottom center.
    bpy.ops.object.select_all(action='DESELECT')
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.object
    ob.name = f'building_low_{int(w)}x{int(d)}_s{seed}'
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # Mesh coordinates were built around (0,0,0): set origin there.
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    # Keep each asset 20m apart in the authoring scene.
    ob.location.x = index * SPACING
    return ob


assets = [build_building(w, d, i) for i, (w, d) in enumerate(PRESETS)]

# Export each asset separately, zeroing translation during export.
blend_path = bpy.data.filepath
out_dir = os.path.dirname(blend_path) if blend_path else os.path.expanduser('~')
os.makedirs(out_dir, exist_ok=True)
for asset in assets:
    bpy.ops.object.select_all(action='DESELECT')
    asset.select_set(True)
    bpy.context.view_layer.objects.active = asset
    old_pos = asset.location.copy()
    asset.location = (0, 0, 0)
    bpy.context.view_layer.update()
    export_path = os.path.join(out_dir, asset.name + '.glb')
    bpy.ops.export_scene.gltf(filepath=export_path, export_format='GLB',
                              use_selection=True, export_apply=True,
                              export_materials='EXPORT', export_yup=True)
    asset.location = old_pos
    print('Exported:', export_path)

# Show the three buildings in the viewport.
bpy.ops.object.select_all(action='DESELECT')
for asset in assets:
    asset.select_set(True)
bpy.context.view_layer.objects.active = assets[0]
print('Created 3 low-poly apartment buildings.')
