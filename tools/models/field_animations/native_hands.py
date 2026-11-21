"""Hands set on the forearms, and arms kept near the body, for a native-donor binding whose donor arms flare.

The recipe's `hands` row, for the slots it names (gaits; `alias` copies a slot to its donor twins):
- `narrow`: the shoulders and elbows are turned about the walking direction so the sideways lean of the upper arm and the
  forearm (against the line of the shoulders) keeps only `keep` of its swing about its mean, set `base` degrees out.
- the hand: the donor's own hand turns are dropped. Each hand is set straight on its forearm, turned about the
  forearm's length so its flat side `palm` (hand-bone axis) faces the body, and bent about the line of the shoulders by
  the forearm's swing `lag` ticks late, scaled by `gain`, plus `base`, never past `limit`: a wrist that trails.
- `clear`: on the ticks a forearm or hand enters the `bones` meshes (legs, feet, cape, body), the whole arm leans from
  the shoulder (`arm` degrees at most) and then the wrist turns (`swing`, `out`) by the smallest turn that clears,
  eased over the neighbouring ticks round the loop.
- `per_slot` overrides any key for one slot; `keep` (a share, or one per hand) holds a gesture instead: the hand keeps
  that share of the donor's own turn of the hand and nothing else runs (an idle fist at the chest).
Every term is cyclic over the clip, so loops close on the clip's own ticks; every other bone, slot and the root travel
are untouched. The gloves' own orientation on the hand bones is the binding's `aim` piece rule (native_binding.py).
"""
import copy
import hashlib
import json
import math
import os
import sys

from tools.derive import arraymath as np

import animsheet
import retarget as R
from tools.models.field_animations import animal_refine as A


def _wrap(degrees):
    return (degrees + 180) % 360 - 180


def _late(values, ticks, lag):
    out = []
    for t in range(ticks):
        x = (t - lag) % ticks
        i = math.floor(x)
        k = x - i
        a, b = values[i % ticks], values[(i+1) % ticks]
        out.append(a + _wrap(b - a)*k)
    return out


def _about(axis, degrees):
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    x, y, z = axis
    return [[c + x*x*(1-c), x*y*(1-c) - z*s, x*z*(1-c) + y*s],
            [y*x*(1-c) + z*s, c + y*y*(1-c), y*z*(1-c) - x*s],
            [z*x*(1-c) - y*s, z*y*(1-c) + x*s, c + z*z*(1-c)]]


def _lean(sk, pose, spec, arm, joint):
    """(lateral lean in degrees of the segment from `joint` to its child, forward axis) at this pose."""
    pos = R.world_pos(sk, pose)
    right, left = spec['narrow']['shoulders']
    ax = [pos[right][i] - pos[left][i] for i in range(3)]
    ax[1] = 0
    n = math.hypot(ax[0], ax[2])
    ax = [ax[0]/n, 0, ax[2]/n]
    child = arm['bones'][arm['bones'].index(joint) + 1]
    v = [pos[child][i] - pos[joint][i] for i in range(3)]
    length = math.sqrt(sum(c*c for c in v))
    return math.degrees(math.asin(max(-1, min(1, sum(v[i]*ax[i] for i in range(3))/length)))) * arm['side'], (-ax[2], 0, ax[0])


def narrow_arms(sk, frames, spec):
    n = spec['narrow']
    ticks = len(frames) - 1
    for arm in n['arms']:
        history = {b: frames[0][b][3:6] for b in arm['bones']}
        for tier, joint in enumerate(arm['bones'][:2]):
            keep, base = n['keep'][tier], n['base'][tier]
            lean = [_lean(sk, frames[t], spec, arm, joint)[0] for t in range(ticks)]
            mean = sum(lean)/ticks
            # the lean of each tick depends on the turns of the joints above it, so the tiers are done in order
            for t in range(ticks):
                pose = frames[t]
                want = base + keep*(lean[t] - mean)
                turn = 0.0
                for _ in range(4):
                    here, forward = _lean(sk, pose, spec, arm, joint)
                    step = 1.0
                    probe = copy.deepcopy(pose)
                    rots = R.world_rots(sk, probe)
                    A.set_world(sk, probe, joint, R.m3mul(_about(forward, step*arm['side']), rots[joint]), dict(history))
                    slope = _lean(sk, probe, spec, arm, joint)[0] - here
                    if abs(slope) < 1e-6:
                        break
                    delta = (want - here)/slope*step
                    rots = R.world_rots(sk, pose)
                    A.set_world(sk, pose, joint, R.m3mul(_about(forward, delta*arm['side']), rots[joint]), history)
                    turn += delta
        for b in arm['bones'][:2]:
            frames[ticks][b][3:6] = frames[0][b][3:6]


