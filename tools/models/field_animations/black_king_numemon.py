"""Slug locomotion and care acting on BlackKingNumemon's own anatomy.

The imported idle supplies the neutral articulation. Eye stalks and the crown
stay in their own local frames instead of receiving Etemon's limb rotations.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
from motioncyclelayer import share_identical_streams
from motiondiscidentity import changed_programs

SOURCE = '608e1ce8ffd194e7b666f661b1b48d5732654935e282a0a831eb50df7480ebf5'


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(skeleton) != 18:
        raise ValueError('BlackKingNumemon requires its pinned 18-bone import')
    old = mmd.MMD.parse(data, 18)
    old.type = 307
    mmd.exe().skeleton[307] = skeleton
    mmd.exe().bone_count[307] = 18
    new = copy.deepcopy(old)
    rest = animsheet.slot_frames(old, 18, 33)[0][0]
    reports = []
    vertices = [(b, old.tmd.obj_verts(obj)) for b,(obj,_) in enumerate(skeleton) if obj >= 0]
    for slot in (2, 3, 4, 11, 12, 25, 27, 35, 36, 42):
        source, loop, events = animsheet.slot_frames(old, 18, slot)
        locomotion = slot in (2, 3, 4, 27, 35, 36)
        period = {2: 32, 3: 40, 4: 24, 27: 32, 35: 32, 36: 24}.get(slot, len(source) - 1)
        speed = {2: 20, 3: 14, 4: 38}.get(slot, 0)
        distance = -speed * period
        if slot in (27, 35, 36):
            # Battle/flee controllers keep their existing average travel.
            distance = round((source[-1][0][8] - source[0][0][8]) * period / (len(source) - 1))
            speed = -distance / period
        poses = []
        for tick in range(period + 1):
            f = copy.deepcopy(rest)
            phase = 2 * math.pi * tick / period
            # Closed smooth waves: compression travels from the snout to the
            # shell, with delayed crown/eye follow-through rather than a hinge.
            if locomotion:
                f[0][8] = round(distance * tick / period)
                lift = round(10 * (1 - math.cos(phase)))
                f[1][7] -= lift
                # The front pads and rear support stay low while the heavy
                # body rises between them; this avoids lifting the whole slug.
                for b in (2, 4, 15):
                    f[b][7] += lift
                f[1][5] += round(36 * math.sin(phase))
                f[6][3] += round(70 * math.sin(phase - .4))
                f[15][3] += round(60 * math.sin(phase - .8))
                f[16][3] += round(30 * math.sin(phase - 1.1))
                for b, lag in ((2, 0), (4, .4)):
                    f[b][3] += round(110 * math.sin(phase - lag))
                for b, lag in ((7, .5), (10, .8)):
                    f[b][3] += round(50 * math.sin(phase - lag))
            else:
                # Anticipation, two nods/shakes, then a soft settle. Envelope
                # vanishes at both endpoints so care returns to the idle pose.
                envelope = math.sin(math.pi * tick / period) ** 2
                wave = math.sin(phase * 2)
                happy = slot in (11, 42)
                lift = round((14 if happy else -4) * envelope)
                f[1][7] -= lift
                for b in (2, 4, 15):
                    f[b][7] += lift
                f[6][3] += round((65 if happy else 90) * envelope * wave)
                f[1][5] += round((35 if happy else 15) * envelope * math.sin(phase))
                for b, lag in ((7, .3), (10, .55)):
                    f[b][3 if happy else 4] += round(65 * envelope * math.sin(phase * 2 - lag))
                f[15][3] += round(25 * envelope * math.sin(phase * 2 - .7))
                f[16][3] += round(18 * envelope * math.sin(phase * 2 - 1))
            matrices = mmd.bone_matrices(old, f)
            bottom = max(sum(matrices[b][1][j] * v[j] for j in range(3)) + matrices[b][1][3]
                         for b, verts in vertices for v in verts)
            f[1][7] -= math.ceil(bottom)
            poses.append(f)
        if locomotion:
            events = [(t, 'sound', dict(bank=1, note=24)) for t in (2, period // 2 + 2)]
            loop = 0
        if slot == 25:
            loop = 0
        authored = mmd.encode_anim(poses, 18, loop_sample=loop, events=events, tol=1, repeats=False)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=period, speed=speed, sounds=[t for t,k,_ in events if k=='sound']))
    new.anims.anims, new.anims.table = share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, 18)
    assert changed_programs(old, actual) == [2, 3, 4, 11, 12, 25, 27, 35, 36, 42]
    assert old.tmd.build() == actual.tmd.build()
    for row in reports:
        if row['slot'] not in (2, 3, 4, 27, 35, 36):
            continue
        slot, period = row['slot'], row['period']
        player = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], 18, slot)
        cycle = []
        for tick in range(period * 9):
            assert player.tick()
            if tick < period:
                cycle.append(copy.deepcopy(player.pose[1:]))
            else:
                assert player.pose[1:] == cycle[tick % period], (slot, tick, 'body drift')
        row['body_repeats_nine_cycles'] = True
    storage = motionstorage.require(result, 18)
    return result, dict(species=307, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[r['slot'] for r in reports], checks=reports, storage=storage)
