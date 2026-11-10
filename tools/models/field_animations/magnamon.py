"""Magnamon's field walk, condition walk and run, authored on its bound skeleton from its own idle.

Magnamon is bound to native Leomon's skeleton and programs (native_binding.py, its recipe in
content/models/imports/native-bindings.json: boots turned forward, fists turned with the forearms, the hips set
apart so the broad armored legs pass each other). Its idle and every other program stay the binding's. Leomon's
walk and run did not suit it: they hunch the torso, crouch the run and point the toes down, and Magnamon's long
boots went through the floor.

These clips start from the idle's first frame instead (upright, legs straight, boots flat), with the arms let down
from the guard to hang relaxed, elbows a little bent. On top of it, per tick:

- Each boot lands heel first on its own track under the hip, rolls flat, and at the end of the stance peels the
  heel and pivots on the toe; in the air it travels to the next footprint on an arc that leaves and meets the
  floor at the ground's speed (no skid), the toe up before it lands. A two-bone solve on the thigh and shin
  reaches the ankle, the knee forward.
- The hips turn with the leg that swings forward, tip forward at each footfall, drop on the side of the lifted
  foot and shift over the planted one; the chest counters them a little later and breathes; the head looks ahead,
  nodding later still; the arms swing opposite to the legs, late, forward quickly and back slowly, the forearm
  trailing the upper arm and whipping through, the fist looser still.
- Nothing moves on a plain sine or in lockstep: every curve is a warped wave (upright_gait.wave) with its own
  ease (the turns, rolls and sways mirrored on the second step, so the gait does not limp), and the two sides
  differ a little (how long each boot stays down, how high it lifts, how far each arm
  swings). The amplitudes of the hips, chest and arms come close to native Leomon's.
- Both arms are let down the same way. The binding builds the left arm as the exact mirror of the right one (the
  recipe's `mirror`): the source's guard had bound each arm in a different orientation, in the idle as well. The
  shoulder armour rides on the chest, not on the upper arms (the recipe's `aim`): it sits on top of each shoulder
  with its point rising up and out, and stays there while the arms swing.
- The walk sinks into each footfall and rises over the planted boot; the condition walk is slower and heavier,
  slumped, the head low, the arms hanging; the run leans in, swings the arms hard with the elbows bent, kicks the
  heels up behind and has both feet in the air between steps.

Root speeds are the binding's field speeds (18.4, 16.25 and 41 a tick) so the boots hold still on the floor, over
cycles of 16, 14 and 10 ticks like the natives' (a stride from heel strike to toe-off the length of Leomon's).
Magnamon's thigh is short, so a small change of hip height swings its knee a long way: the planted leg keeps one
slight bend instead of crouching, and where the stride reaches past it the heel peels off the floor (pitching the
boot on its toe) rather than the knee straightening or the body dropping. The body sinks only by what a leg
still cannot reach, eased over neighbouring ticks. The knee points forward along the boot, turned by half the
hips' yaw and never by their roll, so it does not wobble in and out. The arms hang out from the hips and the
elbows stay bent, so the fists and forearms swing clear of the thigh armour.
"""
import copy
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import legik  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import native_binding  # noqa: E402
from tools.models.field_animations.upright_gait import (  # noqa: E402
    apply, leg, lift_off_floor, mul, neutral_worlds, positions, rx, ry, rz, side_variation, smooth, to_pose,
    wave)

SPECIES = 197
BODY, CHEST, HEAD, HIPS = 1, 2, 3, 11
HEAD_TIP = 4
TAIL = (12, 13, 14)
# thigh, shin, boot (ankle), side's sign in x
LEGS = [(15, 16, 17, 1), (19, 20, 21, -1)]
# upper arm, forearm, fist, side
ARMS = [(5, 6, 7, 1), (8, 9, 10, -1)]
FLOOR = (16, 17, 20, 21)
# the relaxed arm: the upper arm hangs a little out and forward, the elbow bent this far
ELBOW = 45
HANG_OUT = 0.45
REACH = 0.99
KNEE_BEND = 20          # a reference bend for the knee's plane (the idle leg is straight)