def _swing(sk, pose, hand, forearm, axis):
    """Angle in degrees of the forearm segment (elbow to wrist) about `axis` (the line of the shoulders): its swing
    forward and back. From the joint positions, so a roll of the forearm about its own length does not move it."""
    pos = R.world_pos(sk, pose)
    v = [pos[hand][i] - pos[forearm][i] for i in range(3)]
    down = [0.0, 1.0, 0.0]
    cross = [down[1]*v[2] - down[2]*v[1], down[2]*v[0] - down[0]*v[2], down[0]*v[1] - down[1]*v[0]]
    return math.degrees(math.atan2(sum(cross[i]*axis[i] for i in range(3)), sum(down[i]*v[i] for i in range(3))))


def _shoulder_axis(sk, pose, spec):
    pos = R.world_pos(sk, pose)
    right, left = spec['narrow']['shoulders']
    ax = [pos[right][i] - pos[left][i] for i in range(3)]
    ax[1] = 0
    n = math.hypot(ax[0], ax[2])
    return [ax[0]/n, 0.0, ax[2]/n]


def _facing(rotation, palm, toward):
    """Degrees to turn a hand about its forearm's length (the bone's x axis) so its flat side `palm` (in the bone's
    frame) faces the world direction `toward` as near as it can."""
    local = [sum(rotation[i][j]*toward[i] for i in range(3)) for j in range(3)]
    return math.degrees(math.atan2(palm[1]*local[2] - palm[2]*local[1], palm[1]*local[1] + palm[2]*local[2]))


def _part(rotation, share):
    """`share` of a rotation: the same axis, that share of its angle."""
    m = np.array(rotation, float)
    angle = math.acos(max(-1.0, min(1.0, (np.trace(m) - 1)/2)))
    if angle < 1e-6:
        return [list(r) for r in m]
    axis = np.array([m[2][1] - m[1][2], m[0][2] - m[2][0], m[1][0] - m[0][1]])/(2*math.sin(angle))
    return _about(axis.tolist(), math.degrees(angle*share))


def pose_hands(sk, frames, spec):
    """Each hand set straight on its forearm (the donor's neutral hand, the way the donor's own fist is built along the
    forearm), turned about the forearm's length so its flat side `palm` faces the body (`face` of the way), then swung
    about the line of the shoulders by the forearm's swing `lag` ticks late, scaled by `gain`, plus `base` degrees,
    never past `limit`: a wrist that trails the arm forward and back. The donor's own hand turns are dropped in these
    slots (a donor run that rolls its round fist 100 degrees about the forearm reads as a twisted wrist on a glove)."""
    ticks = len(frames) - 1
    history = {int(h): frames[0][int(h)][3:6] for h in spec['bones']}
    axes = [_shoulder_axis(sk, frames[t], spec) for t in range(ticks)]
    sides = {arm['bones'][-1]: arm['side'] for arm in spec['narrow']['arms']}
    for hand, forearm in ((int(h), f) for h, f in spec['bones'].items()):
        swing = [_swing(sk, frames[t], hand, forearm, axes[t]) for t in range(ticks)]
        late = _late(swing, ticks, spec['lag'])
        flex = [max(-spec['limit'], min(spec['limit'], spec['base'] + spec['gain']*_wrap(late[t] - swing[t])))
                for t in range(ticks)]
        for _ in range(2):      # a 1-2-1 smoothing round the loop
            flex = [(flex[t-1] + 2*flex[t] + flex[(t+1) % ticks])/4 for t in range(ticks)]
        palm = spec['palm'][str(hand)]
        for t in range(ticks):
            pose = frames[t]
            rots = R.world_rots(sk, pose)
            if spec.get('keep'):
                # a held gesture (an idle fist at the chest): only `keep` of the donor's own turn of the hand
                keep = spec['keep'][str(hand)] if isinstance(spec['keep'], dict) else spec['keep']
                hand_world = R.m3mul(rots[forearm], _part(R.rot_of(pose[hand]), keep))
                A.set_world(sk, pose, hand, hand_world, history)
                continue
            inward = [-sides[hand]*v for v in axes[t]]
            turn = spec['face']*_facing(rots[forearm], palm, inward)
            hand_world = R.m3mul(R.m3mul(_about(axes[t], flex[t]), rots[forearm]), _about((1, 0, 0), turn))
            A.set_world(sk, pose, hand, hand_world, history)
        frames[ticks][hand][3:6] = frames[0][hand][3:6]


