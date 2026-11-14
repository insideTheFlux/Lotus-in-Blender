"""A procedural lotus for Blender (Cycles, CPU or GPU), lit in a black space, from closed bud (0) to fully open (1).

    blender --background --python lotus.py -- <out.png> [openness 0..1] [samples] [resolution scale] [cpu|gpu]

The petals, stamens, materials, lights and camera are all built in code (no assets). Eight stacked petal layers wrap
round the axis so none cuts into another; the bud is a closed tulip shape that opens along one smooth curve. The
receptacle with its seed bumps and the fringe of stamens are sized to the opening the inner petals leave. From about
40 % the whole flower turns on its pivot to face the camera while the petals are still opening, and at 1 it looks
straight at it. The camera backs off a little during the turn so the lowest petal stays in frame.
"""
import bpy, bmesh, math, sys, random
random.seed(7)
args = sys.argv[sys.argv.index('--') + 1:]
out = args[0]
o = float(args[1]) if len(args) > 1 else 0.8
samples = int(args[2]) if len(args) > 2 else 96
use_gpu = len(args) > 4 and args[4].lower() == 'gpu'

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


# How far open the petals are. It eases in and out over the first 95 % of the load (so the opening keeps going
# while the flower lifts and turns) and is one smooth curve: no breakpoints.
BUD_TILT = 0.9       # closed bud: petals start out leaning, then curve right over the top like a tulip
BUD_CURL = 1.3
LAYER_TILT = 0.075   # open flower: each layer in is a little steeper than the one below
D = 0.04             # gap between stacked layers, measured along the petals' own normal
a_open = min(1.0, o / 0.95)
e = a_open * a_open * (3 - 2 * a_open)
CURL_POW = 1.0 + e                                   # bends evenly along the length when closed, near the tip when open
tilt0 = BUD_TILT * (1 - e) + 0.05 * e
def spread(u):
    """How much of its layer offset a petal has at fraction `u` of its length: a quarter of it at the root, where every layer
    is attached at the centre, all of it from 40 % out."""
    s = min(1.0, u / 0.4)
    return 0.25 + 0.75 * s * s * (3 - 2 * s)


def lowest_point():
    """The lowest height the outermost layer reaches (nominal petal, no jitter)."""
    curl = -0.95 * 0.45 * e + BUD_CURL * (1 - e)
    x = z = 0.0
    low = 0.0
    n = 40
    for i in range(n + 1):
        u = i / n
        ang = tilt0 + curl * u ** CURL_POW
        low = min(low, z - 7 * D * spread(u) * math.cos(ang))
        z += 1.55 / n * math.sin(ang)
    return low


ROOT_LIFT = -lowest_point() + 0.01                   # raises the flower so its lowest petal clears the floor


def petal(length, width, angle, lift, curl, cup, mat, tilt, off=0.0):
    """A petal growing outwards along +X from the centre, then turned round Z by `angle`.
    tilt: start angle above flat (radians); curl: how much that angle changes by the tip.
    off: slides the whole petal outwards along its own normal, which stacks the layers: the same distance apart
    everywhere, whether the petals stand up in the bud or lie flat when open, so they cannot cut through each other."""
    nu, nv = 18, 10
    bm = bmesh.new()
    pts = []
    x = z = 0.0
    for i in range(nu + 1):
        u = i / nu
        ang = tilt + curl * u ** CURL_POW
        so = off * spread(u)
        pts.append((x + so * math.sin(ang), z - so * math.cos(ang)))
        step = length / nu
        x += step * math.cos(ang)
        z += step * math.sin(ang)
    verts = []
    for i in range(nu + 1):
        u = i / nu
        w = width * (math.sin(math.pi * u ** 0.75) ** 0.85) + 0.004
        w *= 0.2 + 0.8 * min(1.0, u / 0.3)      # a narrow claw at the root, so the bases do not form a disc
        row = []
        for j in range(nv + 1):
            v = j / nv * 2 - 1
            px, pz = pts[i]
            px = max(px, 0.0)
            # wrap the petal round the axis: a point keeps its distance from the axis and its height, so stacked
            # petal layers are surfaces of revolution. Narrow at the root, widening outwards, and never wider than
            # the gap to the next petal of the same layer.
            amp = 0.15 + 0.47 * min(1.0, px / 0.6)
            phi = amp * math.tanh(v * w / max(px, 0.3) / amp)
            row.append(bm.verts.new((px * math.cos(phi), px * math.sin(phi), pz + cup * v * v * w * (0.4 + u))))
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

