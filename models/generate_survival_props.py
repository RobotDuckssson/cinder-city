"""Blender 4.x: eight low-poly post-apocalyptic props in one GLB.
Run in Blender's Scripting workspace. Each prop is a single independent mesh.
Bounding boxes are measured in local object coordinates; Z starts at zero.
"""
import bpy
import math
import os
import random
from mathutils import Vector

# ---------------- USER PARAMETERS ----------------
width = 2.4             # default container width (m)
depth = 4.6             # default container depth (m)
floors = 1              # retained for consistency with building generators
seed = 1
lit_window_ratio = 0.0 # no illuminated windows on these props
damage = 0.55
SPACING = 15.0          # presentation spacing between prop origins
EXPORT_NAME = 'survival_props_s1.glb'
# -------------------------------------------------
random.seed(seed)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for material in list(bpy.data.materials):
    if material.users == 0:
        bpy.data.materials.remove(material)


def mat(name, rgb, metallic=0, roughness=0.85, emission=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*rgb, 1)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    if emission:
        p.inputs['Emission Color'].default_value = (*rgb, 1)
        p.inputs['Emission Strength'].default_value = emission
    return m

M = {
 'red': mat('faded_shipping_red', (.40,.095,.075), .35),
 'blue': mat('faded_shipping_blue', (.09,.21,.29), .35),
 'green': mat('faded_shipping_green', (.17,.27,.17), .35),
 'rust': mat('rust_orange_brown', (.34,.135,.065), .1),
 'rust_dark': mat('rust_dark', (.19,.085,.048), .1),
 'steel': mat('steel_dark', (.13,.15,.16), .65),
 'black': mat('charcoal', (.045,.045,.046), .05),
 'glass': mat('dark_glossy_glass', (.025,.035,.04), .15, .15),
 'wood': mat('aged_wood', (.31,.21,.12)),
 'wood2': mat('wood_edge', (.21,.14,.08)),
 'concrete': mat('grey_concrete', (.40,.40,.37)),
 'concrete2': mat('concrete_edge', (.29,.30,.29)),
 'redcar': mat('dull_red_car_paint', (.48,.10,.075), .25),
 'ash': mat('soot', (.085,.08,.075)),
}


