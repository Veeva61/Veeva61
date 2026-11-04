# Soft "white roses + lavender filigree" profile art.
# Usage: blender -b --factory-startup --python rose.py -- <what> <out> [percent] [extra...]
#   what: hero | footer | div:<Title> | emblem (out = folder for frames)
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix

ARGS = sys.argv[sys.argv.index("--") + 1:]
WHAT, OUT = ARGS[0], ARGS[1]
PCT = int(ARGS[2]) if len(ARGS) > 2 else 100
EXTRA = ARGS[3:]

F_SCRIPT = r"C:\Windows\Fonts\Gabriola.ttf"
F_ITALIC = r"C:\Windows\Fonts\palai.ttf"


def lin(h, a=1.0):
    h = h.lstrip("#")
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(f(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


# ---------------- scene ----------------
def reset(w, h, samples=64):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    s = bpy.context.scene
    try:
        s.render.engine = "BLENDER_EEVEE"
    except TypeError as e:
        print("engine", e)
    s.render.resolution_x, s.render.resolution_y = w, h
    s.render.resolution_percentage = PCT
    s.eevee.taa_render_samples = samples
    s.eevee.use_raytracing = True
    for vt, look in (("AgX", "AgX - Medium High Contrast"), ("AgX", "Medium High Contrast"), ("AgX", "None"), ("Standard", "None")):
        try:
            s.view_settings.view_transform = vt
            s.view_settings.look = look
            break
        except TypeError:
            continue
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGB"
    w_ = bpy.data.worlds.new("W")
    s.world = w_
    w_.use_nodes = True
    bg = next(n for n in w_.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = lin("#2a2438")
    bg.inputs["Strength"].default_value = 0.6
    return s


def bloom(strength=0.55, threshold=0.85, size=0.8):
    s = bpy.context.scene
    ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    g = ng.nodes.new("CompositorNodeGlare")
    out = ng.nodes.new("NodeGroupOutput")
    for v in ("Bloom", "BLOOM"):
        try:
            g.inputs["Type"].default_value = v
            break
        except Exception:
            pass
    g.inputs["Threshold"].default_value = threshold
    g.inputs["Strength"].default_value = strength
    try:
        g.inputs["Size"].default_value = size
    except Exception as e:
        print("glare size", e)
    ng.links.new(rl.outputs["Image"], g.inputs["Image"])
    ng.links.new(g.outputs["Image"], out.inputs[0])
    s.compositing_node_group = ng
    s.render.use_compositing = True


def link(o):
    bpy.context.scene.collection.objects.link(o)
    return o


def empty(loc):
    return link(bpy.data.objects.new("E", None)) if False else _empty(loc)


def _empty(loc):
    e = link(bpy.data.objects.new("E", None))
    e.location = loc
    return e


def ortho_camera(width, y=-30):
    cd = bpy.data.cameras.new("C")
    cd.type = "ORTHO"
    cd.ortho_scale = width
    cd.clip_end = 200
    o = link(bpy.data.objects.new("C", cd))
    o.location = (0, y, 0)
    o.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.scene.camera = o
    return o


def area(loc, color, power, size, target):
    ld = bpy.data.lights.new("L", "AREA")
    ld.color = color[:3]
    ld.energy = power
    ld.size = size
    o = link(bpy.data.objects.new("L", ld))
    o.location = loc
    c = o.constraints.new("TRACK_TO")
    c.target = target
    return o


# ---------------- node helpers ----------------
def new_mat(name, method=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    if method:
        try:
            m.surface_render_method = method
        except Exception as e:
            print("render method", e)
    return m, m.node_tree


def math_node(nt, op, a=None, b=None, va=None, vb=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    if a is not None:
        nt.links.new(a, n.inputs[0])
    elif va is not None:
        n.inputs[0].default_value = va
    if b is not None:
        nt.links.new(b, n.inputs[1])
    elif vb is not None:
        n.inputs[1].default_value = vb
    return n.outputs[0]


def ramp_node(nt, fac, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0]
    els[1].position, els[1].color = stops[-1]
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = col
    nt.links.new(fac, r.inputs["Fac"])
    return r.outputs["Color"]


# ---------------- materials ----------------
def petal_mat():
    m, nt = new_mat("petal")
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vl = nt.nodes.new("ShaderNodeVectorMath")
    vl.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], vl.inputs[0])
    col = ramp_node(nt, vl.outputs["Value"], [(0.0, lin("#9d8bd8")), (0.28, lin("#d9d0fb")), (0.6, lin("#f7f4ff")), (1.0, lin("#ffffff"))])
    nt.links.new(col, p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = 0.5
    p.inputs["Subsurface Weight"].default_value = 0.35
    p.inputs["Sheen Weight"].default_value = 0.5
    p.inputs["Sheen Tint"].default_value = lin("#e8e0ff")
    return m


def silver_mat(glow=0.25):
    m, nt = new_mat("silver")
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = lin("#d8d0f5")
    p.inputs["Metallic"].default_value = 0.85
    p.inputs["Roughness"].default_value = 0.22
    p.inputs["Emission Color"].default_value = lin("#b9a8f0")
    p.inputs["Emission Strength"].default_value = glow
    return m


def leaf_mat():
    m, nt = new_mat("leaf")
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = lin("#a395d6")
    p.inputs["Metallic"].default_value = 0.75
    p.inputs["Roughness"].default_value = 0.3
    p.inputs["Emission Color"].default_value = lin("#9c8ad6")
    p.inputs["Emission Strength"].default_value = 0.12
    return m


def pearl_mat():
    m, nt = new_mat("pearl")
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = lin("#fbf8ff")
    p.inputs["Roughness"].default_value = 0.15
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Thin Film Thickness"].default_value = 380
    p.inputs["Emission Color"].default_value = lin("#ffffff")
    p.inputs["Emission Strength"].default_value = 0.3
    return m


def glow_mat(color, strength):
    m, nt = new_mat("glow")
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = color
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], o.inputs["Surface"])
    return m


def bokeh_mat(color, strength, opacity):
    """Soft round dot: radial alpha falloff from object-space centre (circle of radius 1)."""
    m, nt = new_mat("bokeh", "BLENDED")
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vl = nt.nodes.new("ShaderNodeVectorMath"); vl.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], vl.inputs[0])
    inv = math_node(nt, "SUBTRACT", va=1.0, b=vl.outputs["Value"])
    a = math_node(nt, "POWER", a=inv, vb=1.6)
    a = math_node(nt, "MULTIPLY", a=a, vb=opacity)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = color
    e.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(a, mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(e.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], o.inputs["Surface"])
    return m


