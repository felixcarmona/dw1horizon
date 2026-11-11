"""Solarmon's complete gears and its four field clips: calm idle, walk, tired walk and run.

The mesh (Digital Card Battle's, imported unchanged) is a sun body (bone 1), a ring of eight rays (bone 2) and two
red gears for hands (bones 3 and 4). Each gear has eight teeth, but the three on the side that faces the body were
modelled as 5 to 8 unit nubs where the other five are 23 units long boxes, so every hand read as a gear with
missing fingers. `complete_gears` lengthens those six nubs to the length of their neighbours along their own axes
(only vertices move: no face, UV or vertex is added), so each gear is whole.

The import played its one 89-tick clip in the idle, the walk, the tired walk and the run: they differed only in root
speed (17, 12, 35 units a tick). Inside it the ring spun with an eased wind-up (4 to 53 units a tick), which is the
"slow, then it speeds up" that was seen. This module writes four different clips over the model that the
earlier recipes (gliding, locomotion and celebrations) made, keeping their other slots:

- Idle (slots 0, 1, 18; 64 ticks): breathing hover. The body bobs twice (2.5 units) and leans a little, the ring
  turns one ray in the loop, the gears turn the other way, one tooth in the loop, and drift a little behind the body.
- Walk (24 ticks, 20 units): a floating stride. The body leans forward, bobs twice a cycle, rolls and yaws once; the
  hands are moved out from the body (so no tooth sweeps through the sun) and trail a little behind it,
  turning like propellers.
- Tired walk (32 ticks, 13 units): the body sags forward, bobs slowly and rolls heavily; the hands hang low and
  trail, turning slowly.
- Run (16 ticks, 38 units): the body leans far forward and bobs fast; the hands stream out and back and turn quickly.

Every clip keeps one base hover height, travels at one speed in every tick (the root runs along -z with a constant
step, no easing), and turns the ring and the gears at constant rates, a whole number of ray (45 degree) or gear
(90 degree) steps per loop, so they look the same when the loop starts again. The secondary motions (bob, lean, roll,
yaw, the hands' drift) are sines whose periods divide the clip. Nothing steps vertically.

Offline authoring (the player's build replays the plain delta): `tools/models/edit.py get 251` at the commit before
this one (its SHA-256 is SOURCE), then `python3 -m tools.models.field_animations.solarmon_gaits --source
build/imported-model-edit/edit/251-Solarmon.MMD --out AFTER.MMD` and `tools/models/edit.py put 251 AFTER.MMD`.
"""
import copy
import hashlib
import math
from pathlib import Path

import animsheet
import mmd
import motionstorage
from tools.models.field_animations import solarmon_face as face

SPECIES = 251
NB = 5
SOURCE = 'c41ea9f94379effbe9f821a3ec2717d59724349ca2ffbabad81667a1d457c732'
BODY, RING, GEAR_R, GEAR_L = 1, 2, 3, 4
TURN = 4096
HOVER = 122              # bone 1's height: the ring's lowest point (97 below) clears the floor by 25 on average
HAND = (105, 42)         # a gear's rest offset from the body (right hand; the left one is mirrored)
TOOTH = 23.5             # length of a full gear tooth
STEP_RING = 512          # the ring has 8 rays: one ray step
STEP_GEAR = 1024         # the gears' hubs have 4 spokes: a quarter turn
GEAR_REST = 281          # the rest pose's gear and ring angles
RING_REST = 409

# n: ticks of the loop; speed: units a tick along -z; ring/gear: whole steps turned in the loop (gears turn against
# each other); bob: (cycles a loop, amplitude); lean: forward pitch (degrees) and its sway; roll/yaw: degrees and
# cycles; hands: offset (out, down, back) in units and its drift amplitudes (out, down, back) with lag in cycles
CLIPS = {
    'idle': dict(n=64, speed=0, ring=1, gear=1, bob=(2, 2.5), lean=(1.0, 1.0, 2), roll=(1.6, 1), yaw=(1.5, 1),
                 hand=(30, 6, 0), drift=(2.0, 3.0, 2.0), lag=.14),
    'walk': dict(n=24, speed=20, ring=2, gear=3, bob=(2, 3.5), lean=(6.0, 2.0, 2), roll=(4.5, 1), yaw=(4.0, 1),
                 hand=(34, 4, 10), drift=(3.0, 5.0, 4.0), lag=.16),
    'tired': dict(n=32, speed=13, ring=1, gear=1, bob=(2, 2.2), lean=(13.0, 2.0, 2), roll=(3.0, 1), yaw=(2.5, 1),
                  hand=(26, 16, 14), drift=(2.0, 4.0, 3.0), lag=.2),
    'run': dict(n=16, speed=38, ring=3, gear=3, bob=(2, 3.0), lean=(15.0, 2.0, 2), roll=(3.5, 1), yaw=(3.0, 1),
                hand=(36, -4, 28), drift=(3.0, 4.0, 5.0), lag=.2),
}
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 18: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}


def units(degrees):
    return degrees * TURN / 360