# (count, length, width, curl, phase, material); every ring has an even count so its petals alternate between two
# layers, eight layers in all, stacked from the outside in (0 = outermost).
jit = 0.1 + 0.9 * e       # petals are nearly identical in the bud and more individual as they open
rings = [
    (8, 1.55, 0.50, 0.95, 0.0, mat_outer),
    (8, 1.40, 0.46, 0.75, 0.5, mat_mid),
    (8, 1.22, 0.42, 0.55, 0.2, mat_in),
    (6, 1.00, 0.36, 0.35, 0.7, mat_in),
]
for ri, (n, L, W, curl, ph, mat) in enumerate(rings):
    for k in range(n):
        layer = 2 * ri + (k % 2)
        a = (k + ph) / n * math.tau + random.uniform(-0.05, 0.05)
        tilt = tilt0 + layer * LAYER_TILT * e + random.uniform(-0.012, 0.012) * jit
        petal(L * (1 + random.uniform(-0.08, 0.08) * jit), W * random.uniform(0.9, 1.1), a, ROOT_LIFT,
              (-curl * 0.45 * e + BUD_CURL * (1 - e)) * (1 + random.uniform(-0.1, 0.1) * jit),
              random.uniform(0.03, 0.06), mat, tilt, (7 - layer) * D)

# seed pod and stamens: sized to the opening the innermost petal ring leaves at this openness, so nothing pokes through
def opening_radius(height, margin=0.045):
    """How far from the axis the innermost layer (with its worst-case lean) is at `height`; 0 if it closes over it."""
    tilt = tilt0 + 7 * LAYER_TILT * e + 0.012
    curl = -0.35 * 0.45 * e + BUD_CURL * (1 - e)
    curl *= 1.1 if curl > 0 else 0.9
    x, z = 0.0, ROOT_LIFT
    n = 80
    step = 1.0 * 0.92 / n
    for i in range(n):
        u = (i + 0.5) / n
        ang = tilt + curl * u ** CURL_POW
        x += step * math.cos(ang)
        z += step * math.sin(ang)
        if z >= height:
            return max(0.0, 0.8 * x - margin)
    return 0.0


dz = ROOT_LIFT - 0.17                         # the centre rests just above the inner petals' roots
import mathutils
# The centre, after a real sacred lotus: a flat-topped yellow receptacle pitted with seed holes, ringed by a dense,
# low collar of short stamens that curve outwards as the flower opens. Everything is sized to the opening the inner
# petals leave at this openness, so nothing pokes through.
r_open = opening_radius(0.34 + dz)
pr = min(0.26, max(0.05, 0.68 * r_open))                # receptacle radius
z_top = 0.31 + dz                                      # height of its flat top
mat_pod = material('pod', (0.62, 0.70, 0.22, 1), 0.55)
mat_top = material('pod_top', (0.86, 0.80, 0.22, 1), 0.5, 0.1)
mat_pit = material('pit', (0.80, 0.52, 0.08, 1), 0.5)
mat_fil = material('filament', (1.0, 0.55, 0.05, 1), 0.5, 0.15)
mat_anth = material('anther', (1.0, 0.72, 0.14, 1), 0.45)
bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=pr * 0.6, radius2=pr, depth=0.10, location=(0, 0, z_top - 0.05))
bpy.context.object.data.materials.append(mat_pod)
for p in bpy.context.object.data.polygons:
    p.use_smooth = True
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=pr * 0.985, depth=0.006, location=(0, 0, z_top + 0.001))
bpy.context.object.data.materials.append(mat_top)
for i in range(30):                                    # seed holes in a spiral, like sunflower seeds
    rr = 0.8 * pr * math.sqrt((i + 0.5) / 30)
    aa = i * 2.39996
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.09 * pr,
                                         location=(rr * math.cos(aa), rr * math.sin(aa), z_top + 0.002))
    bpy.context.object.scale = (1, 1, 0.5)
    bpy.context.object.data.materials.append(mat_pit)
