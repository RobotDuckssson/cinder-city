"""Blender 4.x procedural high-rises; all facade detail is proud of the wall."""
import bpy
import random
import os
from mathutils import Vector

# ---- PARAMETERS ----
width = 6.0
depth = 6.0
floors = 5                 # 4..7; height = floors * 2.9
seed = 17
lit_window_ratio = 0.14  # 0..1
damage = 0.6              # 0..1
footprints = [(6.0, 6.0), (13.0, 13.0)]
spacing = 20.0           # center-to-center distance in the Blender scene

FLOOR_H = 2.9
WALL_INSET = 0.11       # structural facade is inside footprint
DETAIL_OFFSET = 0.025   # ALL facade overlays at least 0.02m beyond wall face

if not (4 <= floors <= 7):
    raise ValueError('floors must be between 4 and 7')
if not (0 <= lit_window_ratio <= 1 and 0 <= damage <= 1):
    raise ValueError('ratios must be in [0,1]')

# ---- SCENE AND MATERIALS ----
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def mat(name, color, rough=0.9, metallic=0.0, glow=0.0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metallic
    if glow:
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = glow
    return m

concrete = mat('concrete_faded', (.37,.39,.40))
concrete_alt = mat('concrete_dusty', (.45,.43,.39))
base = mat('base_charcoal', (.13,.15,.16))
soot = mat('soot_black', (.045,.042,.04))
scorch = mat('scorched_concrete', (.115,.105,.10))
frame = mat('window_frames_steel', (.11,.12,.13), .6)
glass = mat('dark_glossy_windows', (.015,.018,.023), .15, .18)
lit = mat('lit_windows_FF9A3A', (1.0, 154/255, 58/255), glow=3.0)
shattered = mat('empty_window_black', (.008,.009,.010))
rust = mat('rusted_rebar', (.30,.15,.085), .78, .3)
roofmat = mat('flat_roof', (.21,.22,.23))

# Cubes with explicit coordinates avoid transform drift and make bounding checks simple.
def cube(parts, name, xyz, dims, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(material)
    parts.append(ob)
    return ob

# A 2D facade detail, with its thickness measured OUTWARD from the structural wall.
# This guarantees it is never flush with or inside the structural facade.
def overlay(parts, name, axis, sign, wall, along, z, span, height, material, thick=0.012):
    outward_center = sign * (wall + DETAIL_OFFSET + thick/2)
    if axis == 'x':
        return cube(parts, name, (outward_center, along, z), (thick, span, height), material)
    return cube(parts, name, (along, outward_center, z), (span, thick, height), material)

def build(w, d, asset_seed):
    random.seed(asset_seed)
    parts = []
    h = floors * FLOOR_H
    wx, wy = w/2-WALL_INSET, d/2-WALL_INSET
    # Outer dimension is exact: corner-cap geometry reaches +/- w/2 and +/- d/2.
    # Facade itself sits inward, leaving space for all raised details.
    wall_t = 0.12
    # A narrow intact perimeter around the top provides an uninterrupted walkable roof.
    cube(parts, 'roof_slab', (0,0,h-.11), (w,d,.22), roofmat)
    # Foundation slab ensures the lower bounding face is exactly z=0.
    cube(parts, 'foundation', (0,0,.09), (w,d,.18), base)

    # Internal floor plates; remove a corner strip at upper damaged levels.
    for f in range(1, floors):
        z = f*FLOOR_H
        if f >= floors-2 and damage > .35:
            cube(parts, 'damaged_floor_plate', (-.20,-.20,z), (w-.4,d-.4,.12), concrete_alt)
        else:
            cube(parts, 'floor_plate', (0,0,z), (w-.25,d-.25,.12), concrete_alt)

    # Facade made of separate panels. Omitted upper corner panels are ACTUAL gaps.
    # All surfaces are within the footprint, and details protrude by >= .02m.
    for axis, side in [('x',-1),('x',1),('y',-1),('y',1)]:
        length = d if axis == 'x' else w
        wall = wx if axis == 'x' else wy
        count = max(2, round(length/1.55))
        bay = length/count
        for f in range(floors):
            upper_burn = f >= floors-2 and ((axis,side) in [('x',1),('y',1)])
            for i in range(count):
                pos = -length/2 + (i+.5)*bay
                collapsed = upper_burn and i >= int(count*.56) and random.random() < damage*.90
                if collapsed:
                    # exposed short rebar inside the missing panel; still inside bounding box
                    if random.random() < .65:
                        inner = wall - .025
                        for j in range(2):
                            rebar_z = f*FLOOR_H + .45+j*.48
                            if axis == 'x':
                                cube(parts,'exposed_rebar',(side*inner,pos+(.13*j),rebar_z),(.022,.022,.65),rust)
                            else:
                                cube(parts,'exposed_rebar',(pos+(.13*j),side*inner,rebar_z),(.022,.022,.65),rust)
                    continue
                material = base if f == 0 else (scorch if upper_burn and i >= count//2 else concrete)
                if axis == 'x':
                    cube(parts,'wall_panel',(side*wall,pos,f*FLOOR_H+FLOOR_H/2),
                         (wall_t,bay+.008,FLOOR_H-.12),material)
                else:
                    cube(parts,'wall_panel',(pos,side*wall,f*FLOOR_H+FLOOR_H/2),
                         (bay+.008,wall_t,FLOOR_H-.12),material)
                # All facade details use overlays, positioned OUTSIDE the wall face.
                # Wall outer face is wall + wall_t/2.
                face = wall + wall_t/2
                if f == 0 and axis == 'y' and side == -1 and i == count//2:
                    overlay(parts,'entrance_door',axis,side,face,pos,1.12,bay*.55,2.05,glass)
                    overlay(parts,'door_header',axis,side,face,pos,2.18,bay*.62,.09,frame)
                    # Canopy is 0.10m deep, entirely within the bounding footprint.
                    # Facade is inset 0.11m; canopy tip remains inside +/- depth/2.
                    if axis == 'y':
                        cube(parts,'entrance_canopy',(pos,side*(face+.01),2.45),
                             (bay*.85,.06,.10),base)
                    continue
                # Windows: small and slightly raised, plus thin raised frame bars.
                win_z = f*FLOOR_H + 1.55
                win_h = 1.18
                win_w = min(.86,bay*.68)
                empty = upper_burn and random.random() < .83*damage
                window_material = shattered if empty else (lit if random.random() < lit_window_ratio else glass)
                overlay(parts,'window',axis,side,face,pos,win_z,win_w,win_h,window_material)
                if random.random() < .25+damage*.35:
                    overlay(parts,'top_frame',axis,side,face,pos,win_z+win_h/2,win_w+.06,.045,frame)
                if random.random() < damage*(.4 if f < floors-2 else .95):
                    # Soot goes UP from windows, not down.
                    overlay(parts,'soot_streak',axis,side,face,pos,win_z+win_h/2+.23,
                            win_w*.50,.42,soot,thick=.008)
                if f > 0 and random.random() < .35:
                    overlay(parts,'floor_band',axis,side,face,pos,f*FLOOR_H+.12,
                            bay,.065,concrete_alt,thick=.009)

    # Corner caps preserve exact X/Y bounds without any detail protruding.
    for x in (-w/2+.045,w/2-.045):
        for y in (-d/2+.045,d/2-.045):
            cube(parts,'corner_pier',(x,y,h/2),(.09,.09,h),concrete_alt)

    # Rooftop antenna is a flush low-profile aerial, with no point above z=h.
    # A vertical mast would violate the mandatory exact height and walkable roof.
    cube(parts,'flush_antenna_base',(0,0,h-.015),(.44,.44,.03),frame)
    cube(parts,'flush_antenna_arm',(0,0,h-.006),(.85,.028,.012),rust)
    cube(parts,'flush_antenna_crossarm',(0,0,h-.006),(.028,.85,.012),rust)

    # Join into one mesh with origin at the bottom-center in LOCAL coordinates.
    bpy.ops.object.select_all(action='DESELECT')
    for ob in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = f'building_high_{int(w)}x{int(d)}_s{asset_seed}'
    bpy.context.scene.cursor.location = (0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # Check dimensions in the asset's local coordinate system.
    verts = [v.co for v in result.data.vertices]
    bounds = [(min(v[i] for v in verts),max(v[i] for v in verts)) for i in range(3)]
    expected = [(-w/2,w/2),(-d/2,d/2),(0,h)]
    for got, want in zip(bounds,expected):
        if any(abs(a-b)>1e-4 for a,b in zip(got,want)):
            raise RuntimeError(f'{result.name} bounds {bounds} != {expected}')
    tri_count = sum(len(p.vertices)-2 for p in result.data.polygons)
    print(f'{result.name}: {tri_count} triangles; bounds {bounds}')
    if tri_count >= 3000:
        print('WARNING: exceeds 3000 triangle limit; reduce window count/detail')
    return result

# Export each asset in LOCAL coordinates; scene spacing is for preview only.
folder = bpy.path.abspath('//') if bpy.data.filepath else os.path.expanduser('~')
assets = []
for index,(w,d) in enumerate(footprints):
    asset = build(w,d,seed+index)
    assets.append(asset)
    bpy.ops.object.select_all(action='DESELECT')
    asset.select_set(True)
    bpy.context.view_layer.objects.active = asset
    out = os.path.join(folder,asset.name+'.glb')
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True,
                              export_apply=True, export_materials='EXPORT')
    print('Exported:',out)

# Move only after export, so GLBs keep their bottom-center origins.
for i,ob in enumerate(assets):
    ob.location.x = i*spacing
bpy.ops.object.select_all(action='DESELECT')
for ob in assets:
    ob.select_set(True)
print('Done: 2 high-rise variants.')
