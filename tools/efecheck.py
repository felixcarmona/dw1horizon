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

    python -m tools.efecheck --disc DW2.bin [--archive EFEDAT.EFE] [keys]   own effects (content/battle/own-effects.json)
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


def main():
    import argparse
    import json
    from tools.derive.steps import effects as E
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--disc', required=True, help='the Digimon World 2 (USA) disc image')
    ap.add_argument('--archive', default='extracted/ETCHI/EFEDAT.EFE', help="this game's effect archive")
    ap.add_argument('keys', nargs='*', help='own-effects.json keys (default: all)')
    a = ap.parse_args()
    disc = D.Disc(a.disc)
    tables = D.Tables(disc)
    with open(a.archive, 'rb') as f:
        archive = f.read()
    with open('content/battle/own-effects.json') as f:
        spec = json.load(f)
    bad = 0
    for key, e in spec.items():
        if key == 'note' or (a.keys and key not in a.keys):
            continue
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
