"""DW1 MetalGreymon care/battle motion after the reviewed species-224 field pass.

Read all geometry and motion from the player's extraction. Register homologous
mesh parts to remove the different baked axes and pivots; never copy bone IDs or
use Etemon's guessed anatomy. Native feet drive a two-link solve on the native
rig before registration, with mesh support and a movable carrier. Preserve the
old event/control programs, duration, and externally driven training root.

Seven rejected actions deliberately keep their old programs; see FALLBACK.
"""
import copy
import hashlib
import itertools
import math
from pathlib import Path
import numeric as np
import mmd
import animsheet
import retarget as R
import legik
import motionsecondary
import motionstorage
import motiontailspace
from motioncyclelayer import share_identical_streams
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.war_greymon import set_rotation
from tools.models.field_animations.metal_greymon import PARENTS
SOURCE = 'e021622a3ae698bb0f2150ed3a783aa8171d9ceae3420143cd4e74aeea3c0dae'
DONOR = '2b330474fc2c5ab1f308c51b7ddaa3c503c79255c0cd2168e9979073125c304d'
BONES = dict(enumerate([2, 3, 4, 5, 7, 8, 9, 11, 12, 13, 15, 17, 18, 19, 20, 21, 23, 24, 25, 27, 28, 29], 1))
KEEP = {0, 1, 2, 3, 4, 0x21, 0x28, 0x29, 0x2a, 0x2b,
        0x30, 0x31, 0x34, 0x36, 0x38, 0x39, 0x3a, 0x3c}
FALLBACK = {
    0x09: 'Sleep: organic hand and subframe support fail the floor/contact limits.',
    0x0a: 'Toilet: fixed-foot support and subframe floor constraints conflict.',
    0x15: 'Fallen pose: arm sweep and support fail the floor/contact limits.',
    0x1b: 'Externally driven training: no feasible integer carrier/contact trajectory.',
    0x23: 'Battle walk: no feasible integer carrier/contact trajectory.',
    0x24: 'Battle run: support transfer still floats more than four units.',
    0x2c: 'Get-up: arm sweep and support fail the floor/contact limits.',
}


def stationary_root(anim):
    """Use stationary native care actions without inherited Etemon shuffles."""
    for ins in anim.instrs:
        if ins['op'] != 'key':
            continue
        for group in ins['bones']:
            if group['bone'] == 0:
                group['vals'] = {k:v for k,v in group['vals'].items() if k not in ('tx','ty','tz')}
        ins['bones'] = [g for g in ins['bones'] if g['vals']]


def fit_piece(vertices, native, initial, search=False):
    """Rigid shape registration, starting from anatomically calibrated axes.

    Vertex ordering differs. ICP matches centered shapes; a bounded rotation
    search resolves the mechanical forearm's misleading local minimum. Only
    the player's vertices enter the covariance/SVD, not frozen poses or clips.
    """
    a, b = (np.array(vertices), np.array(native))
    ac, bc = (a - a.mean(0), b - b.mean(0))
    scale = math.sqrt(float(np.sum(bc * bc) / np.sum(ac * ac)))
    seeds = [np.array(initial)]
    if search:
        seeds += [np.array(mmd.rot_matrix(*angles)) @ np.array(initial) for angles in itertools.product((0, 512, -512, 1024), repeat=3)]
    for seed in seeds:
        q = seed.copy()
        for _ in range(35):
            transformed = (ac @ q.T * scale).tolist()
            points = bc.tolist()
            nearest = [min(range(len(points)), key=lambda j: sum(((x - y) ** 2 for x, y in zip(p, points[j])))) for p in transformed]
            u, _, v = np.linalg.svd(ac.T @ bc[nearest])
            rotation = v.T @ u.T
            if np.linalg.det(rotation) < 0:
                v[-1] *= -1
                rotation = v.T @ u.T
            if float(np.max(np.abs(rotation - q))) < 1e-08:
                q = rotation
                break
            q = rotation
        transformed = (ac @ q.T * scale).tolist()
        error = math.sqrt(sum((min((sum(((x - y) ** 2 for x, y in zip(p, n))) for n in points)) for p in transformed)) / len(transformed))
        if error < 1.5:
            return (q, b.mean(0), a.mean(0), scale, error)
    raise ValueError('homologous mesh registration failed')

