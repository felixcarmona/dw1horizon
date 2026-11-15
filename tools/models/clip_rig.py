"""One rig fit for source, donor and authored clips, and pose-independent proportion QA.

Root travel and the carrier's height are acting, not limb lengths. Visible bones
are compared with the first field-idle tick; rotations never enter this metric.
The 0.12 bound rounds up the larger control-population 99th percentile across
all ticks (native 0.110, non-chibi imports 0.11644). The first-tick bound
rounds 0.07398 up to 0.08. Both are independent of the existing size QA.
"""
import copy
import json
import math
from pathlib import Path
import statistics
import sys
from functools import lru_cache

PROPORTION_TOLERANCE = 0.12
FIRST_TOLERANCE = 0.08
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
PARTS = {'head': 'head', 'headpart': 'head', 'neck': 'torso', 'chest': 'torso',
         'pelvis': 'torso', 'carrier': 'torso', 'shoulder': 'arms', 'arm': 'arms',
         'thigh': 'legs', 'shin': 'legs', 'hipjoint': 'legs', 'hand': 'hands/feet',
         'foot': 'hands/feet', 'footpart': 'hands/feet', 'tail': 'tail/wings', 'wing': 'tail/wings'}


@lru_cache(maxsize=1)
def _rows():
    return (json.loads((ROOT / 'content/models/imports/chibi.json').read_text()),
            json.loads((ROOT / 'content/models/imports/native-bindings.json').read_text()))


def groups_for(sid, skeleton):
    rows, bindings = _rows()
    if str(sid) not in rows:
        return None
    groups = {int(b): g for b, g in rows[str(sid)]['groups'].items()}
    if str(sid) in bindings:
        from tools.models.field_animations import chibi
        groups = chibi.donor_groups(bindings[str(sid)]['map'], groups)
    return groups


@lru_cache(maxsize=1)
def post_fits():
    """Reviewed clearance placements after dimension fitting; authored inputs, not exceptions to QA."""
    path = ROOT / 'content/models/imports/rig-fits.json'
    return json.loads(path.read_text()) if path.exists() else {}



def proportions(frames, idle, parents, groups=None):
    """Exact per-bone length*mean-scale ratios: first, extrema, and median over every tick.

    Zero scale is a hidden part. Carrier translation is excluded by parentage,
    not a hardcoded bone number. Short offsets (<20 units) are unstable under
    integer quantization and have the same exclusion as the size check.
    """
    bones, parts = {}, {}
    for b in range(1, len(idle)):
        length = math.dist((0, 0, 0), idle[b][6:9])
        scale = sum(idle[b][:3])
        if parents[b] <= 0 or length < 20 or scale <= 0:
            continue
        ratios = [(t, math.dist((0, 0, 0), pose[b][6:9]) / length * sum(pose[b][:3]) / scale)
                  for t, pose in enumerate(frames) if sum(pose[b][:3]) > 0]
        if not ratios:
            continue
        values = [v for _, v in ratios]
        part = PARTS.get((groups or {}).get(b), 'other')
        row = dict(part=part, first=next((v for t, v in ratios if t == 0), None),
                   min=min(values), max=max(values), median=statistics.median(values),
                   deviation=max(abs(v - 1) for v in values))
        bones[str(b)] = row
        parts.setdefault(part, []).append(row['deviation'])
    return dict(bones=bones, parts={p: max(v) for p, v in parts.items()},
                deviation=max((r['deviation'] for r in bones.values() if groups is None or r['part'] != 'other'), default=0.0))


def failure(report):
    return any(bone_failure(r) for r in report['bones'].values() if r['part'] != 'other')


def bone_failure(row):
    return ((row['first'] is not None and not 1 - FIRST_TOLERANCE <= row['first'] <= 1 + FIRST_TOLERANCE)
            or row['min'] < 1 - PROPORTION_TOLERANCE or row['max'] > 1 + PROPORTION_TOLERANCE)


