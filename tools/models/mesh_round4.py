"""Exhaustive crossing ledger for the five reported meshes (final atlas pairs).

Every crossing, including shallow joint contacts, is retained in CSV. Depth is
symmetric and triangles use the GPU quad diagonal. No visibility claim follows
from an intersection alone. Slots are numbered exactly as in the MMD table.
"""
import argparse
import copy
import math
import csv
import json
import itertools
from pathlib import Path
import numpy as np
from tools.models import meshcheck as MC

IDS = (409, 406, 336, 335, 461)
PART_NAMES = {
    409: {4: 'head', 14: 'tail socket', 15: 'tail fan base', 16: 'tail fan middle',
          17: 'tail fan tips', 19: 'rear thigh', 23: 'rear thigh'},
    406: {2: 'left cannon housing', 3: 'left cannon cap',
          10: 'right cannon housing', 11: 'right cannon cap'},
    336: {3: 'left forearm', 9: 'right shoulder plate', 11: 'right forearm',
          16: 'right calf', 21: 'left calf', 23: 'left shoulder plate'},
    335: {2: 'torso', 4: 'calf shell', 9: 'calf shell', 13: 'shoulder shell',
          14: 'upper arm', 23: 'shoulder shell', 24: 'upper arm', 25: 'forearm'},
    461: {2: 'head', 6: 'sword guard', 7: 'sword', 16: 'left calf', 17: 'left boot',
          18: 'left toe armour', 20: 'right calf', 21: 'right boot',
          22: 'right toe armour', 23: 'cape base', 24: 'cape tip'},
}


def part_name(sid, bone, obj):
    return PART_NAMES[int(sid)].get(bone, f'object {obj}')


def motion_name(slot):
    return {0: 'idle', 1: 'condition idle', 2: 'walk', 3: 'condition walk', 4: 'run'}.get(
        slot, 'battle' if 33 <= slot <= 63 else 'other')


def sparse_crossing(a, b):
    """Same inclusive segment/triangle rule as meshclash, with triangle AABBs."""
    lo_a, hi_a = a.min(1), a.max(1)
    lo_b, hi_b = b.min(1), b.max(1)
    ia, ib = np.nonzero(np.all(hi_a[:, None] >= lo_b, axis=2) &
                        np.all(hi_b[None] >= lo_a[:, None], axis=2))
    if not len(ia):
        return 0, 0.
    aa, bb = a[ia], b[ib]
    hit = np.zeros(len(ia), bool)
    for left, right in ((aa,bb),(bb,aa)):
        e1, e2 = right[:,1]-right[:,0], right[:,2]-right[:,0]
        for k in range(3):
            d = left[:,(k+1)%3]-left[:,k]
            h = np.cross(d,e2)
            det = (e1*h).sum(1)
            ok = np.abs(det)>1e-9
            f = 1/np.where(ok,det,1)
            ss = left[:,k]-right[:,0]
            u = f*(ss*h).sum(1)
            q = np.cross(ss,e1)
            v = f*(q*d).sum(1)
            t = f*(e2*q).sum(1)
            hit |= ok & (u>=0) & (v>=0) & (u+v<=1) & (t>=0) & (t<=1)
    if not hit.any():
        return 0, 0.
    aa, bb = aa[hit], bb[hit]
    depth = 0.
    for left,right in ((aa,bb),(bb,aa)):
        n = np.cross(right[:,1]-right[:,0],right[:,2]-right[:,0]).astype(float)
        n /= np.linalg.norm(n,axis=1)[:,None]+1e-9
        dd = np.einsum('nvi,ni->nv',left-right[:,None,0],n)
        depth = max(depth,float(np.minimum(np.maximum(dd.max(1),0),np.maximum(-dd.min(1),0)).max()))
    return int(hit.sum()),depth


