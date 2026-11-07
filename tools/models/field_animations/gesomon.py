"""Gesomon's tentacle-supported field gait, timed from native Kunemon.

Only walk and run are replaced. The small tentacles alternate planted tips
and eased recoveries; the mantle and long arms overlap the supporting steps.
"""
import copy
import hashlib
import math
from pathlib import Path

import animsheet
import legik
import mmd
import motionstorage
import numeric as np
from motioncyclelayer import share_identical_streams
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import align, set_rotation

SOURCE = '605d75215668121e51e820d468b3864012411ff78d4bf0b4f8caff456258cc54'
CHAINS = [(11, 12, 13), (14, 15, 16), (17, 18), (19, 20),
          (21, 22), (23, 24), (25, 26), (27, 28)]
VARIANT = 'terrestrial'
HOPS_SHA256 = '550fdc964d4584fe27dcc5a07b9a1d3738dcc238efb14915d7ceb6d07f0dd0d5'
TERRESTRIAL_SHA256 = 'ecf09e3abea9c24e111a543860de3a6568b77bbd26a0a3a3d222e25a274d6474'


def world(model, pose):
    p = copy.deepcopy(pose)
    p[0] = [4096]*3 + [0]*6
    return np.array(mmd.bone_matrices(model, p))


def build(data, skeleton):
    return _build(data, skeleton, hopping=False)