_RAYS = ([1, .3, .2], [0, 1, .1], [.1, .2, 1], [-.7, .2, .5], [.3, -1, .2])


def _inside(points, tris, direction):
    """Points inside the closed mesh `tris` (n, 3, 3) by one ray's parity (Moeller-Trumbore)."""
    # Scalar ray tests avoid allocating point-by-triangle arrays in the
    # standard-library backend. Keep the same cross/dot order and thresholds.
    dx, dy, dz = direction
    rows = tris.tolist()
    if not rows:
        return np.zeros(len(points), bool)
    # A ray that misses the whole piece cannot hit any triangle, including
    # open pieces. Expand the bounds to retain grazing rays despite rounding.
    bounds = [(min(v[i] for tri in rows for v in tri) - 1e-6,
               max(v[i] for tri in rows for v in tri) + 1e-6) for i in range(3)]
    prepared = []
    for a, b, c in rows:
        ex, ey, ez = (b[i] - a[i] for i in range(3))
        fx, fy, fz = (c[i] - a[i] for i in range(3))
        hx, hy, hz = dy*fz - dz*fy, dz*fx - dx*fz, dx*fy - dy*fx
        det = (ex*hx + ey*hy) + ez*hz
        if abs(det) > 1e-9:
            prepared.append((a, ex, ey, ez, fx, fy, fz, hx, hy, hz, det))
    result = []
    for point in points.tolist():
        near, far = 0., math.inf
        for coordinate, d, (low, high) in zip(point, direction, bounds):
            if d == 0:
                if coordinate < low or coordinate > high:
                    far = -math.inf
                    break
            else:
                a, b = (low - coordinate) / d, (high - coordinate) / d
                near, far = max(near, min(a, b)), min(far, max(a, b))
        if far < near:
            result.append(False)
            continue
        hits = 0
        for a, ex, ey, ez, fx, fy, fz, hx, hy, hz, det in prepared:
            sx, sy, sz = (point[i] - a[i] for i in range(3))
            u = ((sx*hx + sy*hy) + sz*hz) / det
            if u < 0 or u > 1:
                continue
            qx, qy, qz = sy*ez - sz*ey, sz*ex - sx*ez, sx*ey - sy*ex
            v = ((qx*dx + qy*dy) + qz*dz) / det
            if v < 0 or u + v > 1:
                continue
            t = ((fx*qx + fy*qy) + fz*qz) / det
            hits += t > 1e-6
        result.append(hits % 2 == 1)
    return np.array(result, bool)


def _parts(rows):
    """The triangles of an object grouped into its separate pieces (shared vertices join them)."""
    up = {}

    def root(v):
        while up.setdefault(v, v) != v:
            up[v] = up[up[v]]
            v = up[v]
        return v
    for tri in rows:
        for v in tri[1:]:
            up[root(v)] = root(tri[0])
    groups = {}
    for i, tri in enumerate(rows):
        groups.setdefault(root(tri[0]), []).append(i)
    return [np.array(g) for g in groups.values()]


class _Mesh:
    """World vertices and triangles of chosen bones' objects in a pose (the root at the origin)."""

    def __init__(self, model, sk):
        self.model, self.sk = model, sk
        self.verts = np.array(model.tmd.verts, float)[:, :3]
        self.tris, self.parts = {}, {}
        for b, (o, _) in enumerate(sk):
            if o < 0:
                continue
            obj = model.tmd.objects[o]
            rows = []
            for prim in obj.prims:
                ids = [obj.vert_start + i for i in prim.decode()['verts']]
                rows += [[ids[k] for k in c] for c in [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else [])]
            self.tris[b] = (np.arange(obj.vert_start, obj.vert_start + obj.nvert), np.array(rows, int))
            self.parts[b] = _parts(rows)

    def world(self, pose, bones):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        rots, pos = R.world_rots(self.sk, p), R.world_pos(self.sk, p)
        out = {}
        for b in bones:
            m, at = np.array(rots[b], float), np.array(pos[b], float)
            ids, tris = self.tris[b]
            out[b] = (self.verts[ids] @ m.T + at, self.verts[tris] @ m.T + at)
        return out

    def inside_count(self, pose, hand, others):
        w = self.world(pose, [hand] + list(others))
        verts, tris = w[hand]
        points = np.concatenate([verts, tris.mean(1)])
        hit = np.zeros(len(points), bool)
        for b in others:
            for part in self.parts[b]:      # one closed piece at a time: two overlapping pieces cancel each other's parity
                votes = sum(_inside(points, w[b][1][part], d).astype(int) for d in _RAYS)
                hit |= votes >= 3
        return int(hit.sum())


