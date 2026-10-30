#!/usr/bin/env python3
"""WaruMonzaemon partner model: WARU.MMD plus the partner slots it lacks.

WaruMonzaemon (type 70, WARU.MMD, 12 bones) is a wild/boss Digimon: it has idle, walk,
run, the battle set and its four techniques, but none of the care and mood slots a
partner plays. Monzaemon (MONZ.MMD, 14 bones) has the same body plan (body, head, two
arms, two legs), so its partner animations are carried over with tools/retarget.py:

  WARU 2 body <- MONZ 2      WARU 3 head <- MONZ 4
  WARU 6 claw arm (+x) <- MONZ 6 (the forearm and claw keep their pose under it)
  WARU 9 arm (-x) <- MONZ 8   WARU 10/11 legs <- MONZ 11/13
  hips: 1.4 times Monzaemon's offsets; root motion 1.33 times (WARU's walk covers 400
  units in 21 ticks, Monzaemon's 300).

Techniques: WARU's own four stay at 0x2E-0x31; the ten Monzaemon techniques it adds
(0x32-0x3B, Lovely Attack the finisher) are Monzaemon's animations of them, retargeted
the same way. Footsteps (1, 11) become WARU's (1, 12).

Usage (from the repository root):
  python3 content/models/partners/warumonzaemon/make-model.py [OUT.MMD] [--pad]
default OUT: build/models/WARU-partner.MMD.
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os

from tools.models.partners import rig as partner_rig  # noqa: E402

TYPE = 70
KEEP = [0, 1, 2, 4, 0x13, 0x21, 0x22, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2E, 0x2F, 0x30, 0x31]
FROM_MONZ = {s: s for s in [3, 5, 7, 8, 9, 0xA, 0xB, 0xC, 0xD, 0xE, 0xF, 0x10, 0x11, 0x12,
                            0x15, 0x16, 0x17, 0x18, 0x19, 0x1B]}
# techniques after its own four (WARU 0x2E-0x31: Megaton Punch, Buster Dive, Muscle Charge,
# Thunder Justice, kept in place because the boss fights equip them by slot): the rest of
# Monzaemon's list, with Monzaemon's animations of them
FROM_MONZ.update({0x32: 0x2E,   # Sonic Jab
                  0x33: 0x2F,   # Dynamite Kick
                  0x34: 0x31,   # Counter
                  0x35: 0x33,   # Tremar
                  0x36: 0x34,   # War Cry
                  0x37: 0x36,   # Static Elect
                  0x38: 0x37,   # Megalo Spark
                  0x39: 0x38,   # Electric Cloud
                  0x3A: 0x3A,   # Confused Storm
                  0x3B: 0x3B})  # Lovely Attack (finisher)
TECH_SLOTS = list(range(0x2E, 0x3C))
BONE_MAP = {2: (2, 1.0), 3: (4, 1.0), 6: (6, 1.0), 9: (8, 1.0), 10: (11, 1.0), 11: (13, 1.0)}
REST_TICK = 8    # idle tick 8: facing forward, claw arm hanging (tick 0 has it folded at the chest)
HIPS = (1, 1, 1.4)
ROOT_SCALE = 400 / 300


def sound(bank, note):
    if (bank, note) == (1, 11):
        return (1, 12)
    return (bank, note)


def build(out_path, pad=False):
    waru = partner_rig.load('extracted/CHDAT/MMD2/WARU.MMD')
    monz = partner_rig.load('extracted/CHDAT/MMD0/MONZ.MMD')
    nb = partner_rig.nbones(TYPE)
    trest = partner_rig.rest(waru, 0, REST_TICK)
    b = partner_rig.Builder(waru)
    b.keep(*KEEP)
    for tslot, sslot in sorted(FROM_MONZ.items()):
        smp, loop, ev = partner_rig.retarget_samples(monz, sslot, TYPE, trest, BONE_MAP, HIPS, ROOT_SCALE)
        b.put(tslot, partner_rig.encode(smp, nb, loop, partner_rig.map_events(ev, sound), tol=1))
    miss = b.missing(partner_rig.PARTNER_SLOTS + TECH_SLOTS)
    assert not miss, miss
    return b.build(waru.tmd, out_path, pad, 'WARU + Monzaemon care slots, ')


if __name__ == '__main__':
    out, pad = partner_rig.args()
    build(out or os.path.join(partner_rig.ROOT, 'build/models/WARU-partner.MMD'), pad)
