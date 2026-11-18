"""Omnimon's field gaits (species 461): the stored clips loosened, with the legs, root motion and floor contact kept.

The walk, tired walk and run of Omnimon were one short cycle of plain sines repeated forever: the chest turned a clean
+-10 degrees against the hips, the head hardly moved, both arms swung as mirror images of each other half a cycle apart,
the cape moved 4 to 10 degrees, and the run leaned no more than the walk. It read as a machine. The feet, however, were
good (planted, soles on the floor, native speeds), so this module keeps every bone below the pelvis, the pelvis itself and
the root motion byte for byte and rewrites only what hangs above the hips.

Each of the three gaits becomes two cycles that differ (the second lands lighter, its arms swing a little wider or
narrower, the chest turns by a different amount), joined by a slow modulation so the loop closes. Then:

* the chest (bone 1) sinks a moment after each landing (a dip and a forward nod, heavier on the first landing of the pair)
  and its turn is run through a loose spring, so it trails the hips;
* the head (bone 2) looks ahead: it takes only part of the chest's turn, late, and nods against the landings;
* both arms (3 with its forearm 4 on one side, 9 with 10 on the other) swing behind the legs with a lag and a small overshoot, the
  forearms later and wider than the shoulders, with a little roll outwards at the forward peak; the cannon arm is the steadier one;
* the cape (23, with its tail 24) streams back with the speed, swings against the chest's turn and flutters on two
  slow incommensurate waves, the tail later than the base;
* the tired walk slumps (chest and head forward, arms hanging, cape drooping) and the run leans into the stride.

`build` takes the stored model (`SOURCE`, pinned by SHA-256) and returns it with slots 2, 3 and 4 rewritten and the idle
(slot 0) given a breath and a drift in the cape; the result is stored as a plain delta (`tools/models/edit.py put 461`).
Offline: `python3 -m tools.models.field_animations.omnimon_gait --source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model
`tools/models/edit.py get 461` makes.
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
import mmd  # noqa: E402
import animsheet  # noqa: E402
import motionstorage  # noqa: E402

SPECIES = 461
SOURCE = 'e9ad56fdd357dca072f1e7f70720b74c076156f2c5b6a5c4220de9d960adc972'     # the stored model before this change
TAU = 2 * math.pi
DEG = 4096 / 360
CHEST, HEAD, CANNON, CANNON_ARM, SWORD, SWORD_ARM, CAPE, CAPE_TAIL = 1, 2, 3, 4, 9, 10, 23, 24
PITCH, YAW, ROLL, TX, TY, TZ = 3, 4, 5, 6, 7, 8

# per gait: the cycle's ticks come from the stored clip. Amplitudes are in degrees, translations in units.
GAITS = {
    2: dict(name='walk', cycles=(1.0, 0.88), nod=(1.6, 0.9), dip=(5.0, 3.0), lean=0.0, head_lean=0.0,
            arm=(0.9, 1.1), arm_lag=(0.5, 0.6), fore=1.0, roll=3.0, chest_lag=0.42, head_follow=0.30,
            cape_base=3.0, cape_swing=4.0, cape_flutter=2.5, breath=0.5, delay=1),
    3: dict(name='tired walk', cycles=(0.92, 0.78), nod=(2.2, 1.2), dip=(7.5, 4.0), lean=6.5, head_lean=9.0,
            arm=(0.85, 0.7), arm_lag=(0.42, 0.48), fore=1.0, roll=2.0, chest_lag=0.34, head_follow=0.20,
            cape_base=1.2, cape_swing=3.0, cape_flutter=1.8, breath=1.2, delay=2),
    4: dict(name='run', cycles=(1.0, 0.9), nod=(2.0, 1.2), dip=(7.0, 4.5), lean=7.5, head_lean=-3.0,
            arm=(0.86, 1.08), arm_lag=(0.7, 0.8), fore=1.0, roll=4.0, chest_lag=0.55, head_follow=0.35,
            cape_base=13.0, cape_swing=7.0, cape_flutter=4.0, breath=0.4, delay=1),
}
STEPS_PER_CYCLE = 2


ARM_BONES = {CANNON: (3, 4, 5, 6, 7), SWORD: (9, 10, 11, 12, 13, 8)}
CLEARANCE = 3.0         # units the hands and arm plates keep above the floor


class Floor:
    """The mesh of the stored model: the floor height and the lowest point of a set of bones in a pose."""

    def __init__(self, model, skeleton, frame0):
        self.model, self.skeleton = model, skeleton
        rest = [list(b) for b in frame0]
        rest[0] = [4096, 4096, 4096] + list(rest[0][3:6]) + [0, 0, 0]
        mats = mmd.bone_matrices(model, rest)
        self.floor = max(M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3]
                         for b, (oi, _) in enumerate(skeleton) if oi >= 0 for M in [mats[b]]
                         for x, y, z, _ in model.tmd.obj_verts(oi))
        self.points = {b: [(x, y, z) for x, y, z, _ in model.tmd.obj_verts(skeleton[b][0])]
                       for b in range(1, len(skeleton)) if skeleton[b][0] >= 0}

    def clearance(self, pose, bones):
        """Height above the floor of the lowest point of `bones` (negative: under it)."""
        p = [list(b) for b in pose]
        root = p[0][7]
        p[0] = [4096, 4096, 4096] + list(p[0][3:6]) + [0, 0, 0]
        mats = mmd.bone_matrices(self.model, p)
        low = -1e9
        for b in bones:
            M = mats[b]
            for x, y, z in self.points[b]:
                low = max(low, M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3])
        return self.floor - (low + root)


def keep_arms_up(frames, floor, passes=5):
    """Turn each shoulder the least that lifts its arm to `CLEARANCE` over the floor, the correction eased over the loop."""
    n = len(frames) - 1
    for shoulder, bones in ARM_BONES.items():
        for _ in range(passes):
            need = []
            for t in range(n):
                pose = frames[t]
                if floor.clearance(pose, bones) >= CLEARANCE:
                    need.append(0.0)
                    continue
                best = None
                for sign in (1, -1):
                    probe = [list(b) for b in pose]
                    probe[shoulder][PITCH] += sign * 2 * DEG
                    if best is None or floor.clearance(probe, bones) > best[1]:
                        best = (sign, floor.clearance(probe, bones))
                sign, step = best[0], 0.0
                while step < 30 * DEG:
                    step += 0.5 * DEG
                    probe = [list(b) for b in pose]
                    probe[shoulder][PITCH] += sign * step
                    if floor.clearance(probe, bones) >= CLEARANCE:
                        break
                need.append(sign * step)
            if not any(need):
                break
            # a correction is a bump: widened by a tick each side, then blurred, so it never starts or stops abruptly
            wide = [max(need[(t + d) % n] for d in (-1, 0, 1)) if need[t] >= 0 else min(need[(t + d) % n] for d in (-1, 0, 1))
                    for t in range(n)]
            wide = [max(abs(w), abs(need[(t + d) % n])) * (1 if (w or need[t]) >= 0 else -1) for t, w in enumerate(wide)
                    for d in (0,)]
            blur = [0.25 * wide[(t - 1) % n] + 0.5 * wide[t] + 0.25 * wide[(t + 1) % n] for t in range(n)]
            blur = [b if abs(b) >= abs(w) * 0.6 else w * 0.6 for b, w in zip(blur, wide)]
            for t in range(n):
                frames[t][shoulder][PITCH] = round(frames[t][shoulder][PITCH] + blur[t])
            frames[n][shoulder] = list(frames[0][shoulder])
    return frames


def spring(values, rate, damping):
    """A loose second-order follower of a cyclic sequence (run round three times so the loop settles)."""
    n = len(values)
    y, v = values[0], 0.0
    out = []
    for i in range(3 * n):
        x = values[i % n]
        v += rate * rate * (x - y) - 2 * damping * rate * v
        y += v
        out.append(y)
    return out[-n:]


def hump(x, width):
    """A smooth bump 0..1..0 over `width` ticks starting at 0, periodic handling done by the caller."""
    return math.sin(math.pi * x / width) ** 2 if 0 <= x < width else 0.0


def mean(values):
    return sum(values) / len(values)


def wrap(a):
    return (a + 2048) % 4096 - 2048


def cycle_frames(frames, cycles):
    """Cycle 0.. of the clip's single loop, the root travelling on: the closing pose included."""
    ticks = len(frames) - 1
    step = frames[-1][0][8] - frames[0][0][8]
    out = []
    for c in range(cycles):
        for pose in frames[:ticks]:
            pose = [list(b) for b in pose]
            pose[0][8] += step * c
            out.append(pose)
    closing = [list(b) for b in frames[0]]
    closing[0][8] = frames[0][0][8] + step * cycles
    out.append(closing)
    return out