# one step differs a little from the other: how long each boot stays down, how high it lifts, how far each arm
# swings (the left foot keeps its exact half cycle: at 10 ticks a cycle any offset lands a boot between ticks)
ASYM = 0.06

GAITS = {
    # ticks and travel of one cycle (two steps); duty: of the cycle each boot is down; rock and chest_rock: the
    # pelvis and chest tipping at each footfall; whip: the forearm's late extra bend through the swing
    2: dict(ticks=16, travel=294, duty=0.55, front=0.38, lift=32, heel=6, strike=10, bob=0, settle=0, sway=6,
            yaw=7.5, roll=6, rock=9, counter=1.4, lean=3, chest_rock=7, hip_lean=1, head=0, nod=3, arm=30,
            arm_back=0.7, arm_base=4, elbow=12, whip=10, arm_out=14, lag=0.08, tail=6, crouch=2, min_bend=20,
            knee_out=0.15, drift=0, peak=0.6, unroll=0.45, peel=0.6, stance_bend=25),
    3: dict(ticks=14, travel=227.5, duty=0.56, front=0.38, lift=18, heel=6, strike=5, bob=0, settle=0, sway=7,
            yaw=5, roll=9, rock=8, counter=1.0, lean=12, chest_rock=5, hip_lean=4, head=14, nod=4, arm=14,
            arm_back=0.8, arm_base=-6, elbow=2, whip=6, arm_out=16, lag=0.12, tail=4, crouch=6, min_bend=24,
            knee_out=0.15, drift=0, peak=0.6, unroll=0.45, peel=0.6, stance_bend=30),
    4: dict(ticks=10, travel=410, duty=0.34, front=0.4, lift=34, heel=6, strike=6, bob=6, settle=0, sway=4, yaw=9,
            roll=8, rock=6, counter=1.2, lean=12, chest_rock=7, hip_lean=8, head=6, nod=5, arm=52, arm_back=0.75,
            arm_base=18, elbow=48, whip=12, arm_out=14, lag=0.06, tail=8, crouch=4, min_bend=25, knee_out=0.15,
            drift=0, peak=0.6, unroll=0.45, peel=0.6, stance_bend=30),
}


def sided(t, *shape):
    """A wave that swings to one side and back to the other the same way: the second half cycle is the first one
    mirrored, so the two steps match (a skewed or doubled wave alone would turn, tip and sway further to one side)."""
    return 0.5 * (wave(t, *shape) - wave(t + 0.5, *shape))


def _identity_root(pose):
    p = [list(b) for b in pose]
    p[0] = [4096] * 3 + [0] * 6
    return p


def boot_track(g, phase, side, toe_off):
    """Per cycle phase (0..1, the boot lands at 0): the ankle's forward offset in the body frame (forward is -z) for
    a flat boot, its lift, and the boot's pitch: positive heel up (on the toe), negative toe up (on the heel)."""
    duty = g['duty'] * side_variation(side, 0.02)
    stride = g['travel'] * duty
    front = stride * g['front']
    t = phase % 1.
    if t < duty:
        s = t / duty
        pitch = g['heel'] * smooth((s - g['peel']) / (1 - g['peel'])) - g['strike'] * (1 - smooth(s / 0.2))
        return -front + stride * s, 0., pitch, s
    u = (t - duty) / (1 - duty)
    # an arc that leaves and meets the floor at the ground's speed under the body (no skid at the toe-off or the
    # landing): the boot keeps drifting back a moment after the toe-off and draws back a little before it lands
    duration, start, end = 1 - duty, stride - front, -front
    speed = g['travel'] * duration * g['drift']
    z = (2 * u**3 - 3 * u**2 + 1) * start + (u**3 - 2 * u**2 + u) * speed + (3 * u**2 - 2 * u**3) * end \
        + (u**3 - u**2) * speed
    lift = g['lift'] * side_variation(side, ASYM) * math.sin(math.pi * min(1., u ** g['peak']))
    # the heel the boot left the floor with comes down through the swing
    pitch = toe_off * (1 - smooth(u / g['unroll']))
    pitch -= g['strike'] * smooth((u - 0.6) / 0.4)
    return z, lift, pitch, None


