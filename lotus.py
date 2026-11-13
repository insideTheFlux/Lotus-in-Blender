"""A procedural lotus for Blender (Cycles, CPU), lit in a black space, from closed bud (0) to fully open (1).

    blender --background --python lotus.py -- <out.png> [openness 0..1] [samples] [resolution scale]

The flower's petals, stamens, materials, lights and camera are all built in code (no assets). As `openness` rises
the petals fall outwards; past 55 % the whole flower turns on its pivot to face the camera, fully facing it at 1.
"""
import bpy, bmesh, math, sys, random
random.seed(7)
args = sys.argv[sys.argv.index('--') + 1:]
out = args[0]
o = float(args[1]) if len(args) > 1 else 0.8
samples = int(args[2]) if len(args) > 2 else 96

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene


def material(name, base, rough=0.45, sss=0.0, emit=None, emit_s=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']

    def setp(k, v):
        if k in b.inputs:
            b.inputs[k].default_value = v
    setp('Base Color', base)
    setp('Roughness', rough)
    setp('Subsurface Weight', sss)
    setp('Subsurface Radius', (0.6, 0.25, 0.2))
    setp('Subsurface Scale', 0.08)
    if emit:
        setp('Emission Color', emit)
        setp('Emission Strength', emit_s)
    return m


def petal_material(name, base, tip):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    mp = nt.nodes.new('ShaderNodeMapRange')
    mp.inputs['From Min'].default_value = 0.0
    mp.inputs['From Max'].default_value = 1.2
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = base
    ramp.color_ramp.elements[1].color = tip
    mid = tuple((base[i] + tip[i]) / 2 for i in range(3)) + (1,)
    ramp.color_ramp.elements.new(0.5).color = mid
    nt.links.new(tc.outputs['Object'], sep.inputs['Vector'])
    nt.links.new(sep.outputs['X'], mp.inputs['Value'])
    nt.links.new(mp.outputs['Result'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    # veins run along the petal (X), so the bands vary across it (Y); a noise wobbles them and the ramp tint
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    wave.inputs['Scale'].default_value = 8.0
    wave.inputs['Distortion'].default_value = 3.0
    wave.inputs['Detail'].default_value = 3.0
    nt.links.new(tc.outputs['Object'], wave.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.12
    bump.inputs['Distance'].default_value = 0.02
    nt.links.new(wave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    dark = nt.nodes.new('ShaderNodeMix')
    dark.data_type = 'RGBA'
    dark.inputs['Factor'].default_value = 0.10
    dark.inputs['B'].default_value = (0.55, 0.1, 0.3, 1)
    nt.links.new(ramp.outputs['Color'], dark.inputs['A'])
    soft = nt.nodes.new('ShaderNodeMath')
    soft.operation = 'MULTIPLY'
    soft.inputs[1].default_value = 0.22
    nt.links.new(wave.outputs['Fac'], soft.inputs[0])
    nt.links.new(soft.outputs['Value'], dark.inputs['Factor'])
    nt.links.new(dark.outputs['Result'], b.inputs['Base Color'])
    dark.inputs['Factor'].default_value = 0.10
    b.inputs['Roughness'].default_value = 0.38
    if 'Subsurface Weight' in b.inputs:
        b.inputs['Subsurface Weight'].default_value = 0.35
        b.inputs['Subsurface Scale'].default_value = 0.1
        b.inputs['Subsurface Radius'].default_value = (0.7, 0.2, 0.2)
    return m


def petal(length, width, angle, lift, curl, cup, mat, tilt):
    """A petal growing outwards along +X from the centre, then turned round Z by `angle`.
    tilt: start angle above flat (radians); curl: how much that angle changes by the tip."""
    nu, nv = 18, 10
    bm = bmesh.new()
    pts = []
    x = z = 0.0
    for i in range(nu + 1):
        u = i / nu
        pts.append((x, z))
        ang = tilt + curl * u * u
        step = length / nu
        x += step * math.cos(ang)
        z += step * math.sin(ang)
    verts = []
    for i in range(nu + 1):
        u = i / nu
        w = width * (math.sin(math.pi * u ** 0.75) ** 0.85) + 0.004
        row = []
        for j in range(nv + 1):
            v = j / nv * 2 - 1
            px, pz = pts[i]
            row.append(bm.verts.new((px, v * w, pz + cup * v * v * w * (0.4 + u))))
        verts.append(row)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((verts[i][j], verts[i][j + 1], verts[i + 1][j + 1], verts[i + 1][j]))
    me = bpy.data.meshes.new('petal')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('petal', me)
    sc.collection.objects.link(ob)
    ob.rotation_euler = (0, 0, angle)
    ob.location = (0, 0, lift)
    for p in me.polygons:
        p.use_smooth = True
    s = ob.modifiers.new('sub', 'SUBSURF')
    s.levels = 2
    s.render_levels = 2
    th = ob.modifiers.new('thick', 'SOLIDIFY')
    th.thickness = 0.006
    ob.data.materials.append(mat)


pale = (0.95, 0.80, 0.84, 1)
rose = (0.93, 0.42, 0.62, 1)
mat_outer = petal_material('outer', (0.98, 0.86, 0.88, 1), (0.85, 0.12, 0.38, 1))
mat_mid = petal_material('mid', (0.99, 0.90, 0.90, 1), (0.92, 0.35, 0.55, 1))
mat_in = petal_material('in', (1.0, 0.95, 0.88, 1), (0.98, 0.62, 0.72, 1))

# (count, length, width, curl, height, phase, material); outer rings fall outwards first as the flower opens
rings = [
    (8, 1.55, 0.50, 0.95, 0.00, 0.0, mat_outer),
    (8, 1.40, 0.46, 0.75, 0.03, 0.5, mat_mid),
    (7, 1.22, 0.42, 0.55, 0.06, 0.2, mat_in),
    (6, 1.00, 0.36, 0.35, 0.09, 0.7, mat_in),
]
for ri, (n, L, W, curl, h, ph, mat) in enumerate(rings):
    # closed: petals stand up; open: they lean out. Inner rings stay more upright.
    stay = ri * 0.18
    for k in range(n):
        a = (k + ph) / n * math.tau + random.uniform(-0.05, 0.05)
        tilt = 1.35 * (1 - o) + (0.05 + stay * 0.6) * o
        # every petal is a little different: length, width, how far it leans and curls, how much it cups
        petal(L * random.uniform(0.92, 1.08), W * random.uniform(0.9, 1.1), a, h,
              (-curl * 0.45 * o + 0.25 * (1 - o)) * random.uniform(0.6, 1.4),
              random.uniform(0.35, 0.8), mat, tilt + random.uniform(-0.12, 0.12))


# seed pod and stamens: sized to the opening the innermost petal ring leaves at this openness, so nothing pokes through
def opening_radius(height, margin=0.045):
    """How far from the axis the innermost ring (with its worst-case lean) is at `height`; 0 if it closes over it."""
    tilt = 1.35 * (1 - o) + (0.05 + 3 * 0.18 * 0.6) * o + 0.12
    curl = -0.35 * 0.45 * o + 0.25 * (1 - o)
    x, z = 0.0, 0.09
    n = 80
    step = 1.0 * 0.92 / n
    for i in range(n):
        u = (i + 0.5) / n
        ang = tilt + curl * u * u
        x += step * math.cos(ang)
        z += step * math.sin(ang)
        if z >= height:
            return max(0.0, 0.8 * x - margin)
    return 0.0


pod_r = min(0.22, max(0.05, opening_radius(0.38)))
bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=pod_r * 0.77, radius2=pod_r, depth=0.16, location=(0, 0, 0.30))
pod = bpy.context.object
pod.data.materials.append(material('pod', (0.55, 0.65, 0.18, 1), 0.5))
for p in pod.data.polygons:
    p.use_smooth = True
mat_st = material('stamen', (1.0, 0.78, 0.15, 1), 0.35, 0.0, (1.0, 0.7, 0.1, 1), 0.8)
ring_max = min(0.36, opening_radius(0.36))
if ring_max > 0.12:
    import mathutils
    lean = 0.35
    for i in range(110):
        a = random.uniform(0, math.tau)
        rb = random.uniform(0.45, 1.0) * ring_max
        axis = mathutils.Vector((-math.cos(a) * math.sin(lean), -math.sin(a) * math.sin(lean), math.cos(lean)))
        base = mathutils.Vector((math.cos(a) * rb, math.sin(a) * rb, 0.36))
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.006, depth=0.3, location=base + axis * 0.15)
        s = bpy.context.object
        s.rotation_mode = 'QUATERNION'
        s.rotation_quaternion = mathutils.Vector((0, 0, 1)).rotation_difference(axis)
        s.data.materials.append(mat_st)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=0.017, location=base + axis * 0.30)
        bpy.context.object.data.materials.append(mat_st)
# turn the whole flower towards the camera as the load passes 40 %: facing us at 100 %
CAM_ELEV = math.atan2(4.0, 5.6)                      # the camera looks down at this angle
turn = max(0.0, min(1.0, (o - 0.55) / 0.45))   # holds still until 55 %, then eases round
turn = turn * turn * (3 - 2 * turn)                  # smoothstep
theta = (math.pi / 2 - CAM_ELEV) * turn              # the flower's axis ends up pointing at the camera
pivot = bpy.data.objects.new('pivot', None)
sc.collection.objects.link(pivot)
pivot.location = (0, 0, 0.5)
bpy.context.view_layer.update()
inv = pivot.matrix_world.inverted()
for ob in list(sc.objects):
    if ob is not pivot:
        ob.parent = pivot
        ob.matrix_parent_inverse = inv
lift = 1.8 * math.sin(theta)                         # float up so a tilted flower clears the floor
pivot.rotation_euler = (theta, 0, 0)
pivot.location = (0, 0, 0.5 + lift)
centre = (0.0, -0.3 * math.sin(theta), 0.5 + lift + 0.3 * math.cos(theta))

# a dark glossy floor: the flower reflects faintly in it and the rest falls into black
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=30, fill_type='NGON', location=(0, 0, -0.02))
floor = bpy.context.object
fm = bpy.data.materials.new('floor')
fm.use_nodes = True
fb = fm.node_tree.nodes['Principled BSDF']
fb.inputs['Base Color'].default_value = (0.004, 0.004, 0.005, 1)
fb.inputs['Roughness'].default_value = 0.22
floor.data.materials.append(fm)

# black world; light comes only from the lamps
world = bpy.data.worlds.new('w')
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0, 0, 0, 1)
bg.inputs['Strength'].default_value = 0.0

