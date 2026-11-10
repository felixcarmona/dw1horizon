#!/usr/bin/env python3
"""Submarimon: drop the red-stencil faces that lie on its body plates, and keep its tail screw turning in every clip.

Authoring only: run on `tools/models/edit.py get 202`'s model (MMD only; the texture stays) and store the result
with `tools/models/edit.py put 202`.

- The body (object 0) carries four faces that duplicate four plates already drawn there (same four corners) and
  sample the red diamond stencil at the texture's UV 172..195 x 88..111 (CLUT row 5, colour 0 clear). Nothing else
  uses that stencil. Where a depth buffer is used they fight the plate under them and show as red specks beside the
  yellow fin. They are removed; the plates stay.
- The screw is bone 8 (the rear piece, parent 3). Its rz, the turn about the screw's own axis, only jerked in the
  idle, walk and run (up to 175 degrees a tick, no net turn). Every clip that does not already turn the screw
  through a good part of its length now turns it steadily, in the direction the original spin had:
  TURN of whole turns per CLUT of 25 ticks, at least one turn a clip. A looping clip turns whole turns over its
  loop body, so the loop has no jump; a one-tick hold body repeats its step forever. rx and ry (the sway of the
  screw with the body) and every other bone and channel are untouched. The start pose of each clip is unchanged.
"""
import argparse
import copy
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.articulation import replace_channels  # noqa: E402

SOURCE = 'aad4f6c4252b099e7e173379d1983f8e5fac6f44e63c511ba6394ea0b9cc5861'
SPECIES, NB = 202, 11
SCREW, RZ = 8, 5
BODY = 0
STENCIL = (172, 88, 195, 111)   # UV box of the red diamond stencil, CLUT row 5
STENCIL_ROW = 5
TICKS_PER_TURN = 25   # about 14 degrees a tick
SPINNING = 4096       # clips whose rz already travels this far in one direction keep their own spin


def twins(model):
    """The stencil faces of the body: each shares its corners with a plate."""
    verts = model.tmd.obj_verts(BODY)
    prims = model.tmd.objects[BODY].prims
    corners = [frozenset(tuple(verts[i][:3]) for i in p.decode()['verts']) for p in prims]
    out = []
    for i, p in enumerate(prims):
        if not p.mode & 4:
            continue
        d = p.decode()
        row = (d['cba'] >> 6) - 488
        us, vs = [u for u, v in d['uv']], [v for u, v in d['uv']]
        if row == STENCIL_ROW and STENCIL[0] <= min(us) and max(us) <= STENCIL[2] and STENCIL[1] <= min(vs) and max(vs) <= STENCIL[3]:
            assert any(j != i and corners[j] == corners[i] for j in range(len(prims))), i
            out.append(i)
    return out


def only_stencil_users(model, drop):
    for oi, ob in enumerate(model.tmd.objects):
        for i, p in enumerate(ob.prims):
            if (oi, i) in drop or not p.mode & 4:
                continue
            d = p.decode()
            if (d['cba'] >> 6) - 488 != STENCIL_ROW:
                continue
            for u, v in d['uv']:
                assert not (STENCIL[0] <= u <= STENCIL[2] and STENCIL[1] <= v <= STENCIL[3]), (oi, i)


def spin(frames, loop):
    """The screw's rz per tick: a steady turn, whole turns over the loop body."""
    n = len(frames) - 1
    start = frames[0][SCREW][RZ]
    length = n - loop if loop is not None else n
    if length > 1:
        turns = max(1, round(length / TICKS_PER_TURN))
        step = -4096 * turns / length
    else:
        step = -4096 / TICKS_PER_TURN
    return [round(start + step * t) for t in range(n + 1)]


def build(data):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the importer output with the stored Submarimon delta (edit.py get 202)')
    mmd.exe().add_type(SPECIES, [(-1, -1), (0, 0), (1, 1), (2, 2), (3, 1), (4, 1), (5, 1), (6, 1), (7, 3), (8, 3), (9, 3)])
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    new = copy.deepcopy(old)
    drop = twins(old)
    assert len(drop) == 4, drop
    only_stencil_users(old, {(BODY, i) for i in drop})
    new.tmd.objects[BODY].prims = [p for i, p in enumerate(old.tmd.objects[BODY].prims) if i not in drop]

    report, done = [], {}
    for slot, index in enumerate(old.anims.table):
        if index is None or index in done:
            continue
        frames, loop, _ = animsheet.slot_frames(old, NB, slot)
        rz = [f[SCREW][RZ] for f in frames]
        if max(rz) - min(rz) >= SPINNING and abs(rz[-1] - rz[0]) >= SPINNING:
            done[index] = None   # already turns through the clip
            report.append(dict(slot=slot, kept='already spins'))
            continue
        samples = copy.deepcopy(frames)
        for f, v in zip(samples, spin(frames, loop)):
            f[SCREW][RZ] = v
        mmd.close_loop(samples, loop)
        anim = replace_channels(old.anims.anims[index], samples, loop, NB, {(SCREW, RZ)})
        new.anims.anims[index] = anim
        done[index] = slot
        before, after = mmd.AnimPlayer(old.anims.anims[index], NB, slot), mmd.AnimPlayer(anim, NB, slot)
        ticks = (len(frames) - 1) * 4 if loop is not None else len(frames) - 1
        for t in range(ticks):
            a, b = before.tick(), after.tick()
            if not (a and b):
                break
            assert before.base == after.base
            for bone in range(NB):
                for c in range(9):
                    if (bone, c) != (SCREW, RZ):
                        assert before.pose[bone][c] == after.pose[bone][c], (slot, t, bone, c)
        report.append(dict(slot=slot, ticks=len(frames) - 1, loop=loop, rz_end=spin(frames, loop)[-1]))
    output = new.build()
    parsed = mmd.MMD.parse(output, NB)
    parsed.type = SPECIES
    changed = changed_programs(old, parsed)
    wanted = {s for s, i in enumerate(old.anims.table) if done.get(i) is not None}
    assert set(changed) <= wanted and set(changed), (changed, wanted)
    for oi in range(len(old.tmd.objects)):
        if oi != BODY:
            assert [q.raw for q in old.tmd.objects[oi].prims] == [q.raw for q in parsed.tmd.objects[oi].prims]
            assert old.tmd.obj_verts(oi) == parsed.tmd.obj_verts(oi)
    storage = motionstorage.require(output, NB)
    return output, dict(removed_prims=drop, changed_slots=changed, clips=report, storage=storage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    data, proof = build(a.source.read_bytes())
    a.out.write_bytes(data)
    for k, v in proof.items():
        print(k, v)


if __name__ == '__main__':
    main()
