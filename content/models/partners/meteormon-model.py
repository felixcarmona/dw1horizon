#!/usr/bin/env python3
"""Meteormon partner model: INSE mesh + a full partner animation set (see golem.py).

Meteormon is the Icemon/Gotsumon model in other colours; the engine draws type 113
1.5 times larger (model.c, initializeDigimonObject; battle_main.c and std_main.c
restore that scale after a flattening), so the mesh is kept as it is.

Slots:
  - Meteormon's own (idle, walk, run, the battle set, its NPC scene slots 0x1C-0x1E
    and its techniques Magma Bomb, Meltdown, Megaton Punch, Tremar at 0x2E-0x31) and
    Gotsumon's Buster Dive, as they are;
  - Meramon's Spit Fire, Heat Laser, Red Inferno, Prominence Beam and its finisher
    Fireball (Meramon has the same bone hierarchy: hips, body, head, 3-piece arms and
    legs);
  - the everyday partner slots from Agumon (as for Icemon); the tired walk is its own
    walk 1.5 times slower with half-shut eyes, the training run its own run.
Technique order (DIGIMON_DATA[113].moves, slot 0x2E + index): Magma Bomb, Meltdown,
Megaton Punch, Tremar, Buster Dive, Spit Fire, Heat Laser, Red Inferno, Prominence
Beam, Fireball.

Usage (from the repository root):
  python3 content/models/partners/meteormon-model.py [OUT.MMD] [--pad]
default OUT: build/models/INSE-partner.MMD
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os
import sys

from tools.models.partners.support import ROOT, write  # noqa: E402
from tools.models.partners.golem import Builder  # noqa: E402

TYPE = 113
AGU = ('AGUM', 3)
MERA = ('MERA', 9)
OWN = [0, 1, 2, 4, 0x13, 0x1C, 0x1D, 0x1E, 0x21, 0x22, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2A, 0x2B, 0x2C,
       0x2E, 0x2F, 0x30, 0x31]
FROM_AGUMON = [5, 7, 8, 9, 0xA, 0xB, 0xC, 0xD, 0xE, 0xF, 0x10, 0x11, 0x12, 0x15, 0x16, 0x17,
               0x18, 0x19]
AGU_K = 1.07              # the mesh is about 267 high before the engine's 1.5; Agumon 250
MERA_K = 0.67             # Meramon 400
# the NPC scene slots and ten techniques leave less room than Icemon has: the everyday
# slots are encoded within TOL units (an angle error of TOL/4096 of a turn at most)
TOL = 4


def build(b):
    for s in OWN:
        b.own(s)
    b.own(0x32, 'GOTU', 0x2F)                                   # Buster Dive (Gotsumon)
    for slot, src in ((0x33, 0x2E), (0x34, 0x32), (0x35, 0x33), (0x36, 0x31), (0x37, 0x38)):
        # Spit Fire, Heat Laser, Red Inferno, Prominence Beam, Fireball (Meramon's)
        b.carry(slot, *MERA, src, hips_k=MERA_K, root_k=MERA_K, tex=False)
    b.stretch(3, 2, 1.5, eye=8)
    b.own(0x1B, from_slot=4)
    for s in FROM_AGUMON:
        b.carry(s, *AGU, hips_k=AGU_K, root_k=AGU_K, tol=TOL)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = args[0] if args else os.path.join(ROOT, 'build/models/INSE-partner.MMD')
    b = Builder(TYPE, 'INSE')
    build(b)
    missing = b.missing(10)
    assert not missing, [hex(s) for s in missing]
    write(out, b.mesh.tmd, b.sset.sec, '--pad' in sys.argv, 'INSE mesh, ')


if __name__ == '__main__':
    main()