def carrier_offsets(bounds, loop):
    """Find integer body heights satisfying floor AND support at ticks/thirds.

    All mesh pieces descend from carrier 13. With the pose fixed, changing its
    Y shifts every transformed vertex equally. Each adjacent key pair therefore
    defines a small discrete constraint on its two heights. Dynamic programming
    minimizes carrier displacement and its changes, including loop closure;
    it does not demand unreachable exact pose-only foot contact.
    """

    def valid(segment, first, second):
        y0, y1, samples = segment
        for alpha, bottom, foot in samples:
            before = y0 + ((y1 - y0) * alpha + 2048 >> 12)
            after = y0 + first + ((y1 + second - y0 - first) * alpha + 2048 >> 12)
            delta = after - before
            if bottom + delta > 1.95 or foot + delta < -3.95:
                return False
        return True
    choices = range(-12, 13)
    best = None
    for closing in choices if loop is not None else [None]:
        states = {d: (d * d, [d]) for d in choices if loop != 0 or d == closing}
        for tick, segment in enumerate(bounds):
            next_states = {}
            for second in choices:
                if loop is not None and tick + 1 in (loop, len(bounds)) and (second != closing):
                    continue
                for first, (cost, path) in states.items():
                    if not valid(segment, first, second):
                        continue
                    score = cost + second * second + 2 * (second - first) ** 2
                    if second not in next_states or score < next_states[second][0]:
                        next_states[second] = (score, path + [second])
            states = next_states
            if not states:
                break
        if states:
            candidate = min(states.values(), key=lambda x: x[0])
            if best is None or candidate[0] < best[0]:
                best = candidate
    if best is None:
        raise ValueError('no carrier trajectory satisfies floor and support limits')
    return best[1]

