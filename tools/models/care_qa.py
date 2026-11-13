#!/usr/bin/env python3
"""Measured QA of an imported species' care and condition clips (the slots the partner plays near its tamer).

  condition idles   1 poor condition, 14 sick or injured, 15 hungry, 16 needs the toilet, 17 sleepy, 18 tired,
                    19 unhappy (they loop while the condition lasts; resident)
  care clips        5 / 7 happy / unhappy gesture, 8 eat, 9 asleep, 10 toilet, 11 going to sleep (praise), 12 after
                    pooping (scold), 13 refuse, 0x16 / 0x1B training, 0x25 blocking (5 and 7-13 are cold)

This tool measures the FINAL model (the provider output after the delta, field overlays, passes and the care-idle stage,
not the `edit.py get` intermediate) slot by slot against the species' field idle (slot 0, the measuring stick: height,
floor, limb chains, body bones as `battle_qa.reference` makes them) and against origin/main's final model, and flags
with fixed thresholds:

  distinct   a condition idle must look different from the field idle: per tick, the pose's mean vertex distance (in the
             body frame: the root's turn and travel taken out) to the nearest pose of the idle, averaged over the clip,
             at least IDLE_DIST heights; two condition idles that are different programs must be PAIR_DIST apart
             (sharing one program is the game's own habit: 25 native species play one clip for all seven)
  liveness   the clip moves (some limb chain's tip travels LIVE_FLOOR heights); a changed clip keeps at least
             LIVE_KEEP of main's motion
  anatomy    a bone rotating BONE_EXCESS degrees beyond what it does in any field clip (0-4) and in the importer's
             same slot (a quadruped's front leg lifted as an arm, a wing used as a hand by a retargeted donor clip)
  posture    the body bones' forward-axis elevation off the field idle (a torso tipped), per slot class; as tipped as
             the importer's own clip (against its own idle) is the source's posture, noted, not flagged (so are
             crossings within SOURCE_CROSS of the importer's same clip: a reworked field idle can cross far less)
  mesh       non-finite numbers, scale channels, the largest vertex step between ticks, the loop seam (last tick to
             first, for clips that loop from their start), a piece leaving the body, triangle crossings between pieces (against the
             species' own field idle, walk and tired walk)
  floor      the lowest vertex under the field idle's own lowest
  length     a condition idle under 127 ticks (the game's 8-bit condition timer wraps beyond: the condition clips would
             never start) and slot 1 no longer than main's (it is the idle the timer counts against)
  buffer     the model's resident part under the partner model buffer (motionstorage.audit)

The thresholds are the measured range of the disc's own DW1 partners (145 native models with every condition slot, 611
condition clips and 65-140 clips of each care slot against their own field idle; docs/reference/motion.md gives the
numbers). A slot whose program is main's is reported with verdict 'main' (pre-existing); a changed slot with a flag
is kept only when no flagged number is worse than main's same slot, else 'fail' (the slot goes back to main's).

  tools/models/care_qa.py check FINAL.MMD BASE.MMD MAIN.MMD SPECIES_JSON [--slots ...] [--json OUT]
            FINAL, BASE and MAIN are the species' final model of this tree, its importer output and origin/main's final
            model; exits 1 when a slot fails

Not proven by these numbers: how a clip reads (character, taste), what the engine interpolates at 60 fps. Uses numpy.
"""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'tools'), os.path.join(ROOT, 'tools', 'models')]

from tools.models import battle_qa as bq  # noqa: E402

CONDITION = (1, 14, 15, 16, 17, 18, 19)
CARE = (5, 7, 8, 9, 10, 11, 12, 13, 22, 27, 37)
FIELD = (0, 1, 2, 3, 4)

