#!/usr/bin/env python3
"""A bone map by anatomy: legs with legs, arms with arms, head, tail and torso, chain against chain.

The importer's map (import_batch.bone_map) pairs bones one by one by position, and ties a hand to a foot or the whole body to a tail
when they happen to be near. Here each skeleton is first read into its parts, from the shape of its bones (import_batch.Shape):

  feet     the lowest mirrored pairs of bones (two, or four for a quadruped)
  hands    the end of the mirrored pair of limbs that hangs the furthest below its shoulder
  head     the highest bone that is not a limb; tail: the furthest back
  limb     the chain from the highest ancestor that holds no other end down to its end (thigh, shin, foot / shoulder, arm, hand)

and the parts are paired (a left leg with a left leg, the front legs of a quadruped with the donor's front legs) and walked together:
bone i of a chain of n against bone round(i*(m-1)/(n-1)) of one of m, with the first and the last fixed; bones without a mesh (pivots)
are skipped on the donor's side. The bones that host the legs, and those that host arms and head, are paired too (hips with hips,
torso with torso). What no part covers is left to the caller.

  limb_map(T, S) -> {target bone: donor bone}      T, S: import_batch.Shape
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, sys


def _positions(S):
    return [tuple(j) for j in S.joint], [tuple(t) for t in S.tip]


def _children(S):
    kids = {}
    for b in range(1, len(S.parent)):
        kids.setdefault(S.parent[b], []).append(b)
    return kids


def _desc(kids, b):
    out, st = set(), [b]
    while st:
        x = st.pop()
        for c in kids.get(x, []):
            if c not in out:
                out.add(c); st.append(c)
    return out


def _chain_to(S, top, bone):
    path = [bone]
    while path[-1] != top and S.parent[path[-1]] > 0:
        path.append(S.parent[path[-1]])
    return path[::-1]


def parts(S):
    """The parts of a Shape: dict(legs=[(key, chain)], arms=[(side, chain)], head=chain, tail=chain, legs_host=bone, upper_host=bone)."""
    import walkpolish
    skel = [(0, p) for p in S.parent]
    pos, tip = _positions(S)
    n = len(S.parent)
    kids = _children(S)
    feet = walkpolish.feet_of(skel, pos)
    feet = [max(_desc(kids, f) | {f}, key=lambda c: tip[c][1] if S.mass[c] else -9) for f in feet]     # the foot, not the shin above it
    # a foot's limb: from the highest ancestor that holds no other terminal
    terminals = set(feet)

    def limb(end, others):
        top = end
        while S.parent[top] > 0:
            p = S.parent[top]
            if _desc(kids, p) & (others - {end}) or p in others:
                break
            top = p
        return _chain_to(S, top, end)

    out = dict(legs=[], arms=[], head=[], tail=[])
    leg_bones = set()
    # arms: the mirrored pair that hangs furthest below its shoulder, found as walkpolish.arms_of does, then followed to the farthest bone
    for f in feet:
        pass
    legs_chains = {f: None for f in feet}
    hands = []
    arms = _arms(S, skel, pos, kids, set(b for f in feet for b in _chain_to(S, _top_of_leg(S, kids, f, terminals), f)))
    for sh, el, x in arms:
        far = max(_desc(kids, sh) | {sh}, key=lambda c: sum((tip[c][i] - joint_of(S, sh)[i]) ** 2 for i in range(3)))
        hands.append(far)
    terminals |= set(hands)
    # head and tail among the bones not in a limb
    limb_bones = set()
    for f in feet:
        limb_bones |= set(limb(f, terminals))
    for h in hands:
        limb_bones |= set(limb(h, terminals))
    free = [b for b in range(1, n) if b not in limb_bones and S.mass[b]]
    top = [b for b in free if tip[b][1] < -0.62 and S.mass[b] > 3]
    head_tip = max(top, key=lambda b: S.mass[b] * max(0.1, 1 - 2 * abs(tip[b][0]))) if top else (min(free, key=lambda b: tip[b][1]) if free else None)
    tail_tip = None
    if free:
        hips = pos[1]
        leaf = lambda b: not any(S.mass[c] for c in _desc(kids, b))
        back = [b for b in free if leaf(b) and tip[b][2] > hips[2] + 0.08 and tip[b][1] > -0.8 and b != head_tip
                and S.parent[b] > 0]
        if back:
            tail_tip = max(back, key=lambda b: tip[b][2])
    terminals |= {x for x in (head_tip, tail_tip) if x}
    for f in feet:
        out['legs'].append((f, limb(f, terminals)))
    for h in hands:
        out['arms'].append((h, limb(h, terminals)))
    out['head'] = limb(head_tip, terminals) if head_tip else []
    out['jaw'] = None                       # the jaw: a mesh leaf under the last head bone that hangs lowest (the mouth opens by turning it)
    if out['head']:
        last = out['head'][-1]
        leaves = [c for c in kids.get(last, []) if S.mass[c] and not any(S.mass[x] for x in _desc(kids, c))]
        if leaves:
            out['jaw'] = max(leaves, key=lambda c: tip[c][1])
    out['tail'] = limb(tail_tip, terminals) if tail_tip else []
    allroots = [c[0] for _, c in out['legs']]
    out['legs_host'] = S.parent[allroots[0]] if allroots else None
    up = [c[0] for _, c in out['arms']] + ([out['head'][0]] if out['head'] else [])
    out['upper_host'] = S.parent[up[0]] if up else None
    out['wings'] = []
    used = set(limb_bones) | set(out['head']) | set(out['tail']) | ({out['jaw']} if out['jaw'] else set())
    for _, c in out['arms']:
        used |= set(c)
    # more limbs hanging from the body's centre line: a second pair of arms (two or more bones) or wings (one bone), mirrored in x
    centre = lambda b: abs(pos[b][0]) < 0.03
    roots = [b for b in range(1, n) if b not in used and not centre(b) and S.parent[b] > 0 and centre(S.parent[b])
             and not (_desc(kids, b) & used) and S.mass[b] + sum(S.mass[x] for x in _desc(kids, b)) > 0]
    def chain_of(b):
        c = [b]
        while True:
            ks = [k for k in kids.get(c[-1], []) if S.mass[k] or _desc(kids, k)]
            if not ks:
                return c
            c.append(max(ks, key=lambda k: S.mass[k] + sum(S.mass[x] for x in _desc(kids, k))))
    taken = set()
    for r in sorted(roots, key=lambda b: pos[b][1]):
        if r in taken or pos[r][0] <= 0:
            continue
        mates = [q for q in roots if q not in taken and pos[q][0] < 0 and abs(pos[q][1] - pos[r][1]) < 0.1 and len(chain_of(q)) == len(chain_of(r))]
        if not mates:
            continue
        q = min(mates, key=lambda q: abs(pos[q][1] - pos[r][1]) + abs(pos[q][0] + pos[r][0]))
        taken |= {r, q}
        cr, cq = chain_of(r), chain_of(q)
        massful = [b for b in cr if S.mass[b]]
        (out['arms'] if len(massful) >= 2 else out['wings']).extend([(cr[-1], cr), (cq[-1], cq)])
    out['pos'], out['tip'] = pos, tip
    return out


def _arms(S, skel, pos, kids, leg_bones):
    """walkpolish.arms_of, but an arm may be held forward or barely hang (a DW2 body): the pair of limbs, not wings, that reaches
    furthest from its shoulder."""
    import rigfix, walkpolish
    a = walkpolish.arms_of(skel, pos, leg_bones)
    if a:
        return a
    roles = rigfix.roles(S)
    n = len(S.parent); tip = S.tip
    best = None
    for b in range(1, n):
        if b in leg_bones or not S.mass[b] or S.tip[b][0] <= 0.03:
            continue
        mates = [c for c in range(1, n) if c not in leg_bones and S.mass[c] and S.tip[c][0] < -0.03 and abs(S.tip[c][0] + S.tip[b][0]) < 0.15
                 and abs(S.tip[c][1] - S.tip[b][1]) < 0.1]
        if not mates or roles[b] == 'wing':
            continue
        c = min(mates, key=lambda c: abs(S.tip[c][0] + S.tip[b][0]))
        # shoulders: climb while the parent is off-centre
        def up(x):
            path = [x]
            while S.parent[path[-1]] > 0 and abs(S.tip[S.parent[path[-1]]][0]) > 0.02 and S.parent[path[-1]] not in leg_bones and len(path) < 4:
                path.append(S.parent[path[-1]])
            return path[::-1]
        pa, pc = up(b), up(c)
        reach = max((sum((S.tip[d][i] - S.joint[pa[0]][i]) ** 2 for i in range(3)) ** .5 for d in _desc(kids, pa[0]) | {pa[0]}), default=0)
        if len(pa) != len(pc) or reach < 0.1:
            continue
        if best is None or reach > best[0]:
            best = (reach, pa, pc)
    if not best:
        return []
    el = lambda c: c[1] if len(c) > 1 else c[0]                 # a one-bone arm: its own bone is its elbow too
    return [(best[1][0], el(best[1]), pos[best[1][-1]][0]), (best[2][0], el(best[2]), pos[best[2][-1]][0])]


def joint_of(S, b):
    return S.joint[b]


def _top_of_leg(S, kids, f, terminals):
    top = f
    while S.parent[top] > 0 and not (_desc(kids, S.parent[top]) & (terminals - {f})):
        top = S.parent[top]
    return top


def _align(a, b):
    """Pair the bones of chain a with those of chain b, ends fixed, in between by proportion."""
    if not a or not b:
        return {}
    if len(a) == 1:
        return {a[0]: b[0]}
    out = {}
    for i, x in enumerate(a):
        out[x] = b[round(i * (len(b) - 1) / (len(a) - 1))] if len(b) > 1 else b[0]
    return out


def _key(P, chain, S):
    """(side, front) of a limb: the sign of its end's x and whether it is in the front half."""
    end = chain[-1]
    return (S.tip[end][0] > 0, S.tip[end][2])