def relaxed_arms(rig, neutral, pos):
    """The idle's arm rotations turned down from the guard: each upper arm hangs a little out and forward, each
    forearm bent forward by ELBOW; the fists keep their turn on the forearm."""
    out = dict(neutral)
    for upper, fore, fist, side in ARMS:
        cur = [pos[fore][i] - pos[upper][i] for i in range(3)]
        hang = R.m3mul(R.swing(cur, [HANG_OUT * side, 1, -0.08]), neutral[upper])
        out[upper] = hang
        cur = apply(R.m3mul(hang, R.m3t(neutral[upper])), [pos[fist][i] - pos[fore][i] for i in range(3)])
        want = apply(rx(-ELBOW), [0.12 * side, 1, 0])
        out[fore] = R.m3mul(R.swing(cur, want), R.m3mul(hang, R.m3mul(R.m3t(neutral[upper]), neutral[fore])))
        out[fist] = R.m3mul(out[fore], R.m3mul(R.m3t(neutral[fore]), neutral[fist]))
    return out


def build(data, skeleton):
    bound, proof = native_binding.build(data, skeleton)
    rig = proof['generated_skeleton']
    nb = len(rig)
    mmd.exe().add_type(SPECIES, rig)
    model = mmd.MMD.parse(bound, nb)
    model.type = SPECIES
    reference = animsheet.slot_frames(model, nb, 0)[0][0]
    offsets = {b: list(reference[b][6:9]) for b in range(1, nb)}
    neutral = neutral_worlds(rig, reference)
    carrier = list(reference[BODY][6:9])
    npos = positions(rig, offsets, neutral, BODY, carrier)
    rest = relaxed_arms(rig, neutral, npos)
    # the boots' toe and heel on the floor, relative to the ankle
    w = mmd.bone_matrices(model, _identity_root(reference))
    contacts = {}
    for thigh, shin, foot, side in LEGS:
        verts = [[sum(w[foot][i][j] * v[j] for j in range(3)) + w[foot][i][3] for i in range(3)]
                 for v in model.tmd.obj_verts(rig[foot][0])]
        floor = max(v[1] for v in verts)
        sole = [v for v in verts if v[1] > floor - 8]
        toe, heel = min(sole, key=lambda v: v[2]), max(sole, key=lambda v: v[2])
        contacts[foot] = ([toe[i] - npos[foot][i] for i in range(3)], [heel[i] - npos[foot][i] for i in range(3)])
    # the body height that puts the idle's soles on the floor
    stand = carrier[1] - max(sum(w[f][1][j] * v[j] for j in range(3)) + w[f][1][3]
                             for _, _, f, _ in LEGS for v in model.tmd.obj_verts(rig[f][0]))
    assert all(abs(npos[b][i] - w[b][i][3]) < 1 for b in npos for i in range(3))
    result = copy.deepcopy(model)
    checks, streams = {}, {}
    for slot, g in GAITS.items():
        n = g['ticks']
        # the planted leg keeps at least a slight bend (min_bend): where the boots are far apart the body sinks
        # just enough for it, eased over the neighbouring ticks, instead of pumping the knees through a crouch
        longest = [math.sqrt(a * a + b * b + 2 * a * b * math.cos(math.radians(g['min_bend'])))
                   for a, b in [(legik.norm(offsets[shin]), legik.norm(offsets[foot])) for _, shin, foot, _ in LEGS]]
        sink = [0.] * n
        # the stance leg's length behind the hip (its knee kept at stance_bend)
        planted = math.sqrt(sum(v * v for v in offsets[LEGS[0][1]]) + sum(v * v for v in offsets[LEGS[0][2]])
                            + 2 * legik.norm(offsets[LEGS[0][1]]) * legik.norm(offsets[LEGS[0][2]])
                            * math.cos(math.radians(g['stance_bend'])))
        toe_off = {foot: g['heel'] for _, _, foot, _ in LEGS}
        for _ in range(2):
            need = [0.] * n
            latest = dict(toe_off)
            history, frames, reach = {}, [], 0.
            for tick in range(n + 1):
                t = (tick % n) / n
                # one step differs a little from the other
                step = 1 + ASYM * math.cos(2 * math.pi * t)
                # the hips turn with the leg going forward, quickly after the footfall and slowly back; the chest
                # counters them a little later
                yaw = g['yaw'] * sided(t, 0., 0.2, 0.12)
                late = g['yaw'] * sided(t, 0.07, 0.2, 0.12)
                # the walk sinks only while both boots are down (where the legs reach furthest) and comes back to the
                # idle's height over the planted boot; the run is low mid-stance and high in the air
                dip = wave((2 * t) % 1., g['duty'] % 1., 0.25) * step
                bob = g['bob'] * dip if slot == 4 else g['bob'] * 0.5 * (1 - dip)
                bob += g['settle'] * max(0., math.cos(4 * math.pi * (t - 0.06))) ** 4
                # the pelvis tips forward as the weight lands and back as the body passes over the foot
                rock = g['rock'] * wave((2 * t) % 1., 0.12, 0.3) * step
                # over the planted boot; the hip of the lifted leg drops quickly and comes back slowly
                sway = g['sway'] * sided(t, 0.28, 0.2)
                roll = -g['roll'] * sided(t, 0.3, 0.35, 0.2)
                breath = 0.8 * wave(t, 0.4, 0.4)
                worlds = dict(rest)
                worlds[HIPS] = mul(ry(yaw), rz(roll), rx(g['hip_lean'] + rock), rest[HIPS])
                turn = ry(-g['counter'] * late)
                chest = mul(turn, rx(g['lean'] + g['chest_rock'] * wave((2 * t) % 1., 0.22, 0.3) * step + breath))
                worlds[CHEST] = mul(chest, rest[CHEST])
                # the head keeps looking ahead, nodding against the bob a little after the chest
                worlds[HEAD] = mul(ry(0.2 * g['yaw'] * sided(t, 0.15, 0.2)),
                                   rx(g['head'] + g['nod'] * wave((2 * t) % 1., 0.3, 0.3)), rest[HEAD])
                worlds[HEAD_TIP] = mul(worlds[HEAD], R.m3t(rest[HEAD]), rest[HEAD_TIP])
                for upper, fore, fist, side in ARMS:
                    # opposite to the leg of the same side, late; forward quickly, back slowly, further forward than
                    # back; both shoulders turn with the chest, so they stay level
                    # the left arm runs the right one's curve half a cycle later (not mirrored in sign, which would
                    # swap its quick and slow halves)
                    half = 0. if side > 0 else 0.5
                    swing = -wave(t, g['lag'] + half, 0.3, 0.1)
                    amount = g['arm'] * side_variation(side, 0.2 * ASYM) * (swing if swing > 0 else g['arm_back'] * swing)
                    arm = mul(turn, rx(-(g['arm_base'] + amount)), rz(-side * g['arm_out']))
                    worlds[upper] = mul(arm, rest[upper])
                    # the elbow bends more on the way forward and the forearm trails the upper arm, then whips through
                    follow = -wave(t, g['lag'] + 0.1 + half, 0.35)
                    bend = g['elbow'] + 0.3 * max(0., amount) + g['whip'] * 0.5 * (1 + follow)
                    hinge = mul(worlds[upper], R.m3t(rest[upper]))
                    elbow = mul(hinge, rx(-bend), R.m3t(hinge))
                    worlds[fore] = mul(elbow, hinge, rest[fore])
                    # the fist hangs loose: it lags the forearm a little more
                    wrist = mul(worlds[fore], R.m3t(rest[fore]))
                    flick = mul(wrist, rx(0.4 * g['whip'] * wave(t, g['lag'] + 0.2 + half, 0.3)), R.m3t(wrist))
                    worlds[fist] = mul(flick, worlds[fore], R.m3t(rest[fore]), rest[fist])
                parent = worlds[HIPS]
                for i, b in enumerate(TAIL):
                    worlds[b] = mul(ry(-g['tail'] * (1 + 0.35 * i) * sided(t, 0.11 + 0.09 * i, 0.3)),
                                    parent, R.m3t(rest[rig[b][1]]), rest[b])
                    parent = worlds[b]
                body = [carrier[0] + sway, stand + g['crouch'] + bob + sink[tick % n], carrier[2]]
                pos = positions(rig, offsets, worlds, BODY, body)
                for thigh, shin, foot, side in LEGS:
                    z, lift, pitch, stance = boot_track(g, t if side > 0 else t + 0.5, side, toe_off[foot])
                    ankle = [npos[foot][0], npos[foot][1] - (carrier[1] - stand) - lift, npos[foot][2] + z]
                    hip = pos[thigh]
                    l1, l2 = legik.norm(offsets[shin]), legik.norm(offsets[foot])

                    def place(pitch):
                        # the boot turns about its toe (heel up) or its heel (toe up), which stays where it was
                        pivot = contacts[foot][0] if pitch > 0 else contacts[foot][1]
                        turned = apply(rx(pitch), pivot)
                        return [ankle[i] + pivot[i] - turned[i] for i in range(3)]
                    target = place(pitch)
                    if (stance is None or stance > 0.3) and legik.norm(legik.sub(place(pitch), hip)) > planted:
                        # behind the hip the planted leg stays at its slight bend and the heel peels off the
                        # floor as far as that needs, like a native's straight push-off
                        low, high = pitch, 60.
                        for _ in range(24):
                            mid = (low + high) / 2
                            low, high = (mid, high) if legik.norm(legik.sub(place(mid), hip)) > planted else (low, mid)
                        pitch = high
                        target = place(pitch)
                        if stance is not None:
                            latest[foot] = pitch
                    boot = rx(pitch)
                    reach = max(reach, legik.norm(legik.sub(target, hip)) / (l1 + l2))
                    across = (target[0] - hip[0]) ** 2 + (target[2] - hip[2]) ** 2
                    depth = math.sqrt(max(0., longest[side < 0] ** 2 - across))
                    need[tick % n] = max(need[tick % n], target[1] - hip[1] - depth + sink[tick % n])
                    # the idle leg is straight: its knee plane is the one it bends in, forward about x
                    knee0 = npos[shin]
                    bent = rx(KNEE_BEND)
                    ankle0 = [knee0[i] + apply(bent, [npos[foot][j] - knee0[j] for j in range(3)])[i] for i in range(3)]
                    # the knee points forward and a little out, turning with half the hips' yaw only (the pelvis
                    # roll would swing it in and out)
                    pole = apply(ry(0.5 * yaw), [g['knee_out'] * side, 0, -1])
                    worlds[thigh], worlds[shin] = leg(hip, target, l1, l2, pole, [npos[thigh], knee0, ankle0],
                                                      [rest[thigh], mul(bent, rest[shin])])
                    worlds[foot] = mul(boot, rest[foot])
                    for b in range(nb):
                        if rig[b][1] == foot:
                            worlds[b] = mul(worlds[foot], R.m3t(rest[foot]), rest[b])
                frames.append(to_pose(rig, reference, worlds, BODY, body, g['travel'] * tick / n, history))
            # the sink each tick needs, widened to its neighbours and eased (never less than needed)
            toe_off = latest
            wide = [max(need[(i + k) % n] for k in range(-2, 3)) for i in range(n)]
            sink = [sum(w * wide[(i + k) % n] for k, w in zip(range(-2, 3), (1, 4, 6, 4, 1))) / 16 for i in range(n)]
        assert reach < REACH, (slot, reach)
        frames, lift = lift_off_floor(model, rig, frames, FLOOR, BODY)
        sounds = [(t, 'sound', {'op': 'sound', 'frame': t + 1, 'bank': 1, 'note': 16}) for t in (0, round(n / 2))]
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(frames, nb, 0, sounds, tol=1, repeats=False))
        checks[slot] = dict(ticks=n, speed=round(g['travel'] / n, 2), reach=round(reach, 3),
                            maximum_body_lift=round(lift, 1))
    for slot, stream in streams.items():
        result.anims.table[slot] = stream
    output = result.build()
    effective = mmd.MMD.parse(output, nb)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert changed == [2, 3, 4], changed
    return output, dict(proof, output_sha256=hashlib.sha256(output).hexdigest(), field_checks=checks,
                        changed_slots=changed, storage=motionstorage.require(output, nb))