def feather_mat(opacity=0.85):
    """Glowing translucent feather from UVs: soft edges, chevron barbs, bright shaft."""
    m, nt = new_mat("feather", "BLENDED")
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    uvn = nt.nodes.new("ShaderNodeUVMap")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uvn.outputs["UV"], sep.inputs[0])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    su = math_node(nt, "ABSOLUTE", a=math_node(nt, "SUBTRACT", a=math_node(nt, "MULTIPLY", a=u, vb=2.0), vb=1.0))
    edge = math_node(nt, "POWER", a=math_node(nt, "SUBTRACT", va=1.0, b=su), vb=0.7)
    chev = math_node(nt, "SINE", a=math_node(nt, "MULTIPLY", a=math_node(nt, "SUBTRACT", a=math_node(nt, "MULTIPLY", a=su, vb=0.45), b=v), vb=90.0))
    barbs = math_node(nt, "MULTIPLY_ADD", a=chev, vb=0.25) if False else math_node(nt, "ADD", a=math_node(nt, "MULTIPLY", a=chev, vb=0.22), vb=0.78)
    tipfade = math_node(nt, "MULTIPLY", a=math_node(nt, "POWER", a=v, vb=0.35), b=math_node(nt, "POWER", a=math_node(nt, "SUBTRACT", va=1.0, b=v), vb=0.25))
    a = math_node(nt, "MULTIPLY", a=math_node(nt, "MULTIPLY", a=edge, b=barbs), b=tipfade)
    a = math_node(nt, "MINIMUM", a=math_node(nt, "MULTIPLY", a=a, vb=opacity * 1.1), vb=1.0)
    shaft = math_node(nt, "MAXIMUM", a=math_node(nt, "SUBTRACT", va=1.0, b=math_node(nt, "MULTIPLY", a=su, vb=18.0)), vb=0.0)
    strength = math_node(nt, "ADD", a=math_node(nt, "MULTIPLY", a=shaft, vb=6.0), vb=4.5)
    col = ramp_node(nt, u if False else v, [(0.0, lin("#b9a6ff")), (0.6, lin("#efe9ff")), (1.0, lin("#ffffff"))])
    e = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(col, e.inputs["Color"])
    nt.links.new(strength, e.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(a, mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(e.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], o.inputs["Surface"])
    return m


def backdrop(width, height, center="#3b3452", edge="#16131d", y=6.0, glow_center=(0, 0), squash=0.55, mid="#272135"):
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, y, 0), rotation=(math.radians(90), 0, 0))
    o = bpy.context.object
    o.scale = (width * 0.6, height * 0.6, 1)
    m, nt = new_mat("bg")
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (-glow_center[0], -glow_center[1], 0)
    mp.inputs["Scale"].default_value = (1.0, width / height * squash, 1)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    vl = nt.nodes.new("ShaderNodeVectorMath"); vl.operation = "LENGTH"
    nt.links.new(mp.outputs["Vector"], vl.inputs[0])
    col = ramp_node(nt, vl.outputs["Value"], [(0.0, lin(center)), (0.55, lin(mid)), (1.0, lin(edge))])
    e = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(col, e.inputs["Color"])
    e.inputs["Strength"].default_value = 1.0
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    o.data.materials.append(m)
    return o


# ---------------- geometry ----------------
def grid(w, h, kind, cup=0.0, curl=0.0, nu=10, nv=16, bend=0.0):
    verts, uvs = [], []
    for j in range(nv + 1):
        v = j / nv
        if kind == "petal":
            hw = 0.5 * w * (math.sin(math.pi * min(v, 0.995)) ** 0.45) * (0.32 + 0.68 * v)
        elif kind == "leaf":
            hw = 0.5 * w * (math.sin(math.pi * v) ** 0.85)
        else:  # feather
            hw = 0.5 * w * (math.sin(math.pi * v) ** 0.6) * (1.15 - 0.35 * v)
        for i in range(nu + 1):
            u = i / nu
            s = 2 * u - 1
            x = s * hw
            z = h * v
            if kind == "petal":
                y = -cup * s * s * (0.3 + 0.7 * v) + curl * h * max(0.0, v - 0.5) ** 2 * 3.0
            elif kind == "leaf":
                y = -cup * abs(s) * math.sin(math.pi * v)
            else:
                y = bend * h * math.sin(math.pi * v) - 0.04 * h * s * s
                x += 0.12 * h * v * v
            verts.append(Vector((x, y, z)))
            uvs.append((u, v))
    faces = [(j * (nu + 1) + i, j * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i)
             for j in range(nv) for i in range(nu)]
    return verts, faces, uvs


