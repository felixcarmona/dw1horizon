"""Geometry and ordering-table diagnostics used by battle_qa mesh-audit.

The depth diagnostic is an orthographic camera probe, not an emulator: eight
azimuths at 30 degrees elevation, libgs first-triangle culling, mean primitive
depth quantised by >>2. A tie or a change of order is a candidate, not proof of
a visible defect. Intersections and coplanarity are measured independently.
"""
import json
from pathlib import Path

import numpy as np

from tools.models import meshcheck as MC


def overlap_pairs(T, primitive, bones, ids):
    """Strict positive projected overlap, excluding a primitive's own halves
    and faces sharing a mesh vertex. SAT rejects bounding-box false positives."""
    lo, hi = T.min(1), T.max(1)
    good = (lo[:, None] < hi[None]).all(2) & (hi[:, None] > lo[None]).all(2)
    good &= np.triu(np.ones(good.shape, bool), 1)
    a, b = np.nonzero(good)
    keep = primitive[a] != primitive[b]
    shared = (ids[a, :, None] == ids[b, None, :]).any((1, 2)) & (bones[a] == bones[b])
    a, b = a[keep & ~shared], b[keep & ~shared]
    for source in (0, 1):
        p, q = (T[a], T[b]) if source == 0 else (T[b], T[a])
        for k in range(3):
            e = p[:, (k + 1) % 3] - p[:, k]
            axis = np.stack([-e[:, 1], e[:, 0]], -1)
            pp = np.einsum('nvi,ni->nv', p, axis)
            pq = np.einsum('nvi,ni->nv', q, axis)
            keep = (pp.min(1) < pq.max(1) - 1e-8) & (pq.min(1) < pp.max(1) - 1e-8)
            a, b, p, q = a[keep], b[keep], p[keep], q[keep]
    return a, b


def depth_probe(model, poses):
    """Counts distinct overlapping primitive pairs, ties and successive order
    reversals. Only pairs overlapping and front-facing in BOTH ticks can flip."""
    keys = [(t[0], t[1], t[2]) for t in model.tris]
    lookup = {key: i for i, key in enumerate(dict.fromkeys(keys))}
    prim = np.array([lookup[k] for k in keys])
    first = np.array([keys.index(k) for k in lookup])
    bones = np.array([t[0] for t in model.tris])
    welded = {}
    for bone, vertices in model.local.items():
        lookup_positions = {}
        welded[bone] = []
        for vertex in vertices:
            key = tuple(vertex)
            lookup_positions.setdefault(key, len(lookup_positions))
            welded[bone].append(lookup_positions[key])
    ids = np.array([[welded[t[0]][i] for i in t[3]] for t in model.tris])
    totals = dict(overlaps=0, ties=0, flips=0, comparisons=0, tied_flips=0)
    if not len(prim):
        return totals
    # Transform each sampled pose once; the eight cameras reuse those triangles.
    # A quad center uses four distinct corners, not its doubled diagonal.
    quad = np.array([len(model.m.tmd.objects[k[1]].prims[k[2]].decode()['verts']) == 4 for k in lookup])
    world = [model.tri_array(model.world(pose)) for pose in poses]
    for yaw in np.arange(8) * np.pi / 4:
        previous = None
        for triangles in world:
            T = MC._rotate(triangles, yaw, np.pi / 6)
            P = T[:, :, :2]
            edge = P[:, 1] - P[:, 0]; other = P[:, 2] - P[:, 0]
            face = (edge[:, 0] * other[:, 1] - edge[:, 1] * other[:, 0] > 1e-8)[first][prim]
            use = np.nonzero(face)[0]
            a, b = overlap_pairs(P[use], prim[use], bones[use], ids[use])
            pa, pb = prim[use[a]], prim[use[b]]
            count = len(lookup)
            pair_ids = np.unique(np.minimum(pa, pb)*count + np.maximum(pa, pb))
            aa, bb = pair_ids // count, pair_ids % count
            centers = T[first].mean(1)
            centers[quad] = (T[first[quad]].sum(1) + T[first[quad]+1, 1]) / 4
            Z = centers[:, 2]
            delta = Z[aa] - Z[bb]
            tied = np.mean(np.floor((Z[aa, None] + np.arange(4)) / 4) ==
                           np.floor((Z[bb, None] + np.arange(4)) / 4), axis=1)
            totals['overlaps'] += len(pair_ids)
            totals['ties'] += float(tied.sum())
            if previous is not None:
                old_ids, old_delta, old_tied = previous
                _, old, cur = np.intersect1d(old_ids, pair_ids, assume_unique=True, return_indices=True)
                flips = delta[cur]*old_delta[old] < 0
                totals['comparisons'] += len(cur)
                totals['flips'] += int(flips.sum())
                totals['tied_flips'] += float(np.maximum(tied[cur], old_tied[old])[flips].sum())
            previous = pair_ids, delta, tied
    return totals


