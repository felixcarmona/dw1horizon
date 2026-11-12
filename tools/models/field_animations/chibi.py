"""Chibi proportions: reshape a reviewed imported partner to Digimon World's anatomy.

Every part of an imported model is one rigid mesh per bone, so the shape can be baked: the vertices of a bone and the
offsets of its children move through one local scale, in every animation, and nothing detaches. Head, hands and feet
grow, legs get shorter and thicker, arms and torso thicker. A uniform rescale brings the idle back to the height of
the species record. The manifest, content/models/imports/chibi.json, holds per species: the pins, the group of every
bone and the factors. An empty manifest changes nothing.

The floor is the one thing a bake cannot keep: a shorter leg leaves a walk floating and a sitting clip sinking, by
different amounts on different ticks. So each clip is replayed with the engine's interpreter and the carrier's height
is rewritten, with as few keys as a tolerance allows. On a tick where the source stands on its feet the feet are what
lands: on the floor, or at the source's clearance if it really hovers or jumps. A part that hangs lower than the feet
(a sleeve, a gun, a crest) must not hold the body up. On a tick where the source rests on something else (lying, a
fall) the lowest vertex of the mesh lands instead, and the two blend over a few ticks. A row's `fit` shortens the
limbs that would otherwise cross the floor with the feet down.

Stride and travel shrink together with the legs, down to the floor of the native speeds (pace.py's). Nothing else of
the root's motion changes. A species failing a check raises Refused, naming the check.
"""
import copy
import hashlib
import importlib
import json
import math
import re
from pathlib import Path

import animsheet
import mmd
import motioncyclelayer
import motionstorage

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / 'content/models/imports/chibi.json'
WALK, CONDITION, RUN = 2, 3, 4
SPEED_FLOOR = {WALK: 15, CONDITION: 9.5, RUN: 35}
SPEED_MARGIN = 1.03
CLEARANCE = 12            # a source this close over the floor counts as standing on it
KEY_TOLERANCE = 1.5       # a height key is dropped when the line through its neighbours stays this close
MAX_SINK = 4              # units a tick may stay under its target: 0.2 px at field size
MAX_FLOAT = 4             # units a tick may stay over it
MAX_PART_SINK = 8         # units a part may go under the floor beyond what the source's own clip does
BLEND_TICKS = 2           # on each side of a change between feet and mesh
MIN_FINAL_SCALE = 0.70    # the uniform rescale must not undo the reshaping
GROUND_PASSES = 3


class Refused(ValueError):
    """The species stays as it is: this check failed."""


# ------------------------------------------------------------------ small vectors
def _scale_matrix(axis, axial, radial):
    """Scale along the unit axis and across it."""
    return [[radial * (i == j) + (axial - radial) * axis[i] * axis[j] for j in range(3)] for i in range(3)]


def _diagonal(k):
    return [[k * (i == j) for j in range(3)] for i in range(3)]


def _apply(M, v):
    return [sum(M[i][j] * v[j] for j in range(3)) for i in range(3)]


def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    return [c / n for c in v] if n else None


def _principal(points):
    """The principal direction of a cloud of points, by power iteration."""
    n = len(points)
    mean = [sum(p[i] for p in points) / n for i in range(3)]
    q = [[p[i] - mean[i] for i in range(3)] for p in points]
    C = [[sum(p[i] * p[j] for p in q) for j in range(3)] for i in range(3)]
    best = max(range(3), key=lambda i: C[i][i])
    v = [float(i == best) for i in range(3)]
    for _ in range(40):
        v = _unit(_apply(C, v)) or v
    return v


def _translation(animation):
    return (6, 7, 8) if animation.has_scale else (3, 4, 5)


def _register(sid, skeleton):
    """The skeleton of type `sid` for the interpreter: a species' own, or a rig the executable does not know (9000 + id)."""
    if sid < len(mmd.exe().skeleton):
        mmd.exe().skeleton[sid] = skeleton
        mmd.exe().bone_count[sid] = len(skeleton)
    else:
        mmd.exe().add_type(sid, skeleton)


def _clamp16(value):
    return max(-32768, min(32767, int(round(value))))