# Thresholds (heights: the species' field idle height; the native rates are over the 145 native partners' clips)
IDLE_DIST = 0.035      # condition idle off the field idle (native 1st percentile 0.035, median 0.12)
PAIR_DIST = 0.026      # two different condition programs (native 1st percentile of the non-shared pairs)
LIVE_FLOOR = 0.015     # some chain tip travels this far (native condition idles: 1st percentile 0.016)
LIVE_KEEP = 0.5
BONE_EXCESS = 60.0     # degrees beyond the bone's field range and the importer's same slot
LEN_MAX = 126
SEAM_MAX = 0.05
WORSE = 0.10
# per slot class (condition idles, then each care slot): native 99th percentile of body tip, vertex step, tear, crossings
# per tick over the field idle's, and the lowest vertex under the floor
CLASS = {'cond': dict(body=45.0, jump=0.47, tear=0.08, cross=4.0, sink=0.30),
         'care': dict(body=80.0, jump=1.35, tear=0.15, cross=4.5, sink=0.80)}
BUFFER = 100352


def slot_class(s):
    return 'cond' if s in CONDITION else 'care'


def _body_vertices(clip, ticks):
    return np.concatenate([np.einsum('fij,nj->fni', clip.Wb[ticks][:, b, :3, :3], v) + clip.Wb[ticks][:, b, None, :3, 3]
                           for b, v in clip.rig.local.items()], 1)


def _ticks(n, k=40):
    return np.unique(np.linspace(0, n - 1, min(n, k)).round().astype(int))


def pose_distance(cx, cy, h):
    """Mean over the ticks of clip cx of the RMS vertex distance (heights, body frame) to the nearest pose of clip cy."""
    X, Y = _body_vertices(cx, _ticks(cx.n)), _body_vertices(cy, _ticks(cy.n))
    d = np.sqrt(((X[:, None] - Y[None]) ** 2).sum(-1).mean(-1)) / h
    return float(d.min(1).mean())


def measure(clip, ref, idle):
    m = bq.measure(clip, ref)
    m['idle_dist'] = pose_distance(clip, idle, ref['h'])
    m['live'] = max(m['chain_amp'].values()) if m['chain_amp'] else 0.0
    return m


def field_ranges(rig):
    out = np.zeros(rig.nb)
    for s in FIELD:
        f = rig.frames(s)
        if f is not None and len(f[0]) > 1:
            c = bq.Clip(rig, *f)
            out = np.maximum(out, [0.0] + [float(bq.angle(c.local_rot[:, b], bq.mean_rotation(c.local_rot[:, b])[None]).max())
                                           for b in range(1, rig.nb)])
    return out


def source_tip(A, fA, body):
    """The importer's same clip: its body bones' largest elevation off the importer's own field idle (degrees)."""
    if A is None or fA is None or not body or max(body) >= A.nb or A.frames(0) is None:
        return None
    idle = bq.Clip(A, *A.frames(0))
    c = bq.Clip(A, *fA)
    ref = bq.elevation(idle.Wb[:, body, :3, :3]).mean(0)
    return float(np.abs(bq.elevation(c.Wb[:, body, :3, :3]).mean(0) - ref).max())


def program(rig, s):
    f = rig.frames(s)
    return None if f is None else f[0]


def same(a, b):
    return a is not None and b is not None and a.shape == b.shape and np.array_equal(a, b)


