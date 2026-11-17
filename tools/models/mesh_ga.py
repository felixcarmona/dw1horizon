"""Scoped before/after evidence for imported species 183, 193, 196 and 218.

Inputs are final atlas-stamped MMD/TIM directories with index.json. Crossing
ledgers cover every occupied slot and decoded tick. PSX-rule sheets remain
orthographic evidence; neither intersections nor bin-phase pixels prove a
visible runtime defect. The opposite-face floor preserves the measured idle
surfaces and height, and does not cover arbitrary vertex or rig redesign.
"""
import argparse
import copy
import csv
import gzip
import json
from pathlib import Path

import numpy as np
from tools.models import mesh_round4 as R, mesh_glitch as G, mesh_cleanup as C
from tools.models.mesh_stability import packet_bytes
import mmd
import motionstorage

IDS = (183, 193, 196, 218)
# Exact source object numbers remain in every ledger, including unnamed pieces.
R.PART_NAMES.update({
    183: {5: 'head', 24: 'rear body socket', 25: 'rear body ring', 26: 'tail base'},
    193: {1: 'pelvis', 2: 'left thigh shell', 3: 'left calf shell',
          6: 'right thigh shell', 7: 'right calf shell', 16: 'left drill', 19: 'right drill'},
    196: {1: 'head', 9: 'pelvis', 10: 'tail base', 11: 'tail tip',
          12: 'left front thigh', 15: 'right front thigh',
          18: 'left rear thigh', 22: 'right rear thigh'},
    218: {1: 'body core', 2: 'head', 4: 'jaw', 5: 'right whisker', 6: 'left whisker'},
})


def preservation(before, after, sid):
    assert before.bones == after.bones
    assert before.m.anims.table == after.m.anims.table
    ticks = 0
    ground = {}
    used = {bone: np.unique([i for t in before.tris if t[0] == bone for i in t[3]])
            for bone in before.local}
    for slot in before.slots():
        a, ia = mmd.simulate(before.m.anims.anims[before.m.anims.table[slot]], len(before.bones), slot=slot)
        b, ib = mmd.simulate(after.m.anims.anims[after.m.anims.table[slot]], len(after.bones), slot=slot)
        expected = np.array(a)
        if sid == 183:
            expected[:, 24, 8] += 10
        assert np.array_equal(expected, np.array(b)), (sid, slot, 'pose')
        assert ia == ib, (sid, slot, 'loop/event')
        ticks += len(a)
        if slot in (0, 1, 2, 3, 4):
            values = []
            for model, poses in ((before, a), (after, b)):
                heights = []
                for pose in poses:
                    world = model.world(pose)
                    heights.append(max(world[bone][ids, 1].max()
                                       for bone, ids in used.items() if len(ids)))
                values.append(np.array(heights))
            ground[slot] = dict(before_range=[float(values[0].min()), float(values[0].max())],
                                after_range=[float(values[1].min()), float(values[1].max())],
                                max_tick_change=float(np.abs(values[1]-values[0]).max()))
    assert before.tim.to_bytes() == after.tim.to_bytes()
    assert packet_bytes(before.m) == packet_bytes(after.m)
    assert [p.raw for ob in before.m.tmd.objects for p in ob.prims] == [
        p.raw for ob in after.m.tmd.objects for p in ob.prims]
    return dict(slots=len(before.slots()), ticks=ticks, textures_equal=True,
                field_ground_extent=ground,
                primitives_materials_uvs_equal=True, packet_bytes=packet_bytes(after.m),
                root_travel_timing_loops_events_equal=True,
                pose_exception='bone 24 local tz +10, every clip' if sid == 183 else None)