def build(name, parts, mat, solid=0.0, subsurf=1, smooth=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for verts, faces, uvs, M in parts:
        bv = [bm.verts.new(M @ v) for v in verts]
        for f in faces:
            try:
                face = bm.faces.new([bv[k] for k in f])
            except ValueError:
                continue
            for loop, k in zip(face.loops, f):
                loop[uvl].uv = uvs[k]
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new(name, me))
    if smooth:
        me.shade_smooth()
    if solid:
        s = o.modifiers.new("s", "SOLIDIFY"); s.thickness = solid; s.offset = 0
    if subsurf:
        d = o.modifiers.new("d", "SUBSURF"); d.levels = 0; d.render_levels = subsurf
    o.data.materials.append(mat)
    return o


MATS = {}


def mats():
    if not MATS:
        MATS.update(petal=petal_mat(), silver=silver_mat(), leaf=leaf_mat(), pearl=pearl_mat())
    return MATS


def rose(loc, scale, tilt=(0, 0), n=34, seed=0, openness=1.0):
    rnd = random.Random(seed)
    parts = []
    spin = rnd.uniform(0, 6.28)
    for i in range(n):
        t = i / (n - 1)
        a = spin + math.radians(i * 137.508) + rnd.uniform(-0.08, 0.08)
        r = 0.02 + 0.42 * t ** 1.3
        h = 0.36 + 0.60 * t
        w = 0.32 + 0.82 * t
        cup = 0.30 * (1 - t) ** 1.5 + 0.05
        curl = (0.03 + 0.34 * t ** 1.6) * openness
        tl = math.radians(4 + 75 * openness * t ** 1.6)
        vs, fs, uv = grid(w, h, "petal", cup=cup, curl=curl, nu=8, nv=12)
        M = (Matrix.Translation((r * math.cos(a), r * math.sin(a), -0.14 * t))
             @ Matrix.Rotation(a - math.pi / 2, 4, "Z") @ Matrix.Rotation(-tl, 4, "X"))
        parts.append((vs, fs, uv, M))
    o = build("rose", parts, mats()["petal"], solid=0.012, subsurf=2)
    o.location = loc
    o.scale = (scale,) * 3
    o.rotation_euler = (math.radians(90 + tilt[0]), math.radians(tilt[1]), 0)
    return o


def leaf(base, length, angle_deg, tilt=15, width=0.42):
    vs, fs, uv = grid(width * length, length, "leaf", cup=0.06 * length, nu=6, nv=14)
    o = build("leaf", [(vs, fs, uv, Matrix())], mats()["leaf"], solid=0.01, subsurf=1)
    o.location = base
    o.rotation_euler = (math.radians(tilt), math.radians(-angle_deg + 90), 0)
    return o


def feather(loc, length, angle_deg, width=0.27, bend=0.12, opacity=0.85):
    vs, fs, uv = grid(width * length, length, "feather", nu=10, nv=24, bend=bend)
    o = build("feather", [(vs, fs, uv, Matrix())], feather_mat(opacity), subsurf=1)
    o.location = (loc[0], -1.2, loc[1])
    o.rotation_euler = (math.radians(-6), math.radians(-angle_deg + 90), 0)
    return o


def star(loc, size, mat, rot=0.0, y=-1.0):
    me = bpy.data.meshes.new("star")
    bm = bmesh.new()
    c = bm.verts.new((0, 0, 0))
    ring = []
    for k in range(8):
        ang = math.radians(k * 45) + rot
        rad = size if k % 2 == 0 else size * 0.11
        if k % 4 == 2:
            rad *= 0.72  # horizontal rays a bit shorter
        ring.append(bm.verts.new((math.cos(ang) * rad, 0, math.sin(ang) * rad)))
    for k in range(8):
        bm.faces.new([c, ring[k], ring[(k + 1) % 8]])
    bm.to_mesh(me)
    bm.free()
    o = link(bpy.data.objects.new("star", me))
    o.location = (loc[0], y, loc[1])
    o.data.materials.append(mat)
    return o


def dot(loc, r, mat, y=0.5):
    bpy.ops.mesh.primitive_circle_add(vertices=32, radius=1.0, fill_type="NGON", location=(loc[0], y, loc[1]), rotation=(math.radians(90), 0, 0))
    o = bpy.context.object
    o.scale = (r, r, r)
    o.data.materials.append(mat)
    return o


def pearl(loc, r, y=-0.3):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=r, location=(loc[0], y, loc[1]))
    o = bpy.context.object
    o.data.shade_smooth()
    o.data.materials.append(mats()["pearl"])
    return o


def curve(points, radii, bevel, mat, name="fil"):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for p, co, r in zip(sp.points, points, radii):
        p.co = (co[0], co[1], co[2], 1.0)
        p.radius = r
    o = link(bpy.data.objects.new(name, cu))
    o.data.materials.append(mat)
    return o


