#!/usr/bin/env python3
"""Keep Gallantmon's right leg on the ground in its care clips, and turn its left foot out as far as the right one.

The retargeted eating, sleeping, reaction and toilet clips swing the right leg up (the ankle rises past 300 units
and crosses the body's middle in the eating clip): the donor's hand-to-mouth motion landed on a leg. The clips'
left leg already follows the body, so the right foot copies how far the left foot has moved from its rest place
(shortest turn of the leg bone towards that spot, kept the length it has), and its sole turns with the left sole.

The left foot also points 50 degrees outwards in every standing and walking clip, twice the right foot's 25, so
the two soles read as one turned in: its sole is turned about the vertical by the difference in all of them.

Authoring only: pass the current MMD and an output path, then store it with tools/models/edit.py put 318 OUT.mmd.
"""
import argparse
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import footfix
import legik
import mmd
import retarget

TYPE = 318
SLOTS = (5, 8, 9, 12, 13)
WALK_SLOTS = (0, 1, 2, 3, 4, 14, 15, 16, 17, 18, 33, 34)
L_FOOT = 26
TOE_OUT = 25.0                         # degrees: the right foot already turns out this much, the left foot 50
HIP, ANKLE, TOE = 21, 22, 23          # right leg: the leg piece, the foot, the toes
L_ANKLE = 26


def turn_left_foot(m, nb, skel, slots):
    """The left sole turned about the vertical so it points out TOE_OUT degrees, like the right one."""
    footfix.unroll_loops(m, slots)
    footfix.unshare(m, slots)
    turn = footfix.ry(math.radians(TOE_OUT - 50.0) * SIGN)
    done = set()
    for slot in slots:
        i = m.anims.table[slot] if slot < len(m.anims.table) else None
        if i is None or i in done:
            continue
        done.add(i)
        an = m.anims.anims[i]
        p = mmd.AnimPlayer(an, nb, slot)
        poses = []
        while p.tick(stop_at_infinite_loop=True):
            poses.append([list(v) for v in p.pose])
        T = [retarget.m3mul(turn, retarget.world_rots(skel, pose)[L_FOOT]) for pose in poses]
        footfix.rewrite_bone(an, nb, skel, slot, L_FOOT, lambda t, pose, wr, T=T: T[min(t, len(T) - 1)], 1)


SIGN = 1


def run(src, out, slots):
    m = mmd.MMD.load(src, TYPE)
    e = mmd.exe()
    nb, skel = e.bone_count[TYPE], e.skeleton[TYPE]
    idle, _, _ = animsheet.slot_frames(m, nb, 0)
    prest = retarget.world_pos(skel, idle[0])
    rid = retarget.world_rots(skel, idle[0])
    reach = legik.norm(legik.sub(prest[ANKLE], prest[HIP]))
    d_rest = legik.sub(prest[ANKLE], prest[HIP])
    footfix.unroll_loops(m, slots)
    footfix.unshare(m, slots)
    done = set()
    for slot in slots:
        i = m.anims.table[slot]
        if i in done:
            continue
        done.add(i)
        an = m.anims.anims[i]
        p = mmd.AnimPlayer(an, nb, slot)
        poses = []
        while p.tick(stop_at_infinite_loop=True):
            poses.append([list(v) for v in p.pose])
        T_hip, T_foot, T_toe = [], [], []
        for pose in poses:
            pos = retarget.world_pos(skel, pose)
            wr = retarget.world_rots(skel, pose)
            tgt = legik.add(prest[ANKLE], legik.sub(pos[L_ANKLE], prest[L_ANKLE]))
            v = legik.sub(tgt, pos[HIP])
            tgt = legik.add(pos[HIP], legik.mul(legik.unit(v), reach))
            T_hip.append(retarget.m3mul(retarget.swing(d_rest, legik.sub(tgt, pos[HIP])), rid[HIP]))
            delta = retarget.m3mul(wr[L_ANKLE], footfix.m3t(rid[L_ANKLE]))
            T_foot.append(retarget.m3mul(delta, rid[ANKLE]))
            T_toe.append(retarget.m3mul(delta, rid[TOE]))
        for b, T in ((HIP, T_hip), (ANKLE, T_foot), (TOE, T_toe)):
            footfix.rewrite_bone(an, nb, skel, slot, b, lambda t, pose, wr, T=T: T[min(t, len(T) - 1)], 1)
    turn_left_foot(m, nb, skel, list(WALK_SLOTS) + list(slots))
    data = m.build()
    assert mmd.MMD.parse(data, nb).build() == data
    Path(out).write_bytes(data)
    print(f'{out}: {len(data)} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mmd')
    ap.add_argument('out')
    ap.add_argument('--slots', type=lambda s: int(s, 0), nargs='*', default=list(SLOTS))
    a = ap.parse_args()
    run(a.mmd, a.out, a.slots)


if __name__ == '__main__':
    main()