tgt = bpy.data.objects.new('t', None)
tgt.location = centre
sc.collection.objects.link(tgt)


def lamp(name, kind, loc, energy, color, size):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'AREA':
        ld.size = size
    lo = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(lo)
    lo.location = loc
    lo.visible_glossy = False   # lamps do not mirror in the floor
    t = lo.constraints.new('TRACK_TO')
    t.target = tgt
    t.track_axis = 'TRACK_NEGATIVE_Z'
    t.up_axis = 'UP_Y'


lamp('key', 'AREA', (-3.5, -4.0, 4.5), 480, (1.0, 0.90, 0.80), 3.0)     # warm, soft, from the front left
lamp('rim', 'AREA', (3.5, 5.0, 3.0), 900, (0.75, 0.85, 1.0), 2.5)       # cool, from behind: edges and glow through
lamp('top', 'AREA', (0.0, 0.5, 6.0), 150, (1.0, 0.92, 0.88), 3.0)      # a little from above for the centre

# camera
cam = bpy.data.cameras.new('c')
cam.lens = 48
cam.dof.use_dof = True
cam.dof.focus_distance = 5.8 + 1.7 * o
cam.dof.aperture_fstop = 5.6
co = bpy.data.objects.new('c', cam)
sc.collection.objects.link(co)
sc.camera = co
DIST = 5.8 + 1.7 * o                                  # closer for the bud, back for the open flower
co.location = (centre[0], centre[1] - DIST * math.cos(CAM_ELEV), centre[2] + DIST * math.sin(CAM_ELEV))
t = co.constraints.new('TRACK_TO')
t.target = tgt
t.track_axis = 'TRACK_NEGATIVE_Z'
t.up_axis = 'UP_Y'

sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = samples
sc.cycles.use_denoising = True
res_scale = float(args[3]) if len(args) > 3 else 1.0
sc.render.resolution_x = int(1600 * res_scale)
sc.render.resolution_y = int(1000 * res_scale)
sc.render.threads_mode = 'FIXED'
sc.render.threads = 6
try:
    sc.view_settings.view_transform = 'AgX'
except TypeError:
    sc.view_settings.view_transform = 'Filmic'
sc.render.filepath = out
sc.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print('DONE', out)