def clear_hands(model, sk, frames, spec, solved=None):
    """Turn each hand, on the ticks it enters a leg, foot or the body (`clear` bones), by the smallest wrist swing about
    the line of the shoulders (`swing` degrees at most) and outward turn about the walking direction (`out` at
    most) that leaves it outside; the turns are eased over the neighbouring ticks round the loop, so the hand dodges
    the passing knee in one smooth flick instead of a snap.

    Returns the turns each tick needs: per hand, per pass, [the arm's, the hand's], each a list of [swing, out] per
    tick. With `solved` (such a list, from an earlier search on the same model and recipe) the search is skipped and
    those turns are applied: the same frames, without the contact tests."""
    c = spec['clear']
    mesh = _Mesh(model, sk) if solved is None else None
    ticks = len(frames) - 1
    sides = {arm['bones'][-1]: arm['side'] for arm in spec['narrow']['arms']}
    grid = sorted(((a, o) for a in range(-c['swing'], c['swing'] + 1, 3) for o in range(0, c['out'] + 1, 3)),
                  key=lambda ao: abs(ao[0]) + 1.5*ao[1])
    arm_grid = sorted(((a, o) for a in range(-c['arm'], c['arm'] + 1, 2) for o in range(0, c['arm'] + 1, 2)),
                      key=lambda ao: abs(ao[0]) + 1.5*ao[1])

    def turned(pose, bone, a, o, hand=None):
        """The pose with `bone` swung `a` degrees about the line of the shoulders and leant `o` degrees outward."""
        q = copy.deepcopy(pose)
        axis = _shoulder_axis(sk, q, spec)
        forward = (-axis[2], 0.0, axis[0])
        rots = R.world_rots(sk, q)
        turn = R.m3mul(_about(forward, -o*sides[hand or bone]), _about(axis, a))
        A.set_world(sk, q, bone, R.m3mul(turn, rots[bone]), {bone: q[bone][3:6]})
        return q

    def least(options, contact):
        """The first (smallest) turn that clears; when none does, the one that leaves the least inside."""
        best, fewest = (0, 0), None
        for a, o in options:
            n = contact(a, o)
            if not n:
                return a, o
            if fewest is None or n < fewest:
                best, fewest = (a, o), n
        return best

    def ease(need):
        """Eased round the loop, never below what a tick needs."""
        eased = list(need)
        for _ in range(c.get('ease', 3)):
            soft = [tuple((eased[t-1][i] + 2*eased[t][i] + eased[(t+1) % ticks][i])/4 for i in range(2)) for t in range(ticks)]
            eased = [tuple(n[i] if abs(n[i]) > abs(s[i]) else s[i] for i in range(2)) for n, s in zip(need, soft)]
        return eased

    record = []
    for index, (hand, forearm) in enumerate((int(h), f) for h, f in spec['bones'].items()):
        shoulder = sk[forearm][1]
        known = solved[index] if solved is not None else None
        passes = []
        record.append(passes)
        for number in range(c.get('passes', 3)):      # an eased turn can still graze on a neighbouring tick: again on top
            if known is not None and number >= len(known):
                break
            moved = False
            # the forearm or the hand in a leg: first the whole arm leans out from the shoulder, as little as clears
            # it, so the wrist keeps its line; the hand turns only for what is left
            def arm_contact(pose):
                return mesh.inside_count(pose, forearm, c['bones']) + mesh.inside_count(pose, hand, c['bones'])
            if known is not None:
                need = [tuple(turn) for turn in known[number][0]]
            else:
                need = [(0, 0)]*ticks
                for t in range(ticks):
                    if arm_contact(frames[t]):
                        need[t] = least(arm_grid, lambda a, o: arm_contact(turned(frames[t], shoulder, a, o, hand)))
            arm_need = need
            if any(a or o for a, o in need):
                moved = True
                for t, (a, o) in enumerate(ease(need)):
                    q = turned(frames[t], shoulder, a, o, hand)
                    frames[t][shoulder][3:6] = q[shoulder][3:6]
                frames[ticks][shoulder][3:6] = frames[0][shoulder][3:6]
            if known is not None:
                need = [tuple(turn) for turn in known[number][1]]
            else:
                need = [(0, 0)]*ticks
                for t in range(ticks):
                    if mesh.inside_count(frames[t], hand, c['bones']):
                        need[t] = least(grid, lambda a, o: mesh.inside_count(turned(frames[t], hand, a, o), hand, c['bones']))
            passes.append([[list(turn) for turn in arm_need], [list(turn) for turn in need]])
            if any(a or o for a, o in need):
                moved = True
                for t, (a, o) in enumerate(ease(need)):
                    frames[t][hand][3:6] = turned(frames[t], hand, a, o)[hand][3:6]
                frames[ticks][hand][3:6] = frames[0][hand][3:6]
            if not moved:
                break
    return record


