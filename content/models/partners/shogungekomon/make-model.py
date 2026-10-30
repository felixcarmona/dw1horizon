#!/usr/bin/env python3
"""ShogunGekomon partner model: TONO mesh at SCALE + a full partner animation set.

ShogunGekomon (type 119, TONO.MMD) is the Gekomon Swamp NPC: 28 bones on a skeleton no
other model uses and 8 animation slots (0 idle; 5, 6, 7, 0xB, 0x1D-0x1F for its
scripts). This builds the partner model:

  - mesh and bone offsets scaled by SCALE (981 high and 1060 wide with the legs: at
    0.55 it is about 540 high, a bit under Cherrymon);
  - the eight NPC slots replayed tick by tick and re-encoded with their translations
    scaled, so the Volume Villa scenes still work; 5 (laugh), 7 (fidget) and 0xB (fan
    wave) are also its happy, unhappy and joy, and 0x1F (the big fan dance) is its victory;
  - every other partner slot and its nine techniques authored in anims.py.

Usage (from the repository root):
  python3 content/models/partners/shogungekomon/make-model.py [OUT.MMD] [--pad]
default OUT: build/models/TONO-partner.MMD.
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tools.models.partners import rig as partner_rig  # noqa: E402
import anims  # noqa: E402

TYPE = 119
SCALE = 0.55
NPC_SLOTS = (0, 5, 6, 7, 0xB, 0x1D, 0x1E, 0x1F)
TECH_SLOTS = list(range(0x2E, 0x37))
TOL = int(os.environ.get('TONO_TOL', '2'))


def build(out_path, pad=False):
    tono = partner_rig.load('extracted/CHDAT/MMD3/TONO.MMD')
    nb = partner_rig.nbones(TYPE)
    b = partner_rig.Builder(tono)
    for s in NPC_SLOTS:
        smp, loop, ev = partner_rig.play(tono, s)
        b.put(s, partner_rig.encode(partner_rig.scale_samples(smp, SCALE), nb, loop, ev, tol=1))
    b.alias(0x2A, 0x1F)                 # victory: the fan dance
    rest = partner_rig.scale_samples([partner_rig.rest(tono)], SCALE)[0]
    for slot, clip in sorted(anims.build_all().items()):
        smp, loop, ev = anims.build_samples(clip, rest)
        b.put(slot, partner_rig.encode(smp, nb, loop, ev, tol=TOL))
    miss = b.missing(partner_rig.PARTNER_SLOTS + TECH_SLOTS)
    assert not miss, miss
    partner_rig.scale_mesh(tono, SCALE)
    return b.build(tono.tmd, out_path, pad, f'TONO x{SCALE} + authored partner set, ')


if __name__ == '__main__':
    out, pad = partner_rig.args()
    build(out or os.path.join(partner_rig.ROOT, 'build/models/TONO-partner.MMD'), pad)