def scan(folder, sid, out):
    index = json.loads((folder/'index.json').read_text())[str(sid)]
    m = MC.Model((folder/f'{sid}.MMD').read_bytes(), index['bones'], (folder/f'{sid}.TIM').read_bytes())
    indices = {b: np.array([t[3] for t in m.tris if t[0] == b], int) for b in m.local}
    indices = {b: t for b, t in indices.items() if len(t)}
    summary = dict(name=index['name'], slots={}, pairs={}, ticks=0, crossing_frames=0, max_depth=0., max_count=0)
    out.mkdir(parents=True, exist_ok=True)
    with (out/f'{sid}-frames.csv').open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['slot','motion','frame','bone_a','object_a','part_a','bone_b','object_b','part_b',
                         'adjacent','triangle_pairs','depth_units'])
        for slot in m.slots():
            poses = m.poses(slot, 6000)
            if len(poses) >= 6000:
                raise ValueError(f'{sid} slot {slot}: decode guard')
            motion = motion_name(slot)
            rows = dict(ticks=len(poses), crossing_frames=0, max_depth=0., pairs={})
            for tick, pose in enumerate(poses):
                world = m.world(pose)
                tri = {b: world[b][t] for b,t in indices.items()}
                box = {b:(t.min((0,1)),t.max((0,1))) for b,t in tri.items()}
                count = 0
                for a in tri:
                    for b in tri:
                        if b <= a or (box[a][0] > box[b][1]).any() or (box[b][0] > box[a][1]).any():
                            continue
                        c, d = sparse_crossing(tri[a],tri[b])
                        if not c:
                            continue
                        count += c
                        adjacent = m.bones[a][1] == b or m.bones[b][1] == a
                        writer.writerow([slot,motion,tick,a,m.bones[a][0],part_name(sid,a,m.bones[a][0]),
                                         b,m.bones[b][0],part_name(sid,b,m.bones[b][0]),int(adjacent),c,round(d,6)])
                        key = f'{a}/{b}'
                        entry = dict(bones=[a,b], objects=[m.bones[a][0],m.bones[b][0]], adjacent=adjacent,
                                     count=c,depth=d,slot=slot,tick=tick)
                        for dest in (summary['pairs'],rows['pairs']):
                            if key not in dest or d > dest[key]['depth']:
                                dest[key] = entry
                        rows['max_depth'] = max(rows['max_depth'],d)
                rows['crossing_frames'] += int(count > 0)
                summary['max_count'] = max(summary['max_count'],count)
            summary['slots'][str(slot)] = rows
            summary['ticks'] += len(poses)
            summary['crossing_frames'] += rows['crossing_frames']
            summary['max_depth'] = max(summary['max_depth'],rows['max_depth'])
            print(sid,slot,len(poses),round(rows['max_depth'],3),flush=True)
    summary['complete'] = True
    (out/f'{sid}.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def _det(a, b, c):
    return np.einsum('...i,...i->...', a, np.cross(b, c))


def translation_constraints(aa, bb):
    """Affine orientation determinants for all edge/face crossing witnesses.

    Translating either complete part keeps the edge/face tests affine. The
    opposite-direction witnesses use -delta after translating the origin.
    These constraints do not cover rotations or deformation.
    """
    allcoef = []
    for swap, (a, b) in enumerate(((aa, bb), (bb, aa))):
        for k in range(3):
            e = np.repeat(a[:, [k, (k+1)%3]], len(b), axis=0)
            t = np.tile(b, (len(a), 1, 1))

            def values(delta):
                v = e + delta
                vals = [_det(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0], v[:, j]-t[:, 0]) for j in range(2)]
                vals += [_det(v[:, 1]-v[:, 0], t[:, j]-v[:, 0], t[:, (j+1)%3]-v[:, 0]) for j in range(3)]
                return np.array(vals).T

            zero = values(np.zeros(3))
            coef = np.stack([values(np.eye(3)[j])-zero for j in range(3)], axis=-1)
            if swap:
                coef = -coef
            allcoef.append((zero, coef))
    return np.concatenate([x[0] for x in allcoef]), np.concatenate([x[1] for x in allcoef])