def _author(old, src, sk, ds):
    bmap = BONES
    rest, drest = (R.rest_pose(old, 23), R.rest_pose(src, 30))
    rest = R.align_reference(sk, rest, ds, drest, [(1, 2, 2, 3), (2, 3, 3, 4), (3, 4, 4, 5), (5, 6, 7, 8), (6, 7, 8, 9), (8, 9, 11, 12), (9, 10, 12, 13), (14, 15, 19, 20), (15, 16, 20, 21)], keep_world=[11, 12, 19, 22])
    dp = R.world_pos(ds, drest)
    wr, dr = (R.world_rots(sk, rest), R.world_rots(ds, drest))
    verts = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}
    regs, calibration = ({}, [])
    for b, s in bmap.items():
        assert sk[b][0] == ds[s][0], (b, s, 'anatomy')
        fit = fit_piece(verts[b], np.array(src.tmd.obj_verts(ds[s][0]))[:, :3], np.array(dr[s]).T @ np.array(wr[b]), search=b == 6)
        regs[b] = fit[:4]
        calibration.append(dict(bone=b, native=s, rms=fit[4]))
    scale = sum((x[3] for x in regs.values())) / len(regs)

    def native_feet(d):
        """Solve native feet by mesh support, allowing the body to move into reach."""
        dw = np.array(mmd.bone_matrices(src, d))
        feet = [25, 29]
        bottoms = [float((np.array(src.tmd.obj_verts(ds[a][0]))[:, :3] @ dw[a, :3, :3].T + dw[a, :3, 3])[:, 1].max()) for a in feet]
        goals = []
        intervals = []
        for h, k, a in [(23, 24, 25), (27, 28, 29)]:
            rf = np.array(dr[a])
            vs = np.array(src.tmd.obj_verts(ds[a][0]))[:, :3]
            g = dw[a, :3, 3].copy()
            # These are stationary care/attack actions: keep the footprint
            # while the body and knees perform the native gesture above it.
            g[[0, 2]] = np.array(dp[a])[[0, 2]]
            up = max(bottoms) - bottoms[feet.index(a)]
            if slot in [27, 35, 36]:
                up = max(0, up - 75)
            g[1] = -up - float((vs @ rf.T)[:, 1].max()) - 1
            hip = dw[h, :3, 3]
            l1 = math.dist(dp[h], dp[k])
            l2 = math.dist(dp[k], dp[a])
            xz = g[[0, 2]] - hip[[0, 2]]
            xzlen = float(np.linalg.norm(xz))
            xzmax = l1 + l2 - 3
            if xzlen > xzmax:
                g[[0, 2]] = hip[[0, 2]] + xz * xzmax / xzlen
            reach = math.sqrt(max(1, (l1 + l2 - 1) ** 2 - float(np.sum((g[[0, 2]] - hip[[0, 2]]) ** 2))))
            intervals.append((g[1] - reach - hip[1], g[1] - 15 - hip[1]))
            goals.append((h, k, a, g, rf, l1, l2))
        low = max((x[0] for x in intervals))
        high = min((x[1] for x in intervals))
        d[1][7] += round(min(max(0, low), high))
        dw = np.array(mmd.bone_matrices(src, d))
        for h, k, a, g, rf, l1, l2 in goals:
            hip = dw[h, :3, 3]
            axis = legik.unit(legik.sub(dp[a], dp[h]))
            kv = legik.sub(dp[k], dp[h])
            pole = legik.sub(kv, legik.mul(axis, legik.dot(kv, axis)))
            knee, ank = legik.solve(hip, g, l1, l2, pole)
            rh, rk = motionsecondary.native_plane_rotations([dp[v] for v in [h, k, a]], [hip, knee, ank], [dr[h], dr[k]])
            for b, rot in [(h, rh), (k, rk), (a, rf)]:
                parent = R.world_rots(ds, d)[ds[b][1]]
                set_rotation(d, b, np.array(parent).T @ np.array(rot), {})
        return d
    new = copy.deepcopy(old)
    reports = []
    keep = KEEP | set(FALLBACK)
    tech = {s: 54 for s in [46, 47, 50, 51, 53, 55, 59]}
    tech[61] = 60
    order = sorted(bmap, key=lambda b: R.depth(sk, b))
    for slot, idx in enumerate(old.anims.table):
        if idx is None or slot in keep:
            continue
        donor = tech.get(slot, slot)
        fs, lp, ev = animsheet.slot_frames(old, 23, slot)
        dfs, dlp, dev = animsheet.slot_frames(src, 30, donor)

        def index(t):
            if lp is not None and dlp is not None:
                if t < lp:
                    return t / max(1, lp) * dlp
                return dlp + (t - lp) / max(1, len(fs) - 1 - lp) * (len(dfs) - 1 - dlp)
            if slot in tech:
                anchor = 26
                oldanchor = 15
                return t / oldanchor * anchor if t <= oldanchor else anchor + (t - oldanchor) / (len(fs) - 1 - oldanchor) * (len(dfs) - 1 - anchor)
            return t / max(1, len(fs) - 1) * (len(dfs) - 1)
        poses = []
        hist = {}
        for t, orig in enumerate(fs):
            x = index(t)
            lo = int(x)
            hi = min(lo + 1, len(dfs) - 1)
            alpha = round((x - lo) * 4096)
            d = motiontailspace.interpolate_pose(dfs[lo], dfs[hi], alpha)
            d[0] = [4096] * 3 + [0] * 6
            d = native_feet(d)
            dm = np.array(mmd.bone_matrices(src, d))
            f = copy.deepcopy(rest)
            f[0] = [4096] * 3 + [0] * 6
            worlds = {}
            for b in order:
                q, bc, ac, _ = regs[b]
                s = bmap[b]
                rot = dm[s, :3, :3] @ q
                pos = (dm[s, :3, 3] + dm[s, :3, :3] @ bc) / scale - rot @ ac
                worlds[b] = (rot, pos)
                par = sk[b][1]
                pr, pp = worlds.get(par, (np.eye(3), np.zeros(3)))
                set_rotation(f, b, pr.T @ rot, hist)
                f[b][6:9] = np.rint(pr.T @ (pos - pp)).astype(int).tolist()
            W = np.array(mmd.bone_matrices(old, f))
            footbottom = max((float((verts[b] @ W[b, :3, :3].T + W[b, :3, 3])[:, 1].max()) for b in [19, 22]))
            f[13][7] -= round(footbottom + 1)
            for chain, hinges in [([5, 6, 7], [6, 5]), ([8, 9, 10], [9, 8]), ([14, 15, 16], [14])]:
                for hinge in hinges:
                    W = np.array(mmd.bone_matrices(old, f))
                    points = [p.tolist() for b in chain if R.depth(sk, b) >= R.depth(sk, hinge) for p in verts[b] @ W[b, :3, :3].T + W[b, :3, 3]]
                    try:
                        fix = motionsecondary.clearance_rotation(points, W[hinge, :3, 3].tolist(), [1, 0, 0], [-110, 0] if hinge != 14 else [0, 110], -100 if slot == 61 and 4 <= t <= 10 and (hinge in [5, 6]) else -12)
                    except ValueError:
                        continue
                    set_rotation(f, hinge, W[sk[hinge][1], :3, :3].T @ np.array(fix) @ W[hinge, :3, :3], hist)
                    break
            f[0] = copy.deepcopy(orig[0])
            if slot in [35, 36]:
                f[0][6:9] = [round((dfs[lo][0][6 + c] + (x - lo) * (dfs[hi][0][6 + c] - dfs[lo][0][6 + c])) / scale) for c in range(3)]
            poses.append(f)
        if lp is not None:
            mmd.close_loop(poses, lp)
        channels = {(b, c) for b in range(1, 23) for c in range(3, 9)}
        anim = replace_channels(old.anims.anims[idx], poses, lp, 23, channels, tolerance=4)
        anim = replace_channels(anim, poses, lp, 23, {(13, 7)}, tolerance=0)
        for correction in range(2):
            decoded, _, _ = R.play(anim, 23, slot)
            for p in decoded:
                p[0] = [4096] * 3 + [0] * 6
                W = np.array(mmd.bone_matrices(old, p))
                bottom = max((float((verts[b] @ W[b, :3, :3].T + W[b, :3, 3])[:, 1].max()) for b in [19, 22]))
                p[13][7] -= round(bottom)
            anim = replace_channels(anim, decoded, lp, 23, {(13, 7)}, tolerance=0)
        decoded, _, _ = R.play(anim, 23, slot)
        bounds = []
        for t in range(len(decoded) - 1):
            segment = []
            for alpha in [0, 1365, 2730, 4096]:
                f = motiontailspace.interpolate_pose(decoded[t], decoded[t + 1], alpha)
                f[0] = [4096] * 3 + [0] * 6
                W = np.array(mmd.bone_matrices(old, f))
                lows = {b: float((v @ W[b, :3, :3].T + W[b, :3, 3])[:, 1].max()) for b, v in verts.items()}
                segment.append((alpha, max(lows.values()), max(lows[19], lows[22])))
            bounds.append((decoded[t][13][7], decoded[t + 1][13][7], segment))
        try:
            offsets = carrier_offsets(bounds, lp)
        except ValueError as exc:
            raise ValueError(f'slot {slot:#x}: {exc}') from exc
        for p, offset in zip(decoded, offsets):
            p[13][7] += offset
        anim = replace_channels(anim, decoded, lp, 23, {(13, 7)}, tolerance=0)
        # These approved native actions have no entity travel. Remove the
        # Etemon care shuffles as well as replacing their body motion.
        assert all(p[0][6:9] == [0,0,0] for p in dfs), slot
        stationary_root(anim)
        new.anims.anims.append(anim)
        new.anims.table[slot] = len(new.anims.anims) - 1
        reports.append(dict(slot=slot, donor=donor, ticks=len(fs), loop=lp, attack_anchor=[15, 26] if slot in tech else None))
    for anim in new.anims.anims:
        anim.tail = b''
    new.anims.anims, new.anims.table = share_identical_streams(new.anims.anims, new.anims.table)
    return (new.build(), reports, calibration, scale)