def limb_map(T, S):
    PT, PS = parts(T), parts(S)
    # parts that cannot be trusted are left out: two arms that are the same chain, a head that is the body root
    ac = [tuple(c) for _, c in PT['arms']]
    if len(set(ac)) < len(ac):
        PT['arms'] = []
    if 1 in PT['head'] or len(PT['head']) > 4:
        PT['head'] = []
    if len(PT['tail']) > 7:
        PT['tail'] = []
    m = {}
    mass = lambda sh, c: [b for b in c if sh.mass[b]] or c

    def pair(listT, listS, shT, shS):
        # by side; within a side by front-to-back order (-z is forward)
        for side in (True, False):
            a = sorted([c for _, c in listT if (shT.tip[c[-1]][0] > 0) == side], key=lambda c: shT.tip[c[-1]][2])
            b = sorted([c for _, c in listS if (shS.tip[c[-1]][0] > 0) == side], key=lambda c: shS.tip[c[-1]][2])
            if len(a) != len(b):                       # a biped against a quadruped: the pair of the matching end
                if len(a) < len(b):
                    b = [b[0]] if len(a) == 1 and shT.tip[a[0][-1]][2] <= 0 else ([b[-1]] if len(a) == 1 else b[:len(a)])
                else:
                    a = a[:len(b)]
            for x, y in zip(a, b):
                m.update(_align(mass(shT, x), mass(shS, y)))
    pair(PT['legs'], PS['legs'], T, S)
    pair(PT['arms'], PS['arms'], T, S)
    pair(PT.get('wings', []), PS.get('wings', []), T, S)
    for k in ('head', 'tail'):
        if PT[k] and PS[k]:
            a, b = mass(T, PT[k]), mass(S, PS[k])
            if k == 'head' and len(a) == 1 and len(b) > 1:          # one head bone against a neck and a head: the head proper (the biggest)
                m[a[0]] = max(b, key=lambda x: S.mass[x])
            else:
                m.update(_align(a, b))
    if PT.get('jaw') and PS.get('jaw'):
        m[PT['jaw']] = PS['jaw']
    if PT['legs_host'] and PS['legs_host'] and T.mass[PT['legs_host']]:
        m.setdefault(PT['legs_host'], PS['legs_host'])
    if PT['upper_host'] and PS['upper_host'] and T.mass[PT['upper_host']]:
        m.setdefault(PT['upper_host'], PS['upper_host'])
    # the target's top bone with mass that no part covers (the body root): the donor's body bone that hosts its limbs
    return {tb: sb for tb, sb in m.items() if T.mass[tb] or True}


def shape_from_mmd(path, t):
    """import_batch.Shape of a finished MMD of species/type t (the donor_shape recipe applied to a model file)."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import import_batch as IB, mmd, retarget
    e = mmd.exe(); nb = e.bone_count[t]
    m = mmd.MMD.load(path, t)
    M = mmd.bone_matrices(m, retarget.rest_pose(m, nb, 0))
    joints, tips, mass, pts, lows = [], [], [], [], []
    for b, (oi, par) in enumerate(e.skeleton[t]):
        joints.append([M[b][r][3] for r in range(3)])
        vs = [IB.m_apply(M[b], v[:3]) for v in m.tmd.obj_verts(oi)] if oi >= 0 else []
        pts += vs
        lows.append(max(v[1] for v in vs) if vs else None)
        tips.append([sum(v[k] for v in vs) / len(vs) for k in range(3)] if vs else joints[-1])
        mass.append(len(vs))
    return IB.Shape(joints, tips, mass, [p for _, p in e.skeleton[t]], IB.bbox(pts), pts, lows)
