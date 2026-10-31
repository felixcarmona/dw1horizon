#!/usr/bin/env python3
"""King of Sukamon partner model: SCUD mesh at SCALE + Sukamon's animations at its size.

Field NPCs use disc-derived twins; this output supplies the partner only.

King of Sukamon (type 120, SCUD.MMD) and Sukamon (type 39, SCUM.MMD) have the same
skeleton contents (21 bones, the same bone -> object and parent lists; only the
DIGIMON_SKELETONS pointer differs: 0x8011cc20 vs 0x8011c348). SCUD is Sukamon built about
2.75 times larger: every bone offset of its rest pose is 2.74..3.0 times Sukamon's. Its
eye frames sit at the same texture rectangles (open at 0,32; rolled 16,0; half-closed
32,0; closed 48,0; destination 0,0), so Sukamon's texture moves work on it unchanged.

At full size the King is 800 high (radius 450), far above the biggest partners
(MasterTyrannomon 590, the scaled Cherrymon 550, the original Megadramon and Gigadramon
500). At 0.7 it still filled Jijimon's house and hid the tamer, so the mesh is scaled by
SCALE = 0.62: about 500 high, the size of the biggest original partners.

Every distinct SCUM animation (39, in 47 slots) is played tick by tick like the engine
(mmd.AnimPlayer); each bone's translation is multiplied by that bone's SCUD/SCUM rest
ratio times SCALE, the root motion by the median ratio times SCALE, and the result is
re-encoded exactly (tol 0, loops, sounds and texture moves kept) and checked by playing
it again. Rotations are untouched: the pose is Sukamon's motion at the King's size.
SCUD's own two slots (0 idle, a wave of the claw, and 0x1E, the NPC's scene animation)
are kept, scaled by SCALE, so the idle is the King's and its scripted scene still plays.

Usage (from the repository root):
  python3 content/models/partners/kingsukamon-model.py [OUT.MMD] [--pad]
default OUT: build/models/SCUD-partner.MMD
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os
import statistics
import sys

from tools.models.partners.support import ROOT, mmd, mmd_path, play, check, SlotSet, write, scale_mesh, PARTNER_SLOTS  # noqa: E402

TYPE, SRC_TYPE = 120, 39
SCALE = 0.62
OWN_SLOTS = (0x00, 0x1E)          # SCUD's own: the King's idle and its NPC scene


def norm(v):
    return sum(x * x for x in v) ** 0.5


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out_path = args[0] if args else os.path.join(ROOT, 'build/models/SCUD-partner.MMD')
    e = mmd.exe()
    mesh = mmd.MMD.load(mmd_path('SCUD'))
    anim = mmd.MMD.load(mmd_path('SCUM'))
    assert e.skeleton[TYPE] == e.skeleton[SRC_TYPE], 'SCUD and SCUM skeletons differ'
    nb = e.bone_count[TYPE]
    pa = mesh.anims.anims[mesh.anims.table[0]].pose
    pb = anim.anims.anims[anim.anims.table[0]].pose
    ratio = [None]
    for x, y in zip(pa, pb):
        ratio.append(norm(x[-3:]) / norm(y[-3:]) if norm(y[-3:]) else None)
    med = statistics.median(r for r in ratio[1:] if r)
    ratio = [r or med for r in ratio]
    ratio[0] = med
    print('bone ratios SCUD/SCUM:', ' '.join(f'{r:.2f}' for r in ratio[1:]), f'(median {med:.3f})')

    def scaled(samples, k):
        return [[v[:6] + [round(x * k[b]) for x in v[6:9]] for b, v in enumerate(s)] for s in samples]

    sset = SlotSet(len(anim.anims.table))
    done = {}
    worst = 0
    for slot, idx in enumerate(anim.anims.table):
        if idx is None or slot in OWN_SLOTS:
            continue
        if idx not in done:
            smp, ls, ev = play(anim.anims.anims[idx], nb, slot)
            target = scaled(smp, [r * SCALE for r in ratio])
            mmd.close_loop(target, ls)
            new = mmd.encode_anim(target, nb, ls, ev, tol=0)
            worst = max(worst, check(new, nb, slot, target, ls, ev))
            done[idx] = new
        sset.put(slot, done[idx])
    for slot in OWN_SLOTS:
        smp, ls, ev = play(mesh.anims.anims[mesh.anims.table[slot]], nb, slot)
        target = scaled(smp, [SCALE] * nb)
        mmd.close_loop(target, ls)
        new = mmd.encode_anim(target, nb, ls, ev, tol=0)
        worst = max(worst, check(new, nb, slot, target, ls, ev))
        sset.put(slot, new)
    assert worst == 0, f're-encoding differs by {worst}'
    missing = sset.missing(PARTNER_SLOTS + list(range(0x2E, 0x37)))
    assert not missing, f'slots without animation: {[hex(s) for s in missing]}'
    scale_mesh(mesh.tmd, SCALE)
    write(out_path, mesh.tmd, sset.sec, '--pad' in sys.argv, f'SCUD mesh x{SCALE} + SCUM animations, ')


if __name__ == '__main__':
    main()