def spiral(c, R, a0, turns, d, y=0.0, n=90, r0=1.0, r1=0.35):
    pts, rad = [], []
    for k in range(n + 1):
        t = k / n
        rr = R * (1 - 0.8 * t)
        a = a0 + d * 2 * math.pi * turns * t
        pts.append((c[0] + rr * math.cos(a), y, c[1] + rr * math.sin(a)))
        rad.append(r0 + (r1 - r0) * t)
    return pts, rad


def vine(x0, x1, z, amp, period, bevel, mirror=False, y=0.0, curl_r=None, pearls=True):
    """Wavy silver vine with spiral curls at every crest/trough."""
    m = mats()["silver"]
    curl_r = curl_r or amp * 1.15
    sx = -1 if mirror else 1
    n = max(40, int(abs(x1 - x0) * 40))
    pts, rad = [], []
    for k in range(n + 1):
        t = k / n
        x = x0 + (x1 - x0) * t
        pts.append((sx * x, y, z + amp * math.sin(2 * math.pi * (x - x0) / period)))
        rad.append(1.0 - 0.45 * t)
    curve(pts, rad, bevel, m)
    xs = x0 + period / 4
    up = True
    while (xs - x1) * (1 if x1 > x0 else -1) < -period * 0.05:
        cz = z + (amp if up else -amp)
        cc = (sx * xs, cz + (curl_r if up else -curl_r))
        a0 = -math.pi / 2 if up else math.pi / 2
        dirn = (1 if up else -1) * (-1 if x1 > x0 else 1) * sx
        p, r = spiral(cc, curl_r, a0, 1.15, dirn, y=y, r0=0.85, r1=0.3)
        curve(p, r, bevel, m)
        if pearls:
            pearl(cc, bevel * 2.2, y=y - 0.05)
        xs += period / 2 * (1 if x1 > x0 else -1)
        up = not up


def rounded_rect(w, h, r, bevel, y=0.0):
    pts = []
    for cx, cz, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(17):
            a = math.radians(a0 + 90 * k / 16)
            pts.append((cx + r * math.cos(a), y, cz + r * math.sin(a)))
    pts.append(pts[0])
    curve(pts, [1.0] * len(pts), bevel, mats()["silver"], name="frame")


def text(body, font, size, mat, loc, align="CENTER", y=-0.6, extrude=0.0):
    cu = bpy.data.curves.new("t", "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    cu.align_y = "CENTER"
    o = link(bpy.data.objects.new("t", cu))
    o.location = (loc[0], y, loc[1])
    o.rotation_euler = (math.radians(90), 0, 0)
    o.data.materials.append(mat)
    return o


def fit(o, max_w, max_h):
    bpy.context.view_layer.update()
    d = o.dimensions
    k = min(max_w / max(d.x, 1e-6), max_h / max(d.y, 1e-6))
    o.scale = (k, k, k)
    return k


def bouquet(cx, cz, s, seed, roses=3, leaves=5, flip=1, y=-0.8):
    rnd = random.Random(seed)
    offs = [(0, 0, 1.0), (0.55, -0.25, 0.72), (-0.45, 0.3, 0.62), (0.2, 0.5, 0.5)][:roses]
    for i, (dx, dz, k) in enumerate(offs):
        rose((cx + flip * dx * s, y - 0.1 * i, cz + dz * s), 0.55 * s * k,
             tilt=(rnd.uniform(-25, 25), rnd.uniform(-25, 25)), seed=seed * 10 + i, openness=0.75 + 0.3 * k)
    for i in range(leaves):
        ang = rnd.uniform(0, 360)
        base = (cx + math.cos(math.radians(ang)) * 0.25 * s, y + 0.25, cz + math.sin(math.radians(ang)) * 0.25 * s)
        leaf(base, rnd.uniform(0.55, 0.85) * s, ang, tilt=rnd.uniform(-20, 20))


def sparkle_field(xr, zr, n_star, n_dot, seed=1, avoid=None, star_max=0.22):
    rnd = random.Random(seed)
    smat = glow_mat(lin("#ffffff"), 9.0)
    smat2 = glow_mat(lin("#e6dcff"), 7.0)
    dmats = [bokeh_mat(lin("#efe8ff"), 2.0, 0.8), bokeh_mat(lin("#cbb8ff"), 2.0, 0.6), bokeh_mat(lin("#ffffff"), 3.0, 0.9)]
    stars, dots = [], []

    def ok(x, z):
        return not avoid or not any(a[0] < x < a[1] and a[2] < z < a[3] for a in avoid)

    while len(stars) < n_star:
        x, z = rnd.uniform(*xr), rnd.uniform(*zr)
        if ok(x, z):
            sz = star_max * rnd.random() ** 2.2 + 0.03
            stars.append(star((x, z), sz, smat if rnd.random() < 0.6 else smat2, rot=rnd.uniform(-0.15, 0.15), y=-1.5 - rnd.random()))
    while len(dots) < n_dot:
        x, z = rnd.uniform(*xr), rnd.uniform(*zr)
        dots.append(dot((x, z), 0.012 + 0.05 * rnd.random() ** 3, rnd.choice(dmats), y=rnd.uniform(-1.2, 1.0)))
    return stars, dots


def key_lights(target, w):
    area((-w * 0.35, -14, 8), lin("#ffffff"), 2600, 8, target)
    area((w * 0.4, -12, 4), lin("#cdbfff"), 1500, 8, target)
    area((0, -6, -9), lin("#b39dff"), 600, 10, target)


def render(path):
    s = bpy.context.scene
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)


