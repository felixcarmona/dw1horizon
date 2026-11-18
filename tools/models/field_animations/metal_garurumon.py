"""MetalGarurumon's wolf walk and run, written from the paws up (quadruped.py).

MetalGarurumon (191) is an armoured wolf: three-bone legs, the forelegs ending in flat paws under shoulder plates,
the hind legs in long flat feet, two missile blades on the back and a single tail spike. The imported walk and run
dragged the paws through the floor and skated them (slip 90-230 % of the body's travel against about 20 % for
DW1's Garurumon); its idle stands with the left foreleg far back, so its legs are written from world targets with
the right legs' standing pose mirrored as the left's reference, not from mirrored angles.

- Walk (slot 2, also 0x23): a dog's lateral sequence (left hind, left fore, right hind, right fore) a quarter cycle
  apart, 62 % stance, 18 ticks at 22 units per tick, a footstep at every touchdown.
- Run (slot 4, also the battle movement 0x24): a rotary gallop (left hind, right hind, right fore, left fore) with a
  gathered flight, 14 ticks at 50 units per tick, footsteps on the two beats.
- The condition walk (slot 3) is the field pace pass's: this walk 1.5 times slower at 2/3 of its speed
  (content/models/imports/pace.json).
- Idle: planted, mirrored paws in the gait's neutral stance; the imported breathing,
  head, missile blades and tail keep moving above them.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations import quadruped

PROFILE = dict(
    species=191, name='MetalGarurumon',
    source='01f41d998cd05cb7a637580877079fa8f0156dabed3e33e92a4e0e6efe0e052e',
    parents=[-1, 15, 1, 2, 3, 6, 1, 6, 7, 10, 1, 10, 11, 1, 1, 0, 15, 16, 17, 15, 19, 20, 15],
    pelvis=15, chest=1, neck=2, head=3,
    # (upper, lower, paw, side (+1 right), front)
    legs={'RF': (6, 7, 8, 1, True), 'LF': (10, 11, 12, -1, True), 'RH': (16, 17, 18, 1, False), 'LH': (19, 20, 21, -1, False)},
    tail=(22,), loose=((13, 1), (14, -1)),
    pole={True: [0.3, 0.2, 1], False: [0.2, 0.2, -1]},   # elbows back, knees forward, both a little out (y down, z back)
    sole={True: [0, 55, -70], False: [0, 50, -60]},     # the point of the sole a paw rolls about (paw bone space)
    reach={'front': -70, 'hind': -20},                    # the sole pivot's place ahead of the shoulder / hip, mid-stance
    fold={True: 90, False: 100},                          # closest a swinging wrist / hock comes to its shoulder / hip
    clear=3,                                              # a standing sole is held this high (rounding between ticks)
    gaits={
        2: dict(name='walk', kind='walk', ticks=18, speed=22,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.62, 'RH': 0.62, 'RF': 0.62, 'LF': 0.62},
                lift={'front': 45, 'hind': 40}, curl={'front': 40, 'hind': 30}, peel={'front': 30, 'hind': 25},
                reach={'front': 0, 'hind': 0}, out={'front': 30, 'hind': 10}, snap=False, slip=0.05,
                height=18, tilt=0, chest_up=0, neck=3, nod=1, bob=4, pitch=1.2, flex=1.5, roll=2, yaw=2.5, head=0.5,
                tail=6, loose=2, steps=('LH', 'LF', 'RH', 'RF')),
        4: dict(name='run', kind='gallop', ticks=14, speed=50,
                touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54},
                duty={'LH': 0.34, 'RH': 0.34, 'RF': 0.34, 'LF': 0.34},
                lift={'front': 55, 'hind': 40}, curl={'front': 45, 'hind': 25}, peel={'front': 35, 'hind': 25},
                reach={'front': 0, 'hind': 20}, out={'front': 60, 'hind': 15}, snap=True, slip=0.08,
                height=30, tilt=0, chest_up=-3, neck=5, nod=1.5, bob=10, pitch=6, flex=8, roll=1.5, yaw=1.5, head=0.6,
                tail=10, loose=6, steps=('LH', 'RF')),
    },
)


def build(data, skeleton):
    walked, report = quadruped.build(data, skeleton, PROFILE)
    old = mmd.MMD.parse(walked, len(skeleton))
    old.type = PROFILE['species']
    new = copy.deepcopy(old)
    rig = quadruped.Rig(old, skeleton, PROFILE)
    frames, loop, events = animsheet.slot_frames(old, rig.n, 0)
    poses = copy.deepcopy(frames)
    history = {}
    for tick, pose in enumerate(poses):
        phase = 2 * math.pi * tick / (len(poses)-1)
        # Slow chest expansion; neck, back plates and tail follow the load.
        pose[15][7] += round(3 * math.sin(phase))
        pose[1][3] += round(0.8 * quadruped.DEG * math.sin(phase-.3))
        pose[2][3] -= round(0.6 * quadruped.DEG * math.sin(phase-.7))
        pose[22][4] += round(1.8 * quadruped.DEG * math.sin(phase-1))
        for name, (upper, lower, paw, side, front) in PROFILE['legs'].items():
            reference = PROFILE['legs'][quadruped.MIRROR.get(name, name)][2]
            track = side * abs(rig.still[reference][0][3])
            centre = rig.still[upper][2][3] + PROFILE['reach']['front' if front else 'hind']
            world = quadruped.rot([0, 0, 0])
            wrist = quadruped.standing(rig, name, track, centre, world)
            rotation, short = rig.solve(pose, name, wrist, history)
            assert short <= 0.5, (name, short)
            quadruped.set_rot(pose, paw, quadruped.mul(quadruped.tr(rotation), world), history)
    poses = [[[round(v) for v in b] for b in p] for p in poses]
    poses[-1] = copy.deepcopy(poses[0])
    index = old.anims.table[0]
    new.anims.anims[index] = mmd.encode_anim(poses, rig.n, loop_sample=loop, events=events, tol=1)
    from tools.models.field_animations.metal_garurumon_stop import author
    programs, stop_metrics = author(old, rig, poses)
    for slot, animation in programs.items():
        assert new.anims.table[slot] is None
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
    result = new.build()
    actual = mmd.MMD.parse(result, rig.n)
    changed = [s for s, i in enumerate(old.anims.table) if i == index]
    assert changed_programs(old, actual) == sorted(changed + list(programs))
    played = animsheet.slot_frames(actual, rig.n, 0)[0]
    floor = quadruped._floor(rig, played)
    assert floor <= quadruped.FLOOR, floor
    report['idle'] = dict(changed_slots=changed, lowest_point=round(floor, 2), planted_paws=True,
                          imported_body_motion=True, events_exact=True)
    report['changed_slots'] = sorted(set(report['changed_slots'] + changed + list(programs)))
    from tools.models.field_animations.metal_garurumon_stop import STOP_SLOTS
    stop_checks=[]
    for slots in STOP_SLOTS.values():
        for slot in slots:
            played, stop_loop, _ = animsheet.slot_frames(actual, rig.n, slot)
            assert stop_loop is None
            lowest=quadruped._floor(rig,played)
            assert lowest<=quadruped.FLOOR,(slot,lowest)
            # After both closing steps, soles remain at their world anchors.
            drift=0.
            for name,(_,_,paw,_,front) in PROFILE['legs'].items():
                points=[]
                for p in played[9:]:
                    w=rig.world(p)
                    point=quadruped.add([w[paw][i][3] for i in range(3)],
                        quadruped.mv([r[:3] for r in w[paw][:3]],PROFILE['sole'][front]))
                    point[2]+=p[0][8];points.append(point)
                drift=max(drift,max(quadruped.norm(quadruped.sub(p,points[0])) for p in points))
            assert drift<5,(slot,drift)
            stop_checks.append(dict(slot=slot,floor_60fps=lowest,settled_sole_drift=drift))
    report['stop_checks']=stop_checks
    report['stops'] = stop_metrics
    report['storage'] = motionstorage.require(result, rig.n)
    report['output_sha256'] = hashlib.sha256(result).hexdigest()
    return result, report
