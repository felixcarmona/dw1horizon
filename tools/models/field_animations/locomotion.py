"""Pinned travel correction for reviewed footless field locomotion.

The preceding field recipe, where present, still owns the performance. Only
forward root momentum changes; every pose, event and loop keeps its timing.
"""
import copy
import hashlib
import importlib
import json
from pathlib import Path

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.gliding import _forward

MANIFEST = Path(__file__).resolve().parents[3] / 'content/models/imports/locomotion.json'


def build(data, skeleton):
    profiles = json.loads(MANIFEST.read_text())
    digest = hashlib.sha256(data).hexdigest()
    matches = [(int(sid), row) for sid, row in profiles.items() if row['source_sha256'] == digest]
    if len(matches) != 1:
        raise ValueError('Footless locomotion requires an individually pinned source')
    sid, profile = matches[0]
    if len(skeleton) != profile['bones'] or hashlib.sha256(json.dumps(skeleton).encode()).hexdigest() != profile['skeleton_sha256']:
        raise ValueError('Footless locomotion skeleton differs from its reviewed source')
    previous = None
    if profile['base_generator']:
        data, previous = importlib.import_module(profile['base_generator']).build(data, skeleton)
    if hashlib.sha256(data).hexdigest() != profile['post_source_sha256']:
        raise ValueError('Preceding field recipe differs from the reviewed post-pass input')
    mmd.exe().skeleton[sid] = skeleton
    mmd.exe().bone_count[sid] = len(skeleton)
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = sid
    new = copy.deepcopy(old)
    checks = []
    for slot, speed in profile['speeds'].items():
        slot = int(slot)
        frames, loop, events = animsheet.slot_frames(old, len(skeleton), slot)
        ticks = len(frames) - 1
        assert loop == 0 and ticks > 0
        travel = frames[-1][0][8] - frames[0][0][8]
        assert travel < 0 and frames[-1][0][6:8] == frames[0][0][6:8]
        animation = old.anims.anims[old.anims.table[slot]]
        authored = _forward(animation, -round(speed * ticks), ticks)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        before = mmd.AnimPlayer(animation, len(skeleton), slot)
        after = mmd.AnimPlayer(authored, len(skeleton), slot)
        cycle = []
        for tick in range(ticks * 9 + 1):
            assert before.tick() and after.tick()
            assert before.pose == after.pose and before.base[:2] == after.base[:2]
            assert before.events == after.events
            if tick < ticks:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick % ticks], (sid, slot, tick, 'cyclic drift')
        checks.append(dict(slot=slot, ticks=ticks, before_units_per_tick=-travel / ticks,
                           after_units_per_tick=round(speed * ticks) / ticks,
                           nine_cycles_pose_events_and_lateral_vertical_root_exact=True))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, len(skeleton))
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(int(s) for s in profile['speeds'])
    # Replay the serialized result as well as the in-memory candidate.
    for row in checks:
        slot = row['slot']
        final = actual.anims.anims[actual.anims.table[slot]]
        expected = new.anims.anims[new.anims.table[slot]]
        assert final.build() == expected.build()
    storage = motionstorage.require(result, len(skeleton))
    return result, dict(species=sid, source_sha256=digest,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        preceding_recipe=previous, checks=checks, storage=storage,
                        changed_slots=sorted(int(s) for s in profile['speeds']),
                        mesh_skeleton_other_slots_exact=True,
                        contact_basis='Footless hover, swim, slug slide or floating base; body pose and every interpolated pose unchanged.')