def modulation(u, amps, wave):
    """A per-cycle gain: `amps` (the gain of each cycle) eased into one another by a half cosine across the loop."""
    a, b = amps
    return (a + b) / 2 + (a - b) / 2 * math.cos(TAU * u + wave)


def gait_frames(frames, events, cfg):
    ticks = len(frames) - 1
    n = ticks * 2
    out = cycle_frames(frames, 2)
    base = [[list(b) for b in pose] for pose in out[:n]]
    landings = sorted(k for k, kind, _ in events if kind == 'sound')
    land = [(c * ticks + k) % n for c in range(2) for k in landings]
    weights = [1.0, 0.75, 0.9, 0.68][:len(land)] if len(land) <= 4 else [1.0] * len(land)

    def ch(bone, k):
        return [base[t][bone][k] for t in range(n)]

    def u(t):
        return t / n

    # ---- the chest: its own turn kept, run through a spring and varied from one cycle to the next
    yaw0 = ch(CHEST, YAW)
    yaw_mean = mean(yaw0)
    gain = [modulation(u(t), cfg['cycles'], 0.4) for t in range(n)]
    yaw_dev = [(yaw0[t] - yaw_mean) * gain[t] for t in range(n)]
    lag = spring(yaw_dev, cfg['chest_lag'], 0.55)
    yaw_new = [yaw_mean + 0.45 * yaw_dev[t] + 0.55 * lag[t] for t in range(n)]
    roll0 = ch(CHEST, ROLL)
    roll_new = [r * gain[t] for t, r in enumerate(roll0)]
    roll_lag = spring([r - mean(roll0) for r in roll_new], cfg['chest_lag'], 0.5)
    roll_new = [mean(roll0) + 0.4 * (roll_new[t] - mean(roll0)) + 0.6 * roll_lag[t] for t in range(n)]
    pitch0 = ch(CHEST, PITCH)
    dip, nod = [0.0] * n, [0.0] * n
    for w, l in zip(weights, land):
        for t in range(n):
            x = (t - l - cfg['delay']) % n
            if x > ticks:
                x -= n
            dip[t] += w * hump(x, ticks * 0.55) * cfg['dip'][0] / 1.0
            nod[t] += w * hump(x, ticks * 0.55) * cfg['nod'][0]
    dip = spring(dip, 0.55, 0.45)
    nod = spring(nod, 0.55, 0.45)
    breath = [cfg['breath'] * math.sin(TAU * (t / n) * 1 + 0.5) + 0.35 * cfg['breath'] * math.sin(TAU * 3 * t / n + 1.1)
              for t in range(n)]
    pitch_add = [(nod[t] + breath[t] + cfg['lean']) * DEG for t in range(n)]
    pitch_new = [pitch0[t] + pitch_add[t] for t in range(n)]
    ty0 = ch(CHEST, TY)

    for t in range(n):
        p = out[t]
        p[CHEST][YAW] = round(yaw_new[t])
        p[CHEST][ROLL] = round(roll_new[t])
        p[CHEST][PITCH] = round(pitch_new[t])
        p[CHEST][TY] = round(ty0[t] + dip[t])

    # ---- the head: looks ahead, takes part of the chest's turn late, nods against the landings
    h_yaw, h_pitch, h_roll = ch(HEAD, YAW), ch(HEAD, PITCH), ch(HEAD, ROLL)
    chest_yaw_dev = [yaw_new[t] - yaw_mean for t in range(n)]
    chest_roll_dev = [roll_new[t] - mean(roll0) for t in range(n)]
    follow_yaw = spring(chest_yaw_dev, cfg['chest_lag'] * 0.8, 0.6)
    follow_roll = spring(chest_roll_dev, cfg['chest_lag'] * 0.8, 0.6)
    follow_pitch = spring([nod[t] * DEG for t in range(n)], 0.5, 0.5)
    for t in range(n):
        p = out[t]
        yaw_want = cfg['head_follow'] * follow_yaw[t]
        p[HEAD][YAW] = round(mean(h_yaw) + (h_yaw[t] - mean(h_yaw)) * 0.5 + yaw_want - chest_yaw_dev[t])
        p[HEAD][ROLL] = round(mean(h_roll) + (h_roll[t] - mean(h_roll)) * 0.5 + 0.2 * follow_roll[t] - chest_roll_dev[t])
        # head level on the landings (it keeps the chest's nod out), plus the gait's own droop or lift
        p[HEAD][PITCH] = round(h_pitch[t] - (cfg['lean'] * DEG + nod[t] * DEG) * 0.8 + follow_pitch[t] * 0.9
                               + cfg['head_lean'] * DEG)

    # ---- the arms: swing behind the legs, forearms later and wider, a little roll
    side = {CANNON: 0, SWORD: 1}
    for shoulder, forearm in ((CANNON, CANNON_ARM), (SWORD, SWORD_ARM)):
        k = side[shoulder]
        amp = [modulation(u(t), (cfg['arm'][0], cfg['arm'][1]) if k == 0 else (cfg['arm'][1], cfg['arm'][0]), 0.0)
               for t in range(n)]
        steady = 0.8 if shoulder == CANNON else 1.0
        sh0 = ch(shoulder, PITCH)
        fo0 = ch(forearm, PITCH)
        sm, fm = mean(sh0), mean(fo0)
        sh_dev = [(sh0[t] - sm) * (1 + (amp[t] - 1) * steady) for t in range(n)]
        fo_dev = [(fo0[t] - fm) * amp[t] * cfg['fore'] for t in range(n)]
        sh_lag = spring(sh_dev, cfg['arm_lag'][k] + 0.05 * k, 0.5)
        fo_lag = spring(fo_dev, cfg['arm_lag'][k] * 0.8, 0.38)
        sh_roll = ch(shoulder, ROLL)
        sign = 1 if shoulder == CANNON else -1
        for t in range(n):
            p = out[t]
            p[shoulder][PITCH] = round(sm + 0.25 * sh_dev[t] + 0.75 * sh_lag[t])
            p[forearm][PITCH] = round(fm + 0.15 * fo_dev[t] + 0.85 * fo_lag[t])
            p[shoulder][ROLL] = round(sh_roll[t] + sign * cfg['roll'] * DEG * sh_lag[t] / (40 * DEG))
            p[shoulder][YAW] = round(base[t][shoulder][YAW] + 0.25 * chest_yaw_dev[t] * (-1 if shoulder == CANNON else 1))

    # ---- the cape: streams with the speed, swings against the chest's turn, flutters
    cape_p0, tail_p0 = ch(CAPE, PITCH), ch(CAPE_TAIL, PITCH)
    cape_y0, tail_y0 = ch(CAPE, YAW), ch(CAPE_TAIL, YAW)
    # a positive pitch drops the cape towards the floor, so the cape only ever lifts: base streaming plus flutter, never below
    heave = spring([dip[t] * 0.12 for t in range(n)], 0.4, 0.4)
    swing = spring(chest_yaw_dev, cfg['chest_lag'] * 0.55, 0.35)
    swing_tail = spring(chest_yaw_dev, cfg['chest_lag'] * 0.4, 0.3)
    flutter = [math.sin(TAU * 3 * t / n + 0.7) + 0.6 * math.sin(TAU * 5 * t / n + 2.1) for t in range(n)]
    lift = [max(0.0, cfg['cape_base'] + heave[t] + cfg['cape_flutter'] * flutter[t] / 1.6) * DEG for t in range(n)]
    tail_lift = spring(lift, 0.38, 0.32)
    for t in range(n):
        p = out[t]
        p[CAPE][PITCH] = round(cape_p0[t] - 0.55 * lift[t])
        p[CAPE][YAW] = round(cape_y0[t] - cfg['cape_swing'] / 12 * swing[t] * 1.0)
        p[CAPE_TAIL][PITCH] = round(tail_p0[t] - 0.9 * max(tail_lift[t], 0.0))
        p[CAPE_TAIL][YAW] = round(tail_y0[t] - cfg['cape_swing'] / 9 * swing_tail[t] * 1.3)

    # the closing pose is the opening one (the loop), root excepted
    for b in range(1, len(out[0])):
        out[n][b] = list(out[0][b])
    return out