# ---------------- compositions ----------------
def hero():
    W, H = 16.0, 6.0
    reset(1600, 600)
    bloom()
    ortho_camera(W)
    tgt = _empty((0, 0, 0))
    backdrop(W, H, center="#4a4166", edge="#1c1825")
    rounded_rect(W - 0.7, H - 0.7, 0.7, 0.025)
    rounded_rect(W - 1.0, H - 1.0, 0.55, 0.012)
    for z, sign in ((H / 2 - 0.42, 1), (-H / 2 + 0.42, -1)):
        vine(0.75, 5.6, z, 0.12, 1.05, 0.022)
        vine(0.75, 5.6, z, 0.12, 1.05, 0.022, mirror=True)
    for x in (W / 2 - 0.42, -W / 2 + 0.42):
        pts = [(x, 0, -1.2 + 2.4 * k / 60) for k in range(61)]
        curve(pts, [1.0] * 61, 0.018, mats()["silver"])
    # corner and centre bouquets
    bouquet(-7.0, 2.2, 1.35, 1, roses=3, leaves=6)
    bouquet(7.0, 2.2, 1.35, 2, roses=3, leaves=6, flip=-1)
    bouquet(-7.0, -2.25, 1.2, 3, roses=2, leaves=5)
    bouquet(7.0, -2.25, 1.2, 4, roses=2, leaves=5, flip=-1)
    bouquet(0, 2.75, 0.85, 5, roses=1, leaves=4)
    bouquet(0, -2.75, 0.85, 6, roses=1, leaves=4)
    # name + subtitle
    name = text("Veeva61", F_SCRIPT, 2.2, glow_mat(lin("#f6f2ff"), 2.2), (0, 0.35))
    fit(name, 7.5, 2.3)
    sub = text("вайбкодер  ·  порты игр на Android  ·  моды", F_ITALIC, 0.36, glow_mat(lin("#c8b7ff"), 1.6), (0, -0.95))
    fit(sub, 8.0, 0.42)
    smat = glow_mat(lin("#ffffff"), 8)
    bpy.context.view_layer.update()
    sx = sub.dimensions.x / 2 + 0.4
    for x in (-sx, sx):
        star((x, -0.93), 0.17, smat)
    feather((-5.4, -1.9), 1.9, 62, opacity=0.8)
    feather((4.7, 0.6), 1.3, 128, opacity=0.6)
    feather((2.6, -2.0), 0.9, 40, opacity=0.55)
    sparkle_field((-7.6, 7.6), (-2.7, 2.7), 46, 170, seed=3, avoid=[(-3.8, 3.8, -0.55, 1.45), (-4.9, 4.9, -1.3, -0.55)])
    key_lights(tgt, W)
    render(OUT)


def divider(title):
    W, H = 16.0, 2.0
    reset(1600, 200)
    bloom(0.5)
    ortho_camera(W)
    tgt = _empty((0, 0, 0))
    backdrop(W, H * 1.6, center="#352e4a", edge="#14111a")
    t = text(title, F_SCRIPT, 1.0, glow_mat(lin("#f3eeff"), 2.0), (0, 0.02))
    t.scale = (1.9, 1.9, 1.9)  # same letter size for every section
    bpy.context.view_layer.update()
    half = t.dimensions.x / 2 + 0.55
    for mirror in (False, True):
        vine(half, 6.2, -0.05, 0.13, 1.0, 0.02, mirror=mirror)
    smat = glow_mat(lin("#ffffff"), 9)
    for x in (half - 0.25, -(half - 0.25)):
        star((x, 0.05), 0.18, smat)
    for x, fl in ((6.95, -1), (-6.95, 1)):
        rose((x, -0.8, 0.0), 0.55, tilt=(10, -20 * fl), seed=int(abs(x) * 10) + len(title), openness=0.9)
        for ang in (20, 160, 250, 300):
            leaf((x, -0.5, 0.0), 0.62, ang + (0 if fl > 0 else 15), tilt=10)
    sparkle_field((-7.8, 7.8), (-0.95, 0.95), 16, 60, seed=len(title), avoid=[(-half + 0.3, half - 0.3, -0.5, 0.5)], star_max=0.14)
    key_lights(tgt, W)
    render(OUT)


def footer():
    W, H = 16.0, 3.4
    reset(1600, 340)
    bloom()
    ortho_camera(W)
    tgt = _empty((0, 0, 0))
    backdrop(W, H * 1.3, center="#3b3452", edge="#14111a", glow_center=(0, 0.2))
    vine(1.4, 7.4, -0.95, 0.12, 1.05, 0.022)
    vine(1.4, 7.4, -0.95, 0.12, 1.05, 0.022, mirror=True)
    bouquet(0, -0.82, 1.1, 9, roses=3, leaves=7)
    t = text("спасибо, что заглянул(а)", F_SCRIPT, 1.0, glow_mat(lin("#f3eeff"), 2.0), (0, 0.75))
    fit(t, 7.0, 1.0)
    feather((-4.8, 0.2), 1.1, 70, opacity=0.6)
    feather((4.6, -0.1), 0.9, 115, opacity=0.5)
    sparkle_field((-7.8, 7.8), (-1.6, 1.6), 30, 110, seed=21, avoid=[(-3.6, 3.6, 0.3, 1.25)])
    key_lights(tgt, W)
    render(OUT)