def translation_cover(z, c, center, half, depth=0):
    """Prove a crossing throughout a cube, or return None (inconclusive).

    Each affine determinant's extrema over the cube are its center value plus
    or minus sum(abs(coefficients))*half. Strict signs prove that an edge
    crosses a triangle's interior everywhere in the cube. Different witnesses
    can cover different subcubes. A conservative numerical margin rejects
    near-zero signs. Returning None is never evidence that a repair exists.
    """
    val = z + np.einsum('nki,i->nk', c, center)
    err = np.abs(c).sum(-1)*half
    lo, hi = val-err, val+err
    tolerance = 1e-7*max(1., float(np.abs(z).max()))
    straddles = ((lo[:, 0] > tolerance) & (hi[:, 1] < -tolerance) |
                 (hi[:, 0] < -tolerance) & (lo[:, 1] > tolerance))
    interior = (np.all(lo[:, 2:] > tolerance, axis=1) |
                np.all(hi[:, 2:] < -tolerance, axis=1))
    ok = straddles & interior
    if ok.any():
        return dict(center=center.tolist(), half=half, witness=int(np.flatnonzero(ok)[0]))
    if depth >= 6:
        return None
    children = []
    for sign in itertools.product((-1, 1), repeat=3):
        child = translation_cover(z, c, center+np.array(sign)*half/2, half/2, depth+1)
        if child is None:
            return None
        children.append(child)
    return dict(center=center.tolist(), half=half, children=children)


def load(folder, sid):
    row = json.loads((folder/'index.json').read_text())[str(sid)]
    return MC.Model((folder/f'{sid}.MMD').read_bytes(), row['bones'], (folder/f'{sid}.TIM').read_bytes())


def verify_cover(aa, bb, tree, limit):
    """Check every leaf at its eight corners using direct determinants.

    This verifies the recorded witness and octant partition independently of
    the affine coefficient calculation used to construct the certificate.
    """
    size = len(aa)*len(bb)

    def check(node, center, half):
        if node['center'] != center.tolist() or node['half'] != half:
            return False
        if 'children' in node:
            return len(node['children']) == 8 and all(
                check(child, center+np.array(sign)*half/2, half/2)
                for sign, child in zip(itertools.product((-1, 1), repeat=3), node['children']))
        witness = node['witness']
        if not 0 <= witness < 6*size:
            return False
        swap, rest = divmod(witness, 3*size)
        edge, rest = divmod(rest, size)
        left, right = (bb, aa) if swap else (aa, bb)
        i, j = divmod(rest, len(right))
        tri = right[j]
        values = []
        for sign in itertools.product((-1, 1), repeat=3):
            delta = (center+np.array(sign)*half)*(-1 if swap else 1)
            e = left[i, [edge, (edge+1)%3]]+delta
            v = [_det(tri[1]-tri[0], tri[2]-tri[0], p-tri[0]) for p in e]
            v += [_det(e[1]-e[0], tri[k]-e[0], tri[(k+1)%3]-e[0]) for k in range(3)]
            values.append(v)
        values = np.array(values)
        tolerance = 1e-7*max(1., float(np.abs(values).max()))
        lo, hi = values.min(0), values.max(0)
        return bool(((lo[0] > tolerance and hi[1] < -tolerance) or
                     (hi[0] < -tolerance and lo[1] > tolerance)) and
                    (np.all(lo[2:] > tolerance) or np.all(hi[2:] < -tolerance)))

    return tree is not None and check(tree, np.zeros(3), limit)


def pair_at(model, pair, slot, tick):
    world = model.world(model.poses(slot, 6000)[tick])
    return [np.array([world[b][list(t[3])] for t in model.tris if t[0] == b]) for b in pair]


def certificate(model, pair, slot, tick, limit=16.):
    aa, bb = pair_at(model, pair, slot, tick)
    z, c = translation_constraints(aa, bb)
    tree = translation_cover(z, c, np.zeros(3), limit)
    if tree is not None and not verify_cover(aa, bb, tree, limit):
        raise ValueError('translation certificate failed independent corner verification')
    return dict(bones=pair, slot=slot, tick=tick, relative_translation_limit=limit,
                proven=tree is not None, triangles_a=aa.tolist(), triangles_b=bb.tolist(), cover=tree)


