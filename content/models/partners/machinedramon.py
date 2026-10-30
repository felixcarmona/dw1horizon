#!/usr/bin/env python3
"""Machinedramon's partner model: MUGE mesh + its own animations + the partner slots it lacks.

Machinedramon (type 115, MUGE.MMD, 32 bones) is the final boss. Its model already has an
idle, walk, run, the battle slots and its seven technique animations (Megaton Punch ...
Infinity Cannon, 0x2E-0x34), but none of the world/care slots a partner plays (eat,
sleep, poop, moods, conditions, reactions). This script writes MUGP.MMD, the partner-only
copy (the boss keeps MUGE.MMD):

  - kept (re-encoded exactly, tol 0): 0, 1, 2, 4, 0x13, 0x21-0x25, 0x28-0x2C and 0x2E-0x34;
  - dropped: 0x1C (a boss-scene animation) and 0x35 (no eighth technique);
  - the slow walk (3) and the training run (0x1B) share its walk (2);
  - retargeted from MetalGreymon (the other armoured biped dinosaur, 30 bones): 5,
    7-0x12 and 0x15-0x19, keyed every 2 ticks and encoded with tol 3 to fit the buffer.
    Machinedramon's right claw hangs to the floor and its tail is longer, so where the
    retargeted pose would push a limb into the floor the limb is lifted (smallest extra
    turn at the shoulder or the tail base), and the hips where the feet would sink. Bone map: torso, neck, head, jaw, both arms (the three
    fingers of the left hand follow its wrist), pelvis, the three tail pieces and both
    legs; the back cannons ride on the chest. Hips bounce 1.5 times MetalGreymon's (its
    hips are at 300, MetalGreymon's at 200). The voice notes (bank 4: 53 roar, 54/55
    shouts) are the same in every voice bank, so they play Machinedramon's own voice.

Usage (from the repository root):
  python3 content/models/partners/machinedramon.py [OUT.MMD]
default OUT: build/models/MUGP.MMD.
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os
import sys

from tools.models.partners import boss as boss_partner  # noqa: E402

TYPE = 115
KEEP = [0, 1, 2, 4, 0x13, 0x21, 0x22, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2A, 0x2B, 0x2C] + \
       list(range(0x2E, 0x35))
RETARGET = [5, 7, 8, 9, 0xA, 0xB, 0xC, 0xD, 0xE, 0xF, 0x10, 0x11, 0x12, 0x15, 0x16, 0x17,
            0x18, 0x19]

# Machinedramon bone <- MetalGreymon bone
BONE_MAP = {
    2: (2, 1.0),                                     # torso (the chest and cannons ride on it)
    4: (3, 1.0), 6: (4, 1.0), 7: (5, 1.0),           # neck, head, jaw
    14: (7, 1.0), 15: (8, 1.0), 16: (9, 1.0),        # right arm, claw hand
    17: (11, 1.0), 18: (12, 1.0),                    # left arm
    19: (13, 1.0), 20: (13, 1.0), 21: (13, 1.0),     # left fingers: MetalGreymon's hand
    22: (18, 1.0), 23: (19, 1.0), 24: (20, 1.0), 25: (21, 1.0),   # pelvis, tail
    26: (23, 1.0), 27: (24, 1.0), 28: (25, 1.0),     # right leg
    29: (27, 1.0), 30: (28, 1.0), 31: (29, 1.0),     # left leg
}
HIPS = (1, 1, 1.5)
LIFT = (14, 17, 23)      # right arm, left arm, tail base
FLOOR = 7                # the lowest point of the rest pose (the feet)
TOL = 3


def build(out_path):
    mesh = boss_partner.load('MUGE')
    src = boss_partner.load('MTGR')
    trest = boss_partner.rest(mesh)
    b = boss_partner.Builder(mesh, 0x35)
    first = {}
    for s in KEEP:
        k = mesh.anims.table[s]
        if k in first:                 # slots that share one animation (0/0x21, 2/0x23...)
            b.share(s, first[k])
            continue
        first[k] = s
        # its own animations, re-encoded exactly (tol 0: the same pose on every tick, ~1 KB
        # smaller than the original encoding)
        smp, loop, ev = boss_partner.play(mesh, s)
        b.put(s, smp, loop, ev, tol=0)
    for s in RETARGET:
        smp, loop, ev = boss_partner.retarget_slot(src, s, TYPE, trest, BONE_MAP, hips=HIPS)
        # Machinedramon's right claw hangs to the floor and its tail is longer than
        # MetalGreymon's: lift those limbs where they would sink, then the hips where the
        # feet would
        boss_partner.lift_chains(mesh, smp, LIFT, floor=FLOOR)
        boss_partner.ground_clamp(mesh, smp, allow=6, ref=trest)
        # keys every 2 ticks, linear in between (fewer bytes: the buffer is full)
        b.put(s, boss_partner.key_every(smp, loop, 2), loop, ev, tol=TOL)
    # the slow walk (3) and the training run (0x1B) share its own walk, as Cherrymon's
    # training run does: the buffer is full (the mesh alone is 36.5 KB, the largest)
    b.share(3, 2)
    b.share(0x1B, 2)
    return b.write(out_path, boss_partner.PARTNER_SLOTS + list(range(0x2E, 0x35)),
                   'MUGE mesh, own + MetalGreymon-retargeted animations')


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(boss_partner.ROOT, 'build/models/MUGP.MMD')
    build(out)


if __name__ == '__main__':
    main()