def opposite_floor(model):
    """Locate the retained same-bone opposite-winding legacy candidates.

    This reproduces the legacy filters exactly. At the fixed measured idle
    pose their sum is a lower bound regardless of inter-part layer repairs.
    It is a surface-preserving floor, not an impossibility theorem for reshaping.
    """
    world = model.world(model.rest())
    triangles = model.tri_array(world)
    area = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0],
                                   triangles[:, 2]-triangles[:, 0]), axis=1)/2
    h = float(np.ptp(triangles[area > 1e-8, :, 1]))
    normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    normals /= np.maximum(lengths[:, None], 1e-12)
    centers = triangles.mean(1)
    rows = []
    for i, a in enumerate(model.tris):
        if lengths[i] < 1e-6:
            continue
        for j in range(i+1, len(triangles)):
            b = model.tris[j]
            if a[0] != b[0] or set(a[3]) == set(b[3]) or a[4] == b[4]:
                continue
            cosine = float(normals[i] @ normals[j])
            # zfight() compares the two plane offsets, not all three vertices.
            gap = abs(float(normals[j] @ triangles[j, 0] * -1 - normals[i] @ triangles[i, 0]))
            if cosine >= -.998 or gap >= .003*h or np.linalg.norm(centers[j]-centers[i]) >= .25*h:
                continue
            overlap = R.MC._overlap(triangles[i], triangles[j], normals[i])
            if overlap > R.MC.ZFIGHT_MIN_AREA*h*h:
                rows.append(dict(a=list(a[:3]), b=list(b[:3]), cosine=cosine,
                                 plane_gap=gap, area=overlap, normalized_area=round(overlap/h**2, 5)))
    return dict(scope='retained idle surfaces and height; no arbitrary reshaping/rig redesign',
                height=h, pairs=rows, count=len(rows),
                normalized_area=sum(r['normalized_area'] for r in rows))


def investigate(before_dir, after_dir, sid, out, thresholds):
    a, b = R.load(before_dir, sid), R.load(after_dir, sid)
    evidence = dict(preservation=preservation(a, b, sid), stages={})
    for stage, folder, model in (('before', before_dir, a), ('after', after_dir, b)):
        d = G.measure(model, samples=3)
        d.update(G.classify(d, thresholds))
        d['surface_pairs'] = G.coplanar_details(model)
        d['exact_duplicate_packets'] = C.duplicate_surfaces(copy.deepcopy(model.m))
        assert d['zero_area'] == 0, (sid, stage, 'zero-area face')
        d['storage'] = motionstorage.require((folder/f'{sid}.MMD').read_bytes(), len(model.bones))
        assert d['storage']['resident_bytes'] <= 100256
        ledger = R.scan(folder, sid, out/f'ledger-{stage}')
        # Retain complete ledgers compressed, with bounded summary sizes.
        path = out/f'ledger-{stage}'/f'{sid}-frames.csv'
        counts = {}
        with path.open() as stream:
            for row in csv.DictReader(stream):
                if not int(row['adjacent']):
                    key = (int(row['slot']), int(row['frame']))
                    counts[key] = counts.get(key, 0)+int(row['triangle_pairs'])
        peak = max(counts, key=counts.get)
        ledger['nonadjacent_max'] = counts[peak]
        ledger['nonadjacent_peak_slot_frame'] = list(peak)
        with gzip.GzipFile(str(path)+'.gz', 'wb', mtime=0) as stream:
            stream.write(path.read_bytes())
        d['full_clip'] = ledger
        evidence['stages'][stage] = d
    cases = [(slot, 0) for slot in (0, 2, 3, 4)]
    cases.extend({183: [(3, 8)], 193: [(3, 0), (35, 10)],
                  196: [(2, 8), (3, 11)], 218: []}[sid])
    for stage in evidence['stages'].values():
        worst = max(stage['full_clip']['pairs'].values(), key=lambda p: p['depth'])
        cases.append((worst['slot'], worst['tick']))
    evidence['renders'] = R.render_evidence(a, b, cases, out/'renders'/str(sid))
    # Retained crossings get an independently verified continuous translation
    # certificate when possible; failed certificates are explicitly inconclusive.
    worst = sorted(evidence['stages']['after']['full_clip']['pairs'].values(), key=lambda p: -p['depth'])
    for witness in worst[:12]:
        certificate = R.certificate(b, witness['bones'], witness['slot'], witness['tick'], 8.)
        if certificate['proven']:
            certificate['pose_trials'] = R.pose_trials(b, witness['bones'], witness['slot'], witness['tick'])
            evidence['bounded_translation_floor'] = certificate
            break
    if sid == 218:
        evidence['opposite_face_floor'] = opposite_floor(b)
    (out/f'{sid}-audit.json').write_text(json.dumps(evidence, indent=2)+'\n')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('ids', nargs='*', type=int, choices=IDS)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--thresholds', type=Path, default=Path('docs/reference/mesh-glitch-thresholds.json'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    thresholds = json.loads(args.thresholds.read_text())['thresholds']
    for sid in args.ids or IDS:
        investigate(args.before, args.after, sid, args.out, thresholds)


if __name__ == '__main__':
    main()