def complete_gears(model):
    """Lengthens the three nubs of each gear to full teeth along their own axes. Returns the vertices moved."""
    moved = []
    for obj in (2, 3):
        o = model.tmd.objects[obj]
        verts = [list(v) for v in model.tmd.obj_verts(obj)]
        prims = [p.decode() for p in o.prims]
        degree = {}
        for p in prims:
            for i in p['verts']:
                degree[i] = degree.get(i, 0) + 1
        # a tooth's cap: a quad whose corners belong to it and to two sides only; the nubs are the short ones
        caps = [k for k, p in enumerate(prims)
                if all(degree[i] == 3 for i in p['verts'])
                and max(math.hypot(*verts[i][:2]) for i in p['verts']) < 40]
        assert len(caps) == 3, caps
        for c in caps:
            tip = prims[c]['verts']
            sides = [p for k, p in enumerate(prims) if k != c and len(set(p['verts']) & set(tip)) == 2]
            assert len(sides) == 4
            base = sorted({i for p in sides for i in p['verts'] if i not in tip})
            assert len(base) == 4
            # the axis: across the base's front pair, outwards from the gear's centre
            front = [i for i in base if verts[i][2] > 0]
            ax, ay = (verts[front[1]][0] - verts[front[0]][0], verts[front[1]][1] - verts[front[0]][1])
            norm = math.hypot(ax, ay)
            axis = (-ay / norm, ax / norm)
            centre = (sum(verts[i][0] for i in base) / 4, sum(verts[i][1] for i in base) / 4)
            if axis[0] * centre[0] + axis[1] * centre[1] < 0:
                axis = (-axis[0], -axis[1])
            for i in tip:
                length = (verts[i][0] - centre[0]) * axis[0] + (verts[i][1] - centre[1]) * axis[1]
                shift = TOOTH - length
                verts[i][0] = int(round(verts[i][0] + shift * axis[0]))
                verts[i][1] = int(round(verts[i][1] + shift * axis[1]))
                moved.append((obj, i))
        for i, v in enumerate(verts):
            model.tmd.verts[o.vert_start + i] = tuple(v)
    return moved


def regularise_gears(model):
    """Makes both gear hands regular: eight identical teeth 45 degrees apart around the axis (bone origin), the same
    on both hands (mirrored). Each vertex keeps its role (hub, inner rim, outer rim or tip; front or back face;
    which side of its tooth) and takes the mean radius and half-angle of that role over the sixteen teeth, set
    symmetrically about the tooth's axis. Only positions change: no face, UV or vertex is added or removed."""
    roles = {}
    gears = []
    for obj in (2, 3):
        o = model.tmd.objects[obj]
        verts = [list(v) for v in model.tmd.obj_verts(obj)]
        polar = [(math.hypot(v[0], v[1]), math.degrees(math.atan2(v[1], v[0])) % 360) for v in verts]
        tips = sorted(a for (r, a), v in zip(polar, verts) if r >= 33)
        # the eight tooth axes: tips come in pairs per tooth and face (4 vertices), whose mean angle is the axis
        groups = []
        for a in tips:
            if groups and a - groups[-1][-1] < 20:
                groups[-1].append(a)
            else:
                groups.append([a])
        if len(groups) > 1 and groups[0][0] + 360 - groups[-1][-1] < 20:
            groups[0] = [a - 360 for a in groups[-1]] + groups[0]
            groups.pop()
        assert len(groups) == 8, groups
        axes = sorted(sum(g) / len(g) for g in groups)
        gears.append((obj, verts, polar, axes))
        for i, (r, a) in enumerate(polar):
            j = min(range(8), key=lambda k: abs((a - axes[k] + 180) % 360 - 180))
            delta = (a - axes[j] + 180) % 360 - 180
            cls = 0 if r < 14 else 1 if r < 22 else 2 if r < 33 else 3
            roles.setdefault((cls, verts[i][2] > 0), {}).setdefault((obj, j), []).append((delta, r, i))
    template = {}
    for key, by_tooth in roles.items():
        slots = {}
        for (obj, j), items in by_tooth.items():
            items.sort()
            slots.setdefault(len(items), []).append(items)
        for count, lists in slots.items():
            if count == 2:
                half = [(abs(it[0][0]) + abs(it[1][0])) / 2 for it in lists]
                rad = [(it[0][1] + it[1][1]) / 2 for it in lists]
                template[(key, count)] = (sum(half) / len(half), sum(rad) / len(rad))
            else:
                assert count == 1 or count == 3, (key, count)
    ideal = [22.5 + 45 * k for k in range(8)]
    for obj, verts, polar, axes in gears:
        todo = {}
        for key, by_tooth in roles.items():
            for (o2, j), items in by_tooth.items():
                if o2 == obj:
                    todo[(key, j)] = items
        for (key, j), items in todo.items():
            if len(items) == 2:
                half, rad = template[(key, 2)]
                for sign, (_, _, i) in zip((-1, 1), items):
                    ang = math.radians(ideal[j] + sign * half)
                    verts[i][0] = int(round(rad * math.cos(ang)))
                    verts[i][1] = int(round(rad * math.sin(ang)))
            else:
                # hub vertices that stand alone in a sector: keep their radius, take the ideal axis plus their offset
                for delta, r, i in items:
                    ang = math.radians(ideal[j] + delta)
                    verts[i][0] = int(round(r * math.cos(ang)))
                    verts[i][1] = int(round(r * math.sin(ang)))
        o = model.tmd.objects[obj]
        for i, v in enumerate(verts):
            model.tmd.verts[o.vert_start + i] = tuple(v)


