"""MetalSeadramon's own serpentine field clips on its own skeleton.

The imported field clips (idle, walk, run) held one undulation with only the
root speed changing. These are authored: MetalSeadramon keeps its upright S rest
pose and one wave travels down the whole body, from the top of the neck through the
hips to the tail tips, each bone a fixed phase later than the one before, so the
body bends as one flexible piece. Bends are about each bone's long axis' two
perpendiculars (side-to-side and forward-back), the head counter-turns to hold its
gaze, and the heavy plates and fins follow their bones a little later. Native
Seadramon only lends its cadence: 20-tick cycles (idle, walk and slow walk take a
multiple). The forward speed of every clip stays what the import had.
Only slots 0-4 change; mesh, battle, care and every other program are exact.
"""
import copy
import math
import hashlib

import animsheet
import mmd
import motioncyclelayer
import motionstorage
import retarget
from motiondiscidentity import changed_programs

SOURCE = '9362cbe5a2750a711021fe5142ac5881943e4e505756ada908ecef34f2a60ac5'
TYPE = 211
BONES = 18
HIPS = 1
NECK = [5, 4, 3, 2]                # top of the neck first: the wave starts there
TAIL = [8, 9, 10, 11]
TIPS = [12, 13]
HEAD, JAW = 6, 7
PLATES = {14: 1, 15: -1}           # chest plates, side of the body
FINS = {16: 1, 17: -1}             # hip fins
# per clip: cycle ticks, wave lag per bone (degrees of the cycle), side-to-side and forward-back bend per neck bone
# and per tail bone (degrees, the tail's grows toward the tip by TAIL_GROWTH), tail tips, hip heave (units) and
# roll, root sway (units), lean of the neck (degrees forward in total), tail straightening, plate/fin flap and
# sweep back, jaw opening (degrees: fast open, brief hold, slower close, once a cycle) with the head nod that goes
# with it, look-around yaw of the head, and a tail flick (degrees, a lash once a cycle that runs down the tail)
CLIPS = {
    0: dict(ticks=60, lag=28, neck=(5.5, 3.0), tail=(6.0, 3.0), tips=3.0, bob=10, roll=1.5, sway=0, lean=0, straight=0,
            flap=4.0, sweep=0, jaw=12, nod=4, look=7, flick=14),
    2: dict(ticks=40, lag=50, neck=(12.0, 6.0), tail=(14.0, 6.0), tips=6.0, bob=18, roll=4.0, sway=24, lean=0, straight=0,
            flap=9.0, sweep=8, jaw=22, nod=7, look=0, flick=0),
    3: dict(ticks=40, lag=50, neck=(8.0, 4.5), tail=(9.5, 4.0), tips=4.5, bob=12, roll=2.5, sway=14, lean=0, straight=0,
            flap=6.0, sweep=4, jaw=16, nod=5, look=0, flick=0),
    4: dict(ticks=40, lag=60, neck=(10.5, 5.0), tail=(12.5, 5.0), tips=5.0, bob=7, roll=3.5, sway=20, lean=11, straight=.4,
            flap=7.0, sweep=20, jaw=18, nod=4.5, look=0, flick=0, heave_h=1),
}
TAIL_GROWTH = [0.7, 1.0, 1.3, 1.6]
JAW_SIGN = 1
JAW_PHASE = 0.0
UNIT = 4096 / 360


def _parse(data, skeleton):
    mmd.exe().skeleton[TYPE] = skeleton
    mmd.exe().bone_count[TYPE] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = TYPE
    return model


def _jaw(u):
    """0..1 opening at cycle fraction u: fast open, brief hold, slower close, then closed."""
    if u < .12:
        x = u / .12
        return x * x * (3 - 2 * x)
    if u < .24:
        return 1.0
    if u < .62:
        x = 1 - (u - .24) / .38
        return x * x * (3 - 2 * x)
    return 0.0