def pose_trials(model, pair, slot, tick):
    """Finite local pose trials; these are not a continuous rotation proof."""
    a, b = pair
    pose = model.poses(slot, 6000)[tick]
    ts = {v: np.array([t[3] for t in model.tris if t[0] == v], int) for v in pair}
    rows = []
    for bone in pair:
        for degrees in itertools.product((-10, -5, 0, 5, 10), repeat=3):
            trial = copy.deepcopy(pose)
            for k, angle in enumerate(degrees):
                trial[bone][3+k] += round(angle*4096/360)
            world = model.world(trial)
            count, depth = sparse_crossing(world[a][ts[a]], world[b][ts[b]])
            rows.append(dict(bone=bone, degrees=degrees, count=count, depth=depth))
    rows.sort(key=lambda r: (r['count'] > 0, r['depth'], r['count']))
    return dict(bones=pair, slot=slot, tick=tick, tested=len(rows),
                clear=sum(r['count'] == 0 for r in rows), rows=rows)


def render_evidence(before, after, cases, out):
    """Matched OT/GPU-diagonal renders; bin-phase sensitivity is not a defect count."""
    from tools.models import psx_blend
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for slot, tick in dict.fromkeys(map(tuple, cases)):
        poses = [m.poses(slot, 6000)[tick] for m in (before, after)]
        sheets = []
        for view in range(8):
            yaw = view*math.pi/4
            a, frame = psx_blend.render(before, yaw, math.pi/6, size=192, pose=poses[0])
            b, _ = psx_blend.render(after, yaw, math.pi/6, size=192, pose=poses[1], frame=frame)
            phase = [psx_blend.render(m, yaw, math.pi/6, size=192, pose=p, frame=frame, depth_offset=2)[0]
                     for m, p in zip((before, after), poses)]
            rows.append(dict(slot=slot, tick=tick, view=view,
                             changed_pixels=int(np.any(a != b, axis=2).sum()),
                             before_bin_phase_pixels=int(np.any(a != phase[0], axis=2).sum()),
                             after_bin_phase_pixels=int(np.any(b != phase[1], axis=2).sum())))
            sheets.append(np.concatenate([a, b], axis=1))
        MC.png(str(out/f'{slot}-{tick}.png'), np.concatenate(sheets, axis=0))
    result = dict(rows=rows)
    for key in ('changed_pixels', 'before_bin_phase_pixels', 'after_bin_phase_pixels'):
        result[key] = sum(r[key] for r in rows)
    (out/'metrics.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder', type=Path)
    p.add_argument('sid', type=int, choices=IDS)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--after', type=Path, help='render matched before/after models')
    p.add_argument('--cases', type=Path, help='JSON list of [slot, tick] render cases')
    p.add_argument('--detector', type=Path, help='write the existing sampled detector report using these thresholds')
    p.add_argument('--certificate', nargs=4, type=int, metavar=('BONE_A', 'BONE_B', 'SLOT', 'TICK'))
    p.add_argument('--translation-limit', type=float, default=16.)
    p.add_argument('--trials', action='store_true', help='also test 250 local pose adjustments at the certificate frame')
    a = p.parse_args()
    if a.after:
        if not a.cases:
            p.error('--after requires --cases')
        render_evidence(load(a.folder, a.sid), load(a.after, a.sid), json.loads(a.cases.read_text()), a.out)
    elif a.detector:
        from tools.models import mesh_glitch
        thresholds = json.loads(a.detector.read_text())['thresholds']
        model = load(a.folder, a.sid)
        result = mesh_glitch.measure(model, samples=3)
        result.update(mesh_glitch.classify(result, thresholds))
        result['surface_pairs'] = mesh_glitch.coplanar_details(model)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=2)+'\n')
    elif a.certificate:
        if not math.isfinite(a.translation_limit) or a.translation_limit <= 0:
            p.error('--translation-limit must be finite and positive')
        model = load(a.folder, a.sid)
        pair, slot, tick = a.certificate[:2], a.certificate[2], a.certificate[3]
        result = certificate(model, pair, slot, tick, a.translation_limit)
        if a.trials:
            result['pose_trials'] = pose_trials(model, pair, slot, tick)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=2)+'\n')
        print(a.sid, 'translation floor proven:', result['proven'])
    else:
        if a.trials:
            p.error('--trials requires --certificate')
        scan(a.folder, a.sid, a.out)


if __name__ == '__main__':
    main()