def fit(frames, source_pose, rig_pose, body='offset', dimensions=()):
    """Transfer a clip's scale and joint offsets through its reference rig transform.

    Animated scales, hidden pieces, rotations and root travel remain acting.
    The body can retain its height excursion about its new resting height, or
    scale it with the rig. Both size and proportions use this same transform.
    """
    if body not in ('offset', 'scale'):
        raise ValueError(f'unknown body fit: {body}')
    out = copy.deepcopy(frames)
    for pose in out:
        for b in range(1, len(pose)):
            bone = pose[b]
            bone[:3] = [bone[i] * rig_pose[b][i] / source_pose[b][i]
                        if source_pose[b][i] and rig_pose[b][i] else bone[i] for i in range(3)]
            for i in range(6, 9):
                s0, r0 = source_pose[b][i], rig_pose[b][i]
                if abs(s0) >= 20:
                    bone[i] = bone[i] + r0 - s0 if b == 1 and i == 7 and body == 'offset' else bone[i] * r0 / s0
    moving = {b for b in dimensions if any(math.dist(pose[b][6:9], frames[0][b][6:9]) > 1 for pose in frames)}
    for pose in out:
        for b in dimensions:
            if not sum(pose[b][:3]):
                continue
            pose[b][:3] = list(rig_pose[b][:3])
            length = math.dist((0, 0, 0), pose[b][6:9])
            target = math.dist((0, 0, 0), rig_pose[b][6:9])
            pose[b][6:9] = ([v * target / length for v in pose[b][6:9]]
                             if b in moving and length else list(rig_pose[b][6:9]))
    # A translated joint must still act after its radius is fitted. Preserve
    # its motion in the same directional arc instead of flattening a tail's
    # authored extension into a nearly stationary point on the new sphere.
    for b in moving:
        def rms(points):
            mean = [sum(p[i] for p in points) / len(points) for i in range(3)]
            return math.sqrt(sum(math.dist(p, mean) ** 2 for p in points) / len(points))
        source_points = [pose[b][6:9] for pose in frames]
        source_motion = rms(source_points)
        points = [pose[b][6:9] for pose in out]
        radius = math.dist((0, 0, 0), rig_pose[b][6:9])
        for _ in range(3):
            motion = rms(points)
            if motion < 1e-8 or motion >= 0.8 * source_motion:
                break
            gain = min(4, 0.85 * source_motion / motion)
            first = points[0]
            points = [[first[i] + gain * (p[i] - first[i]) for i in range(3)] for p in points]
            points = [[v * radius / math.dist((0, 0, 0), p) for v in p] for p in points]
        for pose, point in zip(out, points):
            pose[b][6:9] = point
    return out