def cube(parts, label, center, dims, material):
    """Create a flat-shaded cuboid with applied dimensions."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = label
    ob.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(material)
    parts.append(ob)
    return ob


def custom_mesh(parts, name, verts, faces, material):
    mesh = bpy.data.meshes.new(name + '_mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material)
    parts.append(ob)
    return ob


def finish(parts, name, scene_xy, bounds, max_tris=800):
    """Join geometry, set origin to local ground center, and verify local bounds."""
    bpy.ops.object.select_all(action='DESELECT')
    for ob in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    # Geometry was authored in local coordinates about (0,0,0).
    # Joining leaves origin at the first primitive's center; reset with cursor.
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    obj.location = (scene_xy[0], scene_xy[1], 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    coords = [Vector(v.co) for v in obj.data.vertices]
    mins = [min(v[i] for v in coords) for i in range(3)]
    maxs = [max(v[i] for v in coords) for i in range(3)]
    measured = [maxs[i]-mins[i] for i in range(3)]
    expected_min = [-bounds[0]/2, -bounds[1]/2, 0]
    for i in range(3):
        assert abs(measured[i]-bounds[i]) < 0.0001, (name, 'size', measured, bounds)
        assert abs(mins[i]-expected_min[i]) < 0.0001, (name, 'min', mins, expected_min)
    triangles = sum(len(poly.vertices)-2 for poly in obj.data.polygons)
    assert triangles < max_tris, (name, 'triangle budget exceeded', triangles)
    print(f'{name}: bounds {tuple(round(n,3) for n in measured)}, {triangles} triangles')
    return obj


def add_container(name, color, at):
    w,d,h = width,depth,2.9
    p=[]
    # Main shell is inset 0.04 m, while edge posts establish exact bounds.
    cube(p, 'shell', (0,0,h/2), (w-.08,d-.08,h-.08), M[color])
    for x in (-w/2+.035,w/2-.035):
        for y in (-d/2+.035,d/2-.035):
            cube(p,'corner_post',(x,y,h/2),(.07,.07,h),M['steel'])
    # Corrugations project 0.02 m beyond the shell surface; remain inside posts.
    for x in (-1,1):
        for k in range(12):
            y=-d/2+.23+k*(d-.46)/11
            cube(p,'side_rib',(x*(w/2-.025),y,h/2),(.03,.055,h-.19),M[color])
    for ysign in (-1,1):
        for k in range(6):
            x=-w/2+.23+k*(w-.46)/5
            cube(p,'end_rib',(x,ysign*(d/2-.025),h/2),(.055,.03,h-.19),M[color])
    # Rear end doors, central seam, handles and rusty hinge plates.
    y=-d/2+.045
    cube(p,'door_seam',(0,y,h/2),(.035,.025,h-.22),M['black'])
    for x in (-.87,.87):
        for z in (.48,2.42):
            cube(p,'hinge',(x,y-.004,z),(.11,.03,.16),M['rust'])
    for x in (-.18,.18):
        cube(p,'door_lock_bar',(x,y-.004,1.4),(.035,.025,2.15),M['steel'])
    # Rust marks are exterior overlays, never hidden in shell.
    for _ in range(int(7+damage*10)):
        side=random.choice([-1,1])
        yy=random.uniform(-d/2+.2,d/2-.2)
        zz=random.uniform(.2,h-.2)
        cube(p,'rust_patch',(side*(w/2-.014),yy,zz),(.012,random.uniform(.08,.24),random.uniform(.08,.3)),M['rust'])
    # Exact top and bottom established by edge rails, making top flat/walkable.
    cube(p,'roof_skin',(0,0,h-.025),(w-.14,d-.14,.05),M[color])
    cube(p,'bottom_rail',(0,0,.025),(w-.14,d-.14,.05),M['steel'])
    return finish(p,name,at,(w,d,h))


def add_crate(at):
    w=d=1.6; h=1.0; p=[]
    cube(p,'crate_body',(0,0,.5),(1.52,1.52,.94),M['wood'])
    # Steel corner brackets and timber slats, with no protrusion past bounds.
    for x in (-.76,.76):
        for y in (-.76,.76):
            cube(p,'corner',(x,y,.5),(.08,.08,1),M['steel'])
    for z in (.17,.5,.83):
        for sign in (-1,1):
            cube(p,'front_slat',(0,sign*.775,z),(1.42,.05,.12),M['wood2'])
            cube(p,'side_slat',(sign*.775,0,z),(.05,1.42,.12),M['wood2'])
    cube(p,'flat_lid',(0,0,.97),(1.48,1.48,.06),M['wood2'])
    cube(p,'floor',(0,0,.03),(1.48,1.48,.06),M['wood2'])
    return finish(p,'crate',at,(w,d,h))


def add_car(name, burnt, at):
    """Y is the car's longitudinal axis. Roof ends at 1.35 m."""
    p=[]; w,d,h=1.9,4.0,1.35
    paint=M['rust_dark'] if burnt else M['redcar']
    cube(p,'lower_body',(0,0,.48),(1.84,3.90,.74),paint) # top .85
    cube(p,'chassis_bottom',(0,0,.06),(1.72,3.85,.12),M['black'])
    # Cabin: sloped windshield/rear windshield, trapezoidal roof profile.
    verts=[]
    for z,half_x,front_y,rear_y in [(.85,.84,-1.05,1.05),(1.35,.68,-.58,.66)]:
        verts += [(-half_x,front_y,z),(half_x,front_y,z),
                  (half_x,rear_y,z),(-half_x,rear_y,z)]
    faces=[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),
           (2,6,7,3),(3,7,4,0)]
    custom_mesh(p,'cabin',verts,faces,M['black'] if burnt else paint)
    # Dark windshield and rear glass: exterior coplanar offsets (2 cm).
    custom_mesh(p,'windshield',[
        (-.65,-.60,1.33),(.65,-.60,1.33),(.80,-1.07,.87),(-.80,-1.07,.87)],
        [(0,1,2,3)],M['glass'] if not burnt else M['ash'])
    custom_mesh(p,'rear_glass',[
        (-.65,.68,1.33),(.65,.68,1.33),(.80,1.07,.87),(-.80,1.07,.87)],
        [(0,3,2,1)],M['glass'] if not burnt else M['ash'])
    # Low-poly side windows, placed outside cabin surfaces.
    for side in (-1,1):
        custom_mesh(p,'side_glass',[
            (side*.865,-.91,.88),(side*.705,-.54,1.32),
            (side*.705,.61,1.32),(side*.865,.99,.88)],
            [(0,1,2,3)],M['glass'] if not burnt else M['ash'])
        # Flat tyres tucked inside wheel arches; no wheels projecting past width.
        for yy in (-1.27,1.25):
            cube(p,'flat_tire',(side*.87,yy,.22),(.06,.55,.30),M['black'])
    for yy in (-1.96,1.96):
        cube(p,'bumper',(0,yy,.40),(1.7,.08,.20),M['steel'])
    # Two small low-poly lights, not emissive.
    for xx in (-.62,.62):
        cube(p,'lamp',(xx,-1.974,.60),(.26,.052,.12),M['ash'] if burnt else M['concrete'])
    # Exact width/depth established by narrow edge details; all within box.
    for xx in (-.925,.925):
        cube(p,'outer_side_trim',(xx,0,.40),(.05,3.4,.09),paint)
    # Car ends at +/-2.0 m via bumpers; cabin ends at exactly 1.35 m.
    cube(p,'roof_flat',(0,.04,1.335),(1.25,1.14,.03),paint)
    if burnt:
        for _ in range(8):
            yy=random.uniform(-1.75,1.75)
            xx=random.choice([-1,1])*.932
            cube(p,'soot',(xx,yy,random.uniform(.4,.75)),(.025,.14,.11),M['ash'])
    return finish(p,name,at,(w,d,h))


