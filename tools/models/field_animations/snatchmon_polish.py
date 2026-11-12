"""Snatchmon's field clips (species 331): the imported clips kept as they are, with a few gentle corrections on top.

Snatchmon (a hooded, chained raptor with a huge head) is an imported partner reshaped to Digimon World's proportions by
`chibi.py` (overlay `snatchmon-chibi`). The reshaped walk, tired walk and run have the right pace and rhythm; what reads
as unnatural in them is:

- the chest is pitched far forward (the tired walk's lean reaches 46 degrees, the run's 56 to 66: almost horizontal) and the
  walk throws the huge head up and down by 33 units with it;
- in the run each foot is on the floor for two ticks only and spends the rest of the cycle thrown up and back behind the
  hips (82 units behind them, level with the hips), so the two hind legs trail like one stretched-out piece;
- the soles skid over the floor in the walk's right foot and in both feet of the tired walk (157 % of the body's travel);
- the head, arms, chain and tail move as one stiff piece with the chest, and the chest does not answer the hips' sway.

`build` runs the reshaping and then rewrites slots 2, 3 and 4 with the same number of ticks, the same root motion, the same
sounds and textures; the idle (slot 0, shared with 33) is not touched. What is changed, and nothing else:

- Chest (bone 1) pitch. The mean lean is lifted (tired walk 10 degrees, run 14, walk 3) and its swing about the mean is damped
  (a share of it); the hips (bone 2) are turned back by the same amount, so the pelvis, legs and tail stay exactly where the
  clip had them. The head turns back a share of the chest's change so it keeps looking where it looked.
- Chest sway. The chest answers the hips' yaw and roll with a share of the opposite turn, so the shoulders counter the hips.
- Follow-through. The head, shoulders, arms, hands, chain and tail carry on a share of their parent's turn a few ticks late.
- Soles (walk, tired walk). In each stance the foot is held where it landed, flat on the floor, and leaves with the swing eased
  in and out of the spot (see `plant_feet`); the leg is solved with two bones towards the corrected ankle and the foot keeps
  the world rotation the clip gave it.
- Run legs. A foot that is thrown up and back behind the hips is brought forward and down by a share of the excess, smoothly,
  so the swing keeps its own timing but the hind legs no longer trail behind the body.
- Footstep sounds play on the touchdown ticks.

Offline: this runs on the reshaped model inside the overlay (tools/derive's overlays step); nothing is stored but the
overlay's recipe name in content/models/imports/species.py.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.hookmon_polish import lagged, retime_sounds, smooth, still_runs, turned  # noqa: E402
from tools.models.field_animations.quadruped import mul, set_rot, tr  # noqa: E402

SPECIES = 331
CHEST, PELVIS, HEAD = 1, 2, 17
LEGS = {'RH': (6, 7, 8, 1, False), 'LH': (10, 11, 12, -1, False)}
TOES = {'RH': 9, 'LH': 13}
ARMS = {14: 'RH', 20: 'LH'}                                  # the upper arms and the hind leg of their side
FEET = {'RH': (8, 9), 'LH': (12, 13)}                       # the bones whose meshes make a sole
# bone: (the bone whose turn it carries on, share of the parent's turn carried on late, delay in ticks)
FOLLOW = {HEAD: (CHEST, 0.30, 1.5), 14: (CHEST, 0.35, 2.0), 20: (CHEST, 0.35, 2.0), 15: (14, 0.30, 2.0), 21: (20, 0.30, 2.0),
          16: (14, 0.30, 3.5), 22: (20, 0.30, 3.5), 18: (CHEST, 0.40, 2.5), 19: (CHEST, 0.35, 4.0), 4: (3, 0.35, 1.5), 5: (4, 0.35, 1.5)}
PROFILE = dict(
    species=SPECIES, name='Snatchmon', source='',
    parents=[-1, 0, 1, 2, 3, 4, 2, 6, 7, 8, 2, 10, 11, 12, 1, 14, 15, 1, 1, 18, 1, 20, 21],
    pelvis=PELVIS, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.12, 0.0, -1.0]},
    paw_flat={}, sole={False: [0, 28, 0]}, reach={'front': 0, 'hind': 0}, fold={False: 96}, clear=0,
    speed_range={}, gaits={},
)
# per slot: lift (degrees the mean chest pitch is lifted), damp (share of the chest's swing about its mean taken out),
# head (share of the chest's change the head turns back), sway (share of the hips' yaw and roll the chest turns against),
# tuck (share of a hind foot's excess behind the hips taken out), plant (feet held in their stances)
SLOTS = {
    2: dict(name='walk', arm=16.0, lift=3.0, damp=0.35, head=0.7, yaw=0.45, roll=0.35, tuck=0.0, plant=True, clear=28.0, hover=30.0, ease=5, early=0, late=2),
    3: dict(name='tired walk', arm=8.0, lift=10.0, damp=0.30, head=0.6, yaw=0.40, roll=0.30, tuck=0.0, plant=True, clear=28.0, hover=30.0, ease=5, early=0, late=2),
    4: dict(name='run', arm=24.0, lift=20.0, damp=0.25, head=0.6, yaw=0.30, roll=0.30, tuck=0.6, plant=False, clear=28.0, hover=30.0, ease=5, early=0, late=2),
}
TUCK_Z, TUCK_Y = 30.0, 56.0            # a hind foot is tucked beyond this far behind the hips / this far under them


def chest_pitch(rot_m):
    """The forward lean of a bone whose local y axis points up and whose z axis points forward-ish, in degrees."""
    return math.degrees(math.atan2(rot_m[2][1], rot_m[1][1]))


def yaw_roll(rot_m):
    return math.degrees(math.atan2(rot_m[0][2], rot_m[2][2])), math.degrees(math.atan2(rot_m[1][0], rot_m[1][1]))


def mean(xs):
    return sum(xs) / len(xs)


def body(rig, frames, period, cfg):
    """Chest pitch lifted and damped, answering the hips' sway; the pelvis, legs and tail stay where they were."""
    out = copy.deepcopy(frames)
    hist = {}
    worlds = [rig.world(f) for f in frames[:period]]
    pitch = [chest_pitch(rig.R(W, CHEST)) for W in worlds]
    hips = [yaw_roll(rig.R(W, PELVIS)) for W in worlds]
    pm, ym, rm = mean(pitch), mean([h[0] for h in hips]), mean([h[1] for h in hips])
    # each upper arm swings against the leg of its side: forward as that foot goes back (a tick late)
    swing = {}
    for arm, leg in ARMS.items():
        z = [W[LEGS[leg][2]][2][3] - W[PELVIS][2][3] for W in worlds]
        zm, half = mean(z), max(0.5 * (max(z) - min(z)), 1.0)
        swing[arm] = [-(z[(t - 1) % period] - zm) / half for t in range(period)]
    for t in range(period):
        dp = -cfg['lift'] - cfg['damp'] * (pitch[t] - pm)                    # negative: the chest comes up
        dy = -cfg['yaw'] * (hips[t][0] - ym)
        dr = -cfg['roll'] * (hips[t][1] - rm)
        l1 = mmd.rot_matrix(*frames[t][CHEST][3:6])
        l2 = mmd.rot_matrix(*frames[t][PELVIS][3:6])
        n1 = mul(quadruped.rot([dp, dy, dr]), l1)
        set_rot(out[t], CHEST, n1, hist)
        set_rot(out[t], PELVIS, mul(tr(n1), mul(l1, l2)), hist)               # the hips keep their world turn
        for arm in ARMS:
            set_rot(out[t], arm, turned(mmd.rot_matrix(*frames[t][arm][3:6]), [-cfg['arm'] * swing[arm][t], 0, 0]), hist)
        set_rot(out[t], HEAD, turned(mmd.rot_matrix(*frames[t][HEAD][3:6]), [-cfg['head'] * dp, -0.5 * dy, -0.5 * dr]), hist)
    return out


