#!/usr/bin/env python3
"""Which donor suits which Digimon: one score per (species, donor), from what a donor's animation does to this body.

  ranking.py build [--jobs 14]       build/review/composite-ranking.json: for every species, every donor, the score and the parts of it
  ranking.py show ID [N]             the first N donors of species ID with the reasons

Penalties (lower is better), each measured, none by eye:
  parts      the fraction of the model's parts (each leg, each arm, head, jaw) that the donor has a counterpart for (limbmap.py)
  limbs      the number of legs and whether both have arms (a biped on a quadruped donor, an armless body on one with arms)
  proportion the length of a leg and an arm against the body's height, the donor's against the model's (the motion of a long leg on a short one
             slides; the same for arms, which must reach the same places)
  head       where the head looks over the idle, the walk and the run once the donor's head motion is added to the model's own rest posture
             (a head that looks 37 degrees down on average, as Gabumon's does on Veemon, is a penalty)
  slots      the everyday animations the model has that the donor does not (the model is then left with the importer's)
  fit        the importer's own skeleton fit (import_batch.donor_score without element and level)
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); TOOLS = str(_DevPath(_DEV_ROOT) / "tools"); ROOT = _DEV_ROOT
sys.path.insert(0, TOOLS); sys.path.insert(0, HERE)
try:
    import numpy  # noqa: F401
except ImportError:
    py = os.path.join(os.environ.get('DCB_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'digimoncardbattle')), '.venv', 'bin', 'python')
    if os.path.exists(py) and not os.environ.get('RANKING_REEXEC'):
        os.environ['RANKING_REEXEC'] = '1'
        os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])
    raise SystemExit('ranking: needs the card-game venv')

OUT = os.path.join(ROOT, 'build/review/composite-ranking.json')
W = dict(parts=2.0, limbs=2.0, proportion=1.2, head=1.0, slots=1.5, fit=1.5)
GAZE_GOAL = 5.0                    # degrees below the horizontal the head should look on average


def _gaze_series(m, t, hb, slots):
    import mmd, animsheet
    e = mmd.exe(); nb = e.bone_count[t]
    vs = m.tmd.obj_verts(e.skeleton[t][hb][0])
    out = {}
    for s in slots:
        if s >= len(m.anims.table) or m.anims.table[s] is None:
            continue
        f, _, _ = animsheet.slot_frames(m, nb, s)
        g = []
        for q in f:
            q = [list(v) for v in q]; q[0] = [4096, 4096, 4096] + q[0][3:6] + [0, 0, 0]
            M = mmd.bone_matrices(m, q)[hb]
            P = sorted(([sum(M[i][j] * v[j] for j in range(3)) + M[i][3] for i in range(3)] for v in vs), key=lambda p: p[2])
            fr = P[:max(2, len(P) // 6)]
            c = [sum(p[i] for p in P) / len(P) for i in range(3)]; fp = [sum(p[i] for p in fr) / len(fr) for i in range(3)]
            g.append(math.degrees(math.atan2(fp[1] - c[1], abs(fp[2] - c[2]) or 1)))
        out[s] = g
    return out


def _lengths(S, P):
    """Leg and arm length (hip or shoulder joint to the end of the limb's mesh) over the body's height."""
    H = S.H or 1.0
    def mean_len(chains):
        L = []
        for _, c in chains:
            c = [b for b in c if S.mass[b]] or c
            a = S.joint[c[0]]; z = S.tip[c[-1]]
            L.append(math.dist(a, z))
        return sum(L) / len(L) if L else None
    return mean_len(P['legs']), mean_len(P['arms'])


def donor_facts(dt):
    import mmd; import species; import import_batch as IB; from tools.dev.models.review import limbmap as limbmap
    e = mmd.exe(); O = species.originals()
    S, _, _ = IB.donor_shape(dt); P = limbmap.parts(S)
    d = mmd.MMD.load(O.model_path(dt), dt)
    hb = [b for b in P['head'] if S.mass[b]]
    gz = _gaze_series(d, dt, hb[-1], [0, 1, 2, 3]) if hb else {}
    ref = gz[0][0] if 0 in gz else 0.0
    delta = [x - ref for s in gz for x in gz[s]]
    leg, arm = _lengths(S, P)
    return dict(legs=len(P['legs']), arms=len(P['arms']), has_jaw=bool(P.get('jaw')), leg=leg, arm=arm, H=S.H,
                slots=[s for s, i in enumerate(d.anims.table) if i is not None],
                gaze_mean=sum(delta) / len(delta) if delta else 0.0, gaze_max=max(delta) if delta else 0.0,
                name=O.rec[dt]['para']['name'])


def species_score(sp, donors, facts, fits):
    import mmd; from tools.dev.models.review import limbmap as limbmap; from tools.dev.models.review import lib as lib
    t = sp['id']
    T = lib.shape_of_mmd(sp['model'], t); PT = limbmap.parts(T)
    m = mmd.MMD.load(lib.default_model(sp), t)
    hb = [b for b in PT['head'] if T.mass[b]]
    v0 = _gaze_series(m, t, hb[-1], [0])[0][0] if hb else 0.0
    tleg, tarm = _lengths(T, PT)
    tslots = [s for s, i in enumerate(m.anims.table) if i is not None and s < 0x2e]
    want_parts = len(PT['legs']) + len(PT['arms']) + (1 if PT['head'] else 0) + (1 if PT.get('jaw') else 0)
    out = []
    for dt in donors:
        f = facts[dt]
        got = min(len(PT['legs']), f['legs']) + (min(len(PT['arms']), f['arms'])) + (1 if PT['head'] else 0) + (1 if PT.get('jaw') and f['has_jaw'] else 0)
        parts = 1 - got / want_parts if want_parts else 0.0
        limbs = (0 if len(PT['legs']) == f['legs'] else 1.0) + (0 if bool(PT['arms']) == bool(f['arms']) else 0.5)
        prop, n = 0.0, 0
        for a, b in ((tleg, f['leg']), (tarm, f['arm'])):
            if a and b:
                prop += abs(math.log((a / T.H) / (b / (f['H'] or 1)))); n += 1
        prop = prop / n if n else 0.5
        mean = v0 + f['gaze_mean']; worst = v0 + f['gaze_max']
        head = min(1.0, abs(mean - GAZE_GOAL) / 40.0) + (0.5 * min(1.0, max(0.0, worst - 30) / 30.0))
        slots = 1 - (len([s for s in tslots if s in f['slots']]) / len(tslots)) if tslots else 0.0
        fit = fits.get(dt, 0.5)
        score = W['parts'] * parts + W['limbs'] * limbs + W['proportion'] * prop + W['head'] * head + W['slots'] * slots + W['fit'] * fit
        out.append(dict(donor=dt, score=round(score, 3), parts=round(parts, 2), limbs=round(limbs, 2), proportion=round(prop, 2),
                        head=round(head, 2), gaze=[round(mean), round(worst)], slots=round(slots, 2), fit=round(fit, 2)))
    out.sort(key=lambda r: r['score'])
    return out


_G = {}


def _one(sid):
    from tools.dev.models.review import lib as lib
    sp = lib.find(sid)
    return sid, species_score(sp, _G['donors'], _G['facts'], _G['fits'].get(sid, {}))


def build(jobs=14):
    from tools.dev.models.review import lib as lib; import import_batch as IB
    from multiprocessing import get_context
    Pool = get_context('fork').Pool                  # the workers inherit the donors' facts
    W_ = lib._walkpolish()
    sps = [s for s in W_.all_species() if os.path.exists(lib.default_model(s))]
    donors = IB.donor_candidates()
    _G['donors'] = donors
    _G['facts'] = {d: donor_facts(d) for d in donors}
    _G['fits'] = {}
    for sp in sps:                                  # the importer's skeleton fit, without element and level
        T = lib.shape_of_mmd(sp['model'], sp['id'])
        _G['fits'][sp['id']] = {d: min(1.0, IB.donor_score(T, d, 0, 5)[1]['fit'] + 0.12 * IB.donor_score(T, d, 0, 5)[1]['aspect']) for d in donors}
    with Pool(jobs) as pool:
        res = dict(pool.map(_one, [s['id'] for s in sps], chunksize=1))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({str(k): v for k, v in res.items()}, open(OUT, 'w'))
    print(len(res), 'species ranked ->', OUT)


def load():
    try:
        return json.load(open(OUT))
    except OSError:
        return {}


def show(sid, n=8):
    r = load().get(str(sid))
    if not r:
        sys.exit('run build first')
    import species
    O = species.originals()
    for i, x in enumerate(r[:n]):
        print(i + 1, O.rec[x['donor']]['para']['name'], {k: v for k, v in x.items() if k != 'donor'})


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['build', 'show']); ap.add_argument('id', nargs='?', type=int); ap.add_argument('n', nargs='?', type=int, default=8)
    ap.add_argument('--jobs', type=int, default=14)
    a = ap.parse_args()
    sys.argv = sys.argv[:1]
    if a.cmd == 'build':
        build(a.jobs)
    else:
        show(a.id, a.n)