def idle_frames(frames):
    """The 78-tick idle: the stored one plus a slow breath in the chest and a drift in the cape; the feet stay."""
    n = len(frames) - 1
    out = [[list(b) for b in pose] for pose in frames]
    for t in range(n):
        s = math.sin(TAU * t / n)
        s2 = math.sin(TAU * 2 * t / n + 0.9)
        out[t][CHEST][PITCH] = round(frames[t][CHEST][PITCH] + (0.9 * s + 0.3 * s2) * DEG)
        out[t][HEAD][PITCH] = round(frames[t][HEAD][PITCH] - 0.5 * math.sin(TAU * t / n - 0.5) * DEG)
        out[t][CAPE][PITCH] = round(frames[t][CAPE][PITCH] + 1.8 * math.sin(TAU * t / n - 0.9) * DEG)
        out[t][CAPE_TAIL][PITCH] = round(frames[t][CAPE_TAIL][PITCH] + 2.6 * math.sin(TAU * t / n - 1.6) * DEG
                                         + 0.9 * math.sin(TAU * 3 * t / n) * DEG)
    out[n] = [list(out[0][b]) if b else list(frames[n][0]) for b in range(len(out[n]))]
    return out


def build(data, skeleton):
    """The stored model with its field clips loosened -> (bytes, report)."""
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Omnimon's gait requires the reviewed source")
    n = len(skeleton)
    exe = mmd.exe()
    kept = exe.skeleton[SPECIES], exe.bone_count[SPECIES]
    exe.skeleton[SPECIES] = skeleton
    exe.bone_count[SPECIES] = n
    try:
        old = mmd.MMD.parse(data, n)
        old.type = SPECIES
        new = copy.deepcopy(old)
        report = []
        for slot in (0, 2, 3, 4):
            frames, _, events = animsheet.slot_frames(old, n, slot)
            if slot == 0:
                out, events_out = idle_frames(frames), events
            else:
                cfg = GAITS[slot]
                ticks = len(frames) - 1
                out = gait_frames(frames, events, cfg)
                out = keep_arms_up(out, Floor(old, skeleton, animsheet.slot_frames(old, n, 0)[0][0]))
                events_out = [(t + c * ticks, kind, dict(e, frame=e['frame'] + c * ticks)) for c in range(2)
                              for t, kind, e in events]
            out = [[[round(x) for x in bone] for bone in pose] for pose in out]
            animation = mmd.encode_anim(out, n, loop_sample=0, events=sorted(events_out, key=lambda e: e[0]), tol=1)
            index = old.anims.table[slot]
            new.anims.anims[index] = animation
            report.append(dict(slot=slot, ticks=len(out) - 1, aliases=sorted(s for s, i in enumerate(old.anims.table) if i == index),
                               stream_bytes=len(animation.build())))
        result = new.build()
        assert old.tmd.build() == mmd.MMD.parse(result, n).tmd.build()
        storage = motionstorage.require(result, n)
    finally:
        exe.skeleton[SPECIES], exe.bone_count[SPECIES] = kept
    return result, dict(species=SPECIES, source_sha256=hashlib.sha256(data).hexdigest(),
                        output_sha256=hashlib.sha256(result).hexdigest(), clips=report, storage=storage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    skeleton = mmd.exe().skeleton[SPECIES]
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    print(json.dumps(proof, indent=1, default=str))


if __name__ == '__main__':
    main()
