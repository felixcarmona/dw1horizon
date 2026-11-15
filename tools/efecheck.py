"""Render fidelity of a converted DW2 technique: the DW2 objects drawn by tools/dw2effect against the chunk's
draws in tools/efesim, frame by frame, both from the same side camera (the DW1 one is the DW2 one shrunk to the
DW1 stage). A conversion fails when it shows much less than the source, drops an object the source shows, or
draws it in a much smaller box.

Frames are aligned as the converter times them: DW1 tick t of the cast is DW2 tick 3t (DW2 frame 1.5t), and
DW1 tick ht + t of the hit (ht: the chunk's first damage event) is DW2 tick CAST_WAIT + 3t.

The converted objects are scaled by the technique's scale (cast) and hit_scale (hit), not by the stage's K, on
purpose (they are sized to the species), so the DW1 areas are divided by (scale / K)^2 and the box sizes by
scale / K before they are compared.

Thresholds: a phase (cast, hit) holding at least 5% of the source's light fails below 35% of its energy or
coverage, or when its box diagonal (median over the lit frames) is below 35% of the source's; a bone (or bones
drawn by the same TMD objects) holding at least 5% of its phase fails below 10% of its energy. The check runs
on this game's 20 Hz ticks against DW2's 60 Hz, palettes squeezed into six rows and additive blending summed by
a different renderer, so a faithful conversion still lands between about 0.5 and 3 on energy and coverage;
0.35 sits under that spread and far above what an empty, lost or shrunk effect gives (0.10 or less).

    python -m tools.efecheck --disc DW2.bin [--archive EFEDAT.EFE] [keys]   (content/battle/own-effects.json)
    python -m tools.efecheck --composed [--archive EFEDAT.EFE] [keys]       (its composed entries)
    python -m tools.efecheck --presence                                     (every entry's in-game size)
    python -m tools.efecheck --anchors --archive BUILT/EFEDAT.EFE [keys]    (objects that start at the caster)

A composed entry (tools/efecompose.py) is checked against its template, both run by the same script: it must
leave the technique as it is (launch table, bytes outside the palette, copied texels, vertices and script colours, and the
run's draws, hits and sounds all the template's), keep at least 35% of the template's energy and coverage per
phase with a box between 0.5 and 3 times the template's, show its declared hue (within 35 degrees), and differ
from the template (summed RGB difference at least 0.25 of the summed RGB of both). See check_composed.
Every entry must also read big enough in the game: --presence checks the emulator measurements of
content/battle/effect-presence.json against vanilla's smallest and biggest finishers (tools/efepresence.py).
"""
import math
import struct

from tools import dw2effect as D
from tools import dw2efe as C
from tools import efesim as S

DIST = 2700                             # the DW1 stage's rows of fighters (tools/test_dw2efe, efesim's tests)
K = DIST / D.HOME_DISTANCE              # DW1 stage units per DW2 unit
W, H = 160, 100
BRIGHT = 128                            # luminance (0-255) of a bright pixel

# Failure thresholds; see check()
MIN_RATIO = 0.35                        # energy and coverage of a phase, against the source's
MIN_BOX = 0.35                          # box diagonal of a phase, against the source's
MIN_PART = 0.10                         # energy of a drawn bone, against the source's bone
SHOWN = 0.05                            # a bone or phase counts when it holds this share of the source's energy


def cameras(w=W, h=H):
    dw2 = D.Camera(w, h)
    dw1 = D.Camera(w, h, eye=tuple(x * K for x in dw2.eye), look=(0, -1400 * K, -D.HOME_DISTANCE / 2 * K))
    return dw2, dw1


def place(casts, hits, head=1600, hit_y=900, row=(0, 1200, 0), self_target=False):
    """The DW2 objects (lists of (DW2 slot 0-2, Effect), as convert_skill takes them) placed as
    Stg30_SpawnSkillCastFx / HitFx place them for a caster and target of the given head height, hit height and
    cast row (dw2effect.Digimon's head, hit_y and cast_rows), named as the converter names them. self_target: the
    hit objects play on the caster (a support technique)."""
    out = []
    for s, e in casts:
        out.append(D.Placed(e, [(0, -0x280 - head, 0), (row[0], -row[1], -(0x100 + row[2])), (0, 0, 0)][s],
                            False, 0, D.CAST_TICKS))
        out[-1].name = f'cast slot {s}'
    for s, e in hits:
        o = [(0, -0x280 - head, 0), (0, -hit_y, 0), (0, 0, 0)][s]
        if self_target:
            out.append(D.Placed(e, o, False, D.CAST_WAIT, D.HIT_TICKS))
        else:
            out.append(D.Placed(e, (-o[0], o[1], -D.HOME_DISTANCE - o[2]), True, D.CAST_WAIT, D.HIT_TICKS))
        out[-1].name = f'hit slot {s}'
    return D.prepare(out)


