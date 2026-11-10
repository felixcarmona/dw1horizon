"""Vikemon's walk, condition walk and run with the upper body on the stride's beat.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the current field model)
and --out, then store the result with tools/models/edit.py put 220.

The imported clips drove the legs with a stride (16, 26 and 13 ticks) and left everything above the pelvis on the
idle's breathing loop (one breath over the whole 64 or 104 ticks, the same 15 degree swing of chest, head, arms,
back and tail in every clip). The pelvis did not move, the chest did not turn against the hips, the fists swung
about a sixth of the feet's travel and a hundred degrees out of step with the same-side foot (about fifty in the
run), so the legs and the body read as two animals.

Each clip keeps its legs, its length, its root travel and its sounds. Every bone above the pelvis (chest, neck, head,
jaw, arms, shoulder pads, back mace rig, tail, loincloth) loses the breathing and is rebuilt as its own mean pose plus
terms locked to the stride phase u (the right foot's z is cos u in the clip itself):

- the pelvis rises over each planted foot in the walks and dips there in the run (two beats a stride);
- the chest twists against the hips (the right shoulder comes forward as the right foot goes back), rolls over the
  planted foot and nods on the pelvis' beat, with a forward lean (more in the tired walk and the run);
- neck and head follow later and turn against the chest so the gaze stays forward;
- the arms swing against their own side's leg;
- the back rig, the tail and the loincloth lag the chest: a heavy thing catching up.

Every term is a whole number of cycles over the clip, so the loops stay seamless; the mesh and every other program
stay exact.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import numpy as np  # noqa: E402
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 220
NB = 28
SLOTS = (2, 3, 4)
TOL_LEGS = 3
CLEAR = -2      # the lowest leg vertex may come this close to the floor (y is down, the floor is 0)
TOL = 8   # the import's own clip tolerance; keeps the resident model inside its buffer
REPEATS = False
LEGS = (12, 13, 14, 15, 16, 17)
PELVIS, CHEST, NECK, HEAD = 11, 1, 2, 3
RARM, LARM = 5, 8
BACK = 20
TAIL = (26, 27)
FOOT = 14
# the legs' stride length in ticks: 16 in the walk, 26 in the condition walk, 13 in the run
PERIOD = {2: 16, 3: 26, 4: 13}
D = 4096 / 360.0
# degrees (the pelvis in units); sign +1: rises over the planted foot (walks), -1: dips there (run)
PARAMS = {
    2: dict(bob=2, bobsign=1, lean=3, twist=5, roll=2.5, nod=1.2, arm=16, tail=6, back=1.5),
    3: dict(bob=1.5, bobsign=1, lean=9, twist=3.5, roll=4, nod=1.5, arm=10, tail=4, back=2),
    4: dict(bob=6, bobsign=-1, lean=11, twist=8, roll=2, nod=2, arm=26, tail=9, back=2.5),
}


def bone_tol():
    # the legs and the pelvis keep a fine fit (the foot's planting depends on it); the smooth upper-body terms take the
    # import's own tolerance, which is what keeps the resident model inside its buffer
    tol = {b: TOL_LEGS for b in (PELVIS,) + LEGS}
    tol[None] = TOL
    return tol


def worlds(model, frames):
    out = []
    for f in frames:
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        out.append(np.array(mmd.bone_matrices(model, g)))
    return out


def lowest(model, skeleton, w):
    return max(float((np.array(model.tmd.obj_verts(skeleton[b][0]))[:, :3] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max())
               for b in LEGS)


def rebuild(model, skeleton, slot, frames):
    n = len(frames) - 1
    prm = PARAMS[slot]
    P = PERIOD[slot]
    assert n % P == 0, (slot, n, P)
    w = worlds(model, frames[:n])
    fz = np.array([m[FOOT, 2, 3] for m in w])
    k = n // P
    ref = float(np.angle(np.fft.rfft(fz - fz.mean())[k]))
    t = np.arange(n)
    u = 2 * math.pi * k * t / n + ref          # the right foot's z is cos(u): +z is backwards
    mean = np.mean([[f[b][3:9] for b in range(NB)] for f in frames[:n]], axis=0)
    new = copy.deepcopy(frames[:n])
    upper = [b for b in range(1, NB) if b != PELVIS and b not in LEGS]
    for f in new:
        f[PELVIS][3:9] = [float(x) for x in mean[PELVIS]]     # the old breathing (and the run's own bob) leave the pelvis
    for i, f in enumerate(new):
        for b in upper:
            f[b][3:9] = [float(x) for x in mean[b]]

    def add(b, c, series):
        for i, f in enumerate(new):
            f[b][c] += float(series[i])
    # pelvis: two beats a stride
    add(PELVIS, 7, prm['bobsign'] * prm['bob'] * np.cos(2 * u))
    # chest: lean, twist against the hips, roll over the planted foot, nod on the pelvis' beat
    add(CHEST, 3, prm['lean'] * D + prm['nod'] * D * -prm['bobsign'] * np.cos(2 * u - 0.8))
    add(CHEST, 4, prm['twist'] * D * np.cos(u - 0.15))
    add(CHEST, 5, prm['roll'] * D * -np.sin(u))
    # neck and head arrive later and turn against the chest
    add(NECK, 3, 0.6 * prm['nod'] * D * -prm['bobsign'] * np.cos(2 * u - 1.4))
    add(NECK, 4, -0.3 * prm['twist'] * D * np.cos(u - 0.5))
    add(NECK, 5, -0.3 * prm['roll'] * D * -np.sin(u - 0.5))
    add(HEAD, 3, -0.2 * prm['lean'] * D + 0.9 * prm['nod'] * D * -prm['bobsign'] * np.cos(2 * u - 2.0))
    add(HEAD, 4, -0.5 * prm['twist'] * D * np.cos(u - 0.9))
    add(HEAD, 5, -0.5 * prm['roll'] * D * -np.sin(u - 0.9))
    # arms against the same side's leg (+rx throws the fist backwards)
    add(RARM, 3, -prm['arm'] * D * np.cos(u))
    add(LARM, 3, prm['arm'] * D * np.cos(u))
    # back rig and tail lag the chest
    add(BACK, 3, prm['back'] * D * -prm['bobsign'] * np.cos(2 * u - 1.8))
    add(BACK, 5, prm['back'] * D * -np.sin(u - 1.0))
    add(TAIL[0], 4, prm['tail'] * D * np.cos(u - 1.0))
    add(TAIL[1], 4, 1.5 * prm['tail'] * D * np.cos(u - 2.0))
    add(TAIL[0], 3, 0.5 * prm['tail'] * D * -prm['bobsign'] * np.cos(2 * u - 1.6))
    add(TAIL[1], 3, 0.8 * prm['tail'] * D * -prm['bobsign'] * np.cos(2 * u - 2.4))
    # the bob must not sink a foot into the floor: raise the pelvis by the deepest sink (the old clip floated 3 units)
    for _ in range(4):
        sink = max(lowest(model, skeleton, m) for m in worlds(model, new)) - CLEAR
        if sink <= 0:
            break
        for f in new:
            f[PELVIS][7] -= sink
    out = []
    for f in new:
        out.append([[round(x) for x in bone] for bone in f])
    last = copy.deepcopy(out[0])
    last[0] = [round(x) for x in frames[n][0]]
    out.append(last)
    return out


def build(data, skeleton):
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        frames, loop, events = animsheet.slot_frames(model, NB, slot)
        mmd.close_loop(frames, loop)
        n = len(frames) - 1
        before = [lowest(model, skeleton, w) for w in worlds(model, frames[:n])]
        frames = rebuild(model, skeleton, slot, frames)
        mmd.close_loop(frames, loop)
        after = [lowest(model, skeleton, w) for w in worlds(model, frames[:n])]
        sounds = [(t, kind, c) for t, kind, c in events if kind == 'sound']
        # replaced in place so the old program leaves the file (the resident budget has almost no room)
        index = result.anims.table[slot]
        assert result.anims.table.count(index) == 1, (slot, 'program shared with another slot')
        result.anims.anims[index] = mmd.encode_anim(frames, NB, loop, sounds, tol=bone_tol(), repeats=REPEATS)
        checks.append(dict(slot=slot, ticks=n, lowest_leg_before=[round(min(before)), round(max(before))],
                           lowest_leg_after=[round(min(after)), round(max(after))]))
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert set(changed) <= set(SLOTS), changed
    return output, dict(source_sha256=hashlib.sha256(data).hexdigest(), output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed, checks=checks, storage=motionstorage.audit(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/220-vikemon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