def contact(model, slot):
    """Decoded engine samples and Euler/SRT thirds, all mesh vertices."""
    frames, loop, _ = animsheet.slot_frames(model, 23, slot)
    sk = mmd.exe().skeleton[224]
    vertices = {b: np.array(model.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}
    floor, floating = (-math.inf, -math.inf)
    for tick, pose in enumerate(frames):
        for alpha in (0, 1365, 2730):
            f = motiontailspace.interpolate_pose(pose, frames[min(tick + 1, len(frames) - 1)], alpha)
            f[0] = [4096] * 3 + [0] * 6
            w = np.array(mmd.bone_matrices(model, f))
            lows = {b: float((vs @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b, vs in vertices.items()}
            floor = max(floor, max(lows.values()))
            floating = max(floating, -max(lows[19], lows[22]))
    return dict(maximum_floor_y=floor, maximum_support_clearance=floating, samples=len(frames) * 3, loop_sample=loop)

def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('MetalGreymon care recipe requires its reviewed field output')
    assert len(skeleton) == 23 and [p for _, p in skeleton] == PARENTS
    mmd.exe().skeleton[224] = skeleton
    mmd.exe().bone_count[224] = 23
    old = mmd.MMD.parse(data, 23)
    old.type = 224
    donor_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD0/MTGR.MMD'
    donor_bytes = donor_path.read_bytes()
    if hashlib.sha256(donor_bytes).hexdigest() != DONOR:
        raise ValueError('MetalGreymon care recipe requires the reviewed player-disc donor')
    src = mmd.MMD.load(str(donor_path), 12)
    result, checks, calibration, scale = _author(old, src, skeleton, mmd.exe().skeleton[12])
    actual = mmd.MMD.parse(result, 23)
    actual.type = 224
    assert old.tmd.build() == actual.tmd.build()
    changed = changed_programs(old, actual)
    assert changed == [r['slot'] for r in checks]
    for row in checks:
        slot = row['slot']
        a, b = (old.anims.anims[old.anims.table[slot]], actual.anims.anims[actual.anims.table[slot]])
        assert a.frame_count == b.frame_count
        assert [i for i in a.instrs if i['op'] != 'key'] == [i for i in b.instrs if i['op'] != 'key']
        before, loop, events = animsheet.slot_frames(old, 23, slot)
        after, new_loop, new_events = animsheet.slot_frames(actual, 23, slot)
        assert len(before) == len(after) and loop == new_loop and (events == new_events)
        assert all(p[0][6:9] == [0,0,0] for p in after), slot
        proof = contact(actual, slot)
        assert proof['maximum_floor_y'] <= 2 and proof['maximum_support_clearance'] <= 4, (slot, proof)
        row.update(proof)
        if loop is not None:
            period = len(after) - 1 - loop
            player = mmd.AnimPlayer(b, 23, slot)
            poses = []
            for _ in range(len(after) + 8 * period):
                assert player.tick()
                poses.append(copy.deepcopy(player.pose))
            for t in range(loop, len(after) - 1):
                for cycle in range(1, 8):
                    for p, q in zip(poses[t][1:], poses[t + cycle * period][1:]):
                        assert p[:3] == q[:3] and p[6:] == q[6:]
                        assert all(((x - y) % 4096 == 0 for x, y in zip(p[3:6], q[3:6])))
            row['eight_cycles_without_drift'] = True
        row.update(events_controls_duration_exact=True)
    storage = motionstorage.require(result, 23)
    return (result, dict(species=224, source_sha256=SOURCE, donor_sha256=DONOR, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=changed, kept_old_slots=FALLBACK, mesh_exact=True, calibration=calibration, native_to_target_scale=1 / scale, checks=checks, storage=storage))
