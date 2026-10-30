#!/usr/bin/env python3
"""Myotismon partner model: VAND.MMD plus the partner slots it lacks.

Myotismon (type 66, VAND.MMD, 25 bones) is a wild/boss Digimon: it has idle, walk, run,
the battle set and its five techniques, but none of the care and mood slots. Devimon
(DEVI.MMD, 28 bones), the Champion it evolves from, has the same body plan (pelvis and
torso, head, two four-piece arms, two three-piece legs, wings where Myotismon has its
cape), so its partner animations are carried over with tools/retarget.py:

  VAND 2 torso <- DEVI 2        VAND 3 head <- DEVI 4
  VAND 10-13 arm (+x) <- DEVI 6-9     VAND 14-17 arm (-x) <- DEVI 11-14
  VAND 18 pelvis <- DEVI 19     VAND 19-21 / 22-24 legs <- DEVI 21-23 / 25-27
  VAND 8 cape <- DEVI 16 (a wing) at 0.3, so the cape sways with the wing beats
  hips: Devimon's offsets; root motion 1.1 times (Myotismon is 430 high, Devimon 400).

Devimon's eye and mouth texture moves become Myotismon's own frames (VAND's texture has
its eyes at x 46 open / 40 half / 34 closed and its mouth at x 38 closed / 28 open).

Techniques: VAND's five stay at 0x2E-0x32; the ten Devimon techniques it adds
(0x33-0x3C, Death Claw the finisher) are Devimon's animations of them, retargeted.

Usage (from the repository root):
  python3 content/models/partners/myotismon/make-model.py [OUT.MMD] [--pad]
default OUT: build/models/VAND-partner.MMD.
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os

from tools.models.partners import rig as partner_rig  # noqa: E402

TYPE = 66
KEEP = [0, 1, 2, 4, 0x13, 0x21, 0x22, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2A, 0x2B, 0x2C,
        0x2E, 0x2F, 0x30, 0x31, 0x32]
FROM_DEVI = {s: s for s in [5, 7, 8, 9, 0xA, 0xB, 0xC, 0xD, 0xE, 0xF, 0x10, 0x11, 0x12,
                            0x15, 0x16, 0x17, 0x18, 0x19]}
# techniques after its own five (VAND 0x2E-0x32: Megaton Punch, Thunder Justice, Hurricane,
# Giga Freeze, Aurora Freeze, kept in place because the boss fights equip them by slot):
# EXTRA (Devimon's slot -> its technique) taken from Devimon's list, then Death Claw,
# Devimon's finisher; each with Devimon's animation of it
EXTRA = [int(x, 0) for x in os.environ.get('VAND_EXTRA', '0x2E').split(',') if x]
for i, s in enumerate(EXTRA + [0x3A]):
    FROM_DEVI[0x33 + i] = s
TECH_SLOTS = list(range(0x2E, 0x34 + len(EXTRA)))
BONE_MAP = {2: (2, 1.0), 3: (4, 1.0),
            10: (6, 1.0), 11: (7, 1.0), 12: (8, 1.0), 13: (9, 1.0),
            14: (11, 1.0), 15: (12, 1.0), 16: (13, 1.0), 17: (14, 1.0),
            18: (19, 1.0), 19: (21, 1.0), 20: (22, 1.0), 21: (23, 1.0),
            22: (25, 1.0), 23: (26, 1.0), 24: (27, 1.0),
            8: (16, 0.3)}
if os.environ.get('VAND_NOCAPE'):
    del BONE_MAP[8]
REST_TICK = int(os.environ.get('VAND_REST_TICK', '0'))
HIPS = (1, 1, 1.0)
ROOT_SCALE = 1.1
SLEEPY = (9, 0x11)
TOL = int(os.environ.get('VAND_TOL', '2'))
STEP = int(os.environ.get('VAND_STEP', '2'))
KEEP_TOL = 1     # its own animations re-encoded within 1 unit (smaller than the originals)

EYES = {'open': 46, 'half': 40, 'closed': 34}
MOUTH = {'closed': 38, 'open': 28}


def eyes(state):
    x = EYES[state]
    return [dict(src=(x, 112), size=(6, 16), dst=(2, 72)), dict(src=(x, 112), size=(6, 16), dst=(10, 72))]


def mouth(state):
    return [dict(src=(MOUTH[state], 88), size=(10, 24), dst=(0, 96))]


def tex_for(slot):
    def tex(c):
        sx, sy = c['src']
        if c['dst'] == (0, 56):            # Devimon's eyes
            if sy == 112:
                return eyes('open')
            return eyes('closed' if slot in SLEEPY else 'half')
        if c['dst'] == (2, 72):            # Devimon's mouth
            return mouth('closed' if sx == 60 else 'open')
        return []
    return tex


def build(out_path, pad=False):
    vand = partner_rig.load('extracted/CHDAT/MMD2/VAND.MMD')
    devi = partner_rig.load('extracted/CHDAT/MMD0/DEVI.MMD')
    nb = partner_rig.nbones(TYPE)
    trest = partner_rig.rest(vand, 0, REST_TICK)
    b = partner_rig.Builder(vand)
    b.keep(*KEEP, tol=KEEP_TOL)
    for tslot, sslot in sorted(FROM_DEVI.items()):
        smp, loop, ev = partner_rig.retarget_samples(devi, sslot, TYPE, trest, BONE_MAP, HIPS, ROOT_SCALE)
        ev = partner_rig.map_events(ev, tex=tex_for(tslot))
        b.put(tslot, partner_rig.encode(smp, nb, loop, ev, tol=TOL, step=STEP))
    # tired walk (3): its own walk at 0.7 speed, stooped (Devimon's, carried over, bent
    # the cape-heavy body much further than Devimon's own stoop)
    smp, loop, ev = partner_rig.play(vand, 2)
    slow = partner_rig.resample(smp, 0.7)
    k = (len(slow) - 1) / (len(smp) - 1)
    tired = partner_rig.layered_cycle(TYPE, slow, rot=lambda i: {2: (10, 0, 0), 3: (12, 0, 0),
                                                             10: (-8, 0, 0), 14: (-8, 0, 0)})
    ev = [(min(len(slow) - 2, round(t * k)), kind, dict(c)) for t, kind, c in ev]
    ev = [e for e in ev if e[1] != 'tex'] + [(0, 'tex', d) for d in eyes('half') + mouth('closed')]
    b.put(3, partner_rig.encode(tired, nb, 0, ev, tol=TOL))
    # training run (0x1B): its own run
    b.alias(0x1B, 4)
    miss = b.missing(partner_rig.PARTNER_SLOTS + TECH_SLOTS)
    assert not miss, miss
    return b.build(vand.tmd, out_path, pad, 'VAND + Devimon care slots and techniques, ')


if __name__ == '__main__':
    out, pad = partner_rig.args()
    build(out or os.path.join(partner_rig.ROOT, 'build/models/VAND-partner.MMD'), pad)
