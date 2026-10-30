#!/usr/bin/env python3
"""Analogman's partner model: ANLG mesh + his own idle and walk + Andromon's motion set.

Analogman (type 116, ANLG.MMD, 18 bones) is the human villain of the story. His NPC
model has an idle, a walk and two scene animations (0x1C, 0x1D). This script writes
ANLP.MMD, the partner-only copy (the NPC keeps ANLG.MMD, so his scenes do not change):

  - kept: his idle (0, the hunched scientist) and his walk (2);
  - everything else is retargeted from Andromon (40, 21 bones: a humanoid of the same
    height, and the Mech techniques he gets): torso, head, both arms (his briefcase
    rides in the right hand), pelvis and both legs. The hips bounce 1.1 times
    Andromon's (209 against 190).
  - techniques (0x2E + i, DIGIMON_DATA[116].moves): Static Elect, Megalo Spark, Delete
    Program, Pulse Laser, Reverse Prog, DG Dimension, Full Potential and the finisher
    Spiral Sword, each from Andromon's animation of that technique.

Usage (from the repository root):
  python3 content/models/partners/analogman.py [OUT.MMD]
default OUT: build/models/ANLP.MMD.
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os
import sys

from tools.models.partners import boss as boss_partner  # noqa: E402

TYPE = 116
KEEP = [0, 2]
# Analogman bone <- Andromon bone
BONE_MAP = {
    2: (2, 1.0), 3: (3, 1.0),                    # torso, head
    4: (5, 1.0), 5: (6, 1.0), 6: (7, 1.0),       # right arm (7, the briefcase, rides on it)
    8: (9, 1.0), 9: (10, 1.0), 10: (11, 1.0),    # left arm
    11: (12, 1.0),                               # pelvis
    12: (14, 1.0), 13: (15, 1.0), 14: (16, 1.0),
    15: (18, 1.0), 16: (19, 1.0), 17: (20, 1.0),
}
HIPS = (1, 1, 1.1)
ROOT = 1.0
# Analogman technique slot <- Andromon slot (Andromon's moves: 0x2E + index in its list)
TECHS = {
    0x2E: 0x32,   # Static Elect
    0x2F: 0x33,   # Megalo Spark
    0x30: 0x35,   # Delete Program
    0x31: 0x36,   # Pulse Laser
    0x32: 0x37,   # Reverse Prog
    0x33: 0x3A,   # DG Dimension
    0x34: 0x3B,   # Full Potential
    0x35: 0x3C,   # Spiral Sword (finisher)
}
TOL = 1
STEP = 2


def build(out_path):
    mesh = boss_partner.load('ANLG')
    src = boss_partner.load('ANDR')
    trest = boss_partner.rest(mesh)
    b = boss_partner.Builder(mesh, 0x36)
    for s in KEEP:
        smp, loop, ev = boss_partner.play(mesh, s)
        b.put(s, smp, loop, ev, tol=0)
    slots = [s for s in boss_partner.PARTNER_SLOTS if s not in KEEP]
    jobs = [(s, s) for s in slots] + sorted(TECHS.items())
    done = {}
    for tgt, sslot in jobs:
        if sslot in done:
            b.share(tgt, done[sslot])
            continue
        smp, loop, ev = boss_partner.retarget_slot(src, sslot, TYPE, trest, BONE_MAP, hips=HIPS, root_scale=ROOT)
        boss_partner.ground_clamp(mesh, smp, allow=4, ref=trest)
        b.put(tgt, boss_partner.key_every(smp, loop, STEP), loop, ev, tol=TOL)
        done[sslot] = tgt
    return b.write(out_path, boss_partner.PARTNER_SLOTS + sorted(TECHS),
                   'ANLG mesh, own idle and walk + Andromon-retargeted animations')


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(boss_partner.ROOT, 'build/models/ANLP.MMD')
    build(out)


if __name__ == '__main__':
    main()
