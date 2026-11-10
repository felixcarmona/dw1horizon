"""Apemon: a grounded gorilla idle and a heavy knuckle walk, tired walk and gallop.

Keeps the 93/20/43/20/20-tick programs. All four limbs are solved per tick, so
every planted hand and foot stays fixed in the world. The torso is driven by
the limbs: the pelvis and chest twist against each other, the body sways over
the loaded side and dips at each landing, the head stays level and looks
around. Idle: breathing, a slow weight shift, head look and one fist lift; no
hop. Walk/condition/run travel 20/14/35 units per tick with three/one/two
gait cycles. Four ordinary MMD limb chains support movement.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motionsecondary
import motioncyclelayer
import motionstorage
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.aero_veedramon import _forward
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

SOURCE = '84c1382c0bd1c7c5ac24b291611aab8a833e8042d8b9102aca96e92006665883'   # the model before this pass (see README)
PARENTS = [-1, 9, 1, 1, 3, 4, 1, 6, 7, 0, 9, 10, 11, 9, 13, 14, 1]

def _parse(data, sk):
    mmd.exe().skeleton[227] = sk
    mmd.exe().bone_count[227] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 227
    return model



def _axis(axis, degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    m = np.eye(3)
    m[i, i] = m[j, j] = c
    m[i, j], m[j, i] = -s, s
    return m


def _step(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _impact(p, width):
    """Zero at touchdown, a peak at `width`, gone after about four widths."""
    x = p / width
    return x * math.exp(1 - x)


# Limb order: (hip, knee, foot, front, right, phase offset) per slot. Walk: diagonal sequence (hind foot, then the
# opposite hand); run: gallop (hands together, hind feet together half a cycle later).
LIMBS = {
    2: [(10, 11, 12, False, 1, 0.0), (13, 14, 15, False, -1, 0.51), (3, 4, 5, True, 1, 0.76), (6, 7, 8, True, -1, 0.26)],
    3: [(10, 11, 12, False, 1, 0.0), (13, 14, 15, False, -1, 0.51), (3, 4, 5, True, 1, 0.76), (6, 7, 8, True, -1, 0.26)],
    4: [(10, 11, 12, False, 1, 0.0), (13, 14, 15, False, -1, 0.5), (3, 4, 5, True, 1, 0.75), (6, 7, 8, True, -1, 0.26)],
}
GAIT = {  # duty, front/hind lift, rock, hip height, front/hind centre z, hand/foot x
    2: dict(duty=0.62, hind=0.57, lift=(26, 16), rock=(4, 6), ankle=(9, 20, 0.0, 0.4), height=-142, lean=20, zc=(-62, 58), xc=(105, 72)),
    3: dict(duty=0.7, hind=0.6, lift=(14, 10), rock=(2, 3), ankle=(4, 12, 0.7, 0.4), height=-136, lean=18, zc=(-52, 52), xc=(105, 72)),
    4: dict(duty=0.32, hind=0.32, lift=(44, 24), rock=(5, 7), ankle=(6, 24, 0.0, 0.5), height=-156, lean=22, zc=(-70, 62), xc=(105, 72)),
}



def _land(k, cycles, sign, salt):
    """Where a planted foot of side `sign` lands in stride `k`, relative to its stride centre: a fixed offset per side plus a
    little difference from stride to stride (periodic in the loop's strides)."""
    return 3 * sign + 2.5 * math.sin(2.1 * (k % cycles) + salt * sign)


def _hind(g, slot, sign, p, u, half, zc, xc, period, contact, speed, tau, k, cycles):
    """One hind foot: where it is (z, x), how far the mesh is lifted and the ankle pitch, at gait phase p.

    Heel strike, flat foot, heel lift and toe push-off; a swing that starts from the ground's own speed, lifts early, peaks
    at about 38% and lands with the toe up. Each side has its own length, height and timing (a few percent), and the
    strides in one loop differ a little, all periodic in the loop."""
    duty = g['hind']
    heel, toe, drag, carry = g['ankle']
    side = 1 if sign > 0 else -1
    height = 1 + 0.06 * side + 0.08 * math.sin(tau * u * (1 if slot == 4 else 2) + (1.9 if side > 0 else 0.4))
    land = _land(k, cycles, sign, 0.7)
    if p <= duty:
        zc = zc + land
        s = p / duty
        z = zc - half + speed * p * period
        # heel first, flat, then the heel leaves and the toes push
        pitch = -heel * (1 - _step(s / 0.2)) + toe * _step((s - 0.62) / 0.38) ** 1.4
        return z, xc, 4 + 0 * s, pitch
    q = (p - duty) / (1 - duty)
    zc = zc + land + (_land(k + 1, cycles, sign, 0.7) - land) * _step(q)
    ts = period - contact
    v = speed * ts * carry
    z0, z1 = zc + half, zc - half
    h00, h10 = 1 - 10 * q ** 3 + 15 * q ** 4 - 6 * q ** 5, q - 6 * q ** 3 + 8 * q ** 4 - 3 * q ** 5
    h01, h11 = 10 * q ** 3 - 15 * q ** 4 + 6 * q ** 5, -4 * q ** 3 + 7 * q ** 4 - 3 * q ** 5
    z = h00 * z0 + h10 * v + h01 * z1 + h11 * v
    # lift peaks early (about 38% of the swing), the foot comes down more gently than it went up
    k = 0.716
    up = 4 + g['lift'][1] * height * math.sin(math.pi * q ** k) ** 1.3
    x = xc + 5 * math.sin(math.pi * q ** 0.8) ** 2
    hold = drag * (1 - _step((q - 0.15) / 0.7))
    pitch = toe * (1 - _step(q / 0.55)) * (1 - drag) + hold * toe - heel * _step((q - 0.4) / 0.6) ** 1.5
    return z, x, up, pitch

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native = animsheet.slot_frames(old, n, 33)[0]
    vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = copy.deepcopy(native[0])
    for a, b in [(3, 6), (4, 7), (5, 8), (10, 13), (11, 14), (12, 15)]:
        ref[b][3:6] = [ref[a][3], -ref[a][4], -ref[a][5]]
    rw = world(ref)
    # the standing pose every clip starts from: slot 1's chest, head and hip
    stand = animsheet.slot_frames(old, n, 1)[0][0]
    reports = []
    for slot in [0, 2, 3, 4]:
        template = slot
        fs, loop, events = animsheet.slot_frames(old, n, template)
        duration = len(fs) - 1
        cycles = {0: 1, 1: 1, 2: 3, 3: 1, 4: 2}[slot]
        period = duration / cycles
        speed = {0: 0, 1: 0, 2: 20, 3: 14, 4: 35}[slot]
        duty = GAIT[slot]['duty'] if slot in GAIT else 1
        contact = period * duty
        poses = []
        hist = {}
        errors = []
        pz = {}
        clipped = []
        def limb(f, hip, knee, foot, x, z, rf, up, front, t=0):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, t, hip, 'XZreach', reach)
            low = h[1] + max(1, math.sqrt(max(0, (abs(a - b) + 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2)))
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            sign = 1 if hip in [3, 10] else -1
            pole = np.array([sign, 0, -0.2 if front else pz.get(hip, 0 if slot == 2 and hip == 10 else -0.5)])

            def solve(y):
                goal[1] = y
                delta = goal - h
                dist = np.linalg.norm(delta)
                direction = delta / dist
                pp = pole - direction * (pole @ direction)
                pp /= np.linalg.norm(pp)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + direction * along + pp * math.sqrt(max(0, a * a - along * along))
                rh, rs = map(np.array, motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [rw[v, :3, :3].tolist() for v in [hip, knee]]))
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
                return (bottom + lift[0], rh, rs)
            lift = [up]
            if solve(low)[0] > 0:          # a leg cannot fold higher than the body allows: lift as much as it can
                clipped.append(lift[0])
                lift[0] -= solve(low)[0] + 0.5
                clipped[-1] -= lift[0]
            assert solve(low)[0] <= 0 <= solve(high)[0], (slot, t, hip, 'Yreach', solve(low)[0], solve(high)[0], h, goal)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            _, rh, rs = solve((low + high) / 2)
            set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errors.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))

        def turn(f, bone, delta):
            """Rotate `bone` by the world rotation `delta` (about its own joint), keeping its parent's."""
            w = world(f)
            pw = w[sk[bone][1], :3, :3]
            local = np.array(mmd.rot_matrix(*f[bone][3:6]))
            set_rotation(f, bone, pw.T @ delta @ pw @ local, hist)

        def gaze(f, yaw, pitch, roll=0):
            """Point the head `yaw`/`pitch` degrees off its standing direction, whatever the body above does."""
            w = world(f)
            base = world(stand_g)
            local = np.array(mmd.rot_matrix(*f[2][3:6]))
            target = _axis(1, yaw) @ _axis(0, pitch) @ _axis(2, roll) @ base[2, :3, :3]
            set_rotation(f, 2, w[1, :3, :3].T @ target, hist)

        stand_g = copy.deepcopy(stand)
        stand_g[0] = [4096] * 3 + [0] * 6
        stand_g[16][3:6] = [-482, -9, -243]   # the staff upright on the unleaned body (the pose it was carried from)
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            # --- every clip: standing chest/head/hip, the staff carried above the limbs
            for bone in (9, 1, 2):
                f[bone][3:6] = stand[bone][3:6]
            f[9][6:9] = [stand[9][6], 0, stand[9][8]]
            for b in (3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16):
                f[b][6:9] = stand[b][6:9]
            f[16][6:9] = [stand[16][6] - 6, stand[16][7] + 9, stand[16][8] - 22]   # lowered onto the back: it rests on the body instead of hovering
            u = t / duration
            tau = 2 * math.pi
            targets = {}
            if slot == 0:
                # idle: grounded, no hop. Breathing, one slow weight shift, head look, one fist lift.
                shift = math.sin(tau * u)
                breath = math.sin(tau * 3 * u)
                f[9][7] = round(-136 + 0.6 * breath - 0.6 * math.cos(tau * 2 * u))
                f[9][6] += round(6 * shift)
                turn(f, 9, _axis(2, -1.6 * shift) @ _axis(1, 2.5 * math.sin(tau * u + 0.6)))
                turn(f, 1, _axis(0, 12 + 1.8 * breath) @ _axis(2, 1.2 * shift) @ _axis(1, -2.5 * math.sin(tau * u + 0.6)))
                look = 24 * math.sin(tau * u + 0.3) * (0.55 + 0.45 * math.sin(tau * 2 * u + 1.0))
                nod = -6 + 4 * math.sin(tau * 2 * u + 0.2) - 4 * breath
                gaze(f, look, nod)
                lift = _step((u - 0.52) / 0.10) * (1 - _step((u - 0.70) / 0.10))
                for side, (hip, knee, foot, front) in enumerate([(10, 11, 12, False), (13, 14, 15, False), (3, 4, 5, True), (6, 7, 8, True)]):
                    sign = 1 if side % 2 == 0 else -1
                    xc, zc = (105, -58) if front else (72, 58)
                    up = 4
                    dz = 0
                    if front and sign < 0:
                        up += 52 * lift
                        dz = -28 * lift
                        xc -= 40 * lift
                    rf, dzr, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, 0, 0]).tolist(), 0)
                    targets[hip] = (sign * xc, zc + dz + dzr, np.array(rf), up, front)
            else:
                g = GAIT[slot]
                half = speed * contact / 2
                phases = {}
                dty = {}
                reach = {}
                for hip, knee, foot, front, sign, off in LIMBS[slot]:
                    ft = 0 if front else 1
                    p = (cycles * u - off) % 1.0
                    ph = p * period
                    zc, xc = g['zc'][ft], g['xc'][ft]
                    rock = g['rock'][ft]
                    if front:
                        k = math.floor(cycles * u - off)
                        zf = _land(k, cycles, sign, 2.0)
                        zn = _land(k + 1, cycles, sign, 2.0)
                        if p <= duty:
                            z = zc - half + speed * ph + zf
                            pitch = -rock * math.cos(math.pi * p / duty)
                            up = 4
                            x = xc
                        else:
                            q = (p - duty) / (1 - duty)
                            smooth = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                            z = zc + zf + (zn - zf) * smooth + half * (1 - smooth) - half * smooth + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                            x = xc + 4 * math.sin(math.pi * q) ** 2
                            up = 4 + g['lift'][ft] * (1 + 0.08 * sign + 0.05 * math.sin(tau * u + 1.3 + sign)) * math.sin(math.pi * q) ** 1.5
                            pitch = rock * math.cos(math.pi * q) + 5 * math.sin(math.pi * q) ** 2
                    else:
                        z, x, up, pitch = _hind(g, slot, sign, p, u, speed * period * g['hind'] / 2, zc, xc, period, period * g['hind'], speed, tau, math.floor(cycles * u - off), cycles)
                    phases[hip] = (p, front, sign)
                    dty[hip] = duty if front else g['hind']
                    if not front:
                        # the hock trails the foot: the knee swings forward late and settles back after touchdown
                        d = g['hind']
                        pz[hip] = -0.5 + (0.3 * math.sin(math.pi * ((p - d) / (1 - d)) ** 1.3) if p > d else -0.15 * (1 - _step(p / 0.25)))
                    reach[hip] = -(z - zc) / max(half, 1)
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, 0, 0]).tolist(), pitch)
                    targets[hip] = (sign * x + (0 if front else stand[9][6] + 4), z + dz, np.array(rf), up, front)   # the hind feet centre on the pelvis, which sits a little left of the origin
                e = 0.09
                load = {h: _step(p / e) - _step((p - dty[h]) / e) for h, (p, fr, sg) in phases.items()}
                hit = {h: (_impact(p, 0.06) if p < dty[h] else 0.0) * (1.5 if fr else 1.0) for h, (p, fr, sg) in phases.items()}
                hands, feet = [3, 6], [10, 13]
                push = sum(_step((p / dty[h] - 0.7) / 0.3) * (p < dty[h]) for h, (p, fr, sg) in phases.items() if not fr)
                hroll = sum(load[h] * phases[h][2] for h in (10, 13)) / 2
                pelvis_yaw = (reach[10] - reach[13]) / 2
                chest_yaw = (reach[3] - reach[6]) / 2
                loaded = sum(load[h] * phases[h][2] for h in load) / 2
                dip = sum(hit.values())
                if slot == 2:
                    f[9][7] = round(g['height'] + 5 * dip - 2 * (sum(load.values()) - 2) - 2 * push)
                    f[9][6] += round(10 * loaded)
                    turn(f, 9, _axis(1, 7 * pelvis_yaw) @ _axis(2, 2.5 * loaded + 1.5 * hroll) @ _axis(0, 1.0 * dip - 0.8 * push))
                    turn(f, 1, _axis(1, 10 * chest_yaw) @ _axis(2, 4 * loaded) @ _axis(0, g['lean'] + 2.0 * dip + 2.0 * math.cos(tau * cycles * u)))
                    gaze(f, 6 * math.sin(tau * cycles * u + 1.0), -6 + 2 * dip)
                elif slot == 3:
                    f[9][7] = round(g['height'] + 8 * dip - 3 * (sum(load.values()) - 2) - 1.5 * push)
                    f[9][6] += round(12 * loaded)
                    turn(f, 9, _axis(1, 8 * pelvis_yaw) @ _axis(2, 3.5 * loaded + 1.5 * hroll) @ _axis(0, 2.0 * dip - 0.8 * push))
                    turn(f, 1, _axis(1, 11 * chest_yaw) @ _axis(2, 5 * loaded) @ _axis(0, g['lean'] + 3 * dip))
                    gaze(f, 3 * math.sin(tau * u + 0.5), 8 + 3 * dip)
                else:
                    air = math.cos(tau * 2 * (cycles * u - 0.4))
                    f[9][7] = round(g['height'] - 11 * air + 3 * dip - 1.5 * push)
                    f[9][6] += round(5 * loaded)
                    pitch = -6 * math.cos(tau * (cycles * u - 0.06))
                    turn(f, 9, _axis(0, 2 + 0.5 * pitch) @ _axis(1, 4 * pelvis_yaw) @ _axis(2, 2 * loaded))
                    turn(f, 1, _axis(0, g['lean'] + pitch) @ _axis(1, 6 * chest_yaw) @ _axis(2, 3 * loaded))
                    gaze(f, 4 * math.sin(tau * cycles * u + 1.0), -4 - 0.8 * pitch)
            set_rotation(f, 16, np.array(mmd.rot_matrix(*stand[16][3:6])), hist)  # the staff lies across the back as it always did, riding the chest
            for hip, knee, foot, front in [(10, 11, 12, False), (13, 14, 15, False), (3, 4, 5, True), (6, 7, 8, True)]:
                x, z, rf, up, fr = targets[hip]
                limb(f, hip, knee, foot, x, z, rf, up, fr, t)
            f[0][6:9] = [0, 0, -speed * t]
            poses.append(f)
        for b in range(1, n):
            assert np.max(np.abs(np.array(mmd.rot_matrix(*poses[0][b][3:6])) - np.array(mmd.rot_matrix(*poses[-1][b][3:6])))) < 0.01, (slot, b, 'closure')
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        limbc = {(b, c) for b in [3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15] for c in [3, 4, 5]}
        channels = {(9, c) for c in (3, 4, 5, 6, 7)} | {(0, 6), (0, 7)} | {(b, c) for b in (1, 2) for c in (3, 4, 5)} | {(16, c) for c in [3, 4, 5, 6, 7, 8]} | {(10, 6)} | limbc
        authored = replace_channels(old.anims.anims[old.anims.table[template]], poses, loop, n, channels)
        footsteps = []
        if slot in [2, 3, 4]:
            authored = _forward(authored, -speed * duration, duration)
            authored.instrs = [i for i in authored.instrs if i['op'] != 'sound']
            sound = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            footsteps = [round(j * duration / (2 * cycles)) for j in range(2 * cycles)]
            for tick in footsteps:
                event = dict(sound, frame=tick + 1)
                at = next((i for i, k in enumerate(authored.instrs) if k.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, event)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, source_template=template, duration=duration, cycles=cycles, gait_period=period, contact=contact, speed=speed, footstep_ticks=footsteps, channels=sorted(channels), maximum_FK_contact_error=max(errors, default=0), maximum_lift_clipped=max(clipped, default=0)))
    return (new, reports)


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1,16))):
        raise ValueError('Apemon requires the reviewed17-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old,actual) == [0,2,3,4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    stand = animsheet.slot_frames(old, 17, 1)[0][0]
    limbs = [3,4,5,6,7,8,10,11,12,13,14,15]
    for row in solver:
        slot, template, duration = row['slot'],row['source_template'],row['duration']
        src = old.anims.anims[old.anims.table[template]]
        dst = actual.anims.anims[actual.anims.table[slot]]
        channels = {tuple(c) for c in row['channels']}
        fs,loop,events = animsheet.slot_frames(actual,17,slot)
        original,oloop,oevents = animsheet.slot_frames(old,17,template)
        assert len(fs) == len(original) == duration+1 and loop == oloop == 0
        assert [i for i in src.instrs if i['op'] not in ('key','sound')] == [i for i in dst.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e) for t,k,e in events if k != 'sound'] == [(t,k,e) for t,k,e in oevents if k != 'sound']
        before,after = mmd.AnimPlayer(src,17,template),mmd.AnimPlayer(dst,17,slot)
        cycle = []
        fixed = None
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert after.root[:2] == [0,0]
            for bone in range(1,17):
                assert before.pose[bone][:3] == after.pose[bone][:3]
                for c in range(9):
                    if (bone,c) not in channels:
                        assert before.pose[bone][c] == after.pose[bone][c],(slot,tick,bone,c)
            translations = [after.pose[b][6:9] for b in limbs]
            if fixed is None: fixed = copy.deepcopy(translations)
            assert translations == fixed
            for b in limbs:
                expected = list(stand[b][6:9])
                assert after.pose[b][6:9] == expected,(slot,tick,b,'jointT')
            if tick < duration: cycle.append(copy.deepcopy(after.pose))
            else: assert after.pose == cycle[tick % duration],(slot,tick,'cyclic drift')
        assert after.root[2] == -row['speed']*duration*9
        sounds = [i for i in dst.instrs if i['op']=='sound']
        assert [i['frame']-1 for i in sounds] == row['footstep_ticks']
        assert all((i['bank'],i['note'])==(1,16) for i in sounds)
        assert len(sounds) == (0 if slot in [0,1] else 2*row['cycles'])
        checks.append(dict(slot=slot,source_template_slot=template,duration=duration,gait_period=row['gait_period'],forward_units_per_tick=row['speed'],unselected_native_channels_exact_nine_cycles=True,original_scales_exact=True,upper_lower_limb_segment_lengths_preserved=True,no_within_clip_limb_stretch=True,pose_repeat_exact_nine_cycles=True,original_non_sound_controls_exact=True,footstep_ticks=row['footstep_ticks']))
    storage = motionstorage.audit(result,17)
    assert storage['fits'],storage
    return result,dict(species=227,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[0,2,3,4],mesh_skeleton_hierarchy_other_slots_exact=True,checks=checks,solver=solver,storage=storage)