def emblem():
    W = 6.0
    reset(420, 420, samples=32)
    bloom(0.6)
    ortho_camera(W)
    tgt = _empty((0, 0, 0))
    backdrop(W, W, center="#463d66", edge="#16131d")
    # filigree ring
    ring = [(2.45 * math.cos(math.radians(a)), 0, 2.45 * math.sin(math.radians(a))) for a in range(0, 361, 3)]
    curve(ring, [1.0] * len(ring), 0.03, mats()["silver"])
    ring2 = [(2.3 * math.cos(math.radians(a)), 0, 2.3 * math.sin(math.radians(a))) for a in range(0, 361, 3)]
    curve(ring2, [1.0] * len(ring2), 0.012, mats()["silver"])
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        c = (2.62 * math.cos(a), 2.62 * math.sin(a))
        p, r = spiral(c, 0.16, a + math.pi, 1.1, 1 if k % 2 else -1, r0=0.8, r1=0.3)
        curve(p, r, 0.02, mats()["silver"])
        pearl((2.45 * math.cos(math.radians(k * 45)), 2.45 * math.sin(math.radians(k * 45))), 0.06)
    main = rose((0, -0.8, 0.5), 0.95, tilt=(18, 0), seed=77, openness=0.9)
    for ang in (195, 235, 305, 345):
        leaf((0, -0.4, 0.15), 1.15, ang, tilt=12)
    t = text("вайбкодер", F_SCRIPT, 0.7, glow_mat(lin("#f3eeff"), 2.2), (0, -1.55), y=-2.0)
    fit(t, 2.6, 0.75)
    feathers = [feather((x, z), l, a, opacity=0.7) for x, z, l, a in ((-1.6, 1.0, 0.9, 70), (1.4, 0.2, 0.7, 120), (0.3, 2.0, 0.6, 95))]
    stars, dots = sparkle_field((-2.2, 2.2), (-2.2, 2.2), 18, 50, seed=8, avoid=[(-0.9, 0.9, -0.9, 1.3)], star_max=0.2)
    key_lights(tgt, 8)
    frames = int(EXTRA[0]) if EXTRA else 48
    os.makedirs(OUT, exist_ok=True)
    rnd = random.Random(4)
    phases = [rnd.random() for _ in stars]
    base = [s.scale.copy() for s in stars]
    f0 = [(f.location.x, f.location.z) for f in feathers]
    for fr in range(frames):
        t = fr / frames
        main.rotation_euler = (math.radians(90 + 18), 0, math.radians(8 * math.sin(2 * math.pi * t)))
        for s, ph, b in zip(stars, phases, base):
            k = 0.25 + 0.75 * abs(math.sin(math.pi * (t + ph)))
            s.scale = b * k
        for f, (x, z) in zip(feathers, f0):
            dz = -4.4 * t
            zz = z + dz
            if zz < -2.2:
                zz += 4.4
            f.location = (x + 0.25 * math.sin(2 * math.pi * (t * 2) + x), f.location.y, zz)
            f.rotation_euler[1] = math.radians(-20 * math.sin(2 * math.pi * t + x))
        render(os.path.join(OUT, "f_%03d.png" % fr))


if WHAT == "hero":
    hero()
elif WHAT == "footer":
    footer()
elif WHAT == "emblem":
    emblem()
elif WHAT.startswith("div:"):
    divider(WHAT[4:])


def rosetest():
    W = 4.0
    reset(500, 500, samples=32)
    bloom(0.4)
    ortho_camera(W)
    tgt = _empty((0, 0, 0))
    backdrop(W, W, center="#463d66", edge="#16131d")
    rose((-0.9, -0.8, 0.6), 0.85, tilt=(15, 10), seed=1, openness=1.0)
    rose((0.9, -0.8, 0.6), 0.85, tilt=(35, -15), seed=2, openness=0.7)
    for ang in (200, 250, 300, 340):
        leaf((0, -0.4, -0.9), 0.9, ang, tilt=12)
    feather((-1.2, -1.6), 1.2, 60)
    star((1.2, -1.0), 0.25, glow_mat(lin("#ffffff"), 9))
    vine(-1.8, 1.8, -1.7, 0.1, 0.9, 0.02)
    key_lights(tgt, 6)
    render(OUT)


if WHAT == "rosetest":
    rosetest()