SOLVED = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../content/models/imports/native-hands-solved.json')
SEARCHED = {}      # key -> {slot: turns} of the searches this process ran (tools/models/solve_hands.py writes them)
SEARCH = 1          # the search's own version: raise it with any change to clear_hands' grids, order or easing


def solved_key(source, sk, spec):
    """What a search depends on: the model the hands are loosened on, its skeleton and the recipe."""
    text = json.dumps([[list(b) for b in sk], spec], sort_keys=True, separators=(',', ':'))
    return hashlib.sha1(bytes(source) + text.encode()).hexdigest()


def solved_turns(key):
    """The committed turns of `key` ({slot: turns}), or None: NATIVE_HANDS_SOLVED=search ignores them (the search runs,
    as it does for a model or recipe the table has not seen), =require refuses to search."""
    mode = os.environ.get('NATIVE_HANDS_SOLVED', '')
    if mode == 'search':
        return None
    table = {}
    if os.path.isfile(SOLVED):
        with open(SOLVED, encoding='utf-8') as f:
            stored = json.load(f)
        if stored.get('search') == SEARCH:      # turns of an older search are not this one's
            table = stored['turns']
    if key not in table and mode == 'require':
        raise ValueError(f'native hands: no solved turns for {key} in {os.path.basename(SOLVED)}: run '
                         'tools/models/solve_hands.py')
    return table.get(key)


def run_hands(model, sk, spec, source=None):
    """`model` with the hands of the recipe's slots loosened; returns the built bytes. `source` is the bytes `model`
    was parsed from: with them, the turns that clear the hands come from the committed table when it has this model
    and recipe (content/models/imports/native-hands-solved.json), and from the search otherwise."""
    n = len(sk)
    additions = []
    key = solved_key(source, sk, spec) if source is not None else None
    known = solved_turns(key) if key else None
    if key and known is None and any(dict(spec, **spec.get('per_slot', {}).get(str(slot), {})).get('clear') for slot in spec['slots']):
        print(f'native hands: no solved turns for this model and recipe ({key[:12]}), searching them: this takes many '
              'minutes (tools/models/solve_hands.py stores them)', file=sys.stderr, flush=True)
    for slot in spec['slots']:
        frames, loop, events = animsheet.slot_frames(model, n, slot)
        frames = copy.deepcopy(frames)
        row = dict(spec, **spec.get('per_slot', {}).get(str(slot), {}))
        if spec.get('narrow') and not row.get('keep'):
            narrow_arms(sk, frames, row)
        pose_hands(sk, frames, row)
        if row.get('clear'):
            if known is not None:
                clear_hands(model, sk, frames, row, known[str(slot)])
            else:
                turns = clear_hands(model, sk, frames, row)
                if key:
                    SEARCHED.setdefault(key, {})[str(slot)] = turns
        additions.append((slot, frames, loop, events))
        additions += [(alias, frames, loop, events) for alias in spec.get('alias', {}).get(str(slot), [])]
    return A.finish(model, additions, n, charts=False)
