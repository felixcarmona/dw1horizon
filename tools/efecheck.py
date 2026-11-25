"""Checks of the effect chunks this project makes, run in tools/efesim and drawn from a side camera.

    python -m tools.efecheck --composed [--archive EFEDAT.EFE] [keys]       (the composed entries)
    python -m tools.efecheck --anchors --archive BUILT/EFEDAT.EFE [keys]    (objects that start at the caster)

A composed entry (tools/efecompose.py) is checked against its template, both run by the same script: it must
leave the technique as it is (launch table, bytes outside the palette, copied texels, vertices and script colours, and the
run's draws, hits and sounds all the template's), keep at least 35% of the template's energy and coverage per
phase with a box between 0.5 and 3 times the template's, show its declared hue (within 35 degrees), and differ
from the template (summed RGB difference at least 0.25 of the summed RGB of both). See check_composed.
"""
import math
import struct

from tools import efesim as S

DIST = 2700                             # the stage's rows of fighters (efesim's tests)
W, H = 160, 100
BRIGHT = 128                            # luminance (0-255) of a bright pixel


def cameras(w=W, h=H):
    """(None, the side camera of the stage): a pair, as the callers unpack it."""
    k = DIST / 0x2800
    eye = (14000, -4200, -5120)
    return None, S.Camera(w, h, eye=tuple(x * k for x in eye), look=(0, -1400 * k, -DIST / 2))


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
    remap = {int(k): int(v) for k, v in spec.get('sounds', {}).items()}
    a.sounds = [(t, remap.get(sid, sid)) for t, sid in a.sounds]       # the template's run with the sounds asked
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
# Entries waived, with the reason: {chunk: text}
ANCHOR_FAITHFUL = {}


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
        kind = e.get('authored', 'composed')
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
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--composed', action='store_true', help='check the composed entries')
    ap.add_argument('--archive', default='extracted/ETCHI/EFEDAT.EFE', help="this game's effect archive")
    ap.add_argument('--anchors', action='store_true',
                    help="check that every entry's objects that start at the caster start on it (a built archive)")
    ap.add_argument('keys', nargs='*', help='own-effects.json keys (default: all)')
    a = ap.parse_args()
    with open(a.archive, 'rb') as f:
        archive = f.read()
    with open('content/battle/own-effects.json') as f:
        spec = json.load(f)
    if a.anchors:
        bad, lines = anchors(archive, spec, a.keys)
        print('\n'.join(lines))
        print(f'{bad} species with objects off the caster')
        raise SystemExit(1 if bad else 0)
    if not a.composed:
        ap.error('--composed or --anchors')
    from tools import efecompose as X
    bad = 0
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


if __name__ == '__main__':
    main()