def add_barricade(at):
    w,d,h=3,.5,.9; p=[]
    cube(p,'concrete_block',(0,0,.42),(2.9,.42,.78),M['concrete'])
    cube(p,'bottom_foot',(0,0,.04),(3,.5,.08),M['concrete2'])
    for z in (.35,.65):
        cube(p,'wood_plank',(0,-.226,z),(2.8,.048,.14),M['wood'])
    for x in (-1.36,1.36):
        cube(p,'edge',(x,-.228,.46),(.09,.045,.88),M['steel'])
    cube(p,'top_cap',(0,0,.865),(2.85,.40,.07),M['concrete2'])
    return finish(p,'barricade',at,(w,d,h))


def add_wall(at):
    # X = 10 m tileable length; Y = 2 m thickness; Z = 5 m height.
    w,d,h=10,2,5; p=[]
    cube(p,'solid_wall',(0,0,h/2),(w,d-.04,h),M['concrete'])
    # Face details at y +/- 1.0, protruding exactly 0.02 m from inset base
    # (the wall still fits within the 2.0 m envelope).
    for side in (-1,1):
        for row in range(8):
            z=.35+row*.60
            for col in range(12):
                x=-4.55+col*.82+(row%2)*.2
                if x > 4.65: continue
                if random.random() < .12*damage:
                    continue
                material = M['rust_dark'] if random.random()<.07 else M['concrete2']
                cube(p,'brick_face',(x,side*.990,z),(.68,.020,.34),material)
        for _ in range(13):
            x=random.uniform(-4.7,4.7)
            z=random.uniform(.4,4.7)
            cube(p,'soot',(x,side*.997,z),(.13,.006,.42),M['ash'])
    # Geometry already reaches exactly X +/-5, Y +/-1, Z 0..5.
    return finish(p,'wall_perimeter',at,(w,d,h))

# One scene containing eight individually selectable and exportable assets.
assets = [
    add_container('container_red','red',(0,0)),
    add_container('container_blue','blue',(SPACING,0)),
    add_container('container_green','green',(SPACING*2,0)),
    add_crate((0,SPACING)),
    add_car('car_wreck',True,(SPACING,SPACING)),
    add_car('car_red',False,(SPACING*2,SPACING)),
    add_barricade((0,SPACING*2)),
    add_wall((SPACING,SPACING*2)),
]

# GLB keeps each mesh separate and preserves its object name and transform.
bpy.ops.object.select_all(action='DESELECT')
for ob in assets:
    ob.select_set(True)
bpy.context.view_layer.objects.active = assets[0]
folder = bpy.path.abspath('//') if bpy.data.filepath else os.path.expanduser('~')
outfile = os.path.join(folder,EXPORT_NAME)
bpy.ops.export_scene.gltf(
    filepath=outfile, export_format='GLB', use_selection=True,
    export_apply=True, export_yup=True, export_materials='EXPORT',
)
print('Exported:',outfile)