def _build(data, skeleton, hopping):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(skeleton) != 29:
        raise ValueError('Gesomon requires its pinned 29-bone source')
    mmd.exe().add_type(240, skeleton)
    old = mmd.MMD.parse(data, 29)
    old.type = 240
    new = copy.deepcopy(old)
    rest = copy.deepcopy(animsheet.slot_frames(old, 29, 0)[0][40])
    rest[0] = [4096]*3 + [0]*6
    rest[1][6:9] = [0, -120, 22]
    rest[7][5] += 500
    rw = world(old, rest)
    vertices = {b: np.array(old.tmd.obj_verts(obj))[:, :3]
                for b, (obj, _) in enumerate(skeleton) if obj >= 0}
    tips = {}
    for chain in CHAINS:
        hip, knee, end = chain[0], chain[1], chain[-1]
        points = vertices[end] @ rw[end, :3, :3].T + rw[end, :3, 3]
        # The pointed end, rather than the ankle, is the support landmark.
        direction = rw[knee, :3, 3] - rw[hip, :3, 3]
        projection = points @ direction
        order = sorted(range(len(points)), key=lambda i: float(projection[i]), reverse=True)
        tip = points[order[0]]
        tips[hip] = (tip, float(np.linalg.norm(rw[knee, :3, 3]-rw[hip, :3, 3])),
                     float(np.linalg.norm(tip-rw[knee, :3, 3])))
    donor_id = 44 if hopping else 32
    donor_name = 'TANE' if hopping else 'KUNE'
    donor_path = Path(mmd.EXTRACTED) / f'CHDAT/MMD1/{donor_name}.MMD'
    donor_hash = ('338d41ff45e5a2429046c8d9b768d726fb1a36d278163de535f8fd47da2c1c87' if hopping else
                  '492137deb94261c47d8729e3c8df2f9758a3b71744df283454b9367a8282197c')
    if hashlib.sha256(donor_path.read_bytes()).hexdigest() != donor_hash:
        raise ValueError('Gesomon requires its pinned native timing donor')
    donor = mmd.MMD.load(str(donor_path), donor_id)
    checks = []
    for slot in (2, 4):
        native, _, native_events = animsheet.slot_frames(donor, mmd.exe().bone_count[donor_id], slot)
        period = len(native)-1
        assert period == (17 if hopping else 18)
        speed = 18 if slot == 2 else 35
        duty = .60 if slot == 2 else .46
        frames, plans = [], []
        history = {}
        for tick in range(period+1):
            theta = 2*math.pi*tick/period
            p = copy.deepcopy(rest)
            p[0][8] = -speed*tick
            # Low, soft mantle movement follows alternating support groups.
            p[1][6] += round(5*math.sin(theta))
            p[1][7] += round((5 if slot == 2 else 9)*math.cos(2*theta-.3))
            p[1][3] += round(20*math.sin(2*theta-.5))
            p[1][5] += round(24*math.sin(theta-.2))
            for b, sign in ((3, 1), (7, -1)):
                for j in range(4):
                    p[b+j][3] += round((24+6*j)*math.sin(theta+sign*.8-j*.4))
                    p[b+j][5] += round(sign*14*math.sin(theta-j*.35))
            if hopping:
                # Tanemon leaves at tick 0 and lands at tick 7, followed by a
                # longer contact and anticipation. Keep that asymmetric beat.
                flight = max(0., (native[0][1][7]-native[tick][1][7])*.65)
                landing = math.exp(-((tick-8.5)/1.6)**2)
                anticipation = math.exp(-((tick-15)/1.4)**2)
                p[1][7] = round(-120-flight+10*landing+9*anticipation)
                p[1][3] = round(native[tick][1][3]*.15)
                stretch = 1+.07*math.sin(math.pi*min(tick,7)/7)-.10*landing-.05*anticipation
                p[1][:3] = [round(4096/math.sqrt(stretch)), round(4096*stretch), round(4096/math.sqrt(stretch))]
                for b, sign in ((3,1),(7,-1)):
                    for j in range(4):
                        p[b+j][3] += round(45*math.sin(theta-.5-j*.35))
                        p[b+j][5] += round(sign*30*math.sin(theta-.7-j*.4))
            row = []
            for index, chain in enumerate(CHAINS):
                hip, knee, end = chain[0], chain[1], chain[-1]
                # Contralateral groups alternate; rear pairs trail the front.
                phase = (tick/period + (index%2)*.5 + (index//2)*.11) % 1
                stance = phase < duty
                half = speed*period*duty/2
                if stance:
                    z = -half + speed*period*phase
                    lift = 0
                else:
                    u = (phase-duty)/(1-duty)
                    ease = u*u*(3-2*u)
                    z = half*(1-2*ease)
                    lift = (32 if slot == 2 else 50)*math.sin(math.pi*u)**2
                tip, length1, length2 = tips[hip]
                if hopping:
                    stance = tick == 0 or tick >= 7
                    if stance:
                        u = (tick-7)/10 if tick >= 7 else 1
                        z = (2*u-1)*(85 if slot == 2 else 125)
                        lift = 0
                        spread = 1+.10*math.sin(math.pi*max(0,u))
                    else:
                        u = tick/7
                        z = (85 if slot == 2 else 125)*(1-2*(u*u*(3-2*u)))
                        lift = flight*.65 + 18*math.sin(math.pi*u)**2
                        spread = 1-.35*math.sin(math.pi*u)
                else:
                    spread = 1
                target = np.array([float(tip[0])*spread, -lift, float(tip[2])+z*((.65 if hopping else .45) if len(chain)==3 else .55)])
                endpoint_rest = rw[end, :3, 3] if len(chain)==3 else tip
                if len(chain)==3:
                    target -= tip-endpoint_rest
                    length2 = float(np.linalg.norm(endpoint_rest-rw[knee, :3, 3]))
                error = 0
                # Repeat after rotating the distal mesh to put its underside on
                # the floor. Translation remains at the original joint lengths.
                # A subpixel contact skin is below one raster pixel and keeps
                # interpolated tentacle surfaces clear between logic ticks.
                for _ in range(8):
                    w = world(old, p)
                    root = w[hip, :3, 3]
                    pole = np.array([80*(1 if index%2==0 else -1), -20, 30])
                    joint, endpoint = map(np.array, legik.solve(root.tolist(), target.tolist(), length1, length2, pole.tolist()))
                    rh = align(rw[knee, :3, 3]-rw[hip, :3, 3], joint-root) @ rw[hip, :3, :3]
                    rk = align(endpoint_rest-rw[knee, :3, 3], endpoint-joint) @ rw[knee, :3, :3]
                    set_rotation(p, hip, (np.linalg.inv(w[1, :3, :3]) if hopping else w[1, :3, :3].T) @ rh, history)
                    w = world(old, p)
                    set_rotation(p, knee, (np.linalg.inv(w[hip, :3, :3]) if hopping else w[hip, :3, :3].T) @ rk, history)
                    if len(chain)==3:
                        w = world(old, p)
                        set_rotation(p, end, np.linalg.inv(w[knee, :3, :3]) @ rw[end, :3, :3], history)
                    w = world(old, p)
                    bottom = float((vertices[end] @ w[end, :3, :3].T + w[end, :3, 3])[:, 1].max())
                    error = bottom+lift+3
                    target[1] -= error
                row.append(dict(tip=end, stance=stance, lift=lift, floor_error=error))
            frames.append(p)
            plans.append(row)
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        events = [(t, 'sound', dict(bank=1, note=17)) for t, kind, _ in native_events if kind == 'sound']
        animation = mmd.encode_anim(frames, 29, loop_sample=0, events=events, tol=0, repeats=False)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        checks.append(dict(slot=slot, period=period, speed=speed, duty=duty, plan=plans))
    new.anims.anims, new.anims.table = share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    expected = HOPS_SHA256 if hopping else TERRESTRIAL_SHA256
    if hashlib.sha256(result).hexdigest() != expected:
        raise ValueError('Gesomon output differs from its reviewed variant pin')
    actual = mmd.MMD.parse(result, 29)
    assert changed_programs(old, actual) == [2, 4]
    assert old.tmd.build() == actual.tmd.build()
    return result, dict(species=240, variant='hops' if hopping else VARIANT, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        donor_sha256=hashlib.sha256(donor_path.read_bytes()).hexdigest(),
                        donor=donor_id, changed_slots=[2, 4], checks=checks,
                        storage=motionstorage.require(result, 29))