def check(F, A, M, slots=CONDITION + CARE, final_bytes=None, nb=None):
    """{slot: row} with `flags`, `keys`, `notes`, `source` ('main' or 'changed'), `verdict` and the numbers."""
    ref = bq.reference(M)
    h = ref['h']
    idle = bq.Clip(M, *M.frames(0))
    idle_sink = bq.measure(idle, ref)['sink']         # a hovering flyer's idle dips under its own mean floor
    fr = field_ranges(M)
    # crossings a tick the species' own field clips have (the idle, the walk, the tired walk): a chibi rig crosses
    field_cross = max([ref['cross']] + [bq.crossings(M, bq.Clip(M, *M.frames(s)).V, len(M.frames(s)[0]))[0]
                                        for s in (2, 3) if M.frames(s) is not None and len(M.frames(s)[0]) > 1])
    rows, clips = {}, {}
    for s in slots:
        fF, fM, fA = F.frames(s), M.frames(s), A.frames(s) if A is not None else None
        if fF is None or len(fF[0]) < 2:
            rows[s] = dict(flags=['missing or empty'], keys=['missing'], notes=[], source='changed', verdict='fail')
            continue
        cF = bq.Clip(F, *fF)
        clips[s] = cF
        mF = measure(cF, ref, idle)
        mM = measure(bq.Clip(M, *fM), ref, idle) if fM is not None and len(fM[0]) > 1 else None
        for m in (mF, mM):
            if m:
                m['sink'] -= idle_sink
        same_main = mM is not None and same(fF[0], fM[0])
        k = CLASS[slot_class(s)]
        flags, notes = [], []

        def flag(key, msg):
            flags.append((key, msg))
        if s in CONDITION:
            if same(fF[0], program(F, 0)):
                flag('distinct', 'the field idle itself')
            elif mF['idle_dist'] < IDLE_DIST:
                flag('distinct', f'{mF["idle_dist"]:.3f} h off the field idle')
            if mF['n'] > LEN_MAX:
                flag('length', f'{mF["n"]} ticks: the condition timer wraps')
            if s == 1 and mM and mF['n'] > mM['n'] and not same_main:
                flag('length', f'{mF["n"]} ticks, main {mM["n"]}')
        if mF['live'] < LIVE_FLOOR:
            flag('live', f'no chain moves ({mF["live"]:.3f} h)')
        elif mM and not same_main and mF['live'] < LIVE_KEEP * mM['live'] and mM['live'] > 2 * LIVE_FLOOR:
            notes.append(f'calmer than main ({mF["live"]:.3f} h, main {mM["live"]:.3f})')
        # anatomy
        rng = np.array(mF['bone_range'])
        allowed = fr.copy()
        if fA is not None and len(fA[0]) > 1 and A.nb == F.nb:
            ca = bq.Clip(A, *fA)
            allowed = np.maximum(allowed, [0.0] + [float(bq.angle(ca.local_rot[:, b], bq.mean_rotation(ca.local_rot[:, b])[None]).max())
                                                   for b in range(1, A.nb)])
        exc = rng - allowed
        exc[[b for b in range(F.nb) if b not in F.meshed and not F.children[b]]] = 0     # a bone that draws nothing
        if exc.max() > BONE_EXCESS:
            b = int(exc.argmax())
            flag('bones', f'bone {b} turns {rng[b]:.0f} deg (field clips and importer {allowed[b]:.0f})')
        # mesh
        if not mF['finite']:
            flag('finite', 'non-finite numbers')
        if mF['jump'] > k['jump']:
            flag('jump', f'vertex step {mF["jump"]:.3f} h a tick')
        if cF.loop == 0 and mF['seam'] > SEAM_MAX and not same_main and (mM is None or mF['seam'] > mM['seam'] + 0.01):
            flag('seam', f'loop seam {mF["seam"]:.3f} h')
        if mF['tear'][0] > k['tear']:
            flag('tear', f'piece {mF["tear"][1]} leaves the body by {mF["tear"][0]:.3f} h')
        if mF['cross'][0] > k['cross'] * field_cross + bq.CROSS_ADD:
            src = (bq.crossings(A, bq.Clip(A, *fA).V, len(fA[0]))[0]
                   if fA is not None and len(fA[0]) > 1 and A.nb == F.nb else None)
            if src is not None and mF['cross'][0] <= SOURCE_CROSS * src + bq.CROSS_ADD:
                notes.append(f'crossings {mF["cross"][0]:.0f} a tick as the importer\'s clip ({src:.0f}): the source\'s pose')
            else:
                flag('cross', f'crossings {mF["cross"][0]:.0f} a tick (field clips {field_cross:.0f})')
        # posture
        if mF['body_off'] > k['body']:
            src = source_tip(A, fA, ref['body'])
            if src is not None and mF['body_off'] <= src + NO_WORSE['body_off']:
                notes.append(f'body tipped {mF["body_off"]:.0f} deg as the importer\'s clip ({src:.0f}): the source\'s posture')
            else:
                flag('body_off', f'body bone {mF["body_bone"]} tipped {mF["body_off"]:.0f} deg off the field idle')
        if mF['sink'] > k['sink']:
            flag('sink', f'under the floor {mF["sink"]:.3f} h')
        for m in (mF, mM):
            if m:
                m.pop('scale', None)
                m.pop('bone_range', None)
        rows[s] = dict(flags=[m for _, m in flags], keys=[k_ for k_, _ in flags], notes=notes,
                       source='main' if same_main else 'changed', final=mF, main=mM)
    # condition idles against each other
    cond = [s for s in CONDITION if s in clips]
    for i, a in enumerate(cond):
        for b in cond[i + 1:]:
            if same(program(F, a), program(F, b)):
                continue
            d = min(pose_distance(clips[a], clips[b], h), pose_distance(clips[b], clips[a], h))
            if d < PAIR_DIST:
                for s, o in ((a, b), (b, a)):
                    rows[s]['flags'].append(f'{d:.3f} h off slot {o}')
                    rows[s]['keys'].append('pair')
    for s, r in rows.items():
        if 'verdict' not in r:
            r['verdict'] = verdict(r)
    if final_bytes is not None:
        import motionstorage
        rep = motionstorage.audit(final_bytes, nb or F.nb)
        rows['buffer'] = dict(resident=rep['resident_bytes'], fits=bool(rep['fits']) and
                              (rep['resident_bytes'] or BUFFER) < BUFFER)
    return rows