def stage(launch_table, enemies=3):
    kind = struct.unpack_from('<h', launch_table, 0)[0]
    f = [None] * 10
    f[1] = S.Fighter(kind, (0, 0, 0), 0)
    for k in range(enemies):
        f[2 + k] = S.Fighter(kind, ((-1) ** k * 900 * ((k + 1) // 2), 0, -DIST - 300 * (k > 0)), 0x800)
    return f


def _stats(px):
    lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]
    on = [i for i, x in enumerate(lum) if x > 0]
    box = None
    if on:
        xs, ys = [i % W for i in on], [i // W for i in on]
        box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    return dict(energy=sum(lum), cover=len(on), bright=sum(1 for x in lum if x >= BRIGHT), box=box)


def _union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _diag(b):
    return math.hypot(b[2] - b[0], b[3] - b[1]) if b else 0.0


def _box_ratio(src, ours, ratio):
    """The median, over the frames where the source shows at least a tenth of its brightest frame, of our box
    diagonal (divided by the scale ratio) against the source's: a whole-phase box would hide a projectile that
    shrank, as its path spans the screen either way."""
    top = max((f['energy'] for f in src), default=0)
    r = sorted(_diag(b['box']) / ratio / _diag(a['box']) for a, b in zip(src, ours)
               if top and a['energy'] >= top / 10 and _diag(a['box']))
    return r[len(r) // 2] if r else None


def _corr(a, b):
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va, vb = sum((x - ma) ** 2 for x in a), sum((x - mb) ** 2 for x in b)
    if va == 0 or vb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def _alone(placed, keep):
    """The placed object with only the bones in keep drawn (the others keep their transforms)."""
    e = placed.effect
    bones = [D.Bone(x.parent, x.vertices, x.prims if i in keep else []) for i, x in enumerate(e.bones)]
    one = D.Effect(bones, e.tim, e.keys, e.frames, e.tex_moves)
    one._image = e._image
    if '_world' in e.__dict__:
        one._world = e._world
    out = D.Placed(one, placed.origin, placed.turn, placed.start, placed.ticks)
    out.name = placed.name
    return out


def frames(chunk, info, launch_table, limit=120):
    """[(DW1 tick, DW2 tick, phase)] of the chunk's run, and the sim."""
    sim = S.Sim(chunk, stage(launch_table), 1, 2)
    for _ in range(limit):
        sim.step(reset_hits=True)
        if not sim.live():
            break
    ht = min((h[0] for h in sim.hits), default=info['cast_ticks'])
    # to the end of whichever lasts longer: a chunk that stops early is compared with the source's whole hit
    last = max(max((d[0] for d in sim.draws), default=0), ht + D.HIT_TICKS // 3 - 1)
    out = [(t, 3 * t if t < ht else D.CAST_WAIT + 3 * (t - ht), 'cast' if t < ht else 'hit')
           for t in range(last + 1)]
    return out, sim


def _source(placed, t2, cam):
    """The source's stats over the DW1 tick that shows DW2 ticks t2..t2+2: DW2 draws a new frame every two
    ticks, so a bone that flickers frame by frame would otherwise be caught always lit or always dark."""
    a, b = (_stats(D.render_tick(placed, t, cam, bg=(0, 0, 0), markers=False)) for t in (t2, t2 + 2))
    return dict(energy=(a['energy'] + b['energy']) / 2, cover=(a['cover'] + b['cover']) / 2,
                bright=(a['bright'] + b['bright']) / 2, box=_union([a['box'], b['box']]))


def groups(placed, ids):
    """[(placed object, bones, TMD ids)]: the drawn bones of each object, those whose TMD objects overlap taken
    together (the converter draws identical bones with one object, and a draw does not say which bone it is)."""
    out = []
    for p in placed:
        mine = ids.get(p.name, {})
        left = [b for b, bone in enumerate(p.effect.bones) if bone.prims and bone.vertices]
        while left:
            bones, tmd = {left.pop(0)}, set()
            tmd.update(mine.get(next(iter(bones)), ()))
            grew = True
            while grew:
                grew = False
                for b in list(left):
                    if tmd & set(mine.get(b, ())):
                        bones.add(b), left.remove(b), tmd.update(mine.get(b, ()))
                        grew = True
            out.append((p, sorted(bones), tmd))
    return out


def check(placed, chunk, info, launch_table, scale, hit_scale=None, size=(W, H)):
    """The fidelity report of a conversion: per phase (cast, hit) the source's and our energy (summed luminance),
    coverage, bright area, box and the correlation of the two per-frame energy curves; per drawn bone (or group
    of bones drawn by the same TMD objects) of each DW2 object its share of the phase and our energy against it;
    'fails', the reasons it fails (empty when it passes). Our areas are normalised by the scale."""
    global W, H
    W, H = size
    hit_scale = scale if hit_scale is None else hit_scale
    ratio = dict(cast=scale / K, hit=hit_scale / K)
    cam2, cam1 = cameras(W, H)
    ticks, sim = frames(chunk, info, launch_table)
    draws = sim.draws
    ids = info.get('parts', {})
    phases = {k: dict(src=[], dw1=[]) for k in ('cast', 'hit')}
    per_part = {}
    blank = [(0, 0, 0)] * (W * H)

    def ours(t1, keep=None):
        sim.draws = [d for d in draws if d[0] == t1 and (keep is None or d[1] in keep)]
        return _stats(S.render(chunk, sim, t1, cam1, fighters=False, bg=(0, 0, 0)) if sim.draws else blank)

    for t1, t2, ph in ticks:
        phases[ph]['src'].append(_source(placed, t2, cam2))
        phases[ph]['dw1'].append(ours(t1))
    for p, bones, tmd in groups(placed, ids):
        alone = _alone(p, bones)
        src = mine = 0.0
        for t1, t2, ph in ticks:
            if p.start <= t2 < p.start + p.ticks:
                src += _source([alone], t2, cam2)['energy']
                mine += ours(t1, tmd)['energy'] if tmd else 0.0
        per_part[(p.name, tuple(bones))] = (src, mine / ratio[p.name.split()[0]] ** 2)
    sim.draws = draws
    report = dict(phases={}, parts={}, fails=[])
    total = sum(f['energy'] for k in phases for f in phases[k]['src']) or 1.0
    for ph, v in phases.items():
        r2 = ratio[ph] ** 2
        es, ed = sum(f['energy'] for f in v['src']), sum(f['energy'] for f in v['dw1']) / r2
        cs, cd = sum(f['cover'] for f in v['src']), sum(f['cover'] for f in v['dw1']) / r2
        bs, bd = sum(f['bright'] for f in v['src']), sum(f['bright'] for f in v['dw1']) / r2
        box_s, box_d = _union(f['box'] for f in v['src']), _union(f['box'] for f in v['dw1'])
        ctr = lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) if b else None
        rep = dict(frames=len(v['src']), share=es / total,
                   energy=ed / es if es else None, cover=cd / cs if cs else None, bright=bd / bs if bs else None,
                   box=_box_ratio(v['src'], v['dw1'], ratio[ph]),
                   centre=(ctr(box_s), ctr(box_d)),
                   corr=_corr([f['energy'] for f in v['src']], [f['energy'] for f in v['dw1']]))
        report['phases'][ph] = rep
        if rep['share'] >= SHOWN:
            if (rep['energy'] or 0) < MIN_RATIO or (rep['cover'] or 0) < MIN_RATIO:
                report['fails'].append(f'{ph}: mostly empty (energy {rep["energy"] or 0:.2f}, '
                                       f'coverage {rep["cover"] or 0:.2f} of the source)')
            if (rep['box'] or 0) < MIN_BOX:
                report['fails'].append(f'{ph}: box collapsed ({rep["box"] or 0:.2f} of the source)')
    for (name, b), (src, ours) in per_part.items():
        ph = name.split()[0]
        phase_e = sum(f['energy'] for f in phases[ph]['src']) or 1.0
        b = '+'.join(map(str, b))
        report['parts'][f'{name} bone {b}'] = dict(share=src / phase_e, energy=ours / src if src else None)
        if src / phase_e >= SHOWN and ours / src < MIN_PART:
            report['fails'].append(f'{name} bone {b}: dropped ({src / phase_e:.0%} of the source\'s {ph}, '
                                   f'drawn at {ours / src:.2f} of its energy)')
    return report


def summary(rep):
    out = []
    for ph, r in rep['phases'].items():
        if not r['frames']:
            continue
        f = lambda x: '-' if x is None else f'{x:.2f}'
        out.append(f'{ph} {r["frames"]}f share {r["share"]:.2f} energy {f(r["energy"])} cover {f(r["cover"])} '
                   f'bright {f(r["bright"])} box {f(r["box"])} corr {f(r["corr"])}')
    return '; '.join(out)


def learner(tables, model):
    """The DW2 skill whose cast or hit plays the effect model (its file name under AAA/4.AAA/EFFECT) and the
    Digimon that learns it, whose head, hit height and cast row place the objects; (None, None) when none does."""
    for skill in tables.skills.values():
        fids = [m for m, _a in skill.cast_fx + skill.hit_fx if m]
        if any((tables.disc.name(m) or '').endswith('/' + model) for m in fids):
            return skill, next((d for d in tables.digimon.values() if d.learned == skill.id), None)
    return None, None


def run(tables, model, casts, hits, like, scale, hit_scale=None, key=0x17A, **kw):
    """Converts and checks one technique; returns (info, report). model: one of its effect files (finds the DW2
    caster), like: the launch table (the chunk it stands for), kw: convert_skill's area, n_hits, self_target."""
    skill, d = learner(tables, model)
    where = dict(head=d.head, hit_y=d.hit_y, row=d.cast_rows[skill.cast]) if d else {}
    chunk, info = C.convert_skill(casts, hits, like, key, scale, hit_scale=hit_scale, **kw)
    hs = scale if hit_scale is None or kw.get('self_target') else hit_scale
    placed = place(casts, hits, self_target=kw.get('self_target', False), **where)
    return info, check(placed, chunk, info, like, scale, hs)


# ----------------------------------------------------------------- composed effects (tools/efecompose.py)

# Failure thresholds of a composed effect, against its template run by the same script in tools/efesim
MIN_COMPOSED = 0.35                     # energy and coverage of a phase, against the template's
BOX_RANGE = (0.5, 3.0)                  # box diagonal of a phase (median over lit frames), against the template's
MAX_HUE = 35.0                          # degrees between the main hue and the entry's check.hue
MIN_DISTINCT = 0.25                     # summed RGB difference over the summed RGB of both, all frames
SATURATED = 0.25                        # a pixel counts toward the hue when its saturation is above this


def hue_of(frames_):
    """The main hue in degrees: the chroma-weighted circular mean over the saturated pixels, or None."""
    sx = sy = 0.0
    for px in frames_:
        for r, g, b in px:
            hi, lo = max(r, g, b), min(r, g, b)
            if hi < 26 or (hi - lo) / hi <= SATURATED:
                continue
            c = hi - lo
            if hi == r:
                h = ((g - b) / c) % 6
            elif hi == g:
                h = (b - r) / c + 2
            else:
                h = (r - g) / c + 4
            a = h * math.pi / 3
            sx += c * math.cos(a)
            sy += c * math.sin(a)
    if not sx and not sy:
        return None
    return math.degrees(math.atan2(sy, sx)) % 360


def hue_distance(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _motion(sim):
    """What a run does, colours and shapes aside: every draw's object and transform, every sprite's and quad's
    place and size, the hits, the hit tests and the sounds."""
    return ([d[:5] for d in sim.draws], [s[:8] + s[9:11] for s in sim.sprites], [q[:6] + q[7:] for q in sim.quads],
            sim.hits, sim.tests, sim.sounds)


def check_composed(template, ours, spec, target_hue=None, size=(W, H)):
    """The report of a composed chunk against its template: 'neutral' (the launch table, the bytes changed only
    where a composition may change them, the same run: draws, hits, sounds), per phase (cast before the
    template's first hit, hit after; 'all' when the simulation deals none) energy, coverage and box against the
    template's, the main hue against target_hue, 'distinct' (frame difference); 'fails' (empty when it passes)."""
    from tools import efecompose as X
    w, h = size
    rep = dict(phases={}, fails=[], fx=[])
    lt = X.launch_table(template)
    if X.launch_table(ours) != lt:
        rep['fails'].append('launch table changed')
    allowed = X.allowed_bytes(template, spec)
    changed = [i for i in range(len(template)) if template[i] != ours[i] and i not in allowed]
    if changed:
        rep['fails'].append(f'{len(changed)} bytes changed outside the palette, texels, vertices and colours '
                            f'(first at {changed[0]:#x})')
    a, b = X.run(template, lt), X.run(ours, lt)
    if _motion(a) != _motion(b):
        rep['fails'].append('the run differs from the template\'s (draws, hits or sounds)')
    rep['hits'] = [(t, f) for t, f, _p in a.hits]
    rep['fx'] = sorted({k for _t, k, *_ in a.fx})          # drawn by the engine with its own colours: not checked
    lit = X.lit_ticks(a)
    if not lit:
        rep['fails'].append('the template draws nothing in the simulation')
        return rep
    ticks = range(1, max(lit) + 1)
    fa, fb = X.frames(template, a, w, h, ticks), X.frames(ours, b, w, h, ticks)
    first = min((t for t, _f in rep['hits']), default=None)
    phases = {'all': list(ticks)} if first is None else {'cast': [t for t in ticks if t < first],
                                                        'hit': [t for t in ticks if t >= first]}
    global W, H
    W, H = w, h
    for ph, ts in phases.items():
        sa, sb = [_stats(fa[t]) for t in ts], [_stats(fb[t]) for t in ts]
        ea, eb = sum(x['energy'] for x in sa), sum(x['energy'] for x in sb)
        ca, cb = sum(x['cover'] for x in sa), sum(x['cover'] for x in sb)
        if not ea:
            continue
        r = dict(frames=len(ts), energy=eb / ea, cover=cb / ca if ca else None, box=_box_ratio(sa, sb, 1.0))
        rep['phases'][ph] = r
        if r['energy'] < MIN_COMPOSED or (r['cover'] or 0) < MIN_COMPOSED:
            rep['fails'].append(f'{ph}: mostly empty (energy {r["energy"]:.2f}, coverage {r["cover"] or 0:.2f} '
                                f'of the template)')
        if r['box'] is not None and not BOX_RANGE[0] <= r['box'] <= BOX_RANGE[1]:
            rep['fails'].append(f'{ph}: box {r["box"]:.2f} of the template\'s, outside {BOX_RANGE}')
    rep['template_hue'], rep['hue'] = hue_of(fa.values()), hue_of(fb.values())
    if target_hue is not None:
        if rep['hue'] is None:
            rep['fails'].append('no saturated colour to take a hue from')
        elif hue_distance(rep['hue'], target_hue) > MAX_HUE:
            rep['fails'].append(f'hue {rep["hue"]:.0f}, {hue_distance(rep["hue"], target_hue):.0f} degrees from '
                                f'the intended {target_hue}')
    num = den = 0
    for t in ticks:
        for p, q in zip(fa[t], fb[t]):
            if p != q:
                num += sum(abs(x - y) for x, y in zip(p, q))
            den += sum(p) + sum(q)
    rep['distinct'] = num / den if den else 0.0
    if rep['distinct'] < MIN_DISTINCT:
        rep['fails'].append(f'too close to the template (difference {rep["distinct"]:.2f}, needs {MIN_DISTINCT})')
    return rep


def composed_summary(rep):
    f = lambda x: '-' if x is None else f'{x:.2f}'
    out = [f'{ph} {r["frames"]}f energy {f(r["energy"])} cover {f(r["cover"])} box {f(r["box"])}'
           for ph, r in rep['phases'].items()]
    g = lambda x: '-' if x is None else f'{x:.0f}'
    out.append(f'hue {g(rep.get("hue"))} (template {g(rep.get("template_hue"))}), distinct '
               f'{rep.get("distinct", 0):.2f}, hits {len(rep.get("hits", []))}')
    if rep['fx']:
        out.append('engine fx unchecked: ' + ', '.join(rep['fx']))
    return '; '.join(out)


# Anchors (--anchors): an object that starts on the caster's half of the field must start on the caster, at its
# size in this game: its first drawn position (the object's origin, or the centre of its vertices for a large
# mesh whose origin sits elsewhere) inside the caster's box, the species' model.height tall and model.radius
# wide, with room for cannons, arms and claws that stick out (ANCHOR_REACH radii around, or up to a height in
# front of it, ANCHOR_HEAD heights up, ANCHOR_FLOOR heights below the ground for a ring or dust at the feet).
ANCHOR_REACH, ANCHOR_HEAD, ANCHOR_FLOOR = 1.5, 1.2, 0.25
# Entries whose part starts away from the caster on the disc too (checked against the DW2003 script and model).
ANCHOR_FAITHFUL = {
    206: 'KongouKaimandara: the mandala opens 1.2 caster heights in front of Sakuyamon, as on the disc',
    216: 'Swing Swing: the thrown part first shows halfway through its flight, as on the disc',
}


def first_spawns(chunk, height=600, radius=150, limit=150):
    """{object: (tick, origin, vertex centre, anchor, origin a tick before)} of the chunk's objects at the first
    tick each is drawn (scale not zero; the last is where its motion from the second tick puts it before that, for
    a shot that leaves the muzzle faster than one 20 Hz tick shows), with the caster at the origin and its target DIST away toward -z; anchor is what the
    object's position was set from (efesim's Context.anchor: 'root', the caster's feet, or 'bone', a launch
    point, which the game takes from the species' own effect origins and efesim only stands in for)."""
    from tools.derive.steps import effects as E
    fighters = stage(E.launch_table(chunk))
    fighters[1].height, fighters[1].radius = height, radius        # the caster at the species' size
    sim = S.Sim(chunk, fighters, 1, 2)
    for _ in range(limit):
        sim.step(reset_hits=True)
        if not sim.live():
            break
    objs = S.tmd_objects(chunk)
    out = {}
    for (t, oid, rot, sc, pos, _uv, *rest), anchor in zip(sim.draws, sim.draw_anchors):
        if oid in out and out[oid][0] + 1 == t and out[oid][4] is None:
            p0 = out[oid][1]
            out[oid] = out[oid][:4] + (tuple(2 * a - b for a, b in zip(p0, pos)),)
        if oid in out or not any(sc) or oid >= len(objs):
            continue
        m = (S.rot_yxz if (rest[0] if rest else 'yxz') == 'yxz' else S.rot_xyz)(*[S._wrap(x, 2) for x in rot])
        k = [x / 4096 for x in sc]
        pts = [[pos[i] + sum(m[i][j] * k[j] * v[j] for j in range(3)) for i in range(3)] for v in objs[oid][0]]
        centre = tuple((min(p[i] for p in pts) + max(p[i] for p in pts)) / 2 for i in range(3)) if pts else pos
        out[oid] = (t, tuple(pos), centre, anchor, None)
    return out


def anchor_check(chunk, height, radius):
    """([(object, tick, origin, centre)] of the objects anchored at the caster's feet that start on the caster's
    half outside its box, the number of objects anchored at a launch point (not checked: see first_spawns))."""
    def inside(p):
        x, y, z = p
        around = math.hypot(x, z) <= ANCHOR_REACH * radius
        ahead = abs(x) <= ANCHOR_REACH * radius and -height <= z <= 0
        return (around or ahead) and -ANCHOR_HEAD * height <= y <= ANCHOR_FLOOR * height
    bad, bone = [], 0
    for obj, (t, pos, centre, anchor, back) in sorted(first_spawns(chunk, height, radius).items(),
                                                      key=lambda kv: (kv[1][0], kv[0])):
        if max(pos[2], centre[2]) < -DIST / 2:
            continue                    # starts on the target's half: a shot that lands, a hit
        if anchor == 'bone':
            bone += 1
        elif not (inside(pos) or inside(centre) or (back and inside(back))):
            bad.append((obj, t, pos, centre))
    return bad, bone


def anchors(archive, spec, keys=(), root='.'):
    """Every own effect's anchor_check against its species' box: (failing species count, report lines)."""
    import glob
    import json
    owner = {}
    for path in sorted(glob.glob(f'{root}/content/species/*.json')):
        with open(path, encoding='utf-8') as f:
            sp = json.load(f)
        if sp.get('own_effect'):
            owner[sp['own_effect']['chunk']] = sp
    lines, bad = [], 0
    for key, e in spec.items():
        if key == 'note' or (keys and key not in keys) or int(key) not in owner:
            continue
        sp = owner[int(key)]
        chunk = archive[int(key) * 0x5000:(int(key) + 1) * 0x5000]
        h, r = sp['model'].get('height', 500), sp['model'].get('radius', 200)
        out, bone = anchor_check(chunk, h, r)
        kind = next((k for k in ('dw3', 'dcb', 'compose') if k in e), 'dw2')
        waived = out and int(key) in ANCHOR_FAITHFUL
        bad += bool(out) and not waived
        lines.append(f'{key} {sp["name"]} ({kind}, {e["name"]}): '
                     f'{"waived (" + ANCHOR_FAITHFUL[int(key)] + ")" if waived else "FAIL" if out else "pass"}; '
                     f'{len(out)} object(s) off the caster (height {h}, radius {r})'
                     + (f', {bone} at a launch point' if bone else '')
                     + ''.join(f'\n    {o} tick {t}: origin {tuple(round(v) for v in p)} centre '
                               f'{tuple(round(v) for v in c)}' for o, t, p, c in out))
    return bad, lines


def main():
    import argparse
    import json
    from tools.derive.steps import effects as E
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--disc', help='the Digimon World 2 (USA) disc image (converted entries)')
    ap.add_argument('--composed', action='store_true', help='check the composed entries (no DW2 disc needed)')
    ap.add_argument('--archive', default='extracted/ETCHI/EFEDAT.EFE', help="this game's effect archive")
    ap.add_argument('--presence', action='store_true', help='check the measured in-game size of every entry')
    ap.add_argument('--anchors', action='store_true',
                    help="check that every entry's objects that start at the caster start on it (a built archive)")
    ap.add_argument('keys', nargs='*', help='own-effects.json keys (default: all)')
    a = ap.parse_args()
    if a.presence:
        from tools import efepresence
        efepresence.main(['check'])
    with open(a.archive, 'rb') as f:
        archive = f.read()
    with open('content/battle/own-effects.json') as f:
        spec = json.load(f)
    if a.anchors:
        bad, lines = anchors(archive, spec, a.keys)
        print('\n'.join(lines))
        print(f'{bad} species with objects off the caster')
        raise SystemExit(1 if bad else 0)
    bad = 0
    if a.composed:
        from tools import efecompose as X
        for key, e in spec.items():
            if key == 'note' or 'compose' not in e or (a.keys and key not in a.keys):
                continue
            template = X.template_of(archive, e)
            ours, _info = X.compose(template, e['compose'], archive)
            rep = check_composed(template, ours, e['compose'], e.get('check', {}).get('hue'))
            bad += bool(rep['fails'])
            print(f'{key} {e["name"]}: {"FAIL" if rep["fails"] else "pass"}; {composed_summary(rep)}'
                  + ''.join(f'\n    {x}' for x in rep['fails']), flush=True)
        raise SystemExit(1 if bad else 0)
    if not a.disc:
        ap.error('--disc is needed for the converted entries (or --composed)')
    disc = D.Disc(a.disc)
    tables = D.Tables(disc)
    for key, e in spec.items():
        if key == 'note' or 'dw3' in e or 'compose' in e or (a.keys and key not in a.keys):
            continue                    # DW2003 ports: tools/test_dw3_ports.py; composed: --composed
        like = E.launch_table(archive[e['stands_for'] * E.CHUNK_SIZE:(e['stands_for'] + 1) * E.CHUNK_SIZE])
        lists = [[(s, D.parse_effect(*(disc.image.read(*disc.files['AAA/4.AAA/EFFECT/' + n]) for n in names)))
                  for s, *names in E.effect_objects(e[p])] for p in ('cast', 'hit')]
        first = e['cast'][0] if isinstance(e['cast'][0], str) else e['cast'][0][1]
        info, rep = run(tables, first.split('/')[-1], lists[0], lists[1], like, e['scale'], e.get('hit_scale'),
                        0x100 + int(key), area=e.get('area', False), n_hits=e.get('hits', 1))
        bad += bool(rep['fails'])
        print(f'{key} {e["name"]}: {"FAIL" if rep["fails"] else "pass"}; {summary(rep)}'
              + ''.join(f'\n    {x}' for x in rep['fails']), flush=True)
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