def _wave(clip, rest, speed, slot):
    """Samples (ticks+1 poses with the root) of one authored field slot."""
    c = CLIPS[slot]
    n = c['ticks']
    lag = math.radians(c['lag'])
    # position along the body, from the top of the neck down to the tail tips
    order = {b: i for i, b in enumerate(NECK)}
    order.update({HIPS: len(NECK)})
    order.update({b: len(NECK) + 1 + i for i, b in enumerate(TAIL)})
    order.update({b: len(NECK) + 1 + len(TAIL) for b in TIPS})
    samples = []
    for t in range(n + 1):
        w = 2 * math.pi * t / n
        pose = [list(v) for v in rest]

        def bend(bone, side, fore, extra=0.0, sign=1.0):
            phase = w - order[bone] * lag - extra
            pose[bone][4] += round(sign * side * math.sin(phase) * UNIT)
            pose[bone][3] += round(fore * math.cos(phase) * UNIT)
        for bone in NECK:
            bend(bone, c['neck'][0], c['neck'][1])
        for i, bone in enumerate(TAIL):
            bend(bone, c['tail'][0] * TAIL_GROWTH[i], c['tail'][1] * TAIL_GROWTH[i])
        for bone in TIPS:
            bend(bone, c['tips'], c['tips'] * .5)
        # forward lean of the neck, spread over its bones, and a straighter tail in the run
        for bone in NECK:
            pose[bone][3] -= round(c['lean'] / len(NECK) * UNIT)
        if c['straight']:
            mean = sum(rest[b][3] for b in TAIL) / len(TAIL)
            for bone in TAIL:
                pose[bone][3] += round(c['straight'] * (mean - rest[bone][3]))
        # the head holds its gaze: it counter-turns what the neck has bent, a little late
        late = order[2] * lag + lag
        pose[HEAD][4] -= round(.5 * c['neck'][0] * len(NECK) * math.sin(w - late) * UNIT * .5)
        pose[HEAD][3] += round(.6 * c['neck'][1] * len(NECK) * .5 * math.cos(w - late - lag) * UNIT)
        # the mouth: fast open, brief hold, slower close; the head lifts with it
        open_ = _jaw((t / n + JAW_PHASE) % 1.0)
        pose[JAW][3] += round(JAW_SIGN * c['jaw'] * open_ * UNIT)
        pose[HEAD][3] += round(-JAW_SIGN * c['nod'] * open_ * UNIT)
        pose[HEAD][4] += round(c['look'] * math.sin(w) * UNIT)           # slow look-around when standing
        # a tail flick once a cycle: a lash that starts at the hips and runs to the tips, a beat later on each bone
        if c['flick']:
            for bone in TAIL + TIPS:
                u = (w - 1.2 - (order[bone] - order[HIPS]) * .55) % (2 * math.pi)
                lash = max(0.0, math.sin(u)) ** 3 * math.sin(2 * u)
                pose[bone][4] += round(c['flick'] * (.5 if bone in TIPS else 1.0) * lash * UNIT)
        # plates and fins follow their bones later: a flap about the body axis and, running, swept back
        for bone, side in {**PLATES, **FINS}.items():
            parent = 4 if bone in PLATES else 2
            phase = w - order[parent] * lag - 1.6 * lag
            pose[bone][5] += round(side * (c['flap'] * math.sin(phase) + (c['sweep'] * .2 if bone in PLATES else 0)) * UNIT)
            pose[bone][4] += round(-side * c['sweep'] * UNIT * (.6 if bone in PLATES else .4))
        pose[HIPS][5] += round(c['roll'] * math.sin(w - order[HIPS] * lag) * UNIT)
        pose[HIPS][7] = round(rest[HIPS][7] - c['bob'] * math.sin(c.get('heave_h', 2) * w - order[HIPS] * lag))   # heave, twice a cycle unless slowed
        pose[0][6:9] = [round(c['sway'] * math.sin(w)), 0, round(speed * t)]
        samples.append(pose)
    samples[-1][1:] = copy.deepcopy(samples[0][1:])      # the closing sample is the first one, exactly
    return samples, dict(period=n, travel=round(speed * n), speed=speed)


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('MetalSeadramon swim requires its reviewed import')
    if len(skeleton) != BONES:
        raise ValueError('MetalSeadramon swim has the wrong bone count')
    old = _parse(data, skeleton)
    new = copy.deepcopy(old)
    rest = retarget.rest_pose(old, BONES, 0)
    reports = []
    for slot in CLIPS:
        frames, loop, _ = animsheet.slot_frames(old, BONES, slot)
        assert loop == 0
        events = [e[2] for e in animsheet.slot_frames(old, BONES, slot)[2] if e[1] == 'sound']
        speed = (frames[-1][0][8] - frames[0][0][8]) / (len(frames) - 1)
        samples, info = _wave(CLIPS[slot], rest, speed, slot)
        mmd.close_loop(samples, 0)
        # the import's own cue (the family's voice) once a cycle, in the middle of it
        ev = [(info['period'] // 2, 'sound', dict(bank=events[0]['bank'], note=events[0]['note']))] if events else []
        animation = mmd.encode_anim(samples, BONES, 0, ev, tol=0, repeats=False)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        reports.append(dict(slot=slot, **info))
    new.anims.table[1] = new.anims.table[0]
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, skeleton)
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4], changed_programs(old, actual)
    assert old.tmd.build() == actual.tmd.build()
    storage = motionstorage.audit(result, BONES)
    assert storage['fits'], storage
    checks = _verify(actual, reports)
    return result, dict(species=TYPE, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 1, 2, 3, 4],
                        mesh_care_battle_exact=True, params=CLIPS, clips=reports, checks=checks, storage=storage)


def _verify(model, reports):
    """Nine cycles repeat exactly, travel per cycle is exact and steady."""
    checks = []
    for row in reports:
        slot, period = row['slot'], row['period']
        player = mmd.AnimPlayer(model.anims.anims[model.anims.table[slot]], BONES, slot)
        cycle, steps = [], []
        for t in range(period * 9 + 1):
            assert player.tick()
            if t < period:
                cycle.append(copy.deepcopy(player.pose[1:]))
            else:
                assert player.pose[1:] == cycle[t % period], (slot, t, [(b+1,player.pose[b+1],cycle[t % period][b]) for b in range(BONES-1) if player.pose[b+1]!=cycle[t % period][b]])
            steps.append(player.base[2])
        nets = [sum(steps[1 + i * period:1 + (i + 1) * period]) for i in range(9)]
        assert nets == [row['travel']] * 9, (slot, nets)
        assert max(steps[1:]) - min(steps[1:]) <= 1
        checks.append(dict(slot=slot, nine_cycles_repeat_exact=True, loop_travel=row['travel']))
    return checks