SOURCE_CROSS = 1.25    # a clip crossing about as much as the importer's same clip carries the source's pose
NO_WORSE = dict(jump=0.05, tear=0.02, sink=0.05, body_off=10.0)


def worse_than_main(row):
    out = []
    for key, msg in zip(row['keys'], row['flags']):
        f, m = row['final'], row.get('main')
        if key in NO_WORSE and m:
            vf = f[key][0] if key == 'tear' else f[key]
            vm = m[key][0] if key == 'tear' else m[key]
            if vf <= vm + NO_WORSE[key]:
                continue
        if key == 'cross' and m and f['cross'][0] <= m['cross'][0] + bq.CROSS_ADD:
            continue
        out.append(msg)
    return out


def verdict(row):
    """'pass', 'main' (main's own clip, pre-existing), 'kept' (flagged, no worse than main's) or 'fail'."""
    if not row['flags']:
        return 'pass'
    if row['source'] == 'main':
        return 'main'
    return 'fail' if worse_than_main(row) else 'kept'


def species_check(final, base, main, bones, slots=CONDITION + CARE):
    R = lambda d: bq.Rig.from_mmd(d, bones)  # noqa: E731
    return check(R(final), R(base) if base else None, R(main), slots, final_bytes=final, nb=len(bones))


def failing(rows):
    return [s for s, r in rows.items() if s != 'buffer' and r['verdict'] == 'fail'] + \
        (['buffer'] if 'buffer' in rows and not rows['buffer']['fits'] else [])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('final')
    c.add_argument('base')
    c.add_argument('main')
    c.add_argument('species_json')
    c.add_argument('--slots', nargs='*', type=int, default=list(CONDITION + CARE))
    c.add_argument('--json')
    a = ap.parse_args()
    rd = lambda p: open(p, 'rb').read()  # noqa: E731
    with open(a.species_json) as fh:
        bones = json.load(fh)['model']['skeleton']
    rows = species_check(rd(a.final), rd(a.base), rd(a.main), bones, tuple(a.slots))
    for s, r in rows.items():
        if s == 'buffer':
            print(f'buffer: resident {r["resident"]} B, fits {r["fits"]}')
            continue
        print(f'slot {s:#x}: {r["verdict"]} ' + '; '.join(r['flags'] + r['notes']))
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump({str(k): v for k, v in rows.items()}, fh, indent=1,
                      default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    sys.exit(1 if failing(rows) else 0)


if __name__ == '__main__':
    main()
