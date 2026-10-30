#!/usr/bin/env python3
"""Jijimon's partner model: JIJI mesh + its own idle and walk + Ogremon's motion set.

Jijimon (type 117, JIJI.MMD, 17 bones) is the File City elder. Its NPC model has an
idle, a walk and four scene animations (0x1D-0x20). This script writes JIJP.MMD, the
partner-only copy (the NPC keeps JIJI.MMD, so its scenes do not change):

  - kept: its idle (0) and its slow old man's walk (2);
  - everything else is retargeted from Ogremon (34, 18 bones: the same body plan, and a
    club in the hand that holds Jijimon's staff): bone map torso, head, both arms
    (Ogremon's club hand -> the staff hand), pelvis and both legs. The hips bounce
    0.39 times Ogremon's (Jijimon's hips are at 79, Ogremon's at 205) and the root
    motion is halved (shorter legs).
  - techniques (0x2E + i, DIGIMON_DATA[117].moves): Tremar, War Cry, Sonic Jab,
    Dynamite Kick, Megaton Punch, Buster Dive and the finisher Pummel Whack, each from
    Ogremon's animation of that technique (Ogremon's slot 0x2E + its own index).

Usage (from the repository root):
  python3 content/models/partners/jijimon.py [OUT.MMD]
default OUT: build/models/JIJP.MMD.
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os
import sys

from tools.models.partners import boss as boss_partner  # noqa: E402

TYPE = 117
KEEP = [0, 2]
# Jijimon bone <- Ogremon bone
BONE_MAP = {
    2: (2, 1.0),                                 # body
    3: (3, 0.7),                                 # face (the head is part of the body piece)
    4: (5, 0.8), 5: (6, 0.8), 6: (7, 0.8),       # free arm (rests behind the back)
    7: (8, 1.0), 8: (9, 1.0), 9: (10, 1.0),      # staff arm, staff <- club
    10: (11, 1.0),                               # pelvis
    11: (12, 1.0), 12: (13, 1.0), 13: (14, 1.0),
    14: (15, 1.0), 15: (16, 1.0), 16: (17, 1.0),
}
HIPS = (1, 1, 0.39)
ROOT = 0.5
# Jijimon technique slot <- Ogremon slot (Ogremon's moves: 0x2E + index in its list)
TECHS = {
    0x2E: 0x35,   # Tremar
    0x2F: 0x36,   # War Cry
    0x30: 0x31,   # Sonic Jab
    0x31: 0x32,   # Dynamite Kick
    0x32: 0x33,   # Megaton Punch
    0x33: 0x34,   # Buster Dive
    0x34: 0x39,   # Pummel Whack (finisher)
}
TOL = 1
STEP = 2


def build(out_path):
    mesh = boss_partner.load('JIJI')
    src = boss_partner.load('OGRE')
    trest = boss_partner.rest(mesh)
    b = boss_partner.Builder(mesh, 0x35)
    for s in KEEP:
        smp, loop, ev = boss_partner.play(mesh, s)
        b.put(s, smp, loop, ev, tol=0)
    slots = [s for s in boss_partner.PARTNER_SLOTS if s not in KEEP]
    jobs = [(s, s) for s in slots] + sorted(TECHS.items())
    done = {}
    for tgt, sslot in jobs:
        if sslot in done:                       # Ogremon shares it: share it too
            b.share(tgt, done[sslot])
            continue
        smp, loop, ev = boss_partner.retarget_slot(src, sslot, TYPE, trest, BONE_MAP, hips=HIPS, root_scale=ROOT)
        boss_partner.ground_clamp(mesh, smp, allow=4, ref=trest)
        b.put(tgt, boss_partner.key_every(smp, loop, STEP), loop, ev, tol=TOL)
        done[sslot] = tgt
    return b.write(out_path, boss_partner.PARTNER_SLOTS + sorted(TECHS),
                   'JIJI mesh, own idle and walk + Ogremon-retargeted animations')


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(boss_partner.ROOT, 'build/models/JIJP.MMD')
    build(out)


if __name__ == '__main__':
    main()