def follow_through(frames, period):
    """Delay and carry on a share of each bone's turn relative to its parent's (see FOLLOW)."""
    out = copy.deepcopy(frames)
    hist = {}
    for t in range(period):
        for bone, (parent, share, delay) in FOLLOW.items():
            now = mmd.rot_matrix(*frames[t][parent][3:6])
            past = mmd.rot_matrix(*lagged([f[parent][3:6] for f in frames[:period]], t, delay))
            extra = R.scale_rot(R.m3mul(R.m3t(now), past), share)
            set_rot(out[t], bone, mul(extra, mmd.rot_matrix(*frames[t][bone][3:6])), hist)
    return out


def legs(rig, frames, period, cfg):
    """Plant the stance feet (walk, tired walk) and tuck the hind feet thrown far behind the hips (run).
    Returns the frames and each foot's touchdown ticks."""
    worlds = [rig.world(f) for f in frames[:period]]
    result = copy.deepcopy(frames)
    hist = {}
    travel = frames[period][0][8] - frames[0][0][8]
    speed = abs(travel) / period
    contacts = {}
    for name, (up, lo, paw, side, front) in LEGS.items():
        ankle = [[W[paw][i][3] for i in range(3)] for W in worlds]
        pawrot = [rig.R(W, paw) for W in worlds]
        root = [f[0][6:9] for f in frames[:period]]
        # the lowest point of the foot's meshes, above the floor
        height = [-max(rig.lowest(b, rig.R(W, b), [W[b][i][3] for i in range(3)]) for b in FEET[name]) - r[1]
                  for W, r in zip(worlds, root)]
        ball = [[W[TOES[name]][i][3] for i in range(3)] for W in worlds]       # where the toes hinge: this is what stays put
        ground = [b[2] + r[2] for b, r in zip(ball, root)]
        off = [[0.0, 0.0, 0.0] for _ in range(period)]                        # x, y (down), z of the ankle
        runs, ext = still_runs(ground, height, travel, period, 1e9)
        contacts[name] = sorted(t % period for t, n in runs)
        if cfg['plant']:
            for start, n in runs:
                core = [(start + k) % period for k in range(n)]
                floor = max(0.0, min(height[i] for i in core))
                med = sorted(ext[start + k] for k in range(n))[n // 2]
                medx = sorted(ball[i][0] for i in core)[n // 2]
                # the foot arrives a tick before the clip's stance starts and stays a tick after it ends
                start, n = start - cfg['early'], n + cfg['early'] + cfg['late']
                ticks = [(start + k) % period for k in range(n)]
                raw = []
                for k, i in enumerate(ticks):
                    # a foot that has peeled well off the floor is left to its swing: the shift fades out above the hover height
                    fade = smooth((cfg['hover'] + 14.0 - height[i]) / 14.0)
                    raw.append([fade * (medx - ball[i][0]), fade * (height[i] - floor), fade * (med - ext[start + k])])
                for k, i in enumerate(ticks):
                    off[i] = raw[k]
                for edge, step in ((raw[0], -1), (raw[-1], 1)):
                    base = start if step < 0 else start + n - 1
                    for j in range(1, cfg['ease'] + 1):
                        w = 1.0 - smooth(j / float(cfg['ease'] + 1))          # the swing runs into (out of) the spot with no speed there
                        t = base + step * j
                        i = t % period
                        if i in ticks:
                            continue
                        here = off[i]
                        drift = [edge[c] * w for c in range(3)]
                        off[i] = [drift[c] if abs(drift[c]) > abs(here[c]) else here[c] for c in range(3)]
            off = [[0.25 * off[t - 1][c] + 0.5 * off[t][c] + 0.25 * off[(t + 1) % period][c] if c == 1 else off[t][c]
                    for c in range(3)] for t in range(period)]
            # a sole that skids along the floor outside a stance is lifted
            lift = []
            for t in range(period):
                fast = max(abs(ground[(t + 1) % period] - ground[t] + (travel if t == period - 1 else 0)),
                           abs(ground[t] - ground[t - 1] + (-travel if t == 0 else 0)))
                lift.append(max(0.0, cfg['clear'] - height[t]) if fast > 1.5 * speed else 0.0)
            for _ in range(2):
                lift = [0.25 * lift[t - 1] + 0.5 * lift[t] + 0.25 * lift[(t + 1) % period] for t in range(period)]
        else:
            lift = [0.0] * period
        if cfg['tuck']:
            for t in range(period):
                pelvis = [worlds[t][PELVIS][i][3] for i in range(3)]
                behind = ankle[t][2] - pelvis[2]                                  # behind the hips: positive
                high = -(ankle[t][1] - pelvis[1]) + TUCK_Y                         # above TUCK_Y under the hips: positive
                ramp = smooth((behind - TUCK_Z) / 30.0)
                if behind > TUCK_Z:
                    off[t][2] -= cfg['tuck'] * (behind - TUCK_Z) * ramp
                if high > 0:
                    off[t][1] += cfg['tuck'] * high * smooth(high / 30.0) * ramp
        for t in range(period):
            dx, dy, dz = off[t]
            if abs(dx) + abs(dy) + abs(dz) < 0.3 and lift[t] < 0.2:
                continue
            W = worlds[t]
            hip = [W[up][i][3] for i in range(3)]
            axis = quadruped.unit(quadruped.sub(ankle[t], hip))
            v = quadruped.sub([W[lo][i][3] for i in range(3)], hip)
            v = quadruped.unit(quadruped.sub(v, quadruped.scale(axis, quadruped.dot(v, axis))))
            target = [ankle[t][0] + dx, ankle[t][1] + dy - lift[t], ankle[t][2] + dz]       # y is down
            lower, _ = rig.solve(result[t], name, target, hist, [v[0] * side, v[1], v[2]], None)
            set_rot(result[t], paw, mul(tr(lower), pawrot[t]), hist)
    return result, contacts


def rewrite(rig, frames, slot):
    cfg = SLOTS[slot]
    period = len(frames) - 1
    out = body(rig, frames, period, cfg)
    out = follow_through(out, period)
    out, contacts = legs(rig, out, period, cfg)
    # the closing frame repeats the first; the root keeps its travel
    for b in range(1, len(out[0])):
        out[period][b] = list(out[0][b])
    return [[[round(x) for x in bone] for bone in pose] for pose in out], contacts


def build(data, skeleton):
    from tools.models.field_animations import chibi
    result, proof = chibi.build(data, skeleton)
    n = len(skeleton)
    old = mmd.MMD.parse(result, n)
    old.type = SPECIES
    new = mmd.MMD.parse(result, n)
    new.type = SPECIES
    profile = dict(PROFILE, source=hashlib.sha256(result).hexdigest())
    rig = quadruped.Rig(old, skeleton, profile)
    checks, changed_indexes = [], {}
    for slot in SLOTS:
        frames, loop, events = animsheet.slot_frames(old, n, slot)
        out, contacts = rewrite(rig, frames, slot)
        events = retime_sounds(events, contacts, len(frames) - 1)
        animation = mmd.encode_anim(out, n, loop_sample=loop, events=events, tol=0, repeats=False)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation
        changed_indexes[slot] = index
        checks.append(dict(slot=slot, gait=SLOTS[slot]['name'], ticks=len(frames), touchdowns=contacts, sounds=[t for t, k, _ in events if k == 'sound'],
                           stream_bytes=len(animation.build())))
    final = new.build()
    actual = mmd.MMD.parse(final, n)
    assert old.tmd.build() == actual.tmd.build()
    aliases = sorted(s for s, i in enumerate(old.anims.table) if i in changed_indexes.values())
    assert changed_programs(old, actual) == aliases, (changed_programs(old, actual), aliases)
    storage = motionstorage.require(final, n)
    proof = dict(proof, output_sha256=hashlib.sha256(final).hexdigest(), changed_slots=aliases, storage=storage, checks=checks,
                 resident_bytes=[storage['resident_bytes'], storage['resident_limit']])
    proof['bytes'] = [proof['bytes'][0], len(final)]
    return final, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True, help='the imported model (edit.py get 331)')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/331-vemmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    print(json.dumps(proof['checks'], indent=1, default=str))


if __name__ == '__main__':
    main()