def avatar():
    """Square avatar built for a circular crop: rose bouquet inside a filigree ring."""
    W = 6.0
    reset(1024, 1024, samples=96)
    bloom(0.55)
    ortho_camera(W)
    tgt = _empty((0, 0, 0))
    backdrop(W, W, center="#524873", edge="#1c1825", glow_center=(0, 0.15))
    # double ring with outward curls and pearls
    for R, bev in ((2.5, 0.032), (2.34, 0.013)):
        ring = [(R * math.cos(math.radians(a)), 0, R * math.sin(math.radians(a))) for a in range(0, 361, 2)]
        curve(ring, [1.0] * len(ring), bev, mats()["silver"])
    for k in range(12):
        a = math.radians(k * 30 + 15)
        c = (2.68 * math.cos(a), 2.68 * math.sin(a))
        p, r = spiral(c, 0.15, a + math.pi, 1.1, 1 if k % 2 else -1, r0=0.8, r1=0.3)
        curve(p, r, 0.02, mats()["silver"])
        pearl((2.5 * math.cos(math.radians(k * 30)), 2.5 * math.sin(math.radians(k * 30))), 0.055)
    # bouquet
    rose((0, -0.9, 0.3), 1.05, tilt=(16, 0), seed=77, openness=0.9)
    rose((-1.05, -0.6, -0.72), 0.62, tilt=(20, 25), seed=78, openness=0.8)
    rose((1.08, -0.6, -0.66), 0.58, tilt=(22, -28), seed=79, openness=0.75)
    for ang, l in ((145, 1.85), (178, 1.95), (212, 1.7), (255, 1.45), (285, 1.45), (328, 1.7), (2, 1.95), (35, 1.85)):
        leaf((0, -0.3, -0.15), l, ang, tilt=12, width=0.36)
    feather((0.9, 0.9), 1.3, 118, opacity=0.65)
    feather((-1.5, 0.75), 0.8, 72, opacity=0.5)
    sparkle_field((-2.1, 2.1), (-2.1, 2.1), 22, 70, seed=12, avoid=[(-1.6, 1.6, -1.3, 1.4)], star_max=0.2)
    key_lights(tgt, 8)
    render(OUT)


if WHAT == "avatar":
    avatar()


def filigree_ring(R=2.5, curls=12, mat=None):
    mat = mat or mats()["silver"]
    for r_, bev in ((R, 0.032), (R - 0.16, 0.013)):
        ring = [(r_ * math.cos(math.radians(a)), 0, r_ * math.sin(math.radians(a))) for a in range(0, 361, 2)]
        curve(ring, [1.0] * len(ring), bev, mat)
    step = 360 / curls
    for k in range(curls):
        a = math.radians(k * step + step / 2)
        c = ((R + 0.18) * math.cos(a), (R + 0.18) * math.sin(a))
        p, r = spiral(c, 0.15, a + math.pi, 1.1, 1 if k % 2 else -1, r0=0.8, r1=0.3)
        curve(p, r, 0.02, mat)
        pearl((R * math.cos(math.radians(k * step)), R * math.sin(math.radians(k * step))), 0.055)


def avatar_base(center="#524873", edge="#1c1825", samples=96, mid="#272135", bloom_t=0.85):
    W = 6.0
    reset(1024, 1024, samples=samples)
    bloom(0.55, threshold=bloom_t)
    ortho_camera(W)
    tgt = _empty((0, 0, 0))
    backdrop(W, W, center=center, edge=edge, glow_center=(0, 0.15), squash=1.0, mid=mid)
    return tgt


def avatar_variant(v):
    if v == "single":
        tgt = avatar_base()
        filigree_ring()
        rose((0, -0.9, 0.05), 1.55, tilt=(12, 0), seed=91, openness=0.95)
        for ang, l in ((140, 2.0), (200, 1.9), (250, 1.6), (290, 1.6), (340, 1.9), (40, 2.0)):
            leaf((0, -0.3, -0.05), l, ang, tilt=10, width=0.34)
        sparkle_field((-2.1, 2.1), (-2.1, 2.1), 20, 60, seed=31, avoid=[(-1.7, 1.7, -1.7, 1.7)], star_max=0.2)
    elif v == "monogram":
        tgt = avatar_base(center="#4d4470")
        filigree_ring()
        t = text("V", F_SCRIPT, 1.0, glow_mat(lin("#f6f2ff"), 2.4), (0.1, 0.2), y=-0.4)
        fit(t, 2.3, 2.5)
        rose((-0.75, -1.1, -1.05), 0.72, tilt=(18, 20), seed=92, openness=0.85)
        rose((0.35, -1.0, -1.45), 0.45, tilt=(25, -20), seed=93, openness=0.7)
        for ang, l in ((150, 1.3), (200, 1.2), (250, 1.0), (330, 1.4), (20, 1.1)):
            leaf((-0.5, -0.6, -1.2), l, ang, tilt=12, width=0.34)
        feather((1.25, 0.6), 1.2, 115, opacity=0.6)
        sparkle_field((-2.1, 2.1), (-2.1, 2.1), 24, 70, seed=32, avoid=[(-1.3, 1.5, -1.0, 1.9), (-1.6, 0.9, -1.9, -0.6)], star_max=0.2)
    elif v == "wreath":
        tgt = avatar_base(center="#4a4168")
        thin = [(2.55 * math.cos(math.radians(a)), 0, 2.55 * math.sin(math.radians(a))) for a in range(0, 361, 2)]
        curve(thin, [1.0] * len(thin), 0.012, mats()["silver"])
        n = 8
        for i in range(n):
            t_ = i / (n - 1)
            a = math.radians(125 + 220 * t_)
            k = 0.35 + 0.45 * math.sin(math.pi * t_)
            R = 1.85
            rose((R * math.cos(a), -0.9 - 0.05 * i, R * math.sin(a)), k, tilt=(15, 0), seed=100 + i, openness=0.8)
            leaf((R * math.cos(a), -0.4, R * math.sin(a)), 0.9 * k + 0.3, math.degrees(a) + 90, tilt=10, width=0.36)
            leaf((R * math.cos(a), -0.4, R * math.sin(a)), 0.8 * k + 0.25, math.degrees(a) - 90, tilt=10, width=0.36)
        feather((0.15, 0.1), 1.6, 105, opacity=0.75)
        star((0.85, 1.0), 0.32, glow_mat(lin("#ffffff"), 9))
        star((-0.6, 0.55), 0.18, glow_mat(lin("#ffffff"), 9))
        sparkle_field((-1.4, 1.6), (-0.6, 1.7), 14, 60, seed=33, avoid=[(-0.4, 0.7, -0.4, 1.4)], star_max=0.16)
    elif v == "light":
        tgt = avatar_base(center="#dcd3fa", edge="#8e7fc6", mid="#b9acec", bloom_t=1.4)
        def metal(name, col, m_, r_):
            mt, nt = new_mat(name)
            p_ = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
            p_.inputs["Base Color"].default_value = lin(col)
            p_.inputs["Metallic"].default_value = m_
            p_.inputs["Roughness"].default_value = r_
            return mt
        mats()  # build the default set first, then swap in darker metals
        dark = metal("silver_dark", "#8a78c8", 0.85, 0.25)
        MATS["silver"] = dark
        MATS["leaf"] = metal("leaf_dark", "#8f80cc", 0.7, 0.3)
        filigree_ring(mat=dark)
        rose((0, -0.9, 0.3), 1.05, tilt=(16, 0), seed=77, openness=0.9)
        rose((-1.05, -0.6, -0.72), 0.62, tilt=(20, 25), seed=78, openness=0.8)
        rose((1.08, -0.6, -0.66), 0.58, tilt=(22, -28), seed=79, openness=0.75)
        for ang, l in ((145, 1.85), (178, 1.95), (212, 1.7), (255, 1.45), (285, 1.45), (328, 1.7), (2, 1.95), (35, 1.85)):
            leaf((0, -0.3, -0.15), l, ang, tilt=12, width=0.36)
        sparkle_field((-2.1, 2.1), (-2.1, 2.1), 18, 40, seed=34, avoid=[(-1.6, 1.6, -1.3, 1.4)], star_max=0.2)
    key_lights(tgt, 8)
    render(OUT)