def coplanar_details(model):
    """Locate co-facing surfaces even when they share vertex IDs or UVs.

    Legacy zfight() excludes both cases, including accidentally duplicated
    packets. Opposite-facing cards cannot compete after libgs culling and are
    listed separately; these diagnostics do not change the native envelope.
    """
    T = model.tri_array(model.world(model.rest()))
    n = np.cross(T[:, 1]-T[:, 0], T[:, 2]-T[:, 0])
    lengths = np.linalg.norm(n, axis=1)
    n /= np.maximum(lengths[:, None], 1e-12)
    drawn = T[lengths > 1e-8]
    h = max(float(np.ptp(drawn[:, :, 1])), 1.) if len(drawn) else 1.
    result, opposite = [], 0
    for i in np.nonzero(lengths > 1e-8)[0]:
        cosine = n @ n[i]
        candidates = np.nonzero((np.arange(len(T)) > i) & (np.abs(cosine) > .998) &
            (np.max(np.abs((T-T[i, 0]) @ n[i]), axis=1) < .003*h))[0]
        for j in candidates:
            if model.tris[i][:3] == model.tris[j][:3]:
                continue
            overlap = MC._overlap(T[i], T[j], n[i]) / h**2
            if overlap <= MC.ZFIGHT_MIN_AREA:
                continue
            if cosine[j] < 0:
                opposite += 1
                continue
            result.append(dict(a=list(model.tris[i][:3]), b=list(model.tris[j][:3]),
                area=float(overlap), gap=float(np.max(np.abs((T[j]-T[i, 0]) @ n[i])))))
    return dict(cofacing_pairs=len(result), cofacing_area=sum(r['area'] for r in result),
                opposite_pairs=opposite, pairs=result)


# A crossing deeper than two OT bins and 2% of the drawn height needs review,
# even when an aggregate native maximum hides a small pair of moving parts.
# This is a geometric candidate policy, not a native-calibrated visual verdict.
PART_DEPTH_UNITS = 8.0
PART_DEPTH_HEIGHT = .02


def part_intersections(model, poses, ticks=None):
    """Locate deep cross-bone intersections, including parent/child pieces.

    Report the slot/tick at the caller, retaining bone identity and depth rather
    than diluting a local defect by total model triangle count. Joint contacts,
    hidden surfaces and transparent effects can also cross: review is required.
    """
    from tools.models.field_animations.meshclash import crossing
    ticks = range(len(poses)) if ticks is None else ticks
    indices = {b: np.array([t[3] for t in model.tris if t[0] == b], int)
               for b in model.local}
    indices = {b: ids for b, ids in indices.items() if len(ids)}
    if not indices:
        return []
    worst = {}
    for tick, pose in zip(ticks, poses):
        world = model.world(pose)
        tri = {b: world[b][ids] for b, ids in indices.items()}
        drawn = np.concatenate(list(tri.values()))
        area = np.linalg.norm(np.cross(drawn[:, 1]-drawn[:, 0], drawn[:, 2]-drawn[:, 0]), axis=1)
        surface = drawn[area > 1e-8]
        height = max(float(np.ptp(surface[:, :, 1])), 1.) if len(surface) else 1.
        box = {b: (t.min((0, 1)), t.max((0, 1))) for b, t in tri.items()}
        for a in tri:
            for b in tri:
                if b <= a or (box[a][0] > box[b][1]).any() or (box[b][0] > box[a][1]).any():
                    continue
                # Reuse one hit mask for both directions: a bone renumbering
                # must not change whether the candidate is detected.
                count, depth = crossing(tri[a], tri[b], symmetric=True)
                if depth <= max(PART_DEPTH_UNITS, PART_DEPTH_HEIGHT*height):
                    continue
                key = (a, b)
                if depth > worst.get(key, {}).get('depth', -1):
                    worst[key] = dict(bones=[a, b], count=count, depth=depth,
                        height_fraction=depth/height, tick=int(tick),
                        adjacent=model.bones[a][1] == b or model.bones[b][1] == a)
    return sorted(worst.values(), key=lambda r: (-r['depth'], r['bones']))


