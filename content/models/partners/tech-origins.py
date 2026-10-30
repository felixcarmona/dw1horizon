#!/usr/bin/env python3
"""Effect origins for the techniques a partner borrows from another Digimon.

Each technique's EFE chunk lists the types that may use it with the bone and the offset
(in that bone's frame) the effect leaves from (checkTechCompatibility). A partner of this
folder that is not listed borrows its donor's row (getModTechBoneOffset, efe.c), moved
onto its own body: a point on donor bone S at local offset o becomes a point on target
bone T = BONE_MAP[S] at

    o' = k · Wt_rest(T)^T · Wd_ref(S) · o

where W are the world rotations of the rest poses the retarget used (the retargeted
animation turns T the way S turned from those poses, so the point stays on the same side
of the body part) and k is the size ratio. Bone 0 (the entity's frame) is scaled by k.
This prints the C table rows for every donor row of the techniques in TECHS.

Usage: python3 content/models/partners/tech-origins.py warumonzaemon|myotismon|shogungekomon
"""
import os as _partner_os
import sys as _partner_sys
_partner_repo_root = _partner_os.path.abspath(_partner_os.path.join(_partner_os.path.dirname(__file__), '../../..'))
_partner_sys.path[:0] = [_partner_repo_root, _partner_os.path.join(_partner_repo_root, "tools")]
import os
import struct
import sys

from tools.models.partners import rig as partner_rig  # noqa: E402
from tools.models.partners.rig import retarget  # noqa: E402

EFE = os.path.join(partner_rig.ROOT, 'extracted/ETCHI/EFEDAT.EFE')


def tables(chunk):
    """Type tables of one EFE chunk: runs of {i16 type, i16 bone, i16 x, y, z} ending in -1."""
    d = open(EFE, 'rb').read()[chunk * 0x5000:(chunk + 1) * 0x5000]
    found = []
    for off in range(0, len(d) - 10, 2):
        recs, o = [], off
        while o + 10 <= len(d):
            t, b, x, y, z = struct.unpack_from('<5h', d, o)
            if t < 0:
                break
            if not (0 < t < 180 and 0 <= b < 34 and all(abs(v) < 3000 for v in (x, y, z))):
                recs = None
                break
            recs.append((t, b, x, y, z))
            o += 10
        if recs and o + 2 <= len(d) and struct.unpack_from('<h', d, o)[0] == -1:
            if len(set(r[0] for r in recs)) == len(recs):
                found.append((off, recs))
    # keep the longest run ending at each terminator
    best = {}
    for off, recs in found:
        e = off + 10 * len(recs)
        if e not in best or len(recs) > len(best[e][1]):
            best[e] = (off, recs)
    return [v for _, v in sorted(best.items())]


CONFIGS = {
    'warumonzaemon': dict(
        target=70, target_mmd='extracted/CHDAT/MMD2/WARU.MMD', target_rest=(0, 8),
        donor=14, donor_mmd='extracted/CHDAT/MMD0/MONZ.MMD', donor_rest=(0, 0),
        bone_map={2: 2, 4: 3, 6: 6, 8: 9, 11: 10, 13: 11}, k=410 / 330,
        techs=[10, 11, 12, 14, 40, 42, 43, 44, 45, 60]),
}


def main():
    cfg = CONFIGS[sys.argv[1]]
    tgt = partner_rig.load(cfg['target_mmd'])
    don = partner_rig.load(cfg['donor_mmd'])
    trest = partner_rig.rest(tgt, *cfg['target_rest'])
    drest = partner_rig.rest(don, *cfg['donor_rest'])
    Wt = partner_rig.world_rots(cfg['target'], trest)
    Wd = partner_rig.world_rots(cfg['donor'], drest)
    k = cfg['k']
    seen = set()
    for c in cfg['techs']:
        for off, recs in tables(c):
            for t, b, x, y, z in recs:
                if t != cfg['donor'] or (b, x, y, z) in seen:
                    continue
                seen.add((b, x, y, z))
                if b == 0:
                    nb, o = 0, [x * k, y * k, z * k]
                else:
                    nb = cfg['bone_map'].get(b)
                    if nb is None:
                        print(f'/* technique {c}: donor bone {b} has no target bone */')
                        continue
                    w = [sum(Wd[b][i][j] * v for j, v in enumerate((x, y, z))) for i in range(3)]
                    o = [k * sum(Wt[nb][j][i] * w[j] for j in range(3)) for i in range(3)]
                o = [round(v) for v in o]
                print(f'\t{{ {{ {b}, {x}, {y}, {z} }}, {{ {nb}, {o[0]}, {o[1]}, {o[2]} }} }}, /* technique {c} */')


if __name__ == '__main__':
    main()
