"""Crossing ledgers and a bounded, surface-preserving quad-split certificate.

The fractional relaxation ignores resident costs and permits fractional splits.
Its residual risk is therefore a LOWER bound, not a heuristic split selection.
It does not bound reshaping, new triangle joins, material changes or deletion.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from tools.models import mesh_round4 as R, mesh_stability as S

IDS = (405, 407, 471, 473, 477)


def fractional_floor(rows, budget):
    if budget < 0 or any(r['cost'] <= 0 or r['risk'] < 0 for r in rows):
        raise ValueError('nonnegative risk/budget and positive split costs required')
    removable = 0.
    for row in sorted(rows, key=lambda r: -r['risk']/r['cost']):
        fraction = min(1., budget/row['cost'])
        removable += row['risk']*fraction
        budget -= row['cost']*fraction
    return max(0., sum(r['risk'] for r in rows)-removable)


def split_certificate(incoming, final, sid):
    """Use the reviewed geometry edits before solving the relaxed packet budget."""
    import hashlib
    import mmd
    model = mmd.MMD.parse(incoming, len(final.bones))
    packet_before = S.packet_bytes(model)
    if sid == 405:
        # The already shipped toe inset precedes this investigation. Include
        # it in the candidate geometry, rather than using a stale bend value.
        for oi in (6, 9):
            obj = model.tmd.objects[oi]
            for vi, v in enumerate(model.tmd.obj_verts(oi)):
                if v[1] == 36:
                    model.tmd.verts[obj.vert_start+vi] = (v[0], v[1]-4, v[2], v[3])
    if sid == 407:
        model.tmd.objects[2].prims.pop(0)
    S.flatten_identical_shading(model)
    budget = 1024+packet_before-S.packet_bytes(model)
    rows = []
    for r in S.bent_quads(model):
        prim = model.tmd.objects[r['object']].prims[r['primitive']]
        cost = sum((p.olen+1)*4 for p in S.split_quad(prim))-(prim.olen+1)*4
        rows.append(dict(**r, cost=cost))
    world = final.tri_array(final.world(final.rest()))
    area = np.linalg.norm(np.cross(world[:, 1]-world[:, 0], world[:, 2]-world[:, 0]), axis=1)
    height = max(1., float(np.ptp(world[area > 1e-8, :, 1])))
    lower = fractional_floor(rows, budget)/height**2
    return dict(scope='existing-quad splits; no new joins, reshaping, shading approximation or deletion',
                incoming_sha256=hashlib.sha256(incoming).hexdigest(),
                packet_budget=budget, height=height, bent_risk_lower_bound=lower, rows=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder', type=Path, help='final atlas-stamped model folder with index.json')
    p.add_argument('sid', type=int, choices=IDS)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--incoming', type=Path, help='pre-stability MMD; write a split-budget certificate instead of a ledger')
    args = p.parse_args()
    if args.incoming:
        if args.sid not in (405, 407, 471):
            p.error('split certificate is scoped to 405, 407 and 471')
        row = split_certificate(args.incoming.read_bytes(), R.load(args.folder, args.sid), args.sid)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(row, indent=2)+'\n')
    else:
        R.PART_NAMES[args.sid] = {}
        R.scan(args.folder, args.sid, args.out)


if __name__ == '__main__':
    main()