def _plant_feet(frames, samples, model, skeleton, groups, bad, carrier):
    """Retarget locomotion contacts with fixed joint lengths, keeping the source's sole paths.

    A shorter leg needs new joint angles. Scaling offsets alone makes a planted
    sole slide. Solve the two leg segments on the fitted rig, retain the sole's
    world orientation, and give the carrier one constant crouch for reach.
    Unreachable airborne targets shorten their arc; planted targets must fit.
    """
    import mmd
    from tools.models import clip_repair as cr
    from tools.models.field_animations import chibi
    parents = [p for _, p in skeleton]
    def ancestor(b, names):
        b = parents[b]
        while b > 0:
            if groups.get(b) in names:
                return b
            b = parents[b]
    legs = []
    for foot, group in groups.items():
        if group != 'foot':
            continue
        knee = ancestor(foot, {'shin'})
        hip = ancestor(knee, {'thigh'}) if knee is not None else None
        if hip is not None:
            legs.append((hip, knee, foot))
    if not legs or not any(set(leg) & bad for leg in legs):
        return samples, set()
    out = copy.deepcopy(samples)
    for old, pose in zip(frames, out):
        pose[carrier][7] = old[carrier][7]
    verts = chibi.Rig(model, skeleton).verts
    old_world = [mmd.bone_matrices(model, pose) for pose in frames]
    world = [mmd.bone_matrices(model, pose) for pose in out]
    def point(mats, b):
        return [mats[b][i][3] for i in range(3)]
    def sub(a, b):
        return [x-y for x,y in zip(a,b)]
    def dot(a, b):
        return sum(x*y for x,y in zip(a,b))
    def unit(v):
        length = math.sqrt(dot(v,v))
        return [x/length for x in v] if length > 1e-9 else [0.,0.,1.]
    contacts, lower, upper = [], -math.inf, math.inf
    for mats, old in zip(world, old_world):
        row = {}
        for hip, knee, foot in legs:
            M = old[foot]
            low = max(sum(M[1][i]*v[i] for i in range(3))+M[1][3] for v in verts[foot])
            row[foot] = low >= -12
            if not row[foot]:
                continue
            h, k, a = (point(mats,b) for b in (hip,knee,foot))
            L1, L2 = math.dist(h,k), math.dist(k,a)
            length = L1+L2-.5
            inner = abs(L1-L2)+.5
            target = point(old,foot)
            horizontal = (target[0]-h[0])**2+(target[2]-h[2])**2
            if horizontal > length*length:
                raise ValueError('field rig cannot reach a planted sole')
            lower = max(lower, target[1]-math.sqrt(max(0.,length*length-horizontal))-h[1])
            upper = min(upper, target[1]-math.sqrt(max(0.,inner*inner-horizontal))-h[1])
        contacts.append(row)
    if lower > upper:
        raise ValueError('field rig cannot keep both planted soles')
    down = max(lower, min(0., upper))
    def rotate(pose, bone, current, target):
        u, v = unit(current), unit(target)
        cross = [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        sine = math.sqrt(dot(cross,cross));cosine=max(-1.,min(1.,dot(u,v)))
        if sine < 1e-9:
            if cosine > 0:
                return
            cross = [0.,u[2],-u[1]] if abs(u[0])<.9 else [-u[2],0.,u[0]]
        Q = cr._axis_angle(unit(cross), math.degrees(math.atan2(sine,cosine)))
        P = cr._chain(parents,pose,parents[bone],{})
        R = cr._mul(cr._tr(P),cr._mul(Q,cr._mul(P,cr._rot(*pose[bone][3:6]))))
        pose[bone][3:6] = list(mmd.matrix_euler(R,prev=pose[bone][3:6]))
    for t, pose in enumerate(out):
        pose[carrier][7] += down
        for hip,knee,foot in legs:
            mats=mmd.bone_matrices(model,pose)
            h,k,a=(point(mats,b) for b in (hip,knee,foot))
            L1,L2=math.dist(h,k),math.dist(k,a)
            target=point(old_world[t],foot)
            direction=sub(target,h);distance=math.sqrt(dot(direction,direction))
            limit=L1+L2-.5
            inner=abs(L1-L2)+.5
            if distance>limit:
                if contacts[t][foot] and distance>limit+1e-6:
                    raise ValueError('field rig cannot keep a planted sole')
                target=[h[i]+direction[i]*limit/max(distance,1e-9) for i in range(3)]
                direction=sub(target,h);distance=limit
            if distance < inner:
                if contacts[t][foot]:
                    raise ValueError('field rig cannot fold onto a planted sole')
                target=[h[i]+direction[i]*inner/max(distance,1e-9) for i in range(3)]
                direction=sub(target,h);distance=inner
            u=unit(direction)
            old_h,old_knee,old_a=(point(old_world[t],b) for b in (hip,knee,foot))
            old_u=unit(sub(old_a,old_h));pole=sub(old_knee,old_h)
            pole=[pole[i]-dot(pole,old_u)*old_u[i] for i in range(3)]
            if dot(pole,pole)<1e-12:
                pole=[-old_world[t][hip][i][2] for i in range(3)]
            pole=[pole[i]-dot(pole,u)*u[i] for i in range(3)]
            w=unit(pole)
            along=max(-L1,min(L1,(L1*L1+distance*distance-L2*L2)/(2*max(distance,1e-9))))
            across=math.sqrt(max(0.,L1*L1-along*along))
            wanted=[h[i]+u[i]*along+w[i]*across for i in range(3)]
            sole_rotation=cr._chain(parents,pose,foot,{})
            rotate(pose,hip,sub(k,h),sub(wanted,h))
            mats=mmd.bone_matrices(model,pose);k,a=point(mats,knee),point(mats,foot)
            rotate(pose,knee,sub(a,k),sub(target,k))
            P=cr._chain(parents,pose,parents[foot],{})
            pose[foot][3:6]=list(mmd.matrix_euler(cr._mul(cr._tr(P),sole_rotation),prev=pose[foot][3:6]))
            actual=point(mmd.bone_matrices(model,pose),foot)
            if contacts[t][foot] and math.dist(actual,target)>2:
                raise ValueError('field rig cannot preserve its sole contact')
    return out, {b for leg in legs for b in leg}


def conform(data, skeleton, sid):
    """Final common fit boundary, after every clip producer (including authored clips).

    Only anatomical dimensions outside the control-population tolerance change.
    Unchanged programs, especially passing field programs, retain their bytes.
    A changing joint direction is retained; its length uses the field rig. The
    carrier follows the old support surface each tick, keeping planted feet and
    authored clearance. Root, events and control flow stay exact; reviewed
    clearance turns and locomotion contact IK can change joint rotations.
    """
    import animsheet
    import mmd
    import motioncyclelayer
    import motionstorage
    from tools.models.field_animations import chibi
    from tools.models.field_animations.articulation import replace_channels
    groups = groups_for(sid, skeleton)
    clearance = post_fits().get(str(sid), {})
    nb = len(skeleton)
    model = mmd.MMD.parse(data, nb)
    idle = animsheet.slot_frames(model, nb, 0)[0][0]
    if groups is None:
        from tools.models.clip_repair import relative_size
        def size(slot, index):
            player = mmd.AnimPlayer(model.anims.anims[index], nb, slot)
            player.tick(stop_at_infinite_loop=True)
            return relative_size(player.pose, idle)
        if not clearance and all(0.92 <= size(slot, index) <= 1.08
                                 for slot, index in enumerate(model.anims.table) if index is not None):
            return data, {}
    parents = [p for _, p in skeleton]
    carrier, = [b for b in range(1, nb) if parents[b] == 0]
    chibi._register(9000 + int(sid), skeleton)
    model.type = 9000 + int(sid)
    rig = chibi.Rig(model, skeleton)
    feet = [b for b, g in (groups or {}).items() if g == 'foot' and b in rig.verts]
    changed = {}
    done = {}
    for slot, index in enumerate(list(model.anims.table)):
        if index is None:
            continue
        if index in done:
            model.anims.table[slot] = done[index]
            continue
        from tools.models.clip_repair import relative_size
        first = mmd.AnimPlayer(model.anims.anims[index], nb, slot)
        first.tick(stop_at_infinite_loop=True)
        size_bad = not 0.92 <= relative_size(first.pose, idle) <= 1.08
        operations = clearance.get(str(slot), [])
        if groups is None and not size_bad and not operations:
            continue
        frames, loop, events = animsheet.slot_frames(model, nb, slot)
        report = proportions(frames, idle, parents, groups)
        bad = {int(b) for b, r in report['bones'].items()
               if r['part'] != 'other' and bone_failure(r)}
        if size_bad:
            bad.update(int(b) for b in report['bones'])
        if not bad and not operations:
            continue
        samples = fit(frames, idle, idle, dimensions=bad)
        channels = {(b, c) for b in bad for c in (0, 1, 2, 6, 7, 8)}
        if operations:
            from tools.models.clip_repair import apply_ops
            adjusted = apply_ops(samples, parents, operations)
            # Reviewed placements can move a joint as well as turn it. Keep
            # those channels in the encoded clip, even when dimensions pass.
            channels.update((b, c) for b in range(1, nb) for c in (0, 1, 2, 6, 7, 8)
                            if any(a[b][c] != z[b][c] for a, z in zip(samples, adjusted)))
            samples = adjusted
            channels.update((op['bone'], c) for op in operations for c in (3, 4, 5))

        # Match the old support surface, in the final mesh. Feet carry standing
        # poses; lying poses rest on the mesh, with chibi's established blend.
        old = []
        for pose in frames:
            lows = chibi.bone_lows(model, rig.verts, pose)
            low = max(lows.values())
            foot = max((lows[b] for b in feet), default=low)
            old.append((foot, low, max(lows, key=lows.get)))
        weights = chibi.on_feet(old, loop)
        for pose, low, w in zip(samples, old, weights):
            lows = chibi.bone_lows(model, rig.verts, pose)
            foot = max((lows[b] for b in feet), default=max(lows.values()))
            delta = w * (low[0] - foot) + (1 - w) * (low[1] - max(lows.values()))
            pose[carrier][7] += delta
        channels.add((carrier, 7))
        if slot in (2, 3, 4) and groups:
            samples, joints = _plant_feet(frames, samples, model, skeleton, groups, bad, carrier)
            channels.update((b, c) for b in joints for c in (3, 4, 5))

        samples = [[[round(v) for v in bone] for bone in pose] for pose in samples]
        original = copy.deepcopy(model.anims.anims[index])
        needs_scale = original.has_scale or any(v != 4096 for pose in samples for bone in pose[1:] for v in bone[:3])
        if not needs_scale:
            channels = {(b, c) for b, c in channels if c >= 3}
        if needs_scale and not original.has_scale:
            original.pose = [[4096] * 3 + list(p) for p in original.pose]
            original.has_scale = True
        clip = replace_channels(original, samples, loop, nb, channels)
        # A finite control loop can replay the same program frame several
        # times. Sample-index keys cannot describe its carrier height; use
        # the interpreter's program frames for those clips instead.
        player = mmd.AnimPlayer(clip, nb, slot)
        decoded = []
        while len(decoded) < len(samples) and player.tick(stop_at_infinite_loop=True):
            decoded.append(player.pose[carrier][7])
        if len(decoded) == len(samples) and max(abs(v - p[carrier][7]) for v, p in zip(decoded, samples)) > 2:
            program_frames = chibi.replay(model, nb, index, slot, carrier)[0]
            heights = dict(zip(program_frames, [p[carrier][7] for p in samples]))
            if chibi._chains(clip) is None:
                raise ValueError(f'{sid} slot {slot}: carrier height cannot preserve the program loop')
            chibi._rewrite_heights(clip, carrier, heights.items(), 1)

        new = len(model.anims.anims)
        model.anims.anims.append(clip)
        model.anims.table[slot] = new
        done[index] = new
        changed[str(slot)] = sorted(bad)
    if not changed:
        return data, {}
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    output = model.build()
    motionstorage.require(output, nb)
    # Gate the encoded program too: interpolation and control loops must not
    # reintroduce a different rig after the fit was computed on decoded ticks.
    final = mmd.MMD.parse(output, nb)
    final_idle = animsheet.slot_frames(final, nb, 0)[0][0]
    for slot in map(int, changed):
        encoded = animsheet.slot_frames(final, nb, slot)[0]
        if not 0.92 <= relative_size(encoded[0], final_idle) <= 1.08 or failure(proportions(encoded, final_idle, parents, groups or {})):
            raise ValueError(f'{sid} slot {slot}: encoded clip does not keep the field rig')
    return output, changed


def check(data, skeleton, sid):
    """Proportion gate for every occupied field, care, battle and technique slot."""
    import animsheet
    import mmd
    model = mmd.MMD.parse(data, len(skeleton))
    idle = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    groups = groups_for(sid, skeleton)
    rows = {}
    for slot, index in enumerate(model.anims.table):
        if index is None:
            continue
        report = proportions(animsheet.slot_frames(model, len(skeleton), slot)[0], idle,
                             [p for _, p in skeleton], groups or {})
        rows[slot] = dict(report, applicable=groups is not None,
                          verdict='fail' if groups is not None and failure(report) else 'pass')
    return rows


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('species', type=Path)
    parser.add_argument('--id')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    record = json.loads(args.species.read_text())
    sid = args.id or args.species.name.split('-')[0]
    results = check(args.model.read_bytes(), record['model']['skeleton'], sid)
    for slot, row in results.items():
        print(f"slot {slot:#x}: {row['verdict']} proportions {row['deviation']:.6f}")
    if args.json:
        args.json.write_text(json.dumps(results, indent=1) + '\n')
    raise SystemExit(int(any(row['verdict'] == 'fail' for row in results.values())))