# ------------------------------------------------------------------ the rig at rest
class Rig:
    def __init__(self, model, skeleton):
        self.m, self.skeleton, self.nb = model, skeleton, len(skeleton)
        self.children = {b: [c for c in range(self.nb) if skeleton[c][1] == b] for b in range(self.nb)}
        self.verts = {b: [list(v[:3]) for v in model.tmd.obj_verts(o)] for b, (o, _) in enumerate(skeleton) if o >= 0}
        self.verts = {b: v for b, v in self.verts.items() if v}
        roots = self.children[0]
        if len(roots) != 1:
            raise Refused(f'one carrier under the root expected, found {roots}')
        self.carrier = roots[0]

    def rest(self):
        """(pose, matrices) of the first idle tick, the root at the origin."""
        frames = animsheet.slot_frames(self.m, self.nb, 0)[0]
        pose = [list(v) for v in frames[0]]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        return pose, mmd.bone_matrices(self.m, pose)

    def bounds(self, feet):
        """(top, ground): the highest y of the rest pose and the lowest of its feet; y grows downwards."""
        _, mats = self.rest()
        ys = {b: [mats[b][1][0] * x + mats[b][1][1] * y + mats[b][1][2] * z + mats[b][1][3] for x, y, z in vs]
              for b, vs in self.verts.items()}
        return -min(min(v) for v in ys.values()), max(max(ys[b]) for b in feet if b in ys)


# ------------------------------------------------------------------ the bake
def _axis(rig, rest, b, groups):
    """The direction along which a limb piece is long, in its own frame: to its child in the chain, else its vertices."""
    g = groups[b]
    follows = {'thigh': ('thigh', 'shin', 'foot'), 'shin': ('shin', 'foot'), 'arm': ('arm', 'hand'),
               'shoulder': ('shoulder', 'arm', 'hand'), 'cloth': ('cloth',)}.get(g, (g,))
    kids = [c for c in rig.children[b] if groups[c] in follows]
    if kids:
        offset = rest[kids[0]][6:9]
        if math.sqrt(sum(c * c for c in offset)) > 3:
            return _unit(offset)
    if b in rig.verts and len(rig.verts[b]) >= 3:
        return _principal(rig.verts[b])
    return [0.0, 1.0, 0.0]


def _sole(rig, mats, b):
    """The height (own frame) of the point of a foot that is lowest at rest: a foot grows about it and stays planted."""
    if b not in rig.verts:
        return [0.0, 0.0, 0.0]
    M = mats[b]
    lowest = max(rig.verts[b], key=lambda v: M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2])
    return [0.0, float(lowest[1]), 0.0]


