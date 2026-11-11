"""Hookmon's field clips (species 299): the imported clips kept as they are, with a few gentle corrections on top.

Hookmon (a hooked, hatted pirate captain) is an imported partner reshaped to Digimon World's proportions by `chibi.py`
(overlay `hookmon-chibi`). The reshaped clips have the right silhouette, timing and bounce; three things are off in them:
the soles slide over the floor while they should stand still (the walk's by half the travel, the tired walk's by more than
the travel), the head, the hook and the gun move as one piece with the trunk, and the idle is almost still.

`build` runs the reshaping and then rewrites slots 0 (idle, shared with 33), 2, 3 and 4 with the same number of ticks, the
same root motion and the same sounds and textures. What is touched, and nothing else:

- Soles (slots 2, 3, 4). In each stance the foot is held where it landed (the ground does not move under it, so in the
  body's frame it runs back at the body's speed). Only the thigh and the shin of that leg change, by a two-bone solve towards
  the corrected ankle; the foot keeps the world rotation the clip gave it. The ankle's offset from the original path
  is zero at touchdown, grows through the stance and is eased back to zero during the swing, so the swing keeps its
  own shape and timing, and the height of the foot is never changed.
- Follow-through (all four clips). The head trails the trunk by a tick and a half, the hook arm the shoulder, the hook
  the arm and the gun arm its shoulder: each bone's turn is delayed a little and partly carried on, never more than a
  few degrees.
- Tired walk (slot 3). The head hangs a few degrees lower and the trunk leans a little further.
- Idle (slot 0, 33). A gentle breath (the trunk and the shoulders rise and fall once per loop) which the head, hook and gun
  follow a little late.

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
from tools.models.field_animations.quadruped import mul, rot, set_rot, tr  # noqa: E402

SPECIES = 299
TORSO, HEAD, PELVIS = 1, 5, 8
LEGS = {'RH': (9, 10, 11, 1, False), 'LH': (13, 14, 15, -1, False)}
TOES = {'RH': 12, 'LH': 16}
# bone: (the bone whose turn it carries on, share of the parent's turn carried on late, delay in ticks)
FOLLOW = {5: (1, 0.30, 1.5), 2: (1, 0.40, 2.0), 3: (1, 0.30, 3.5), 4: (1, 0.30, 5.0), 6: (1, 0.40, 2.0), 7: (1, 0.30, 3.5)}
FOOT_YAW = 14
PROFILE = dict(
    species=SPECIES, name='Hookmon', source='',
    parents=[-1, 0, 1, 2, 3, 1, 1, 6, 1, 8, 9, 10, 11, 8, 13, 14, 15],
    pelvis=TORSO, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.12, 0.0, -1.0]},
    paw_flat={'RH': [0, -FOOT_YAW, 0], 'LH': [0, FOOT_YAW, 0]},
    sole={False: [0, 31, 0]}, reach={'front': 0, 'hind': 0}, fold={False: 96}, clear=0,
    speed_range={}, gaits={},
)
# per slot: how much of the stance slide is taken out (1 = planted), the extra of the tired walk
SLOTS = {
    0: dict(name='idle', breath=1.2, breath_shoulder=1.6),
    2: dict(name='walk', clear=28.0, hover=30.0, ease=3, early=1, late=2),
    3: dict(name='tired walk', clear=28.0, hover=30.0, ease=3, early=1, late=2, droop=7.0, lean=3.0),
    4: dict(name='run', clear=28.0, hover=30.0, ease=3, early=1, late=2),
}


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def turned(local, degrees):
    """A bone's local rotation matrix turned by `degrees` (x, y, z) about its parent's axes."""
    return mul(rot(degrees), local)


def lagged(series, t, delay):
    """A cyclic list of three-angle poses sampled `delay` ticks earlier (linear in the angle)."""
    n = len(series)
    x = (t - delay) % n
    i = int(math.floor(x))
    f = x - i
    a, b = series[i % n], series[(i + 1) % n]
    out = []
    for p, q in zip(a, b):
        d = (q - p + 2048) % 4096 - 2048        # the short way round
        out.append(p + d * f)
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


def still_runs(ground, height, speed, period, up, share=0.6, shortest=3):
    """The stances of one foot: runs of ticks (start, count, start in 0..period-1) in which its sole stays over the same
    spot of the ground (it moves less than `share` of the body's speed), found over several loops so they may cross the end."""
    total = 4 * period
    ext = [ground[t % period] + speed * (t // period) for t in range(total)]       # speed is the (negative) travel per loop
    still = [abs(ext[t + 1] - ext[t]) < share * abs(speed) / period and abs(ext[t] - ext[t - 1]) < share * abs(speed) / period
             for t in range(1, total - 1)]
    still = [False] + [s and height[(t + 1) % period] <= up for t, s in enumerate(still)] + [False]
    runs, t = [], period
    while t < 2 * period:
        if still[t] and not still[t - 1]:
            n = 0
            while still[t + n]:
                n += 1
            if n >= shortest:
                runs.append((t, n))
            t += n
        else:
            t += 1
    return runs, ext


def plant_feet(rig, frames, period, cfg):
    """Footfalls: each stance foot is put down at one spot, stays flat on the floor there until lift-off and leaves cleanly.

    Per foot and stance (the ball of the foot standing over one spot of the ground, see `still_runs`): from touchdown to
    lift-off the ball is held at its median place (the heel may rise about it: the toe-off) and, where the clip leaves it hovering a little, lowered onto the floor. The swing's last
    ticks before touchdown and first after lift-off carry the same offset, eased away, so the swing keeps its own shape,
    timing and height. A sole that skids low over the floor elsewhere is lifted. The leg is solved with two bones towards
    the corrected ankle with the clip's own knee direction; the foot keeps the world rotation the clip gave it.
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
        sole = [quadruped.add(a, quadruped.mv(m3, rig.sole(front))) for a, m3 in zip(ankle, pawrot)]
        root = [f[0][6:9] for f in frames[:period]]
        height = [-s[1] - r[1] for s, r in zip(sole, root)]
        ball = [[W[TOES[name]][i][3] for i in range(3)] for W in worlds]     # where the toes hinge: this is what stays put
        ground = [b[2] + r[2] for b, r in zip(ball, root)]
        off = [[0.0, 0.0, 0.0] for _ in range(period)]          # x, y (down), z of the ankle
        runs, ext = still_runs(ground, height, travel, period, 1e9)
        contacts[name] = sorted(t % period for t, n in runs)
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
                drop = height[i] - floor if height[i] - floor <= cfg['hover'] else 0.0
                # a foot that has peeled well off the floor is left to its swing: the shift fades out above the hover height
                fade = min(1.0, max(0.0, (cfg['hover'] + 14.0 - height[i]) / 14.0))
                raw.append([fade * (medx - ball[i][0]), drop, fade * (med - ext[start + k])])
            for k, i in enumerate(ticks):
                off[i] = raw[k]
            for edge, step in ((raw[0], -1), (raw[-1], 1)):
                base = start if step < 0 else start + n - 1
                for j in range(1, cfg['ease'] + 1):
                    w = 1.0 - smooth(j / float(cfg['ease'] + 1))      # the swing runs into (out of) the spot with no speed there
                    t = base + step * j
                    i = t % period
                    if i in ticks:
                        continue
                    here = off[i]
                    drift = [edge[c] * w for c in range(3)]
                    off[i] = [drift[c] if abs(drift[c]) > abs(here[c]) else here[c] for c in range(3)]
        for _ in range(1):                                          # a hover that ends inside a stance is eased
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


def idle_breath(frames, period, cfg):
    out = copy.deepcopy(frames)
    hist = {}
    for t in range(period):
        s = math.sin(2 * math.pi * t / period)
        for bone, deg in ((TORSO, [cfg['breath'] * s * 0.5, 0, 0]),
                          (2, [cfg['breath_shoulder'] * s, 0, 0]), (6, [cfg['breath_shoulder'] * s, 0, 0])):
            set_rot(out[t], bone, turned(mmd.rot_matrix(*out[t][bone][3:6]), deg), hist)
    return out


def tired(frames, period, cfg):
    out = copy.deepcopy(frames)
    hist = {}
    for t in range(period):
        set_rot(out[t], HEAD, turned(mmd.rot_matrix(*out[t][HEAD][3:6]), [cfg['droop'], 0, 0]), hist)
        set_rot(out[t], TORSO, turned(mmd.rot_matrix(*out[t][TORSO][3:6]), [cfg['lean'], 0, 0]), hist)
    return out


def rewrite(rig, frames, slot):
    cfg = SLOTS[slot]
    period = len(frames) - 1
    out = copy.deepcopy(frames)
    if slot == 0:
        out = idle_breath(out, period, cfg)
    if slot == 3:
        out = tired(out, period, cfg)
    out = follow_through(out, period)
    contacts = {}
    if slot != 0:
        out, contacts = plant_feet(rig, out, period, cfg)
    # the closing frame repeats the first; the root keeps its travel
    for b in range(1, len(out[0])):
        out[period][b] = list(out[0][b])
    return [[[round(x) for x in bone] for bone in pose] for pose in out], contacts


def retime_sounds(events, contacts, period):
    """Each footstep sound plays on its foot's touchdown tick: the clip's sounds, in order, go to the touchdowns, in order."""
    downs = sorted(t for ticks in contacts.values() for t in ticks)
    sounds = [e for e in events if e[1] == 'sound']
    if not downs or len(downs) != len(sounds):
        return events
    first = sorted(sounds)[0][0]
    # start from the touchdown closest to the first sound, so the pairing keeps the clip's order around the loop
    best = min(range(len(downs)), key=lambda i: min((downs[i] - first) % period, (first - downs[i]) % period))
    order = downs[best:] + downs[:best]
    moved = dict(zip(sorted(s[0] for s in sounds), order))
    out = []
    for t, k, e in events:
        if k == 'sound':
            e = dict(e, frame=e['frame'] + moved[t] - t)
        out.append((moved.get(t, t) if k == 'sound' else t, k, e))
    return sorted(out, key=lambda x: x[0])


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
    p.add_argument('--source', type=Path, required=True, help='the imported model (edit.py get 299)')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/299-hookmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    print(json.dumps(proof['checks'], indent=1, default=str))


if __name__ == '__main__':
    main()