grow = min(1.0, o / 0.9)
grow = grow * grow * (3 - 2 * grow)
spread = 0.15 + 0.85 * e                               # upright and tight in the bud, curving out as it opens
for i in range(560):
    a = random.uniform(0, math.tau)
    rb = pr * random.uniform(0.88, 1.18)
    l = random.uniform(0.14, 0.27) * (0.7 + 0.3 * grow)
    lean = (0.12 + 0.62 * spread) * random.uniform(0.7, 1.2)     # angle from the vertical, outwards
    twist = random.uniform(-0.6, 0.6)                              # a little sideways curl
    zb = z_top - 0.07
    # never let the tip reach the petals
    r_lim = opening_radius(zb + l * math.cos(min(lean, 1.4)))
    if rb + l * math.sin(lean) > r_lim:
        lean = math.asin(max(0.0, min(0.9, (r_lim - rb) / l))) if r_lim > rb else 0.0
    az = a + twist
    axis = mathutils.Vector((math.cos(az) * math.sin(lean), math.sin(az) * math.sin(lean), math.cos(lean)))
    base = mathutils.Vector((math.cos(a) * rb, math.sin(a) * rb, zb))
    bpy.ops.mesh.primitive_cylinder_add(vertices=5, radius=0.0042, depth=l, location=base + axis * (l / 2))
    s = bpy.context.object
    s.rotation_mode = 'QUATERNION'
    s.rotation_quaternion = mathutils.Vector((0, 0, 1)).rotation_difference(axis)
    s.data.materials.append(mat_fil)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=6, radius=0.0062, location=base + axis * l)
    bpy.context.object.scale = (1, 1, 1.8)
    bpy.context.object.rotation_mode = 'QUATERNION'
    bpy.context.object.rotation_quaternion = mathutils.Vector((0, 0, 1)).rotation_difference(axis)
    bpy.context.object.data.materials.append(mat_anth)# turn the whole flower towards the camera as the load passes 40 %: facing us at 100 %
CAM_ELEV = math.atan2(4.0, 5.6)                      # the camera looks down at this angle
turn = max(0.0, min(1.0, (o - 0.38) / 0.62))   # holds still until 38 %, then eases round while the petals are still opening
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
PULL = 1.1 * math.sin(math.pi * max(0.0, min(1.0, (o - 0.50) / 0.32))) ** 2   # back off while the turned flower swings its lowest petal past the frame edge
cam.dof.focus_distance = 5.8 + 1.7 * o + PULL
cam.dof.aperture_fstop = 5.6
co = bpy.data.objects.new('c', cam)
sc.collection.objects.link(co)
sc.camera = co
DIST = 5.8 + 1.7 * o + PULL                                # closer for the bud, back for the open flower
co.location = (centre[0], centre[1] - DIST * math.cos(CAM_ELEV), centre[2] + DIST * math.sin(CAM_ELEV))
t = co.constraints.new('TRACK_TO')
t.target = tgt
t.track_axis = 'TRACK_NEGATIVE_Z'
t.up_axis = 'UP_Y'

sc.render.engine = 'CYCLES'
if use_gpu:                      # CUDA on an NVIDIA card; falls back to the CPU if none is found
    cp = bpy.context.preferences.addons['cycles'].preferences
    cp.compute_device_type = 'CUDA'
    cp.refresh_devices()
    for d in cp.devices:
        d.use = (d.type == 'CUDA')
    sc.cycles.device = 'GPU' if any(d.type == 'CUDA' for d in cp.devices) else 'CPU'
else:
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