def _times(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def bone_scales(rig, groups, factors, fit=None):
    """bone -> (local scale matrix, anchor in the bone's frame). fit: bone -> length factor along the bone's axis."""
    rest, mats = rig.rest()
    F = lambda name: factors.get(name, 1.0)
    out = {}
    for b in range(1, rig.nb):
        g = groups[b]
        anchor = [0.0, 0.0, 0.0]
        M = None
        if g in ('head', 'headpart') and F('head') != 1:
            M = _diagonal(F('head'))
        elif g == 'hand' and F('hand') != 1:
            M = _diagonal(F('hand'))
        elif g in ('foot', 'footpart') and F('foot') != 1:
            M = _diagonal(F('foot'))
            if g == 'foot':
                anchor = _sole(rig, mats, b)
        elif g in ('thigh', 'shin', 'hipjoint') and (F('leg_axial') != 1 or F('leg_radial') != 1):
            M = _scale_matrix(_axis(rig, rest, b, groups), F('leg_axial'), F('leg_radial'))
        elif g in ('arm', 'shoulder') and F('arm_radial') != 1:
            M = _scale_matrix(_axis(rig, rest, b, groups), 1.0, F('arm_radial'))
        elif g in ('chest', 'carrier', 'pelvis', 'neck') and F('torso') != 1:
            M = _diagonal(F('torso'))
        elif g == 'cloth' and F('leg_axial') != 1:
            M = _scale_matrix(_axis(rig, rest, b, groups), F('leg_axial'), 1.0)
        if fit and str(b) in fit:
            shorter = _scale_matrix(_axis(rig, rest, b, groups), fit[str(b)], 1.0)
            M = _times(shorter, M) if M is not None else shorter
        if M is not None:
            out[b] = (M, anchor)
    return out


def _bake(rig, scales):
    """The vertices of each scaled bone, and in every animation the offsets of its children."""
    tmd = rig.m.tmd
    for b, (M, anchor) in scales.items():
        o = rig.skeleton[b][0]
        if o < 0:
            continue
        ob = tmd.objects[o]
        for i in range(ob.vert_start, ob.vert_start + ob.nvert):
            x, y, z, p = tmd.verts[i]
            v = _apply(M, [x - anchor[0], y - anchor[1], z - anchor[2]])
            v = [v[j] + anchor[j] for j in range(3)]
            if any(abs(c) > 32767 for c in v):
                raise Refused('a vertex leaves the 16-bit range')
            tmd.verts[i] = (round(v[0]), round(v[1]), round(v[2]), p)
    rig.verts = {b: [list(v[:3]) for v in tmd.obj_verts(rig.skeleton[b][0])] for b in rig.verts}
    for a in rig.m.anims.anims:
        ti = _translation(a)
        for b, (M, anchor) in scales.items():
            for c in rig.children[b]:
                v = a.pose[c - 1]
                moved = _apply(M, [v[ti[j]] - anchor[j] for j in range(3)])
                for j in range(3):
                    v[ti[j]] = _clamp16(moved[j] + anchor[j])
        for instruction in a.instrs:
            if instruction['op'] != 'key':
                continue
            for block in instruction['bones']:
                parent = rig.skeleton[block['bone']][1] if block['bone'] < rig.nb else -1
                if parent in scales and any(ch in block['vals'] for ch in ('tx', 'ty', 'tz')):
                    moved = _apply(scales[parent][0], [block['vals'].get(ch, 0) for ch in ('tx', 'ty', 'tz')])
                    for ch, value in zip(('tx', 'ty', 'tz'), moved):
                        if ch in block['vals']:
                            block['vals'][ch] = _clamp16(value)


def _scale_keys(animations, bone, k):
    """Multiply a bone's translation keys by k; their sum per loop segment stays what k times the old sum is."""
    for a in animations:
        segment, groups = 0, {}
        for instruction in a.instrs:
            if instruction['op'] == 'loop_start':
                segment += 1
            elif instruction['op'] == 'key':
                for block in instruction['bones']:
                    if block['bone'] == bone:
                        for ch in ('tx', 'ty', 'tz'):
                            if ch in block['vals']:
                                groups.setdefault((segment, ch), []).append((block, block['vals'][ch]))
        for (_, ch), items in groups.items():
            new = [_clamp16(v * k) for _, v in items]
            rest = round(sum(v for _, v in items) * k) - sum(new)
            if rest:
                i = max(range(len(items)), key=lambda n: abs(items[n][1]))
                new[i] = _clamp16(new[i] + rest)
            for (block, _), value in zip(items, new):
                block['vals'][ch] = value


def _rescale(model, k):
    """The whole model grows by k (sizes.py's rule: vertices and every translation)."""
    t = model.tmd
    t.verts = [tuple(_clamp16(c * k) for c in v[:3]) + (v[3],) for v in t.verts]
    for a in model.anims.anims:
        ti = _translation(a)
        for v in a.pose:
            for i in ti:
                v[i] = _clamp16(v[i] * k)
        for instruction in a.instrs:
            if instruction['op'] == 'key':
                for block in instruction['bones']:
                    for ch in ('tx', 'ty', 'tz'):
                        if ch in block['vals']:
                            block['vals'][ch] = _clamp16(block['vals'][ch] * k)


# ------------------------------------------------------------------ clips
def clips(model):
    """{animation index: the first slot that plays it}."""
    out = {}
    for slot, index in enumerate(model.anims.table):
        if index is not None:
            out.setdefault(index, slot)
    return out


def replay(model, nb, index, slot, carrier):
    """A clip through the engine's interpreter, one pass of any loop: its frames (the frame counter of each tick), the
    poses with the root travel taken out but for its height, the carrier's height per tick, and its events."""
    player = mmd.AnimPlayer(model.anims.anims[index], nb, slot)
    frames, poses, heights = [], [], []
    while len(poses) < 600 and player.tick(stop_at_infinite_loop=True):
        frames.append(player.frames[-1])
        pose = [list(v) for v in player.pose]
        pose[0][6:9] = [0, player.root[1], 0]
        poses.append(pose)
        heights.append(pose[carrier][7])
    return frames, poses, heights, player.events


def bone_lows(model, verts, pose):
    """{bone: the lowest y of its piece} in a pose."""
    mats = mmd.bone_matrices(model, pose)
    out = {}
    for b, vs in verts.items():
        M = mats[b][1]
        p, q, r, d = M[0], M[1], M[2], M[3]
        out[b] = max(p * x + q * y + r * z + d for x, y, z in vs)
    return out


def clip_lows(model, rig, index, slot, feet):
    """Per tick of a clip: (lowest foot, lowest of the mesh, the bone that is lowest)."""
    out = []
    for pose in replay(model, rig.nb, index, slot, rig.carrier)[1]:
        lows_ = bone_lows(model, rig.verts, pose)
        bone = max(lows_, key=lows_.get)
        out.append((max(lows_[b] for b in feet if b in lows_), lows_[bone], bone))
    return out


def lows(model, rig, feet):
    """{animation index: clip_lows}."""
    return {index: clip_lows(model, rig, index, slot, feet) for index, slot in clips(model).items()}


def target(low):
    """Where a tick's lowest vertex belongs, given the source's: y grows downwards, the floor is 0."""
    if low >= -CLEARANCE:
        return 0.0
    return max(low, 2.0 * (low + CLEARANCE))        # a ramp, so a hover at twice the margin stays where it was


def _chains(animation):
    """The clip's key instructions cut at its loop marks: [(instructions, frame the last one runs up to, loop start
    frame or None)], or None when a stretch of the clip has no key where the height could change."""
    chains, keys = [], []
    def flush(until, jump=None):
        if keys:
            chains.append((list(keys), until, jump))
            keys.clear()
    for instruction in animation.instrs:
        op = instruction['op']
        if op == 'key':
            keys.append(instruction)
            continue
        if op == 'loop_start':
            if keys:
                chains.append((list(keys), None, None))
                keys.clear()
        elif op == 'loop_end':
            flush(instruction['frame'], instruction['jump'])
        elif op == 'end':
            flush(animation.frame_count)
    flush(animation.frame_count)
    for i, (keyset, until, jump) in enumerate(chains):
        if until is None:
            if i + 1 == len(chains):
                return None
            chains[i] = (keyset, chains[i + 1][0][0]['frame'], None)
        if jump is not None and keyset[0]['frame'] != jump:
            return None
        if i and chains[i][0][0]['frame'] > chains[i - 1][1]:
            return None
    return chains


def _simplify(points, tolerance):
    """Indices kept of [(x, y)]: the ends and whatever a line between kept points misses by more than the tolerance."""
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        (xa, ya), (xb, yb) = points[a], points[b]
        worst, at = tolerance, None
        for i in range(a + 1, b):
            x, y = points[i]
            miss = abs(y - (ya + (yb - ya) * (x - xa) / (xb - xa)))
            if miss > worst:
                worst, at = miss, i
        if at is not None:
            keep.add(at)
            stack += [(a, at), (at, b)]
    return sorted(keep)


def _rewrite_heights(animation, carrier, height, tolerance):
    """The carrier's height follows height[frame] (rounded) with as few keys as the tolerance allows; the old height
    keys go. A key lands on an existing key instruction when one sits on that frame, else on a new one."""
    animation.instrs = [i for i in animation.instrs if not i.get('added')]
    height = dict(height)
    for f in range(min(height) + 1, animation.frame_count + 2):   # frames after a loop that never ends are not played
        height.setdefault(f, height[f - 1])
    for instruction in animation.instrs:
        if instruction['op'] == 'key':
            for block in instruction['bones']:
                if block['bone'] == carrier:
                    block['vals'].pop('ty', None)
            instruction['bones'] = [g for g in instruction['bones'] if g['vals']]
    chains = _chains(animation)
    ti = _translation(animation)
    animation.pose[carrier - 1][ti[1]] = _clamp16(height[chains[0][0][0]['frame']])
    for keys, until, jump in chains:
        first = keys[0]['frame']
        if first >= until:
            continue
        end = height[jump if jump is not None else until]
        line = [(f, height[f]) for f in range(first, until)] + [(until, end)]
        kept = _simplify(line, tolerance)
        for a, b in zip(kept, kept[1:]):
            frame, ticks = line[a][0], line[b][0] - line[a][0]
            delta = round(line[b][1]) - round(line[a][1])
            instruction = next((k for k in keys if k['frame'] == frame and frame != until), None)
            if instruction is None:
                instruction = dict(op='key', frame=frame, bones=[], added=True)
                after = animation.instrs.index(keys[0])
                at = next(i for i in range(after, len(animation.instrs))
                          if animation.instrs[i]['op'] in ('end', 'loop_start', 'loop_end') or animation.instrs[i]['frame'] > frame)
                animation.instrs.insert(at, instruction)
            block = next((g for g in instruction['bones'] if g['bone'] == carrier and g['div'] == ticks), None)
            if block is None:
                block = dict(bone=carrier, div=ticks, vals={})
                instruction['bones'].append(block)
            block['vals']['ty'] = delta


def _spread(raw, cyclic):
    """Each value averaged with BLEND_TICKS on each side."""
    n = len(raw)
    at = (lambda i: raw[i % n]) if cyclic else (lambda i: raw[max(0, min(n - 1, i))])
    return [sum(at(i + d) for d in range(-BLEND_TICKS, BLEND_TICKS + 1)) / (2 * BLEND_TICKS + 1) for i in range(n)]


def on_feet(source, loop=None):
    """Per tick of a source clip, how much it stands on its feet (1) or rests on something else (0); the changes
    between the two spread over a few ticks, so the body does not jump. loop: the tick its loop starts at, whose body
    repeats (its last tick is its first) and must not blend with what came before."""
    raw = [1.0 if foot >= low - CLEARANCE else 0.0 for foot, low, _ in source]
    if loop is None or loop >= len(raw) - 1:
        return _spread(raw, False)
    body = _spread(raw[loop:-1], True)
    return (_spread(raw[:loop], False) if loop else []) + body + body[:1]


def ground(model, rig, source_lows, feet, tolerance=KEY_TOLERANCE, rest_slots=()):
    """Rewrite the carrier's height of every clip (the module's header says how). rest_slots: clips that land on the
    lowest vertex throughout, because shorter legs bring a kneeling body to the floor. -> report per slot, all in y (down):
    feet: the lowest foot of the ticks on the feet, source and result, with the worst miss each way; mesh: the lowest
    vertex over the clip, source and result; part_sink: how far a part goes under the floor beyond the source's own,
    and which bone."""
    carrier, nb = rig.carrier, rig.nb
    report = {}
    for index, slot in clips(model).items():
        animation = model.anims.anims[index]
        frames, poses, _, events = replay(model, nb, index, slot, carrier)
        reference = [[v for j, v in enumerate(bone) if (b, j) != (carrier, 7)] for p in poses for b, bone in enumerate(p)]
        source = source_lows[index]
        weight = on_feet(source, animsheet.slot_frames(model, nb, slot)[1])
        if slot in rest_slots:
            weight = [0.0] * len(weight)
        constant = _chains(animation) is None
        for _ in range(GROUND_PASSES):
            frames, poses, heights, _ = replay(model, nb, index, slot, carrier)
            now = clip_lows(model, rig, index, slot, feet)
            miss = [w * (n[0] - target(s[0])) + (1 - w) * (n[1] - target(s[1])) for w, n, s in zip(weight, now, source)]
            if constant:
                ti = _translation(animation)
                animation.pose[carrier - 1][ti[1]] = _clamp16(animation.pose[carrier - 1][ti[1]] - max(miss))
                continue
            height = {}
            for f, h, m in zip(frames, heights, miss):
                height[f] = min(height.get(f, 1e9), h - m)
            _rewrite_heights(animation, carrier, height, tolerance)
        frames, poses, _, after_events = replay(model, nb, index, slot, carrier)
        same = [[v for j, v in enumerate(bone) if (b, j) != (carrier, 7)] for p in poses for b, bone in enumerate(p)]
        if same != reference or after_events != events:
            raise Refused(f'slot {slot:#x}: the height rewrite changed something else')
        after = clip_lows(model, rig, index, slot, feet)
        standing = [t for t, w in enumerate(weight) if w == 1]
        foot_miss = [after[t][0] - target(source[t][0]) for t in standing]
        resting = [after[t][1] - target(source[t][1]) for t, w in enumerate(weight) if w == 0]
        parts = [(after[t][1] - max(source[t][1], 0.0), after[t][2]) for t in standing] or [(0.0, None)]
        part = max(parts, key=lambda row: row[0])
        report[slot] = dict(ticks=len(after), standing=len(standing),
                            source_feet=_span([source[t][0] for t in standing] or [0.0]),
                            feet=_span([after[t][0] for t in standing] or [0.0]),
                            feet_under=round(max(foot_miss, default=0.0), 1), feet_over=round(-min(foot_miss, default=0.0), 1),
                            resting_under=round(max(resting, default=0.0), 1), resting_over=round(-min(resting, default=0.0), 1),
                            mesh=_span([s[1] for s in source]), mesh_after=_span([a[1] for a in after]),
                            part_sink=round(part[0], 1), part=part[1], constant=constant)
    return report


def _span(values):
    return [round(min(values), 1), round(max(values), 1)]


def _close_loops(model, nb, carrier):
    """Rounding can leave a looping clip a few units open sideways: take that off its last key inside the loop."""
    left = {}
    for index, slot in clips(model).items():
        animation = model.anims.anims[index]
        for _ in range(8):
            frames, start, _ = animsheet.slot_frames(model, nb, slot)
            if start is None or len(frames) - 1 <= start:
                break
            first, last = frames[start][carrier], frames[-1][carrier]
            drift = {ch: last[j] - first[j] for j, ch in zip((6, 7, 8), ('tx', 'ty', 'tz')) if last[j] != first[j]}
            if not drift:
                left.pop(slot, None)
                break
            left[slot] = drift
            body, inside = [], False
            for instruction in animation.instrs:
                if instruction['op'] == 'loop_start':
                    inside = True
                elif instruction['op'] == 'loop_end':
                    inside = False
                elif instruction['op'] == 'key' and inside:
                    body.append(instruction)
            for ch, d in drift.items():
                j = {'tx': 6, 'ty': 7, 'tz': 8}[ch]
                for instruction in reversed(body):      # a key's momentum can outlast its tick: keep the one that helps
                    block = next((g for g in instruction['bones'] if g['bone'] == carrier and ch in g['vals']), None)
                    if block is None:
                        continue
                    old = block['vals'][ch]
                    block['vals'][ch] = _clamp16(old - d)
                    frames = animsheet.slot_frames(model, nb, slot)[0]
                    if abs(frames[-1][carrier][j] - frames[start][carrier][j]) < abs(d):
                        break
                    block['vals'][ch] = old
    return left


def _speed(model, nb, slot):
    """Forward units per tick of a looping field clip, or None."""
    if slot >= len(model.anims.table) or model.anims.table[slot] is None:
        return None
    frames, loop, _ = animsheet.slot_frames(model, nb, slot)
    if loop is None or len(frames) - 1 <= loop:
        return None
    return abs(frames[-1][0][8] - frames[loop][0][8]) / (len(frames) - 1 - loop)


def carried_point(scales, k, bone, point):
    """Where a point fixed to a bone (an effect origin, a condition bubble) lands: the same bake as the bone's vertices."""
    p = [float(c) for c in point]
    if bone in scales:
        M, anchor = scales[bone]
        p = _apply(M, [p[j] - anchor[j] for j in range(3)])
        p = [p[j] + anchor[j] for j in range(3)]
    return [round(c * k) for c in p]


def species_patch(record, scales, k):
    """The fields of the species record tied to bones, carried through the bake."""
    patch = {}
    def moved(bone, xyz):
        if 'any' in xyz:
            return xyz[:1] + carried_point(scales, k, bone, [0, *xyz[1:]])[1:] if xyz[0] == 'any' else xyz
        return carried_point(scales, k, bone, xyz)
    if 'effect_origins' in record:
        patch['effect_origins'] = [[e[0], *moved(e[0], e[1:4]), e[4], *moved(e[4], e[5:8])] for e in record['effect_origins']]
    if 'effect_origin_fallback' in record:
        e = record['effect_origin_fallback']
        patch['effect_origin_fallback'] = [e[0], *moved(e[0], e[1:4])]
    if 'condition_bubble' in record:
        e = record['condition_bubble']
        patch['condition_bubble'] = [*moved(e[3], e[:3]), e[3]]
    return patch


def reshape(data, skeleton, sid, row):
    """The reshaped model of a row (groups, factors, height) -> (bytes, report, the bone scales and the final k).
    Raises Refused when a check fails."""
    _register(sid, skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = sid
    rig = Rig(model, skeleton)
    groups = {int(b): g for b, g in row['groups'].items()}
    groups = [groups.get(b, 'other') for b in range(rig.nb)]
    factors = row['factors']
    feet = [b for b in range(rig.nb) if groups[b] in ('foot', 'footpart', 'shin', 'thigh', 'hipjoint')]   # or a kneeling leg
    if not feet:
        raise Refused('no feet in the bone table')
    source_lows = lows(model, rig, feet)
    speeds = {slot: _speed(model, rig.nb, slot) for slot in SPEED_FLOOR}
    standing = rig.bounds(feet)[1]            # a hovering species keeps its clearance
    scales = bone_scales(rig, groups, factors, row.get('fit'))
    _bake(rig, scales)
    kl = factors.get('leg_axial', 1.0)
    carrier = rig.carrier
    if kl != 1:
        # a clip's first carrier offset differs from the idle's by the leg geometry of its first pose: it shrinks too
        idle = model.anims.anims[model.anims.table[0]]
        base = [idle.pose[carrier - 1][i] for i in _translation(idle)]
        for a in model.anims.anims:
            if a is not idle:
                v = a.pose[carrier - 1]
                for i, b0 in zip(_translation(a), base):
                    v[i] = _clamp16(b0 + kl * (v[i] - b0))
        _scale_keys(model.anims.anims, carrier, kl)
    top, floor = rig.bounds(feet)
    for a in model.anims.anims:
        ti = _translation(a)
        a.pose[carrier - 1][ti[1]] = _clamp16(a.pose[carrier - 1][ti[1]] + standing - floor)
    k = row.get('trim', 1.0) * (row['height'] + standing) / (top + floor)       # trim: the idle's lift after grounding
    if k < MIN_FINAL_SCALE:
        raise Refused(f'final scale {k:.3f}: the height rule shrinks the body too much')
    _rescale(model, k)
    rig.verts = {b: [list(v[:3]) for v in model.tmd.obj_verts(skeleton[b][0])] for b in rig.verts}
    for slot, speed in speeds.items():
        if speed:
            wanted = min(speed, max(speed * kl, SPEED_FLOOR[slot] * SPEED_MARGIN))
            now = _speed(model, rig.nb, slot)
            _scale_keys([model.anims.anims[model.anims.table[slot]]], 0, wanted / now)
    left = {slot: drift for slot, drift in _close_loops(model, rig.nb, carrier).items() if set(drift) != {'ty'}}
    if left:                # the height is rewritten next, and closed there
        raise Refused(f'loops left open: {left}')
    floors = ground(model, rig, source_lows, feet, row.get('key_tolerance', KEY_TOLERANCE), row.get('rest_slots', ()))
    left = _close_loops(model, rig.nb, carrier)
    if left:
        raise Refused(f'loops left open after grounding: {left}')
    for slot, r in floors.items():
        if max(r['feet_under'], r['resting_under']) > MAX_SINK or max(r['feet_over'], r['resting_over']) > MAX_FLOAT:
            raise Refused(f'slot {slot:#x}: feet {r["feet_under"]} under, {r["feet_over"]} over their floor; '
                          f'resting {r["resting_under"]} under, {r["resting_over"]} over')
        if r['part_sink'] > MAX_PART_SINK:
            raise Refused(f'slot {slot:#x}: bone {r["part"]} goes {r["part_sink"]} under the floor beyond the source')
    after = {slot: _speed(model, rig.nb, slot) for slot in SPEED_FLOOR}
    for slot, speed in after.items():
        if speed is not None and speed < SPEED_FLOOR[slot] and speed < speeds[slot]:
            raise Refused(f'slot {slot}: {speed:.1f} under the speed floor')
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    result = model.build()
    try:
        storage = motionstorage.require(result, len(skeleton))
    except ValueError as error:
        raise Refused(str(error))
    rig.m = mmd.MMD.parse(result, len(skeleton))
    rig.m.type = sid
    height = rig.bounds(feet)[0]
    if abs(height - row['height']) > 0.01 * row['height']:
        raise Refused(f'height {height:.0f} against {row["height"]}')
    report = dict(species=sid, factors=factors, final_scale=round(k, 4), height=round(height), bytes=[len(data), len(result)],
                  speeds={str(s): [speeds[s] and round(speeds[s], 1), after[s] and round(after[s], 1)] for s in speeds},
                  floors={f'{s:#x}': v for s, v in floors.items()},
                  resident_bytes=[storage['resident_bytes'], storage['resident_limit']])
    return result, report, scales, k


# ------------------------------------------------------------------ proportions, and the bake over another rig
RANK = ('head', 'foot', 'footpart', 'hand', 'shin', 'thigh', 'arm', 'shoulder', 'chest', 'pelvis', 'neck', 'headpart',
        'wing', 'tail', 'cloth', 'hipjoint', 'other', 'carrier')
FIT_GROUPS = ('arm', 'shoulder', 'hand', 'thigh', 'shin', 'tail', 'cloth', 'wing')
FIT_STEP = 0.9
MAX_ATTEMPTS = 40


def donor_groups(mapping, groups):
    """The group of every bone of a rig the mesh was bound to: the first of its source pieces' groups in RANK order.
    mapping: {source bone: bound bone} (a native binding's `map`), groups: {source bone: group}."""
    out = {}
    for source, bound in mapping.items():
        group = groups.get(int(source), 'other')
        if bound not in out or RANK.index(group) < RANK.index(out[bound]):
            out[bound] = group
    return out


def proportions(data, skeleton, groups, sid):
    """What makes a body chibi, as ratios of its height at rest: the head's height and width, the feet's width plus depth,
    the hands' height and the length of the legs (thigh, shin and foot together). groups: {bone: group}."""
    _register(sid, skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = sid
    rig = Rig(model, skeleton)
    group = [groups.get(b, 'other') for b in range(rig.nb)]
    feet = [b for b in range(rig.nb) if group[b] in ('foot', 'footpart', 'shin', 'thigh', 'hipjoint')]
    top, floor = rig.bounds(feet)
    _, mats = rig.rest()

    def extent(names, axis):
        values = []
        for b, vs in rig.verts.items():
            if group[b] in names:
                row = mats[b][axis]
                values += [row[0] * x + row[1] * y + row[2] * z + row[3] for x, y, z in vs]
        return max(values) - min(values) if values else 0.0
    height = top + floor
    return dict(height=round(height), head=round(extent(('head',), 1) / height, 3), head_width=round(extent(('head',), 0) / height, 3),
                foot=round((extent(('foot',), 0) + extent(('foot',), 2)) / height, 3), hand=round(extent(('hand',), 1) / height, 3),
                legs=round(extent(('thigh', 'shin', 'foot'), 1) / height, 3))


def reshape_bound(data, rig, sid, mapping, row, overrides=None):
    """The chibi bake over a mesh already bound to another rig (a native binding): the row's groups and fit follow the
    `mapping` onto the bound bones, its factors apply as they are (`overrides` replaces some), and the height it
    keeps is the bound model's own. A limb that the shorter legs leave crossing the floor is shortened a step at a
    time, and the uniform rescale is trimmed until the height holds. -> (bytes, report, scales, k, the row used)."""
    groups = donor_groups(mapping, {int(b): g for b, g in row['groups'].items()})
    used = dict(row, groups={str(b): g for b, g in groups.items()}, factors=dict(row['factors'], **(overrides or {})))
    used.pop('rest_slots', None)
    fit = {}
    for source, factor in (row.get('fit') or {}).items():
        bound = mapping.get(source)
        if bound is not None:
            fit[str(bound)] = min(fit.get(str(bound), 1.0), factor)
    used['fit'] = fit
    used['trim'] = 1.0
    used['height'] = proportions(data, rig, groups, sid)['height']
    for _ in range(MAX_ATTEMPTS):
        try:
            return (*reshape(data, rig, sid, used), used)
        except Refused as refusal:
            sunk = re.search(r'bone (\d+) goes', str(refusal))
            height = re.match(r'height (\d+) against (\d+)', str(refusal))
            if sunk:
                chain, b = [], int(sunk.group(1))
                while b > 0:
                    if used['groups'].get(str(b)) in FIT_GROUPS:
                        chain.append(b)
                    b = rig[b][1]
                if not chain:
                    raise
                for b in chain[:3]:
                    used['fit'][str(b)] = round(used['fit'].get(str(b), 1.0) * FIT_STEP, 3)
            elif height:
                used['trim'] = round(used['trim'] * int(height.group(2)) / int(height.group(1)), 4)
            else:
                raise
    raise Refused('the bake over the bound rig did not settle')


def build(data, skeleton):
    """The reviewed overlay of a pinned species (the manifest's row) over the recipe before it."""
    rows = json.loads(MANIFEST.read_text())
    from tools.models.field_animations.reviewed import reviewed
    digest = hashlib.sha256(data).hexdigest()
    matches = [(int(sid), row) for sid, row in rows.items() if row['source_sha256'] == reviewed(digest)]
    if len(matches) != 1:
        raise ValueError('Chibi proportions require an individually pinned source')
    sid, row = matches[0]
    if hashlib.sha256(json.dumps(skeleton).encode()).hexdigest() != row['skeleton_sha256']:
        raise ValueError('Chibi proportions: the skeleton differs from its reviewed source')
    previous = None
    if row.get('base_generator'):
        data, previous = importlib.import_module(row['base_generator']).build(data, skeleton)
    if reviewed(hashlib.sha256(data).hexdigest()) != row['post_source_sha256']:
        raise ValueError('Chibi proportions: the preceding recipe differs from the reviewed input')
    result, report, scales, k = reshape(data, skeleton, sid, row)
    if row.get('salute_cape_slots'):
        from tools.models.field_animations.cape import clear_salute
        result = clear_salute(result, skeleton, row['salute_cape_slots'], sid)
        storage = motionstorage.require(result, len(skeleton))
        report['bytes'][1] = len(result)
        report['resident_bytes'] = [storage['resident_bytes'], storage['resident_limit']]
    record = json.loads(next((ROOT / 'content/species').glob(f'{sid}-*.json')).read_text())
    proof = dict(report, source_sha256=digest, output_sha256=hashlib.sha256(result).hexdigest(),
                 preceding_recipe=previous, species_patch=species_patch(record, scales, k))
    if previous and 'generated_skeleton' in previous:
        proof['generated_skeleton'] = previous['generated_skeleton']
    return result, proof