def geometry(model):
    W = model.world(model.rest())
    T = model.tri_array(W)
    area = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1) / 2
    drawn = T[area > 1e-8]
    h = max(float(np.ptp(drawn[:, :, 1])), 1.0) if len(drawn) else 1.0
    # Scale-independent tiny threshold: a triangle < 1 square unit on a
    # 500-unit model. Exact zero is reported separately.
    local = model.tri_array(model.local)
    local_area = np.linalg.norm(np.cross(local[:, 1]-local[:, 0], local[:, 2]-local[:, 0]), axis=1)/2
    from tools.models.mesh_stability import bent_quads
    bent = bent_quads(model.m)
    z = MC.zfight(model, W, h)
    distinct = np.array([len({tuple(model.local[t[0]][i]) for i in t[3]}) == 3 for t in model.tris], dtype=bool)
    return dict(triangles=len(T), bent_quads=len(bent), bent_risk=sum(r['risk'] for r in bent)/h**2,
                zero_area=int((local_area < 1e-8).sum()),
                collapsed_indices=int(((local_area < 1e-8) & ~distinct).sum()),
                degenerate=int(((local_area < 1e-8) & distinct).sum()), rest_collapsed=int(((area < 1e-8) & (local_area > 1e-8)).sum()),
                tiny=int(((area > 1e-8) & (area < h*h/250000)).sum()),
                coplanar_pairs=len(z), coplanar_area=sum(p[2] for p in z))


def measure(model, slots=(0, 2, 3, 4, 33, 34, 35, 36), samples=4):
    from tools.models import battle_qa as Q
    out = geometry(model)
    slots = model.slots() if slots is None else slots
    rig = Q.Rig.from_mmd(model.m, model.bones)
    clips = {}
    part_pairs = []
    for slot in slots:
        if slot not in model.slots():
            continue
        poses = model.poses(slot, max_ticks=6000)
        if len(poses) >= 6000:
            raise ValueError(f'slot {slot}: 6000-tick decode guard reached')
        if not poses:
            continue
        # Evenly spaced samples include both ends. samples=0 measures every
        # decoded tick (6000-tick guard fails explicitly).
        idx = np.unique(np.linspace(0, len(poses)-1, min(samples, len(poses)), dtype=int)) if samples else np.arange(len(poses))
        selected = [poses[i] for i in idx]
        clip = Q.Clip(rig, np.array(selected, float))
        cross = Q.crossings(rig, clip.V, len(selected), step=1)
        depth = depth_probe(model, selected)
        part_pairs.extend(dict(slot=int(slot), **r) for r in part_intersections(model, selected, idx))
        clips[str(slot)] = dict(decoded_ticks=len(poses), measured_ticks=len(selected),
                                crossings_mean=cross[0], crossings_max=cross[1], **depth)
    out['clips'] = clips
    out['part_intersections'] = part_pairs
    out['part_candidates'] = len({tuple(r['bones']) for r in part_pairs})
    out['tie_rate'] = sum(c['ties'] for c in clips.values()) / max(1, sum(c['overlaps'] for c in clips.values()))
    out['flip_rate'] = sum(c['flips'] for c in clips.values()) / max(1, sum(c['comparisons'] for c in clips.values()))
    out['crossings_max'] = max((c['crossings_max'] for c in clips.values()), default=0)
    return out


def audit_one(job):
    folder, sid, row, slots, samples, details = job
    try:
        model = MC.Model((Path(folder) / f'{sid}.MMD').read_bytes(), row['bones'])
        result = dict(name=row['name'], **measure(model, slots, samples))
        if details:
            result['surface_pairs'] = coplanar_details(model)
        return sid, result
    except Exception as exc:
        return sid, dict(name=row['name'], error=repr(exc))


def audit(folder, slots, samples, jobs=1, *, details=False):
    from concurrent.futures import ProcessPoolExecutor
    index = json.loads((Path(folder) / 'index.json').read_text())
    work = [(folder, sid, row, slots, samples, details) for sid, row in index.items()]
    if jobs == 1:
        return dict(audit_one(w) for w in work)
    with ProcessPoolExecutor(jobs) as pool:
        return dict(pool.map(audit_one, work))


METRICS = ('bent_risk', 'coplanar_area', 'degenerate', 'tiny', 'crossings_max', 'tie_rate', 'flip_rate')


def calibrate(rows):
    """A control envelope, not a fitted visual-defect classifier. Every native
    passes by construction; report the actual bounds so this is reviewable.
    The same bounds must be reused, unchanged, for before/after comparisons."""
    native = [r for sid, r in rows.items() if 0 < int(sid) < 180 and 'error' not in r]
    if not native:
        raise ValueError('native control models are required for calibration')
    thresholds = {key: max(r[key] for r in native) + 1e-12 for key in METRICS}
    return thresholds


def classify(row, thresholds):
    if 'error' in row:
        return dict(verdict='error', flags=[row['error']])
    flags = [k for k in METRICS if row[k] > thresholds[k]]
    candidates = ['part_interpenetration'] if row.get('part_candidates', 0) else []
    return dict(verdict='fail' if flags else ('review' if candidates else 'pass'),
                envelope_verdict='fail' if flags else 'pass', flags=flags+candidates,
                severity=max(row[k]/max(thresholds[k], 1 if k in ('degenerate', 'tiny', 'crossings_max') else 1e-12) for k in METRICS))