if WHAT.startswith("avatar:"):
    avatar_variant(WHAT.split(":", 1)[1])


def hole_backdrop(W, hole_r, center="#524873", edge="#1c1825"):
    """Gradient backdrop with a transparent round hole in the middle (holdout)."""
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 6.0, 0), rotation=(math.radians(90), 0, 0))
    o = bpy.context.object
    half = W * 0.6
    o.scale = (half, half, 1)
    m, nt = new_mat("bg_hole")
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vl = nt.nodes.new("ShaderNodeVectorMath"); vl.operation = "LENGTH"
    nt.links.new(tc.outputs["Object"], vl.inputs[0])
    col = ramp_node(nt, vl.outputs["Value"], [(0.0, lin(center)), (0.55, lin("#2c2540")), (1.0, lin(edge))])
    e = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(col, e.inputs["Color"])
    hold = nt.nodes.new("ShaderNodeHoldout")
    inside = math_node(nt, "LESS_THAN", a=vl.outputs["Value"], vb=hole_r / half)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(inside, mix.inputs["Fac"])
    nt.links.new(e.outputs[0], mix.inputs[1])
    nt.links.new(hold.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    o.data.materials.append(m)


def frame_overlay():
    """Discord-style avatar decoration: filigree ring + roses, transparent centre for a photo."""
    W = 6.0
    s = reset(1024, 1024, samples=96)
    s.render.film_transparent = True
    s.render.image_settings.color_mode = "RGBA"
    bloom(0.5)
    ortho_camera(W)
    tgt = _empty((0, 0, 0))
    hole_backdrop(W, 2.2)
    filigree_ring(R=2.36)
    # main cluster bottom-left
    rose((-1.62, -1.0, -1.58), 0.78, tilt=(15, 18), seed=201, openness=0.9)
    rose((-2.25, -0.9, -0.62), 0.46, tilt=(18, 30), seed=202, openness=0.8)
    rose((-0.62, -0.9, -2.2), 0.44, tilt=(22, 5), seed=203, openness=0.8)
    for ang, l in ((95, 1.1), (125, 0.9), (200, 1.0), (240, 1.15), (285, 1.0), (320, 0.85), (20, 0.9)):
        leaf((-1.55, -0.6, -1.5), l, ang, tilt=12, width=0.36)
    # small cluster top-right
    rose((1.72, -1.0, 1.66), 0.44, tilt=(12, -20), seed=204, openness=0.85)
    rose((2.25, -0.95, 0.85), 0.28, tilt=(15, -30), seed=205, openness=0.6)
    for ang, l in ((10, 0.8), (60, 0.7), (110, 0.75), (300, 0.65)):
        leaf((1.75, -0.6, 1.6), l, ang, tilt=12, width=0.36)
    feather((-2.15, 1.25), 1.05, 70, opacity=0.65)
    feather((2.0, -1.8), 0.8, 125, opacity=0.5)
    sparkle_field((-2.9, 2.9), (-2.9, 2.9), 26, 60, seed=41, avoid=[(-2.0, 2.0, -2.0, 2.0)], star_max=0.2)
    for x, z, sz in ((1.25, 1.95, 0.22), (-1.95, 0.35, 0.15), (0.6, -2.05, 0.17)):
        star((x, z), sz, glow_mat(lin("#ffffff"), 9), y=-2.0)
    key_lights(tgt, 8)
    render(OUT)


if WHAT == "frame":
    frame_overlay()