def wave(u, cycles, phase=0.):
    return math.sin(2 * math.pi * (cycles * u + phase))


def pose(clip, u):
    """The five bones' [scale xyz, rotation xyz, translation xyz] at loop position u (0..1, fractions of the loop)."""
    c = CLIPS[clip]
    n = c['n']
    cyc, amp = c['bob']
    bob = amp * wave(u, cyc)
    pitch, sway, sway_cycles = c['lean']
    lean = pitch + sway * wave(u, sway_cycles, .25)
    roll = c['roll'][0] * wave(u, c['roll'][1], .1)
    yaw = c['yaw'][0] * wave(u, c['yaw'][1], .35)
    body = [4096, 4096, 4096, units(lean), units(yaw), units(roll), 0, -(HOVER + bob), 0]
    ring = [4096, 4096, 4096, 0, 0, RING_REST + c['ring'] * STEP_RING * u, 0, 0, 0]
    out, down, back = c['hand']
    dx, dy, dz = c['drift']
    lag = c['lag']
    hands = []
    for side, bone in ((1, GEAR_R), (-1, GEAR_L)):
        spin = c['gear'] * STEP_GEAR * u * (1 if side > 0 else -1)
        hands.append([4096, 4096, 4096, 0, 0, GEAR_REST + spin,
                      side * (HAND[0] + out + dx * wave(u, cyc, -lag)),
                      HAND[1] + down + dy * wave(u, cyc, -lag - .25),
                      back + dz * wave(u, cyc, -lag - .5)])
    return [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0], body, ring] + hands


def frames_of(clip):
    c = CLIPS[clip]
    n = c['n']
    poses = []
    for t in range(n + 1):
        p = pose(clip, (t % n) / n)
        if t == n:       # the spin goes on over the loop: only whole steps, symmetrical to the start
            p = pose(clip, 0.)
            for bone in (RING, GEAR_R, GEAR_L):
                p[bone][5] = pose(clip, 1.)[bone][5]
        p[0][8] = -c['speed'] * t
        poses.append([[int(round(x)) for x in v] for v in p])
    mmd.close_loop(poses, 0)
    return poses


# The face's plan per clip: (tick, state) changes inside the clip, ending in open eyes.
FACE = {
    'idle': dict(eyes=face.blink(11) + face.blink(47)),
    'walk': dict(eyes=face.blink(6)),
    'tired': dict(eyes=[(13, face.HALF), (14, face.SHUT), (18, face.OPEN)]),
    'run': dict(eyes=[]),
}


def put_clip(model, frames, slots, events=(), tol=1):
    model.anims.anims.append(mmd.encode_anim(frames, NB, 0, list(events), tol=tol, repeats=False))
    for slot in slots:
        model.anims.table[slot] = len(model.anims.anims) - 1


def drop_unused(model):
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]


def build(data, skeleton, tim):
    """data, tim: the model and its texture before this change (SOURCE) -> (the model with whole gears and the four
    clips, its texture with the face frames, a report)."""
    from tools.models.field_animations import celebrations
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Solarmon's gaits need the reviewed model as it was before they were baked")
    chain, _ = celebrations.build(data, skeleton)
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(chain, NB)
    model.type = SPECIES
    moved = complete_gears(model)
    regularise_gears(model)
    for clip in ('idle', 'walk', 'tired', 'run'):
        slots = [s for s, k in CLIP_OF_SLOT.items() if k == clip]
        frames = frames_of(clip)
        put_clip(model, frames, slots, face.events(ticks=len(frames) - 1, **FACE[clip]))
    drop_unused(model)
    result = model.build()
    texture = mmd.Tim4(tim)
    face.stamp(texture)
    return result, texture.to_bytes(), dict(species=SPECIES, source_sha256=SOURCE, moved_vertices=len(moved),
                        changed_slots=sorted(CLIP_OF_SLOT), storage=motionstorage.require(result, NB))


def main():
    import argparse
    import json
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True, help="the model before this change (edit.py get 251)")
    ap.add_argument('--tim', required=True, help="the texture before this change (edit.py get 251)")
    ap.add_argument('--out', required=True)
    ap.add_argument('--tim-out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/251-solarmon.json').read_text())['model']['skeleton']
    data, texture, report = build(Path(args.source).read_bytes(), rig, Path(args.tim).read_bytes())
    Path(args.out).write_bytes(data)
    Path(args.tim_out).write_bytes(texture)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
