# Renders maximalist profile art. Usage:
#   blender -b --factory-startup --python make.py -- <what> <out> [percent] [extra]
import bpy, math, random, sys, os
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]
WHAT, OUT = ARGS[0], ARGS[1]
PCT = int(ARGS[2]) if len(ARGS) > 2 else 100
EXTRA = ARGS[3:] if len(ARGS) > 3 else []

F_BLACK = r"C:\Windows\Fonts\ariblk.ttf"
F_IMPACT = r"C:\Windows\Fonts\impact.ttf"
F_MONO = r"C:\Windows\Fonts\consolab.ttf"


def lin(h, a=1.0):
    h = h.lstrip("#")
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(f(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


PAL = {k: lin(v) for k, v in dict(
    pink="#ff2bd6", cyan="#00f0ff", yellow="#ffe600", lime="#7cff00", orange="#ff6a00",
    purple="#8a2be2", red="#ff1744", blue="#2979ff", white="#ffffff", deep="#12002a",
    mint="#00ffa3", gold="#ffb300").items()}
CANDY = ["pink", "cyan", "yellow", "lime", "orange", "purple", "red", "blue", "mint"]


# ---------- scene ----------
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
    try:
        s.eevee.use_fast_gi = True
    except Exception:
        pass
    order = (("AgX", "AgX - Punchy"), ("AgX", "Punchy"), ("Filmic", "High Contrast"), ("Standard", "None"))
    if os.environ.get("VT") == "std":
        order = (("Standard", "None"),) + order
    for vt, look in order:
        try:
            s.view_settings.view_transform = vt
            s.view_settings.look = look
            break
        except TypeError:
            continue
    print("color mgmt:", s.view_settings.view_transform, s.view_settings.look)
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGB"
    return s


def bloom(strength=0.8, threshold=0.9, size=None):
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
        except Exception as e:
            print("glare type", v, e)
    g.inputs["Threshold"].default_value = threshold
    g.inputs["Strength"].default_value = strength
    if size is not None:
        try:
            g.inputs["Size"].default_value = size
        except Exception as e:
            print("glare size", e)
    ng.links.new(rl.outputs["Image"], g.inputs["Image"])
    ng.links.new(g.outputs["Image"], out.inputs[0])
    s.compositing_node_group = ng
    s.render.use_compositing = True


def world(stops, stars=0.0, strength=1.0, lo=-0.3, hi=0.7):
    w = bpy.data.worlds.new("W")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mr.inputs["From Min"].default_value = lo
    mr.inputs["From Max"].default_value = hi
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    set_ramp(ramp, stops)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    if stars > 0:
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 260
        nt.links.new(tc.outputs["Generated"], vor.inputs["Vector"])
        sm = nt.nodes.new("ShaderNodeMapRange")
        sm.inputs["From Min"].default_value = 0.0
        sm.inputs["From Max"].default_value = 0.05
        sm.inputs["To Min"].default_value = stars
        sm.inputs["To Max"].default_value = 0.0
        nt.links.new(vor.outputs["Distance"], sm.inputs["Value"])
        bg2 = nt.nodes.new("ShaderNodeBackground")
        bg2.inputs["Color"].default_value = (1, 0.9, 1, 1)
        nt.links.new(sm.outputs["Result"], bg2.inputs["Strength"])
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(bg.outputs[0], add.inputs[0])
        nt.links.new(bg2.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(bg.outputs[0], out.inputs["Surface"])


def set_ramp(ramp, stops):
    els = ramp.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position, els[0].color = stops[0]
    for pos, col in stops[1:]:
        e = els.new(pos)
        e.color = col


# ---------- materials ----------
def pbr(name, color, metal=0.0, rough=0.25, coat=0.0, film=0.0, emis=None, es=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = color
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = coat
    if film:
        p.inputs["Thin Film Thickness"].default_value = film
    if emis:
        p.inputs["Emission Color"].default_value = emis
        p.inputs["Emission Strength"].default_value = es
    return m


def emit(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = color
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], o.inputs["Surface"])
    return m


def chrome(name="chrome", tint="#f4e9ff", film=520, rough=0.07, glow=0.35):
    return pbr(name, lin(tint), metal=1.0, rough=rough, film=film, emis=lin("#c8b0ff"), es=glow)


def candy(c):
    return pbr("candy_" + c, PAL[c], metal=0.0, rough=0.18, coat=1.0)


def neon(c, s=6.0):
    return emit("neon_" + c, PAL[c], s)


def stripes_mat(name, c1, c2, strength=0.6, scale=6.0, angle=0.7):
    """Diagonal two-colour stripes, emissive (for backdrops)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, angle)
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.inputs["Scale"].default_value = scale
    wv.inputs["Distortion"].default_value = 0.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    set_ramp(ramp, [(0.0, c1), (0.5, c2)])
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], e.inputs["Color"])
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], o.inputs["Surface"])
    return m


def sun_mat():
    """Retro sun: yellow->pink gradient with cut-out stripes in the lower half."""
    m = bpy.data.materials.new("sun")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    y = sep.outputs["Y"]
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    set_ramp(ramp, [(0.0, PAL["pink"]), (0.45, PAL["orange"]), (1.0, PAL["yellow"])])
    nt.links.new(y, ramp.inputs["Fac"])
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = 2.2
    nt.links.new(ramp.outputs["Color"], e.inputs["Color"])
    # mask = fract(y*11) < (0.55 - y) * 0.9
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 11
    fr = nt.nodes.new("ShaderNodeMath"); fr.operation = "FRACT"
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[0].default_value = 0.55
    sc = nt.nodes.new("ShaderNodeMath"); sc.operation = "MULTIPLY"; sc.inputs[1].default_value = 0.9
    lt = nt.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"
    nt.links.new(y, mul.inputs[0]); nt.links.new(mul.outputs[0], fr.inputs[0])
    nt.links.new(y, sub.inputs[1]); nt.links.new(sub.outputs[0], sc.inputs[0])
    nt.links.new(fr.outputs[0], lt.inputs[0]); nt.links.new(sc.outputs[0], lt.inputs[1])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lt.outputs[0], mix.inputs["Fac"])
    nt.links.new(e.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], o.inputs["Surface"])
    return m


# ---------- objects ----------
def link(o):
    bpy.context.scene.collection.objects.link(o)
    return o


def text(body, font, size, mat, loc=(0, 0, 0), rot=(90, 0, 0), extrude=0.2, bevel=0.03, align="CENTER", spacing=1.0):
    cu = bpy.data.curves.new("t", "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 3
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.space_line = 0.9
    cu.space_character = spacing
    o = link(bpy.data.objects.new("t", cu))
    o.location = loc
    o.rotation_euler = [math.radians(a) for a in rot]
    o.data.materials.append(mat)
    return o


def fit(o, max_w, max_h):
    bpy.context.view_layer.update()
    d = o.dimensions
    k = min(max_w / max(d.x, 1e-6), max_h / max(d.y, 1e-6))
    o.scale = (k, k, k)
    bpy.context.view_layer.update()
    return k


def layered(body, font, size, top_mat, layer_cols, loc, offset=(0.09, 0.14, -0.09), extrude=0.25, max_w=None, max_h=None, rot=(90, 0, 0)):
    """Main text + coloured copies stepped behind it (retro 3D stack)."""
    main = text(body, font, size, top_mat, loc, rot, extrude=extrude)
    k = fit(main, max_w, max_h) if max_w else 1.0
    objs = [main]
    for i, c in enumerate(layer_cols, 1):
        t = text(body, font, size, neon(c, 3.5), loc, rot, extrude=extrude * 0.6, bevel=0.0)
        t.scale = (k, k, k)
        t.location = Vector(loc) + Vector(offset) * i
        objs.append(t)
    return objs


def prim(kind, loc, r, mat, rot=None):
    ops = bpy.ops.mesh
    if kind == "sphere":
        ops.primitive_uv_sphere_add(segments=48, ring_count=24, radius=r, location=loc)
    elif kind == "torus":
        ops.primitive_torus_add(major_radius=r, minor_radius=r * 0.32, major_segments=64, minor_segments=24, location=loc)
    elif kind == "cube":
        ops.primitive_cube_add(size=r * 1.5, location=loc)
    elif kind == "cone":
        ops.primitive_cone_add(vertices=48, radius1=r, depth=r * 2, location=loc)
    elif kind == "ico":
        ops.primitive_ico_sphere_add(subdivisions=1, radius=r, location=loc)
    elif kind == "monkey":
        ops.primitive_monkey_add(size=r * 1.8, location=loc)
    elif kind == "cyl":
        ops.primitive_cylinder_add(vertices=48, radius=r * 0.6, depth=r * 2, location=loc)
    o = bpy.context.object
    if kind in ("sphere", "torus", "cone", "monkey", "cyl"):
        o.data.shade_smooth()
        if kind == "monkey":
            m = o.modifiers.new("s", "SUBSURF"); m.levels = 1; m.render_levels = 2
    if kind == "cube":
        b = o.modifiers.new("b", "BEVEL"); b.width = r * 0.15; b.segments = 3
    o.rotation_euler = rot if rot is not None else [random.uniform(0, 6.28) for _ in range(3)]
    o.data.materials.append(mat)
    return o


def rand_mat():
    r = random.random()
    c = random.choice(CANDY)
    if r < 0.5:
        return candy(c)
    if r < 0.75:
        return chrome("chr", tint=random.choice(["#ffffff", "#ffd6f5", "#d6fbff", "#fff3b0"]), film=random.choice([0, 380, 520, 700]))
    return neon(c, 5)


def scatter(n, xr, yr, zr, avoid, rmin=0.15, rmax=0.6, kinds=None, seed=7):
    random.seed(seed)
    kinds = kinds or ["sphere", "sphere", "torus", "torus", "cube", "cone", "ico", "monkey", "cyl"]
    placed = 0
    tries = 0
    while placed < n and tries < n * 50:
        tries += 1
        p = (random.uniform(*xr), random.uniform(*yr), random.uniform(*zr))
        if any(a[0] < p[0] < a[1] and a[2] < p[2] < a[3] and p[1] < a[4] for a in avoid):
            continue
        prim(random.choice(kinds), p, random.uniform(rmin, rmax), rand_mat())
        placed += 1


def glyphs(items, xr, yr, zr, avoid, size=(0.35, 0.8), seed=3):
    random.seed(seed)
    for g in items:
        for _ in range(60):
            p = (random.uniform(*xr), random.uniform(*yr), random.uniform(*zr))
            if not any(a[0] < p[0] < a[1] and a[2] < p[2] < a[3] and p[1] < a[4] for a in avoid):
                break
        t = text(g, F_MONO, random.uniform(*size), neon(random.choice(CANDY), 4), p,
                 rot=(90 + random.uniform(-15, 15), random.uniform(-25, 25), random.uniform(-30, 30)), extrude=0.08, bevel=0.01)


def sparkles(n, xr, yr, zr, seed=11):
    random.seed(seed)
    mats = [neon("white", 12), neon("yellow", 10), neon("cyan", 10), neon("pink", 10)]
    for _ in range(n):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=random.uniform(0.015, 0.05),
                                              location=(random.uniform(*xr), random.uniform(*yr), random.uniform(*zr)))
        bpy.context.object.data.materials.append(random.choice(mats))


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


def empty(loc):
    e = link(bpy.data.objects.new("E", None))
    e.location = loc
    return e


def camera(loc, target, lens=35, ortho=None):
    cd = bpy.data.cameras.new("C")
    cd.lens = lens
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    o = link(bpy.data.objects.new("C", cd))
    o.location = loc
    c = o.constraints.new("TRACK_TO")
    c.target = target
    bpy.context.scene.camera = o
    return o


def neon_grid(z=0.0, color="pink", strength=2.2, size=90, sub=70, y=25):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=sub, y_subdivisions=sub, size=size, location=(0, y, z))
    g = bpy.context.object
    w = g.modifiers.new("w", "WIREFRAME")
    w.thickness = 0.05
    g.data.materials.append(neon(color, strength))
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, z - 0.03))
    bpy.context.object.data.materials.append(pbr("floor", lin("#14002e"), rough=0.12, coat=1.0))


def render(path):
    s = bpy.context.scene
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("WROTE", path)


# ---------- assets ----------
def hero():
    reset(1600, 600)
    world([(0.0, lin("#12002a")), (0.27, lin("#a0108a")), (0.38, lin("#33086a")), (0.7, lin("#0a0428")), (1.0, lin("#020108"))], stars=6.0, lo=-0.25, hi=0.75)
    bloom(0.5, 1.0)
    tgt = empty((0, 0, 1.75))
    camera((0, -15.5, 2.3), tgt, lens=33)
    neon_grid()
    # sun
    bpy.ops.mesh.primitive_circle_add(vertices=128, radius=7.5, fill_type="NGON", location=(0, 30, 6.2), rotation=(math.radians(90), 0, 0))
    bpy.context.object.data.materials.append(sun_mat())
    # title
    layered("VEEVA61", F_BLACK, 2.0, chrome(glow=0.6), ["cyan", "pink", "yellow"], (0, 0, 2.15), offset=(0.08, 0.16, -0.08), max_w=10.4, max_h=2.2)
    # ribbon + subtitle
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.55, 0.62), rotation=(0, math.radians(-2.5), 0))
    rb = bpy.context.object
    rb.scale = (10.2, 0.08, 0.62)
    b = rb.modifiers.new("b", "BEVEL"); b.width = 0.02
    rb.data.materials.append(pbr("ribbon", lin("#0a0014"), rough=0.2, coat=1.0, emis=PAL["pink"], es=0.15))
    sub = text("ВАЙБКОДЕР  //  ПОРТЫ ИГР  //  МОДЫ  //  КОМПЬЮТЕРНОЕ ЗРЕНИЕ", F_BLACK, 0.3, neon("yellow", 5), (0, -0.62, 0.6), rot=(90, -2.5, 0), extrude=0.02, bevel=0)
    fit(sub, 9.4, 0.4)
    for x in (-5.0, 5.0):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, -0.6, 0.62 + (0.22 if x < 0 else -0.22) * 0.0))
        e = bpy.context.object; e.scale = (0.08, 0.1, 0.7); e.data.materials.append(neon("cyan", 8))
    avoid = [(-5.6, 5.6, 0.1, 3.5, 2.0)]
    scatter(46, (-10.5, 10.5), (-4.0, 7.0), (-0.6, 5.2), avoid, seed=7)
    glyphs(["</>", "{ }", "AI", "C++", "0x61", "#", "λ", "fn()", "01", "=>", ";", "++"], (-10, 10), (-3, 4), (0.2, 4.8), avoid)
    sparkles(160, (-16, 16), (-2, 20), (-0.5, 9))
    area((-7, -7, 5), PAL["cyan"], 2500, 5, tgt)
    area((7, -7, 5), PAL["pink"], 2500, 5, tgt)
    area((0, -6, 9), PAL["white"], 1200, 6, tgt)
    render(OUT)


SECTIONS = {
    "about": ("ОБО МНЕ", "pink", ["yellow", "cyan"], ("#2a0033", "#4a005c")),
    "vibe": ("ВАЙБКОДИНГ", "cyan", ["pink", "yellow"], ("#001f33", "#003a52")),
    "stack": ("СТЕК", "lime", ["purple", "pink"], ("#102600", "#1d4200")),
    "projects": ("ПРОЕКТЫ", "orange", ["blue", "yellow"], ("#2b1000", "#4a1c00")),
    "stats": ("СТАТИСТИКА", "red", ["cyan", "yellow"], ("#2b0008", "#4d0010")),
    "snake": ("ЗМЕЙКА", "mint", ["pink", "purple"], ("#00261a", "#00402b")),
    "thanks": ("СПАСИБО ЗА ВАЙБ", "yellow", ["pink", "cyan"], ("#1a0033", "#33005c")),
}


def section(key):
    word, main_c, layers, (bg1, bg2) = SECTIONS[key]
    tall = key == "thanks"
    H = 360 if tall else 260
    reset(1600, H, samples=48)
    world([(0.0, lin("#000000")), (1.0, lin("#050010"))], strength=0.6)
    bloom(0.75, 0.9)
    tgt = empty((0, 0, 0))
    cam = camera((0, -14, 0), tgt, lens=50)
    vis_w = 2 * 14 * 18 / 50
    vis_h = vis_w * H / 1600
    # striped backdrop
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 4, 0), rotation=(math.radians(90), 0, 0))
    bd = bpy.context.object
    bd.scale = (vis_w * 1.6, vis_h * 1.8, 1)
    bd.data.materials.append(stripes_mat("bd", lin(bg1), lin(bg2), strength=1.0, scale=3.0, angle=0.6))
    # neon frame lines
    for z in (vis_h * 0.43, -vis_h * 0.43):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 1.5, z))
        ln = bpy.context.object; ln.scale = (vis_w * 1.2, 0.04, 0.035); ln.data.materials.append(neon(layers[0], 6))
    mat = candy(main_c)
    layered(word, F_BLACK, 1.0, mat, layers, (0, 0, 0), offset=(0.03, 0.09, -0.03), extrude=0.22,
            max_w=vis_w * 0.66, max_h=vis_h * 0.6)
    random.seed(hash(key) % 1000)
    side = vis_w * 0.5
    avoid = [(-vis_w * 0.34, vis_w * 0.34, -vis_h, vis_h, 3.0)]
    scatter(16 if not tall else 22, (-side, side), (-1.5, 2.5), (-vis_h * 0.42, vis_h * 0.42), avoid,
            rmin=0.12, rmax=vis_h * 0.22, seed=sum(map(ord, key)))
    sparkles(50, (-side, side), (0, 3.5), (-vis_h * 0.5, vis_h * 0.5), seed=len(key))
    area((-5, -6, 3), PAL[layers[0]], 900, 4, tgt)
    area((5, -6, 3), PAL[layers[1]], 900, 4, tgt)
    area((0, -6, -3), PAL["white"], 400, 4, tgt)
    render(OUT)


def vibe_gif():
    reset(440, 440, samples=24)
    world([(0.0, lin("#12002a")), (0.5, lin("#3a0066")), (1.0, lin("#05001a"))], stars=4.0, lo=-0.8, hi=0.8)
    bloom(0.9, 0.85)
    tgt = empty((0, 0, 0))
    camera((0, -9, 0.6), tgt, lens=45)
    title = layered("VIBE\nCODER", F_BLACK, 1.0, candy("yellow"), ["pink"], (0, 0, 0), offset=(0.025, 0.14, -0.025), extrude=0.3, max_w=4.3, max_h=3.0)
    pivot = empty((0, 0, 0))
    for o in title:
        o.parent = pivot
        o.location = o.location - pivot.location
    # neon rings
    ring_piv = empty((0, 0, 0))
    for i, (c, r, tilt) in enumerate([("pink", 2.6, 72), ("cyan", 2.9, 105), ("lime", 3.2, 88)]):
        bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=0.035, major_segments=128, minor_segments=12,
                                         rotation=(math.radians(tilt), math.radians(i * 25), 0))
        t = bpy.context.object; t.data.materials.append(neon(c, 7)); t.parent = ring_piv
    orb = empty((0, 0, 0))
    random.seed(5)
    kinds = ["sphere", "torus", "cube", "ico", "monkey", "cone"]
    n = 12
    for i in range(n):
        a = i / n * 2 * math.pi
        rr = 2.75 + 0.25 * math.sin(i * 1.7)
        o = prim(kinds[i % len(kinds)], (rr * math.cos(a), 0.6 * math.sin(a * 2), rr * math.sin(a) * 0.55), random.uniform(0.16, 0.3), rand_mat())
        o.parent = orb
    sparkles(70, (-5, 5), (0, 6), (-4, 4))
    area((-4, -5, 3), PAL["cyan"], 900, 3, tgt)
    area((4, -5, 3), PAL["pink"], 900, 3, tgt)
    area((0, -5, -3), PAL["yellow"], 400, 3, tgt)
    frames = int(EXTRA[0]) if EXTRA else 40
    os.makedirs(OUT, exist_ok=True)
    for f in range(frames):
        t = f / frames
        pivot.rotation_euler = (0, 0, math.radians(15 * math.sin(2 * math.pi * t)))
        from mathutils import Euler
        e = Euler((math.radians(14), 0, 0))
        e.rotate_axis("Y", 2 * math.pi * t)
        orb.rotation_euler = e
        ring_piv.rotation_euler = (0, 2 * math.pi * t, 0)
        render(os.path.join(OUT, "f_%03d.png" % f))


if WHAT == "hero":
    hero()
elif WHAT == "gif":
    vibe_gif()
else:
    section(WHAT)
