#!/usr/bin/env python3
"""Icemon partner model: ICEM mesh + a full partner animation set (see golem.py).

Slots:
  - Icemon's own (idle, walk, run, the battle set and its techniques Megaton Punch,
    Giga Freeze, Ice Needle at 0x2E-0x30) and Gotsumon's Tremar and Buster Dive
    (same rig and rest pose) as they are;
  - SnowAgumon's Ice Statue and Winter Blast, and its Muscle Charge (Agumon's rig);
  - the everyday partner slots (moods, eating, sleep, poop, conditions, scripted
    reactions) from Agumon; the tired walk is its own walk 1.5 times slower with
    half-shut eyes (Agumon's crawls on all fours), the training run its own run;
  - the finisher Subzero Ice Punch from Frigimon's own (a 19-bone skeleton: arm
    and leg chains mapped onto Icemon's).
Technique order (DIGIMON_DATA[94].moves, slot 0x2E + index): Megaton Punch, Giga
Freeze, Ice Needle, Tremar, Buster Dive, Ice Statue, Winter Blast, Muscle Charge,
Subzero Ice Punch.

Usage (from the repository root):
  python3 content/models/partners/icemon-model.py [OUT.MMD] [--pad]
default OUT: build/models/ICEM-partner.MMD
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os
import sys

from tools.models.partners.support import ROOT, write  # noqa: E402
from tools.models.partners.golem import Builder  # noqa: E402

TYPE = 94
AGU = ('AGUM', 3)
OWN = [0, 1, 2, 4, 0x13, 0x21, 0x22, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2A, 0x2B, 0x2C]
FROM_AGUMON = [5, 7, 8, 9, 0xA, 0xB, 0xC, 0xD, 0xE, 0xF, 0x10, 0x11, 0x12, 0x15, 0x16, 0x17,
               0x18, 0x19]
HIPS_K = 1.15            # Icemon is 310 high, Agumon 250
ROOT_K = 1.15

# Frigimon (YUKI, 19 bones) -> Icemon: body, neck/head, the arm chains, the leg chains
FRIGI_MAP = {1: (1, 1.0), 2: (2, 1.0), 3: (3, 1.0),
             5: (4, 1.0), 6: (5, 1.0), 7: (6, 1.0), 8: (7, 1.0),
             9: (8, 1.0), 10: (9, 1.0), 11: (10, 1.0), 12: (11, 1.0),
             13: (12, 1.0), 14: (13, 1.0), 15: (14, 1.0), 16: (15, 1.0),
             18: (16, 1.0), 19: (17, 1.0), 20: (18, 1.0)}


def build(b):
    for s in OWN:
        b.own(s)
    b.own(0x2E)                              # Megaton Punch
    b.own(0x2F)                              # Giga Freeze
    b.own(0x30)                              # Ice Needle
    b.own(0x31, 'GOTU', 0x30)                # Tremar (Gotsumon)
    b.own(0x32, 'GOTU', 0x2F)                # Buster Dive (Gotsumon)
    b.carry(0x33, 'YKAG', 71, 0x2F, hips_k=HIPS_K, root_k=ROOT_K)    # Ice Statue
    b.carry(0x34, 'YKAG', 71, 0x30, hips_k=HIPS_K, root_k=ROOT_K)    # Winter Blast
    b.carry(0x35, 'YKAG', 71, 0x32, hips_k=HIPS_K, root_k=ROOT_K)    # Muscle Charge
    b.carry(0x36, 'YUKI', 23, 0x38, hips_k=0.8, root_k=0.8, bone_map=FRIGI_MAP, tex=False)  # Subzero Ice Punch
    b.stretch(3, 2, 1.5, eye=8)              # tired walk: its own walk, slower, eyes half shut
    b.own(0x1B, from_slot=4)                 # training run: its own run
    for s in FROM_AGUMON:
        b.carry(s, *AGU, hips_k=HIPS_K, root_k=ROOT_K)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = args[0] if args else os.path.join(ROOT, 'build/models/ICEM-partner.MMD')
    b = Builder(TYPE, 'ICEM')
    build(b)
    missing = b.missing(9)
    assert not missing, [hex(s) for s in missing]
    write(out, b.mesh.tmd, b.sset.sec, '--pad' in sys.argv, 'ICEM mesh, ')


if __name__ == '__main__':
    main()
