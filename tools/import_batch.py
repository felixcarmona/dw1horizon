#!/usr/bin/env python3
"""Batch import: Digimon from other PS1 games -> DW1 species, with no per-Digimon hand work.

Documented in docs/mods/models.md, "Batch import", and content/imports/.
Each entry of a list (JSON) names a source model; for every one this tool:

 1. loads it (tools/dcb2mmd.py: Digimon Digital Card Battle; tools/dw3mmd.py: DW2003) and
    takes its first idle frame as the rest pose (the card game's modelling pose is not
    always a standing pose);
 2. fixes budgets by rule: palettes merged down to 15 (row 15 stays the flat sprite's), the
    model scaled when it is taller or wider than any DW1 partner of its level, animation
    tolerance raised until the MMD fits PARTNER_MODEL_BUFFER (0x18800), then layered idle
    motion dropped, then source-game technique clips dropped; or reported as hand work;
 3. picks the DW1 donor of the everyday animations by skeleton similarity (`donor_scores`:
    joints, piece directions and masses in height units, sides, hierarchy, proportions,
    element and level) and builds the bone map with the same costs;
 4. cuts the source game's 8 battle animations into battle slots by analysing them
    (`analyse_clips`: motion energy, hips travel and height; per-game convention for which
    animation is what);
 5. picks level, element (the card's own specialty through a mapping derived from the
    Digimon both games share), stats by level (medians of DW1 partners), techniques (the
    donor's own, filtered by element: their effects know the donor's original type), the
    donor's finisher, an evolution source with a free slot (level - 1, element), effect
    origins and the condition bubble moved onto the new skeleton;
 6. writes content/imports/specs/<Name>.json (mmdport.build_partner),
    build/batch/<Name>.MMD/.TIM, content/species/<id>-<name>.json, a contact sheet and a
    report.

Usage (from the repository root):
  import_batch.py run LIST.json [--only NAME ...]      everything above, for the whole list
  import_batch.py donors LIST.json [--only NAME]       donor ranking of each entry
  import_batch.py clips LIST.json [--only NAME]        battle clip analysis of each entry
  import_batch.py report LIST.json                     the per-Digimon outcome table

LIST.json: {"first_id": 183, "out": "build/batch", "digimon": [
              {"name": "Wormmon", "game": "dcb", "model": 149}, ...
              optional per entry: "level" (3 rookie, 4 champion, 5 ultimate, "mega"),
              "element" (0..6), "donor" (DW1 type), "anims_from" (another model id of the
              same game whose battle animations are used), "height" (units)]}

Player replay uses the bundled readers and the Python standard library.
"""
import argparse
import collections
import copy
import importlib.util
import json
import math
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DCB_ROOT = os.environ.get('DCB_ROOT', os.path.join(os.path.dirname(ROOT), 'digimoncardbattle'))
sys.path.insert(0, HERE)


def _venv():
    """Kept for developer front ends; replay uses the standard library."""



import mmd  # noqa: E402
import meshfix  # noqa: E402
import mmdport  # noqa: E402
import retarget  # noqa: E402
import species  # noqa: E402

LEVELS = {3: 'Rookie', 4: 'Champion', 5: 'Ultimate', 6: 'Mega'}
ELEMENTS = ['Fire', 'Battle', 'Air', 'Nature', 'Ice', 'Mech', 'Filth']
MOVE_DATA = 0x9623C                        # file offset of MOVE_DATA in SLUS_010.32 (docs/reference/combat.md)
CONDITION_FX = 0x8012A2C4                  # SVECTOR CONDITION_FX_OFFSETS[177] (x, y, z, bone)
FINISHER_FIRST = 58
# everyday slots that get the source game's idle motion on the bones the map leaves out
# (the list dcb-import used for Veemon: idle, walk, run, moods, tired, battle walks)
LAYER_SLOTS = [0x00, 0x01, 0x02, 0x03, 0x04, 0x11, 0x12, 0x1B, 0x22, 0x23, 0x24]
# slots every DW1 partner (Rookie and up) has: the state machine's (docs/mods/species.md)
REQUIRED_SLOTS = [s for s in range(0x2D) if s not in (0x06, 0x14, 0x1A, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x26, 0x27)]
OPTIONAL_SLOTS = [0x1C, 0x1D, 0x1E, 0x1F, 0x20]   # only some partners have them (27, 17, 8, 3, 1 of 53)
# sizes: DW1 partners of each level, idle pose (tools: `donors`); a model outside is scaled
HEIGHT_RANGE = {3: (180, 320), 4: (200, 460), 5: (180, 500), 6: (400, 500)}
MAX_HALF_WIDTH = 360            # Birdramon 333, Phoenixmon 356 (wings)
MAX_HALF_DEPTH = 420            # Drimogemon 426
# battle stats by level (wild battles, dws.py place); the partner's are the DW1 medians
WILD = {3: dict(hp=600, mp=500, off=120, deff=90, speed=110, brain=80, bits=200),
        4: dict(hp=1500, mp=1200, off=250, deff=200, speed=200, brain=180, bits=600),
        5: dict(hp=3000, mp=3000, off=400, deff=350, speed=300, brain=300, bits=1500)}


# ------------------------------------------------------------------ small math
def v_sub(a, b): return [x - y for x, y in zip(a, b)]
def v_add(a, b): return [x + y for x, y in zip(a, b)]
def v_mul(a, k): return [x * k for x in a]
def v_len(a): return math.sqrt(sum(x * x for x in a))
def m_apply(M, v): return [sum(M[r][c] * v[c] for c in range(3)) + M[r][3] for r in range(3)]
def m_rot(M, v): return [sum(M[r][c] * v[c] for c in range(3)) for r in range(3)]
def m_rot_t(M, v): return [sum(M[c][r] * v[c] for c in range(3)) for r in range(3)]


def q_angle(a, b):
    d = abs(sum(x * y for x, y in zip(a, b)))
    return 2 * math.acos(min(1.0, d))


# ------------------------------------------------------------------ loading
DROP_OVER = 0.27           # primitives over 713 that the smallest-face drop may remove (was 0.12 up to batch 11)


def load_source(entry, log=print, card_metadata=True):
    """(mmdport.Model, meta) of a list entry; meta: card level/element when known."""
    game = entry.get('game', 'dcb')
    clip_policy = entry.get('clip_policy')
    if clip_policy is not None and (game != 'dcb' or clip_policy not in ('dcb-original', 'dcb-grounded')):
        raise ValueError(f'unsupported clip_policy: {clip_policy!r} for {game}')
    if game == 'dcb':
        _venv()
        import dcb2mmd
        m = dcb2mmd.load(int(entry['model']), log=log, max_palettes=64)
        meta = dcb_card(int(entry['model'])) if card_metadata else {}
        if entry.get('anims_from') is not None:
            a = dcb2mmd.load(int(entry['anims_from']), log=lambda *x: None, max_palettes=64)
            if len(a.bones) != len(m.bones):
                raise SystemExit(f'{entry["name"]}: anims_from {entry["anims_from"]} has another skeleton')
            m.anims = a.anims
    elif game == 'dw3':
        import dw2mmd
        import dw3mmd
        # rule: over 713 primitives (the largest DW1 model) the triangle pairs are merged into quads at wider
        # angles (8, 15, 25, 40 degrees) until it fits; a spec records the angle it needed
        # Only the mesh angle varies between candidates. Decode the source,
        # texture and every animation once, then try each angle on fresh bones.
        raw = dw3mmd.load(entry['model'], scale=float(entry.get('scale', dw3mmd.UNIT_SCALE)),
                          quad_angle=0, normal_angle=0, log=log)
        for qa in ([entry['quad_angle']] if entry.get('quad_angle') else (8.0, 15.0, 25.0, 40.0)):
            m = copy.copy(raw)
            m.bones = copy.deepcopy(raw.bones)
            nq = sum(dw3mmd.merge_quads(b, qa) for b in m.bones) if qa > 0 else 0
            nn = sum(dw3mmd.merge_normals(b, 4.0) for b in m.bones)
            if qa == 8.0:
                log(f'  {nq} quads made from pairs of triangles')
                log(f'  {nn} normals merged into one within 4 degrees')
            if sum(len(b['prims']) for b in m.bones) <= 713:
                break
        m.quad_angle = qa
        n0 = sum(len(b['prims']) for b in m.bones)
        if 713 < n0 <= 713 * (1 + float(entry.get('drop_over', DROP_OVER))) and not entry.get('no_drop') \
                and not entry.get('meshfix'):     # (no_drop: the before/after comparison)
            # rule: up to DROP_OVER (27 %; 12 % until batch 12) over the limit, the smallest faces (by area) are dropped: they are the seam and
            # detail slivers (a piece never loses its last face)
            faces = []
            for bi, b in enumerate(m.bones):
                V = b['verts']
                ars = []
                for pi, pr in enumerate(b['prims']):
                    v = [V[k] for k in pr['verts']]
                    ar = 0.0
                    for t in ((0, 1, 2),) if len(v) == 3 else ((0, 1, 2), (1, 3, 2)):
                        a_, b_, c_ = (v[k] for k in t)
                        u = [b_[i] - a_[i] for i in range(3)]
                        w = [c_[i] - a_[i] for i in range(3)]
                        ar += 0.5 * math.sqrt((u[1] * w[2] - u[2] * w[1]) ** 2 + (u[2] * w[0] - u[0] * w[2]) ** 2
                                              + (u[0] * w[1] - u[1] * w[0]) ** 2)
                    ars.append(ar)
                mean = sum(ars) / max(1, len(ars))
                # rule (batch 12): the area is taken relative to the piece's own mean face, so a small piece made of
                # small faces (a head: batch 11's absolute-area drop took WarGrowlmon's and MegaGargomon's faces)
                # is not stripped before the sliver faces of the big pieces
                faces += [(ar / mean if mean else 0.0, bi, pi) for pi, ar in enumerate(ars)]
            faces.sort()
            drop = {}
            for cap in (0.35, 0.6, 1.0):               # at most this share of a piece's faces, then more if still over
                for ar, bi, pi in faces:
                    if n0 - sum(len(x) for x in drop.values()) <= 713:
                        break
                    left = len(m.bones[bi]['prims']) - len(drop.get(bi, ()))
                    if left > max(1, (1 - cap) * len(m.bones[bi]['prims'])) and pi not in drop.get(bi, ()):
                        drop.setdefault(bi, set()).add(pi)
            for bi, ds in drop.items():
                m.bones[bi]['prims'] = [pr for pi, pr in enumerate(m.bones[bi]['prims']) if pi not in ds]
            m.dropped_faces = n0 - sum(len(b['prims']) for b in m.bones)
            log(f'  primitives still {n0}: the {m.dropped_faces} smallest faces dropped')
        if qa != 8.0:
            log(f'  primitives over 713 at 8 degrees: triangle pairs merged within {qa:g} degrees')
        dw2mmd._dw2()
        m.game, m.idle = 'dw3', 'anim_00'                      # slot 0 loops and stands (dw1-port.md there)
        import rigfix
        m.hub = dw2mmd.hub_roots(m, log)                       # rule: one root (the body), as for DW2
        rigfix.on_load(m, entry, log)                          # rule: too many bones merged (rigfix.py)
        meta = {}
    elif game == 'dw2':
        import dw2mmd
        m = dw2mmd.load(entry['model'], scale=entry.get('scale'), log=log)  # DW1 units; size rules come later
        m.game, m.idle = 'dw2', 'A0'
        m.hub = dw2mmd.hub_roots(m, log)                      # rule: one root (the body), the other pieces hang from it
        dw2mmd.concat(m, 'C012', ['C0', 'C1', 'C2'])          # the three knock-backs are one fall (0x2b)
        meta = {}
    else:
        raise SystemExit(f'{entry["name"]}: unknown game {game}')
    # rule (meshfix): a model over a mesh budget (more than 713 primitives, 34 bones, a piece over 172 vertices) is brought
    # under it by tools/meshfix.py (weld the least important bones, decimate keeping the seams, split pieces onto helper
    # bones) when the list entry asks (`"meshfix": true` or a dict of parameters) or the model is beyond what the
    # smallest-face drop can take; the parameters used are recorded in the spec
    mf = entry.get('meshfix')
    over = meshfix.prim_count(m) > (713 * (1 + float(entry.get('drop_over', DROP_OVER))) if game == 'dw3' else 713)
    if mf is not False and (mf is not None or (over and game != 'dw1')):
        params = mf if isinstance(mf, dict) else {}
        lines = []
        info = meshfix.apply(m, params, log=lines.append)
        m.meshfix = meshfix.spec_params(info, params) or True
        m.meshfix_log = [x.strip() for x in lines if 'candidate' not in x]
    m.name = entry['name']
    m.clip_policy = clip_policy
    return m, meta


def dcb_card(fid):
    """Level and specialty of the card whose technique scripts the model file holds."""
    _venv()
    sys.path.insert(0, DCB_ROOT)
    import dcb.model
    import dcb.cards
    cards = dcb.cards.read_cards(os.path.join(DCB_ROOT, 'drv/B/CARD2.CDD'))
    m = dcb.model.parse_model(open(os.path.join(DCB_ROOT, 'drv/F', f'{fid:03d}.PAK'), 'rb').read(), str(fid))
    card, n = dcb.cards.card_for(m, cards)
    if not card:
        return {}
    d = open(os.path.join(DCB_ROOT, 'drv/B/CARD2.CDD'), 'rb').read()
    rec = d[8 + card['index'] * dcb.cards.RECORD:8 + (card['index'] + 1) * dcb.cards.RECORD]
    return dict(card=card['name'], card_level=rec[26] & 15, card_spec=rec[26] >> 4)


_MAPS = None


def dcb_mappings():
    """Card level and specialty -> DW1 level and element, derived from the Digimon both games
    have (majority vote over names that match): the card record's byte 26 is
    specialty << 4 | level (0 Rookie, 2 Champion, 3 Ultimate; Fire, Ice, Nature, Darkness, Rare)."""
    global _MAPS
    if _MAPS is None:
        from collections import Counter, defaultdict
        O = species.originals()
        dw = {r['para']['name'].strip(): r for r in O.rec}
        d = open(os.path.join(DCB_ROOT, 'drv/B/CARD2.CDD'), 'rb').read()
        spec, lev = defaultdict(Counter), defaultdict(Counter)
        for p in range(8, len(d) - 0x13C + 1, 0x13C):
            r = d[p:p + 0x13C]
            n = r[3:23].split(b'\0')[0].decode('latin1').replace(' *e1', '').strip()
            if n in dw and dw[n]['para']['level'] >= 3:
                s = dw[n]['para']['special'][0]
                if s != 255:
                    spec[r[26] >> 4][s] += 1
                lev[r[26] & 15][dw[n]['para']['level']] += 1
        _MAPS = ({k: c.most_common(1)[0][0] for k, c in spec.items()},
                 {k: c.most_common(1)[0][0] for k, c in lev.items()})
    return _MAPS


# ------------------------------------------------------------------ model edits (rules)
def merge_palettes(model, maxp=15, log=print):
    """Merges the least used palettes into the closest ones (dw3mmd.merge_palettes) until
    `maxp` remain. Returns the number merged."""
    if len(model.pals) <= maxp:
        return 0
    import dw3mmd
    by_pal = {}
    for b in model.bones:
        for p in b['prims']:
            if p['uvs']:
                by_pal.setdefault(p['row'], []).append(p)
    pals = {k: model.pals[k] for k in range(len(model.pals))}
    idx = model.idx
    remap = dw3mmd.merge_palettes(by_pal, pals, lambda pr: [idx[v * 256 + u] for u, v in dw3mmd._face_pixels(pr)
                                                            if 0 <= u < 256 and 0 <= v < 128], maxp, log)
    final = sorted(set(remap.values()))
    for b in model.bones:
        for p in b['prims']:
            if p['uvs']:
                p['row'] = final.index(remap[p['row']])
    n = len(model.pals) - len(final)
    model.pals = [pals[c] for c in final]
    return n


def scale_model(model, s):
    for b in model.bones:
        b['offset'] = tuple(x * s for x in b['offset'])
        b['verts'] = [tuple(x * s for x in v) for v in b['verts']]
    for a in model.anims.values():
        a.map_frames(lambda frames: [[(q, tuple(x * s for x in t), sc) for q, t, sc in f] for f in frames])


def idle_rest(model, anim=None):
    """The first frame of the idle becomes the rest pose (rotations and joints)."""
    f = model.anims[anim or getattr(model, 'idle', 'anim_00')].frames[0]
    for i, b in enumerate(model.bones):
        b['rest'] = tuple(f[i][0])
        b['offset'] = tuple(f[i][1])


def model_world(model, frame=None):
    """World 4x4 matrices of the model bones (index = model bone) at a frame or the rest."""
    W = {}

    def get(i):
        if i not in W:
            if frame is None:
                q, t, s = model.bones[i].get('rest', mmdport.IDENTITY_Q), model.bones[i]['offset'], (1, 1, 1)
            else:
                q, t, s = frame[i]
            R = mmd.quat_matrix(q)
            L = [[R[r][c] * s[c] for c in range(3)] + [t[r]] for r in range(3)] + [[0, 0, 0, 1]]
            p = model.bones[i]['parent']
            W[i] = mmd.mat_mul(get(p), L) if p >= 0 else L
        return W[i]
    return [get(i) for i in range(len(model.bones))]


def bbox(points):
    return [(min(p[k] for p in points), max(p[k] for p in points)) for k in range(3)]


# ------------------------------------------------------------------ skeleton features
class Shape:
    """Per DW1 bone: joint, piece centre ('tip'), mass (vertices); all in height units, the
    entity origin on the ground, Y down, facing -Z."""

    def __init__(self, joints, tips, mass, parents, bb, pts, lows=None):
        self.H = -bb[1][0] or 1.0
        self.bb = bb
        n = self.H
        self.joint = [v_mul(j, 1 / n) for j in joints]
        self.tip = [v_mul(t, 1 / n) for t in tips]
        self.mass, self.parent = mass, parents

        def spread(k):              # 10..90 % of the vertices: the body, not a tail or wing tip
            v = sorted(p[k] for p in pts)
            return (v[int(0.9 * (len(v) - 1))] - v[int(0.1 * (len(v) - 1))]) / n
        self.aspect = (spread(0) / spread(1), spread(2) / spread(1))
        # feet: pieces that reach the ground (lowest vertex within 6 % of the height) with no
        # descendant that does too: 2 for a biped, 4 for a quadruped, 0 when it hovers
        # (a foot hangs from the hips: the chain's first piece below the root bone has its joint no
        # higher than 10 % of the height above the root's, so arms and wings that reach the ground
        # do not count)
        touch = {b for b, y in enumerate(lows or []) if y is not None and y > -0.06 * n and self.tip[b][1] > -0.12}
        self.feet = len([b for b in touch if not any(self.is_desc(c, b) for c in touch if c != b)
                         and self.hangs_from_hips(b)])

    def hangs_from_hips(self, b):
        chain = [b] + self.ancestors(b)            # b, parent, ..., 0
        if len(chain) < 3:
            return True
        root, first = chain[-2], chain[-3]          # the root bone (child of the entity), the chain's first piece
        return self.joint[first][1] >= self.joint[root][1] - 0.1

    def is_desc(self, c, b):
        while c > 0:
            c = self.parent[c]
            if c == b:
                return True
        return False

    def ancestors(self, b):
        out = []
        while b > 0:
            b = self.parent[b]
            out.append(b)
        return out


def shape_of_model(model):
    W = model_world(model)
    joints, tips, mass, parents, pts, lows = [[0, 0, 0]], [[0, 0, 0]], [0], [-1], [], [None]
    for i, b in enumerate(model.bones):
        M = W[i]
        joints.append([M[r][3] for r in range(3)])
        vs = [m_apply(M, v) for v in b['verts']]
        pts += vs
        lows.append(max(v[1] for v in vs) if vs else None)
        tips.append([sum(v[k] for v in vs) / len(vs) for k in range(3)] if vs else joints[-1])
        mass.append(len(b['verts']))
        parents.append(b['parent'] + 1 if b['parent'] >= 0 else 0)
    for i, b in enumerate(model.bones):        # rule (meshfix): a helper bone (the rest of a split piece) is its parent's mass, never mapped
        if b.get('helper'):
            mass[b['parent'] + 1] += mass[i + 1]
            mass[i + 1] = 0
    return Shape(joints, tips, mass, parents, bbox(pts), pts, lows)


_DONORS = {}


def donor_shape(t):
    if t not in _DONORS:
        e = mmd.exe()
        src = mmd.MMD.load(species.originals().model_path(t), t)
        pose = retarget.rest_pose(src, e.bone_count[t], 0)
        M = mmd.bone_matrices(src, pose)
        joints, tips, mass, pts, lows = [], [], [], [], []
        for b, (oi, par) in enumerate(e.skeleton[t]):
            joints.append([M[b][r][3] for r in range(3)])
            vs = [m_apply(M[b], v[:3]) for v in src.tmd.obj_verts(oi)] if oi >= 0 else []
            pts += vs
            lows.append(max(v[1] for v in vs) if vs else None)
            tips.append([sum(v[k] for v in vs) / len(vs) for k in range(3)] if vs else joints[-1])
            mass.append(len(vs))
        _DONORS[t] = (Shape(joints, tips, mass, [p for _, p in e.skeleton[t]], bbox(pts), pts, lows), src, M)
    return _DONORS[t]


ROLES = False                 # set per entry by plan()/cmd_donors from the list option "roles" (rigfix.role_cost)


def bone_cost(T, S, tb, sb):
    """How unlike target bone tb is to source bone sb (height units)."""
    c = v_len(v_sub(T.joint[tb], S.joint[sb])) + 0.5 * v_len(v_sub(T.tip[tb], S.tip[sb]))
    xt, xs = T.tip[tb][0], S.tip[sb][0]
    if abs(xt) > 0.04 and abs(xs) > 0.04 and (xt > 0) != (xs > 0):
        c += 0.3                                    # the other side
    if ROLES:
        import rigfix
        c += rigfix.role_cost(T, S, tb, sb)         # rule (list option "roles"): a leg is not mapped onto a wing or an arm
    return c


def bone_map(T, S, max_cost=0.32):
    """Greedy one-to-one assignment by cost (parents first on ties); a target bone whose mapped
    parent's source is not an ancestor of its candidate pays 0.08 (hierarchy)."""
    pairs = []
    for tb in range(1, len(T.joint)):
        if not T.mass[tb]:
            continue
        for sb in range(1, len(S.joint)):
            if S.mass[sb] or any(S.mass[c] for c in range(len(S.parent)) if S.parent[c] == sb):
                pairs.append((bone_cost(T, S, tb, sb), tb, sb))
    pairs.sort()
    out, used = {}, set()
    order = sorted(range(1, len(T.joint)), key=lambda b: len(T.ancestors(b)))
    # two passes: a cheap pass that ignores hierarchy, then fix-ups with the hierarchy cost
    for c, tb, sb in pairs:
        if tb in out or sb in used or c > max_cost:
            continue
        out[tb] = sb
        used.add(sb)
    cost = {}
    for tb in order:
        if tb not in out:
            continue
        c = bone_cost(T, S, tb, out[tb])
        p = T.parent[tb]
        while p > 0 and p not in out:
            p = T.parent[p]
        if p > 0 and out[p] not in S.ancestors(out[tb]) and out[p] != out[tb]:
            c += 0.08
        cost[tb] = c
    return out, cost


def donor_score(T, t, element, level):
    S = donor_shape(t)[0]
    m, cost = bone_map(T, S)
    tot = sum(T.mass) or 1
    unmapped = 0.35
    fit = sum(T.mass[b] * (cost[b] if b in m else unmapped) for b in range(1, len(T.joint))) / tot
    asp = abs(T.aspect[0] - S.aspect[0]) + abs(T.aspect[1] - S.aspect[1])
    r = species.originals().rec[t]
    els = moves_by_element(t)
    el = 0.0 if len(els.get(element, [])) >= 2 else (0.02 if els.get(element) else 0.04)
    lv = 0.03 * abs(min(level, 5) - r['para']['level'])
    feet = 0.04 * abs(min(T.feet, 4) - min(S.feet, 4))
    return fit + 0.12 * asp + feet + el + lv, dict(fit=round(fit, 3), aspect=round(asp, 3), feet=(T.feet, S.feet),
                                                    element=el, level=lv, mapped=len(m), map=m)


def donor_candidates():
    O = species.originals()
    out = []
    for t in range(1, 62):
        r = O.rec[t]
        if r['para']['level'] >= 3 and O.model_path(t) and r.get('evoReqs'):
            out.append(t)
    return out


def donor_scores(T, element, level):
    res = [(donor_score(T, t, element, level), t) for t in donor_candidates()]
    return sorted(((s, t, d) for (s, d), t in res), key=lambda x: x[0])


# ------------------------------------------------------------------ techniques
_EXE = None


def exe_bytes():
    global _EXE
    if _EXE is None:
        _EXE = open(os.path.join(ROOT, 'extracted', 'SLUS_010.32'), 'rb').read()
    return _EXE


def move(m):
    d = exe_bytes()
    o = MOVE_DATA + 16 * m
    dist, power, mp, ifr, rng, el = struct.unpack_from('<ihBBBB', d, o)
    return dict(id=m, power=power, mp=mp * 3, range=rng, element=el)


def moves_by_element(t):
    out = {}
    for m in species.originals().rec[t]['para']['moves']:
        if m != 255 and m < FINISHER_FIRST:
            out.setdefault(move(m)['element'], []).append(m)
    return out


def pick_moves(donor, element):
    """The donor's 16-entry list (index i plays slot 0x2E+i, retargeted from the donor's own
    0x2E+i, so every effect knows the original type), keeping the techniques of the new
    species' specialties and the finisher. Returns (moves[16], specials[3], finisher index)."""
    r = species.originals().rec[donor]
    dsp = [s for s in r['para']['special'] if s != 255]
    els = moves_by_element(donor)
    if element not in els:
        element = dsp[0]                    # rule: the donor has no technique of that element
    spec = [element] + [s for s in dsp if s != element]
    spec = (spec + [255, 255, 255])[:3]
    out, fin = [], None
    for i, m in enumerate(r['para']['moves']):
        if m == 255:
            out.append(255)
        elif m >= FINISHER_FIRST:
            out.append(m)
            fin = i
        else:
            out.append(m if move(m)['element'] in spec else 255)
    return out, spec, fin


def efe_tables():
    spec = importlib.util.spec_from_file_location('efe_origins', os.path.join(HERE, 'efe-origins.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    data = open(os.path.join(ROOT, 'extracted/ETCHI/EFEDAT.EFE'), 'rb').read()
    return mod, data


def borrowed_origins(otype, moves):
    """(bone, x, y, z) the effects of these techniques start from for original type otype
    (the first row of that type in each EfeTechBoneOffset table, as checkTechCompatibility)."""
    mod, data = efe_tables()
    out = []
    for m in moves:
        if m == 255:
            continue
        chunk = data[m * 0x5000:(m + 1) * 0x5000]
        for off, rows in mod.tables(chunk):
            for t, b, x, y, z in rows:
                if t == otype:
                    if (b, x, y, z) not in out:
                        out.append((b, x, y, z))
                    break
    return out


def condition_fx(t):
    d = exe_bytes()
    o = CONDITION_FX - 0x80090000 + 8 * t
    return list(struct.unpack_from('<4h', d, o))


def move_origin(T, Tw, S, Sw, inv, b, off, k):
    """A point given in source bone b's space -> (target bone, offset in its space)."""
    P = m_apply(Sw[b], off)
    if b in inv and inv[b]:
        tb = min(inv[b], key=lambda x: v_len(v_sub(T.joint[x], S.joint[b])))
        v = v_mul(v_sub(P, [Sw[b][r][3] for r in range(3)]), k)
        world = v_add([Tw[tb][r][3] for r in range(3)], v)
    else:
        a = b
        while a > 0 and not inv.get(a):
            a = S.parent[a]
        tb = min(inv[a], key=lambda x: len(T.ancestors(x))) if a > 0 else 1
        world = v_mul(P, k)
    o = m_rot_t(Tw[tb], v_sub(world, [Tw[tb][r][3] for r in range(3)]))
    return tb, [round(x) for x in o]


def effect_origins(T, Tw, donor, otype, bmap, moves, k, log=print):
    S, src, Sw = donor_shape(donor)
    inv = {}
    for tb, sb in bmap.items():
        inv.setdefault(sb, []).append(tb)
    rows = [r for r in borrowed_origins(otype, moves) if r[0] > 0]
    bad = [r for r in rows if r[0] >= len(Sw)]      # rule: a row naming a bone the donor lacks (MetalGreymon's
    if bad:                                          # (32, -1, -1, -1)) is a sentinel, not an origin: dropped
        log(f'  effect origins: dropped {len(bad)} row(s) on bones the donor does not have: {bad}')
        rows = [r for r in rows if r[0] < len(Sw)]
    out = []
    if len(rows) <= 8:
        for b, x, y, z in rows:
            tb, o = move_origin(T, Tw, S, Sw, inv, b, [x, y, z], k)
            out.append([b, x, y, z, tb] + o)
    else:                                   # rule: more than 8 rows -> one "any" entry per bone
        seen = []
        for b, x, y, z in rows:
            if b in seen:
                continue
            seen.append(b)
            tb, o = move_origin(T, Tw, S, Sw, inv, b, [x, y, z], k)
            out.append([b, 'any', 0, 0, tb] + o)
        if len(out) > 8:
            log(f'  hand work: {len(out)} effect-origin bones, the record has room for 8')
            out = out[:8]
    cx, cy, cz, cb = condition_fx(otype)
    tb, o = move_origin(T, Tw, S, Sw, inv, cb, [cx, cy, cz], k)
    return out, o + [tb]


# ------------------------------------------------------------------ battle clips
def energy(model, name):
    """Per tick: mass-weighted joint rotation speed (radians/tick), hips height and hips
    horizontal travel from the first tick (height units)."""
    a = model.anims[name]
    mass = [len(b['verts']) + 1 for b in model.bones]
    roots = [i for i, b in enumerate(model.bones) if b['parent'] < 0]
    r = roots[0]
    H = getattr(model, 'H', 300.0)
    e, hy, hd = [], [], []
    x0 = a.frames[0][r][1]
    for t, f in enumerate(a.frames):
        if t == 0:
            e.append(0.0)
        else:
            p = a.frames[t - 1]
            e.append(sum(mass[i] * q_angle(f[i][0], p[i][0]) for i in range(len(f))) / sum(mass))
        hy.append(f[r][1][1] / H)
        hd.append(math.hypot(f[r][1][0] - x0[0], f[r][1][2] - x0[2]) / H)
    return e, hy, hd


def smooth(xs, w=3):
    return [sum(xs[max(0, i - w):i + w + 1]) / len(xs[max(0, i - w):i + w + 1]) for i in range(len(xs))]


def best_window(e, ok, L):
    """Start of the window of L ticks with the most motion, all of whose ticks are ok."""
    best, bs = None, -1
    for s in range(0, len(e) - L + 1):
        if not all(ok[s:s + L]):
            continue
        v = sum(e[s:s + L])
        if v > bs:
            best, bs = s, v
    return best


def attack_window(model, name, want):
    """A technique out of a card attack (~9 s: wind-up, strike, dash to the opponent and
    back): the window of `want` source ticks with the most motion while the hips stay within
    0.35 heights of where they started (the dash is left out)."""
    e, hy, hd = energy(model, name)
    e = smooth(e, 2)
    L = max(24, min(want, len(e) - 1))
    # The first four DCB batches predate the flight/hidden-pose guards.
    # Keep their source bytes reproducible for the ImportedModels deltas, using today's codec.
    policy = getattr(model, 'clip_policy', None)
    if policy in ('dcb-original', 'dcb-grounded'):
        limits = ((0.35, 0.8), (0.6, 1.2), (1.0, 2.0), (1e9, 1e9)) if policy == 'dcb-grounded' else (
            (0.35, 1e9), (0.6, 1e9), (1e9, 1e9))
        for lim, up in limits:
            s = best_window(e, [d < lim and hy[0] - y < up for d, y in zip(hd, hy)], L)
            if s is not None:
                return s, s + L, sum(e[s:s + L])
        return 0, L, 0.0
    # rule: a tick where a piece is hidden by a zero scale although the animation shows it at other ticks (DW2003
    # makes the body appear and vanish that way: Taomon's attack starts hidden) is not part of the window
    fr = model.anims[name].frames
    shown = [i for i, b in enumerate(model.bones) if b['verts'] and max(max(f[i][2]) for f in fr) > 0.5]
    hidden = [any(min(f[i][2]) < 0.2 for i in shown) for f in fr]
    # also not up in the air: a jump that carries the hips more than `up` heights above their
    # starting height leaves the camera's view (Shurimon's and Sylphymon's leaps were blank rows)
    for lim, up in ((0.35, 0.8), (0.6, 1.2), (1.0, 2.0), (1e9, 1e9)):
        ok = [d < lim and hy[0] - y < up and not h for d, y, h in zip(hd, hy, hidden)]
        s = best_window(e, ok, L)
        if s is not None:
            return s, s + L, sum(e[s:s + L])
    return 0, L, 0.0


def analyse_clips(model, donor_src, donor_t, tech_slots, fin_slot):
    """The card game's convention (dcb2mmd.DEFAULT_SLOTS): anim_00 idle (loop), anim_01..03
    attacks, anim_04 hit, anim_05 knocked down (and up again), anim_06 victory (loop),
    anim_07 entrance (unused). Ranges are chosen from the motion (see each rule)."""
    e = mmd.exe()
    nb = e.bone_count[donor_t]

    def donor_len(slot):
        i = donor_src.anims.table[slot] if slot < len(donor_src.anims.table) else None
        if i is None:
            return 40
        return len(retarget.play(donor_src.anims.anims[i], nb, slot)[0])
    clips = {'0x21': {'anim': 'anim_00'}}
    why = {}
    # hit: the card game knocks the Digimon back; the slot runs from the impact to the
    # farthest point of the knockback (hips travel, turned into root motion), 30..75 ticks
    en, hy, hd = energy(model, 'anim_04')
    end = max(range(min(len(hd), 90)), key=lambda i: hd[i])
    end = max(30, min(75, end))
    clips['0x28'] = dict(anim='anim_04', start=0, end=end, hips='entity')
    clips['0x29'] = dict(anim='anim_04', start=0, end=end, hips='entity', root_scale=-0.8)
    why['hit'] = f'anim_04 0..{end} (farthest knockback)'
    # knocked down: "down" is the first tick where the hips have made 70 % of their largest
    # drop; the faint slot ends a little after it (at least 36 ticks, at most 90)
    en, hy, hd = energy(model, 'anim_05')
    standing = hy[0]
    drop_max = max(hy) - standing
    down = next(i for i in range(len(hy)) if hy[i] - standing >= 0.7 * drop_max)
    fe = min(len(hy), max(36, down + 8))
    fs = max(0, fe - 90)
    clips['0x2b'] = dict(anim='anim_05', start=fs, end=fe, hips='entity', root_scale=0.3,
                         speed=round(max(1.0, (fe - fs) / 60), 2))
    why['faint'] = f'anim_05 {fs}..{fe} (hips down at {down})'
    drop = hy[down] - standing
    up = next((i for i in range(down, len(hy)) if hy[i] - standing < 0.2 * drop), None) if drop > 0.08 else None
    if up is not None and up - fe >= 12:
        clips['0x2c'] = dict(anim='anim_05', start=fe, end=min(len(hy), up + 10), hips='entity', root_scale=0.3)
        why['get up'] = f'anim_05 {fe}..{min(len(hy), up + 10)}'
    else:
        why['get up'] = 'donor (the card animation does not stand up again)'
    # victory: the liveliest 80 ticks of the loop
    en, hy, hd = energy(model, 'anim_06')
    L = min(80, len(en) - 1)
    H = getattr(model, 'H', 300.0)
    s = None
    for up in (0.5, 1.0, 1e9):              # not flying off (Shadramon's and Thundermon's victory jumps)
        s = best_window(smooth(en, 2), [hy[0] - y < up for y in hy], L)
        if s is not None:
            break
    s = s or 0
    clips['0x2a'] = dict(anim='anim_06', start=s, end=s + L, hz=0.3, rise=round(0.5 * H))
    original = getattr(model, 'clip_policy', None) in ('dcb-original', 'dcb-grounded')
    if original:
        s = best_window(smooth(en, 2), [True] * len(en), L) or 0
        clips['0x2a'] = dict(anim='anim_06', start=s, end=s + L, hz=0.3)
    why['victory'] = f'anim_06 {s}..{s + L}'
    # attacks: the liveliest one is the finisher, the others the first kept techniques
    atk = []
    for name in ('anim_01', 'anim_02', 'anim_03'):
        if name in model.anims:
            atk.append((attack_window(model, name, 90)[2], name))
    atk.sort(reverse=True)
    targets = ([fin_slot] if fin_slot is not None else []) + tech_slots
    for (score, name), slot in zip(atk, targets):
        n = donor_len(slot)
        want = int(n * 1.5 * 1.5)                         # card ticks (30 fps) for ~n DW1 ticks at speed 1.5
        s, t, _ = attack_window(model, name, want)
        speed = round(min(2.2, max(0.9, (t - s) * 20 / 30 / n)), 2)
        clips[f'{slot:#04x}'] = dict(anim=name, start=s, end=t, speed=speed, hz=0.2, settle=4,
                                     rise=round(0.5 * getattr(model, 'H', 300.0)))
        if original:
            clips[f'{slot:#04x}'].pop('rise')
        why[f'{slot:#04x}'] = f'{name} {s}..{t} x{speed} (donor slot {n} ticks)'
    return clips, why


def dw3_getup(model):
    """Rule (DW2003's slots are not decoded; found by the hips on 6 models): the get-up is the
    animation that plays once, whose hips start low and end high (the most rise, at least 0.08 of
    the height) among slots 0-11 (usually slot 11; Marsmon and Dokugumon never lie down: none, the
    donor's faint and get-up stay). Its reverse is the fall (`model.anims['fall']`: DW2003 has no
    fall that is not part of a loop). Returns the animation's name, or None."""
    best = None
    for n, a in model.anims.items():
        if a.loop or n == 'fall' or int(n[5:]) > 11:      # slots 4-11 are the fall group; 12 up are walks and techniques
            continue
        en, hy, hd = energy(model, n)
        rise = hy[0] - hy[-1]
        if rise >= 0.08 and (best is None or rise > best[0]):
            best = (rise, n)
    if best is None:
        return None
    a = model.anims[best[1]]
    model.anims['fall'] = mmdport.Anim(a.frames[::-1], a.fps, False)
    model.getup = best[1]
    return best[1]


def analyse_clips_dw3(model, donor_src, donor_t, tech_slots, fin_slot):
    """Digimon World 2003: slots undecoded, so the clips are chosen by their features (seen on 6
    models: 0 idle loop, 2 a small flinch, 3 the hit with the stagger, 4-10 falling and lying, 11
    getting up, 12/13 walk loops with forward travel, then runs of five slots per technique: wind-up,
    loop, the attack itself, loop, recovery). idle = anim_00; hit = anim_03 (else 02), cut at the
    farthest stagger; faint = the get-up reversed; get up = `dw3_getup`; victory stays the donor's;
    technique casts = the once-or-looping animations of slot 12 up (not walks: a loop whose hips
    travel more than 0.25 of the height; not the get-up) of at least 40 frames, ranked by the
    motion of their liveliest window (the DCB attack window: lunge out, 0.35 heights); the
    liveliest is the finisher."""
    nb = mmd.exe().bone_count[donor_t]

    def donor_len(slot):
        i = donor_src.anims.table[slot] if slot < len(donor_src.anims.table) else None
        if i is None:
            return 40
        return len(retarget.play(donor_src.anims.anims[i], nb, slot)[0])
    H = getattr(model, 'H', 300.0)
    clips = {'0x21': {'anim': 'anim_00'}}
    why = {}
    hitn = 'anim_03' if 'anim_03' in model.anims else 'anim_02'
    en, hy, hd = energy(model, hitn)
    end = max(30, min(60, max(range(min(len(hd), 60)), key=lambda i: hd[i])))
    end = min(end, len(hd))
    clips['0x28'] = dict(anim=hitn, start=0, end=end, hips='entity')
    clips['0x29'] = dict(anim=hitn, start=0, end=end, hips='entity', root_scale=-0.8)
    why['hit'] = f'{hitn} 0..{end}'
    up = getattr(model, 'getup', None)
    if up:
        n = len(model.anims[up].frames)
        speed = round(max(1.0, n * 20 / model.anims[up].fps / 60), 2)
        clips['0x2b'] = dict(anim='fall', hips='entity', root_scale=0.3, speed=speed)
        clips['0x2c'] = dict(anim=up, hips='entity', root_scale=0.3, speed=speed)
        why['faint'] = f'{up} reversed x{speed}'
        why['get up'] = f'{up} x{speed}'
    else:
        why['faint'] = why['get up'] = 'donor (no animation of this model stands up)'
    why['victory'] = 'donor (DW2003 slots are not decoded)'
    cands = []
    for n, a in model.anims.items():
        slot = int(n[5:]) if n[5:].isdigit() else -1
        if slot < 12 or n == up or len(a.frames) < 40:
            continue
        en, hy, hd = energy(model, n)
        if a.loop and max(hd) > 0.25:
            continue
        if a.loop and sum(en) < 0.5:
            continue
        cands.append((attack_window(model, n, 90)[2], n))
    cands.sort(reverse=True)
    targets = ([fin_slot] if fin_slot is not None else []) + tech_slots
    for (score, name), slot in zip(cands, targets):
        k = donor_len(slot)
        s, t, _ = attack_window(model, name, int(k * 2.25))
        speed = round(min(2.2, max(0.9, (t - s) * 20 / 30 / k)), 2)
        clips[f'{slot:#04x}'] = dict(anim=name, start=s, end=t, speed=speed, hz=0.2, settle=4, loop=False,
                                     rise=round(0.5 * H))
        why[f'{slot:#04x}'] = f'{name} {s}..{t} x{speed} (donor slot {k} ticks)'
    return clips, why


def analyse_clips_dw2(model, donor_src, donor_t, tech_slots, fin_slot):
    """Digimon World 2's convention (docs/mods/models.md section 13, as the hand-made Kimeramon): A0 idle (loop),
    B0 hit, C0-C2 the knock-back (one fall), J0 getting up (it starts lying and ends standing),
    F0/G0/H0 the three technique casts, I0 the second action, K0 lying (unused). No victory: 0x2a
    stays the donor's. The four casts are ranked by motion: the liveliest is the finisher, the next
    ones the kept techniques; each plays whole, once, at the speed that makes it as long as the
    donor's slot (the effects are timed to it), lunge removed, 4 ticks of settle."""
    nb = mmd.exe().bone_count[donor_t]

    def donor_len(slot):
        i = donor_src.anims.table[slot] if slot < len(donor_src.anims.table) else None
        if i is None:
            return 40
        return len(retarget.play(donor_src.anims.anims[i], nb, slot)[0])
    H = getattr(model, 'H', 300.0)
    clips = {'0x21': {'anim': 'A0'}, '0x28': {'anim': 'B0'}, '0x29': {'anim': 'B0'},
             '0x2b': {'anim': 'C012', 'eyes': 'closed'}, '0x2c': {'anim': 'J0'}}
    why = {'hit': 'B0', 'faint': 'C0+C1+C2', 'get up': 'J0', 'victory': 'donor (DW2 has none)'}
    atk = sorted(((sum(energy(model, n)[0]), n) for n in ('F0', 'G0', 'H0', 'I0') if n in model.anims), reverse=True)
    targets = ([fin_slot] if fin_slot is not None else []) + tech_slots
    for (score, name), slot in zip(atk, targets):
        n = donor_len(slot)
        frames = len(model.anims[name].frames)
        speed = round(min(2.2, max(0.75, frames * 20 / model.anims[name].fps / n)), 2)
        clips[f'{slot:#04x}'] = dict(anim=name, speed=speed, hz=0.2, settle=4, loop=False, rise=round(0.5 * H))
        why[f'{slot:#04x}'] = f'{name} whole x{speed} (donor slot {n} ticks)'
    return clips, why


# ------------------------------------------------------------------ evolution, stats
def level_medians(level):
    O = species.originals()
    rows = [O.rec[t]['evoGains'] for t in range(1, 62) if O.rec[t]['para']['level'] == min(level, 5)
            and O.rec[t].get('evoGains')]
    out = {}
    for k in ('hp', 'mp', 'offense', 'defense', 'speed', 'brains'):
        v = sorted(r[k] for r in rows)
        out[k] = v[len(v) // 2]
    return out


# Authored fields a re-run must preserve: the fields of a species file that were set after the import, by
# hand or by another tool (identity sheet, renames, provisional finishers and their slot aliases, the gym picks of the
# audit, evolution parents, the size pass of tools/sizes.py and tools/fitfix.py: the model file it points to). When
# content/species already has a file for the id, these keep the file's values; the
# run prints each one it kept where the import would have written something else. `--overwrite FIELD ...` (or `all`)
# takes the import's value instead. Paths are keys of the file, dotted for nested ones.
PRESERVED = ['name', 'level', 'attribute', 'specialties', 'techniques', 'drop', 'effects_like', 'battle_music',
             'model.file', 'model.slot_aliases', 'model.radius', 'model.height', 'size', 'sizing', 'needs_ram_mb', 'partner.training', 'partner.training2',
             'evolution.from', 'evolution.to', 'evolution.requirements', 'evolution.gains', 'effect_origin_fallback']
RETIRED_PATH = os.path.join(ROOT, 'content', 'imports', 'retired.json')


def retired():
    """{id: entry} of the list entries whose species no longer exists under that id: {"removed": why} (a run skips
    it) or {"merged_into": id, "why": ...} (a run builds it and writes the file of that id, a record original)."""
    if not os.path.exists(RETIRED_PATH): return {}
    return {int(k): v for k, v in json.load(open(RETIRED_PATH)).items() if not k.startswith('_')}


MERGED = {}     # list id -> the id its file has now (retired.json "merged_into")


def existing_file(typ):
    """The species file content/species already has for an id (any name: renamed species keep their id), or None."""
    hits = [p for p in species.content_files() if re.match(rf'{typ}-', os.path.basename(p))]
    return hits[0] if hits else None


def _get(d, path):
    for k in path.split('.'):
        if not isinstance(d, dict) or k not in d: return _MISSING
        d = d[k]
    return d


def _set(d, path, v):
    ks = path.split('.')
    for k in ks[:-1]: d = d.setdefault(k, collections.OrderedDict())
    if v is _MISSING: d.pop(ks[-1], None)
    else: d[ks[-1]] = v


_MISSING = object()
OVERWRITE = set()
BEFORE_RUN = {}  # id -> the species file content/species had when the run started (None: a new species)


def write_species(path, sp):
    """The species file of a plan: the plan is a copy of its donor with changes (the old sparse format, sp), written
    complete (tools/species.py materialize). An existing file of the id keeps its PRESERVED fields (and its name, so
    a renamed species keeps its file)."""
    new = species.materialize(dict(sp, _path=path), from_files=True)
    if new['id'] in MERGED:              # a record original now: the disc's model name and bone count, its id
        t = MERGED[new['id']]
        new['id'] = t
        disc = species.disc_file(t)['model']
        m = collections.OrderedDict(name=disc['name'], bones=disc['bones'])
        m.update((k, v) for k, v in new['model'].items() if k not in ('name', 'bones', 'from'))
        new['model'] = m
        new.setdefault('texture', {'from': t})
    old_path = existing_file(new['id'])
    if new['id'] not in BEFORE_RUN:      # the file as it was before this run (a run writes each species twice)
        BEFORE_RUN[new['id']] = json.load(open(old_path), object_pairs_hook=collections.OrderedDict) if old_path else None
    old = BEFORE_RUN[new['id']]
    if old_path and old is not None:
        for f in PRESERVED:
            ov, nv = _get(old, f), _get(new, f)
            if ov == nv or ov is _MISSING or 'all' in OVERWRITE or f in OVERWRITE: continue
            _set(new, f, ov)
            print(f'{os.path.relpath(old_path, ROOT)}: kept {f} = {json.dumps(ov)} (the import would write '
                  f'{json.dumps(nv) if nv is not _MISSING else "nothing"}; --overwrite {f} takes it)')
        for k, v in old.items():
            if k.startswith('_'): new[k] = v      # comments and _source: the file's (a merge note stays)
        new = species.ordered_file(new)
        if os.path.abspath(old_path) != os.path.abspath(path): os.remove(old_path)
        path = os.path.join(os.path.dirname(path), species.file_name(new))
    species.write_file(path, new)
    return path


def free_slots(existing):
    """Original partners' free evolution targets after the species already in content/."""
    O = species.originals()
    free = {}
    for t in range(1, 62):
        p = O.rec[t].get('evoPaths')
        if p:
            free[t] = p['to'].count(-1)
    for t, s in existing.items():           # rule: a new species is a source too: 5 target slots, one level up
        if t >= species.NUM_ORIGINAL and (s.get('partner') is not None):
            free[t] = NEW_TARGETS
    for s in existing.values():
        for f in (s.get('evolution') or {}).get('from', []):
            if f in free:
                free[f] -= 1
    return free


NEW_TARGETS = 5          # evolution targets of a new species' record (species.py: 'to' holds 5)


def pick_source(level, element, donor, free, used, prefer=()):
    O = species.originals()
    best = None
    for t in prefer:                        # the list names the natural parent(s): first one with a free slot
        if free.get(t, 0) > 0:
            return t
    for t, n in free.items():
        if n <= 0:
            continue
        if t >= species.NUM_ORIGINAL:
            continue                        # only by "from" in the list: the rule would stack on the newest species
        r = O.rec[t]['para']
        if r['level'] != min(level, 5) - 1:
            continue
        sc = 0
        if element in r['special']:
            sc += 2
        if donor in (O.rec[t].get('evoPaths') or {}).get('to', []):
            sc += 1
        sc -= 1.5 * used.get(t, 0)
        sc += 0.1 * n
        if best is None or sc > best[0]:
            best = (sc, t)
    if best is None:                        # every original partner of the level below is full: an imported one
        for t, n in free.items():           # (same level, free slot), same element first, the least stacked
            if n <= 0 or t < species.NUM_ORIGINAL:
                continue
            s = species.load_content().get(t)
            r = species.species_record(s)['para'] if s else {}
            if r.get('level') != min(level, 5) - 1:
                continue
            sc = (2 if element in r.get('special', []) else 0) - 1.5 * used.get(t, 0) + 0.1 * n
            if best is None or sc > best[0]:
                best = (sc, t)
    return best[1] if best else None


# ------------------------------------------------------------------ one Digimon
def size_source(m, entry, level):
    """The batch's size pass, shared by planning and replay of a frozen build spec.

    Palettes/rig/mesh have already been prepared by the caller. No species
    records, donor selection or generated files are needed by this operation.
    """
    idle_rest(m)
    sh = shape_of_model(m)
    top, hw, hd = -sh.bb[1][0], max(-sh.bb[0][0], sh.bb[0][1]), max(-sh.bb[2][0], sh.bb[2][1])
    lo, hi = HEIGHT_RANGE[level]
    s = 1.0
    if entry.get('height'):
        s = entry['height'] / top
    elif top > hi or top < lo:
        s = (hi if top > hi else lo) / top
    s = min(s, float(entry.get('max_half_width', MAX_HALF_WIDTH)) / hw,
            float(entry.get('max_half_depth', MAX_HALF_DEPTH)) / hd)
    if abs(s - 1) > 0.01:
        scale_model(m, s)
        idle_rest(m)
        sh = shape_of_model(m)
    m.H = sh.H
    return sh, top, hw, hd, s


def replay_model(entry, level, spec, out_dir, log=print, frozen_mesh=True):
    """Replay a selected batch spec without planning, validation or content writes.

    The entry freezes source mesh/rig preparation, the level freezes the batch
    size rule, and the final spec freezes donor, clips and budget decisions.
    This path needs only the source discs and the explicit recipes.
    """
    entry = dict(entry)
    params = spec.get('meshfix')
    if frozen_mesh and entry.get('meshfix') is not None and entry.get('meshfix') is not False \
            and isinstance(params, dict) and all(k in params for k in ('kappa', 'kmove', 'quad_angle')):
        # The checked spec already records the winner of the six-way visual
        # search. Keep the entry's budgets/other rules, and replay that choice.
        original = entry['meshfix'] if isinstance(entry['meshfix'], dict) else {}
        entry['meshfix'] = dict(original, **{k: params[k] for k in ('kappa', 'kmove', 'quad_angle')})
    m, _ = load_source(entry, log=log, card_metadata=False)
    merge_palettes(m, 15, log=log)
    size_source(m, entry, level)
    if entry.get('game') == 'dw3':
        dw3_getup(m)
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, spec['name'])
    builder = mmdport.build_partner
    if entry.get('game') == 'dw2':
        import dw2mmd
        builder = dw2mmd.build_partner
    return builder(m, spec, stem + '.MMD', stem + '.TIM', out_dir, log=log)


def plan(entry, typ, out_dir, ctx, log=print):
    global ROLES
    ROLES = bool(entry.get('roles'))
    rep = dict(name=entry['name'], id=typ, rules=[], hand=[])
    m, meta = load_source(entry, log=lambda *a: None)
    rep['source'] = f'{entry.get("game", "dcb")} {entry["model"]}' + (f' (card {meta.get("card")})' if meta else '')
    game = entry.get('game', 'dcb')
    spec_map, lev_map = dcb_mappings() if game == 'dcb' else ({}, {})
    # level and element
    lv = entry.get('level')
    if lv == 'mega':
        lv = 6
    if lv is None:
        lv = lev_map.get(meta.get('card_level'), 4)
    if game != 'dcb' and ('level' not in entry or 'element' not in entry):
        rep['hand'].append(f'{game} has no card data: the list must give "level" and "element"')
    element = entry.get('element', spec_map.get(meta.get('card_spec'), 1))
    rep['level'], rep['element_card'] = lv, element
    if getattr(m, 'hub', None) is not None:
        rep['rules'].append(f'one root: the body (old bone {m.hub + 1}) is bone 1 and the other roots hang from it')
    if getattr(m, 'rig', None) or getattr(m, 'rig_error', None):
        import rigfix
        rigfix.report(m, rep)                                  # rule: bones merged / animation synthesised (rigfix.py)
    # palettes
    plog = []
    n = merge_palettes(m, 15, log=plog.append)
    if n:
        rep['rules'].append(f'{n} palette(s) merged (row 15 is the flat sprite\'s):' + ';'.join(plog))
    # rest = first idle frame; size
    sh, top, hw, hd, s = size_source(m, entry, lv)
    lo, hi = HEIGHT_RANGE[lv]
    if abs(s - 1) > 0.01:
        rep['rules'].append(f'scaled x{s:.3f}: {top:.0f} -> {-sh.bb[1][0]:.0f} tall, half width {hw * s:.0f} '
                            f'(DW1 {LEVELS[lv]}s: {lo}..{hi} tall, half width <= {entry.get("max_half_width", MAX_HALF_WIDTH)})')
    for line in getattr(m, 'meshfix_log', ()):
        rep['rules'].append(line)
    m.H = sh.H
    nprim = sum(len(b['prims']) for b in m.bones)
    nvert = sum(len(b['verts']) for b in m.bones)
    if len(m.bones) + 1 > 34:
        rep['hand'].append(f'{len(m.bones) + 1} bones: a partner has room for 34')
    if nprim > 713:
        rep['hand'].append(f'{nprim} primitives (the largest DW1 model has 713)')
    rep['budget'] = dict(bones=len(m.bones) + 1, primitives=nprim, vertices=nvert, palettes=len(m.pals),
                         height=round(sh.H))
    # donor
    ranking = donor_scores(sh, element, lv)
    if entry.get('donor'):
        pick = next(x for x in ranking if x[1] == entry['donor'])
    else:
        pick = ranking[0]
    score, donor, info = pick
    O = species.originals()
    rep['donor'] = dict(type=donor, name=O.rec[donor]['para']['name'], score=round(score, 3),
                        runner_up=[(O.rec[t]['para']['name'], round(x, 3)) for x, t, _ in ranking[1:4]],
                        **{k: v for k, v in info.items() if k != 'map'})
    bmap = info['map']
    S, src, Sw = donor_shape(donor)
    k = sh.H / S.H
    moves, special, fin = pick_moves(donor, element)
    if special[0] != element:
        rep['rules'].append(f'element {ELEMENTS[element]} -> {ELEMENTS[special[0]]}: the donor has no '
                            f'{ELEMENTS[element]} technique')
    rep['element'] = special[0]
    kept = [i for i, x in enumerate(moves) if x != 255 and i != fin]
    kept.sort(key=lambda i: (move(moves[i])['element'] != special[0], move(moves[i])['power']))
    tech_slots = [0x2E + i for i in kept[:2]]
    rep['tech_order'] = kept
    fin_slot = 0x2E + fin if fin is not None else None
    if game == 'dw3':
        dw3_getup(m)
    clips, why = {'dw2': analyse_clips_dw2, 'dw3': analyse_clips_dw3}.get(game, analyse_clips)(
        m, src, donor, tech_slots, fin_slot)
    if entry.get('victory'):
        # list entry "victory": "anim_NN": the victory (slot 0x2a) is the liveliest window of that source animation, for a
        # model whose donor map is too poor for the donor's victory to bend the body (Armagemon: 3 bones mapped)
        vn = entry['victory']
        vs, ve, _ = attack_window(m, vn, 80)
        clips['0x2a'] = dict(anim=vn, start=vs, end=ve, hz=0.3, rise=round(0.5 * getattr(m, 'H', 300.0)))
        why['victory'] = f'{vn} {vs}..{ve}'
    rep['clips'] = why
    # slots: the donor's everyday slots, its technique slots for the kept techniques only
    dmoves = O.rec[donor]['para']['moves']
    skip = [0x2E + i for i, x in enumerate(dmoves) if x != 255 and moves[i] == 255]
    roots = [b for b in range(1, len(sh.joint)) if sh.parent[b] == 0]
    hips_src = [b for b in range(1, len(S.joint)) if S.parent[b] == 0][0]
    spec = {
        '_generated': 'tools/import_batch.py (do not edit: rerun the batch)',
        game: entry['model'],
        'type': typ, 'name': entry['name'],
        'source': {'type': donor, 'mmd': os.path.relpath(O.model_path(donor), ROOT)},
        'map': {str(tb): sb for tb, sb in sorted(bmap.items())},
        'hips': [roots[0], hips_src, round(k, 3)],
        'root_scale': round(k, 3),
        'tol': 8, 'tol_clips': 4,
        'clips': clips,
        'skip': [f'{x:#04x}' for x in skip],
        'layer': {'anim': getattr(m, 'idle', 'anim_00'), 'bones': 'unmapped', 'slots': [f'{x:#04x}' for x in LAYER_SLOTS]},
    }
    if getattr(m, 'meshfix', None):                       # what meshfix.apply needs to repeat the same edits
        spec['meshfix'] = m.meshfix if isinstance(m.meshfix, dict) else {}
    if entry.get('root_slots'):     # rule (list option, mmdport.build_partner): the ground travel of a slot times a factor
        spec['root_slots'] = entry['root_slots']
    if entry.get('roles'):      # rule (list option "roles", tools/rigfix.py): unmapped legs get a generic gait
        import rigfix
        g = rigfix.gait_spec(sh, bmap)
        if g:
            spec['gait'] = g
            rep['rules'].append(f'rigfix: {len([x for x in g["legs"] if not x[2]])} unmapped leg(s) walk by a generic gait (stride {g["stride"]:g}, amplitude {g["amp"]} degrees)')
    if game == 'dw3':       # what `dw3mmd.py partner` needs to rebuild the same model from this spec
        spec['scale'] = round(m.scale * s, 6)
        spec['hub_roots'] = True
        if getattr(m, 'rig', None):
            spec['rigfix'] = m.rig['spec']                     # what rigfix.prepare needs to rebuild the same skeleton
        if getattr(m, 'dropped_faces', 0):
            rep['rules'].append(f'primitives: the {m.dropped_faces} smallest faces dropped ({round(100 * m.dropped_faces / 713)} % of 713 over the limit)')
        if getattr(m, 'quad_angle', 8.0) != 8.0:
            spec['quad_angle'] = m.quad_angle
            rep['rules'].append(f'primitives: triangle pairs merged into quads within {m.quad_angle:g} degrees')
        if getattr(m, 'getup', None):
            spec['reverse'] = {'fall': m.getup}
    if game == 'dw2':       # what `dw2mmd.py partner` needs to rebuild the same model from this spec
        spec['scale'] = round(m.scale * s, 6)
        spec['hub_roots'] = True
        spec['concat'] = {'C012': ['C0', 'C1', 'C2']}
    eo, cfx = effect_origins(sh, model_world_dw(m), donor, O.original_type(donor), bmap, moves, k,
                             log=lambda s: rep['rules' if 'dropped' in s else 'hand'].append(s.strip()))
    # evolution source
    src_t = pick_source(lv, special[0], donor, ctx['free'], ctx['used'], entry.get('from', ()))
    if src_t is None and min(lv, 5) == 3:      # rule (batch 13): a Rookie has no parent (the four Baby II partners are full):
        rep['rules'].append('no natural evolution parent (the Baby II partners have no free slot): lab menu or script only')
    elif src_t is None:
        rep['hand'].append(f'no {LEVELS.get(lv - 1, "lower")} partner with a free evolution slot')
    else:
        ctx['free'][src_t] -= 1
        ctx['used'][src_t] = ctx['used'].get(src_t, 0) + 1
    gains = level_medians(lv)
    W = WILD[min(lv, 5)]
    para = dict(boneCount=len(m.bones) + 1, radius=int(round(min(300, max(100, 0.6 * max(hw, hd) * s)))),
                height=int(round(sh.H)), level=min(lv, 5), special=special, moves=moves)
    sp = {
        'id': typ, 'name': entry['name'], 'base': donor,
        '_source': f'{rep["source"]} (tools/import_batch.py run {ctx["list"]})',
        'model': {'file': os.path.relpath(os.path.join(out_dir, entry['name'] + '.MMD'), ROOT)},
        'texture': {'file': os.path.relpath(os.path.join(out_dir, entry['name'] + '.TIM'), ROOT), 'entry': 0},
        'bones': [list(x) for x in mmdport.skeleton(m)],
        'para': para,
        'originalType': O.original_type(donor),
        'effectOrigins': eo, 'conditionFx': cfx,
        'wild': dict(hp=W['hp'], mp=W['mp'], off=W['off'], **{'def': W['deff']}, speed=W['speed'],
                     brain=W['brain'], bits=W['bits']),
        'partner': {'base': donor, 'from': [src_t] if src_t else [], 'evoGains': gains},
    }
    rep['techniques'] = [dict(slot=f'{0x2E + i:#04x}', id=x, element=ELEMENTS[move(x)['element']]
                              if x < FINISHER_FIRST else 'finisher', clip=f'{0x2E + i:#04x}' in clips)
                         for i, x in enumerate(moves) if x != 255]
    rep['evolves_from'] = (src_t, O.rec[src_t]['para']['name'] if src_t < species.NUM_ORIGINAL else ctx['names'].get(src_t, str(src_t))) if src_t else None
    return m, spec, sp, rep


def model_world_dw(model):
    """World matrices indexed by DW1 bone (0 = entity, identity)."""
    W = model_world(model)
    return [[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]] + W


BUDGET_STEPS = [
    # (name, tol, tol_clips, drop optional slots, techniques kept besides the finisher, layer, clips)
    ('as planned', 8, 4, False, 99, True, 'all'),
    ('tol 10/6', 10, 6, False, 99, True, 'all'),
    ('tol 10/6, optional slots 0x1c-0x20 dropped', 10, 6, True, 99, True, 'all'),
    ('tol 10/6, optional slots dropped, 6 techniques', 10, 6, True, 6, True, 'all'),
    ('tol 10/6, optional slots dropped, 4 techniques', 10, 6, True, 4, True, 'all'),
    ('tol 12/8, optional slots dropped, 4 techniques', 12, 8, True, 4, True, 'all'),
    ('tol 12/8, optional slots dropped, 4 techniques, no layered idle motion', 12, 8, True, 4, False, 'all'),
    ('tol 14/8, optional slots dropped, 3 techniques, no layered idle motion', 14, 8, True, 3, False, 'all'),
    ('tol 14/8, optional slots dropped, 3 techniques, no layer, finisher clip only', 14, 8, True, 3, False, 'fin'),
    ('tol 14/12, optional slots dropped, 3 techniques, no layer, finisher clip only, hit-back (0x29) from the donor',
     14, 12, True, 3, False, 'fin-0x29'),
    ('tol 16/16, optional slots dropped, 2 techniques, no layer, finisher clip only, hit-back and victory from '
     'the donor', 16, 16, True, 2, False, 'fin-0x29-0x2a'),
]


def build_one(m, spec, sp_species, out_dir, rep, log=print):
    """mmdport.build_partner with the budget rules (BUDGET_STEPS, in order): raise the
    tolerance, drop the optional everyday slots, keep fewer techniques (the clip ones and the
    finisher stay; the species' move list loses the others), drop the layered idle motion,
    keep only the finisher's clip. Updates sp_species['para']['moves']."""
    stem = os.path.join(out_dir, spec['name'])
    moves = sp_species['para']['moves']
    clip_slots = [int(k, 16) for k in spec['clips'] if int(k, 16) >= 0x2E]
    fin = next((i for i, x in enumerate(moves) if x != 255 and x >= FINISHER_FIRST), None)
    order = [i for i in rep['tech_order'] if moves[i] != 255]
    for step in BUDGET_STEPS:
        name, tol, tolc, dropopt, ntech, layer, clips = step
        sp = json.loads(json.dumps(spec))
        sp['tol'], sp['tol_clips'] = tol, tolc
        if dropopt:
            sp['skip'] = sp['skip'] + [f'{x:#04x}' for x in OPTIONAL_SLOTS]
        keep = [i for i in order if 0x2E + i in clip_slots] + [i for i in order if 0x2E + i not in clip_slots]
        keep = set(keep[:ntech]) | ({fin} if fin is not None else set())
        newm = [x if (i in keep or x == 255) else 255 for i, x in enumerate(moves)]
        sp['skip'] = sp['skip'] + [f'{0x2E + i:#04x}' for i, x in enumerate(moves) if x != 255 and newm[i] == 255]
        if not layer:
            sp.pop('layer', None)
        for k in clips.split('-')[1:]:
            sp['clips'].pop(k, None)
        if clips.startswith('fin'):
            for k in [k for k in sp['clips'] if int(k, 16) >= 0x2E and fin is not None and int(k, 16) != 0x2E + fin]:
                del sp['clips'][k]
        for k in [k for k in sp['clips'] if int(k, 16) >= 0x2E and newm[int(k, 16) - 0x2E] == 255]:
            del sp['clips'][k]
        lines = []
        try:
            builder = mmdport.build_partner
            if getattr(m, 'game', '') == 'dw2':             # with the blinks (DW2's texture-animation parts)
                import dw2mmd
                builder = dw2mmd.build_partner
            data = builder(m, sp, stem + '.MMD', stem + '.TIM', out_dir, log=lines.append)
        except SystemExit as e:
            if 'PARTNER_MODEL_BUFFER' not in str(e):
                raise
            continue
        if step is not BUDGET_STEPS[0]:
            rep['rules'].append(f'size: {name}')
        sp_species['para']['moves'] = newm
        rep['mmd_bytes'] = len(data)
        json.dump(sp, open(os.path.join(ctx_spec_dir(), spec['name'] + '.json'), 'w'), indent=1)
        json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))
        return data
    import fitfix            # rule (tools/fitfix.py): the fit rules, then the 8 MB buffer ("needs_ram_mb": 8)
    data = fitfix.rescue(m, spec, sp_species, out_dir, rep, log)
    if data is not None:
        return data
    rep['hand'].append(f'does not fit PARTNER_MODEL_BUFFER after: {BUDGET_STEPS[-1][0]} and the fit rules')
    return None


_SPEC_DIR = os.path.join(ROOT, 'content', 'imports', 'specs')


def ctx_spec_dir():
    os.makedirs(_SPEC_DIR, exist_ok=True)
    return _SPEC_DIR


def verify(path, typ, tim, sp, rep, out_dir):
    """Byte-exact reparse, required slots, contact sheet."""
    data = open(path, 'rb').read()
    m = mmd.MMD.parse(data, len(sp['bones']))
    ok = m.build() == data
    tab = m.anims.table
    missing = [s for s in REQUIRED_SLOTS + [0x2E + i for i, x in enumerate(sp['para']['moves']) if x != 255]
               if s >= len(tab) or tab[s] is None]
    rep['verify'] = dict(roundtrip=ok, missing_slots=[f'{s:#04x}' for s in missing])
    if not ok:
        rep['hand'].append('MMD does not reparse byte for byte')
    if missing:
        rep['hand'].append(f'missing slots {rep["verify"]["missing_slots"]}')
    techs = [0x2E + i for i, x in enumerate(sp['para']['moves']) if x != 255]
    slots = [0x00, 0x02, 0x21, 0x28, 0x2B, 0x2C, 0x2A] + techs
    sheet = os.path.join(out_dir, sp['name'] + '-sheet.png')
    cmd = [sys.executable, os.path.join(HERE, 'animsheet.py'), path, sheet, '--type', str(typ), '--alltim', tim,
           '--tex-type', '0', '--frames', '8', '--size', '96', '--slots'] + [hex(s) for s in slots if s < len(tab)
                                                                             and tab[s] is not None]
    r = subprocess.run(cmd, capture_output=True, text=True)
    rep['sheet'] = os.path.relpath(sheet, ROOT) if r.returncode == 0 else f'failed: {r.stderr[-200:]}'


# ------------------------------------------------------------------ DW1 models (wild-enemy-only Digimon)
def plan_dw1(entry, typ, out_dir, ctx, log=print):
    """A Digimon that exists in DW1 only as a wild enemy: its model, texture and battle animations are native
    (`mmdport.build_partner` with `native`: they stay byte for byte). Only the slots a partner needs and the
    enemy lacks are retargeted from a donor partner; the record keeps the enemy's own technique list (its slots
    0x2E+ are native), voice and technique effect type, and takes the donor's raise data and requirements."""
    t = int(entry['type'])
    O, e = species.originals(), mmd.exe()
    para = O.rec[t]['para']
    rep = dict(name=entry['name'], id=typ, rules=[], hand=[], source=f'dw1 type {t} ({para["name"]})')
    nb = e.bone_count[t]
    src = mmd.MMD.load(O.model_path(t), t)
    have = {s_ for s_, x in enumerate(src.anims.table) if x is not None}
    lv = entry.get('level', para['level'])
    element = entry.get('element', para['special'][0])
    rep['level'], rep['element'] = lv, element
    moves = [x for x in para['moves'] if x != 255]
    if not moves or para['level'] < 3 or lv < 3:
        rep['hand'].append('no native battle set of its own (level 0, no techniques): needs the other games\' animations')
    nmoves = [0x2E + i for i, x in enumerate(para['moves']) if x != 255]
    lack = [s_ for s_ in nmoves if s_ not in have]
    if lack:
        rep['hand'].append(f'technique slots {[hex(x) for x in lack]} are not in its model')
    T, _, Tw = donor_shape(t)
    ot = O.original_type(t)
    ranking = donor_scores(T, element, lv)
    if entry.get('donor'):
        pick = next(x for x in ranking if x[1] == entry['donor'])
    elif ot != t and ot in donor_candidates() and e.skeleton[ot] == e.skeleton[t]:
        pick = next(x for x in ranking if x[1] == ot)       # rule: the enemy is a recolour or twin of a partner's rig:
        rep['rules'].append(f'donor {O.rec[ot]["para"]["name"]}: same skeleton (identity map)')   # its own slots, bone for bone
    else:
        pick = ranking[0]
    score, donor, info = pick
    S, dsrc, Sw = donor_shape(donor)
    if e.skeleton[donor] == e.skeleton[t]:
        bmap = {b: b for b in range(1, nb)}
    else:
        bmap = info['map']
    rep['donor'] = dict(type=donor, name=O.rec[donor]['para']['name'], score=round(score, 3),
                        runner_up=[(O.rec[x]['para']['name'], round(y, 3)) for y, x, _ in ranking[1:4]],
                        mapped=len(bmap), bones=nb - 1)
    roots = [b for b in range(1, nb) if T.parent[b] == 0]
    hips_src = [b for b in range(1, len(S.joint)) if S.parent[b] == 0][0]
    k = T.H / S.H
    own = {}
    missing = [s_ for s_ in REQUIRED_SLOTS if s_ not in have]
    if 2 in have:
        own['0x03'] = {'from': 2, 'stretch': 1.5}               # the tired walk: its own walk, 1.5 times slower
        missing.remove(3)
    if 4 in have:
        own['0x1b'] = {'from': 4}                               # the training run: its own run
        missing.remove(0x1B)
    spec = {
        '_generated': 'tools/import_batch.py (do not edit: rerun the batch)',
        'native': os.path.relpath(O.model_path(t), ROOT),
        'type': t, 'name': entry['name'],
        'source': {'type': donor, 'mmd': os.path.relpath(O.model_path(donor), ROOT)},
        'map': {str(tb): sb for tb, sb in sorted(bmap.items())},
        'hips': [roots[0], hips_src, round(k, 3)],
        'root_scale': round(k, 3),
        'tol': 2,
        'retarget': [f'{x:#04x}' for x in missing],
        'own': own,
        'layer': {'anim': 'idle', 'bones': 'unmapped', 'slots': [f'{x:#04x}' for x in LAYER_SLOTS]},
    }
    src_t = pick_source(lv, element, donor, ctx['free'], ctx['used'], entry.get('from', ()))
    if src_t is None:
        rep['rules'].append('no natural evolution parent (no species of the level below has a free slot): '
                            'reached by the lab menu or a script only')
    else:
        ctx['free'][src_t] -= 1
        ctx['used'][src_t] = ctx['used'].get(src_t, 0) + 1
    W = WILD[min(lv, 5)]
    sp = {
        'id': typ, 'name': entry['name'], 'base': t,
        '_source': f'dw1 {para["name"]} type {t}, native model and texture (tools/import_batch.py run {ctx["list"]})',
        'model': {'file': os.path.relpath(os.path.join(out_dir, entry['name'] + '.MMD'), ROOT)},
        'texture': {'from': t},
        'wild': dict(hp=W['hp'], mp=W['mp'], off=W['off'], **{'def': W['deff']}, speed=W['speed'],
                     brain=W['brain'], bits=W['bits']),
        'partner': {'base': donor, 'from': [src_t] if src_t else [], 'evoGains': level_medians(lv)},
    }
    if lv != para['level']:
        sp['para'] = {'level': min(lv, 5)}
    rep['techniques'] = [dict(slot=f'{0x2E + i:#04x}', id=x, element=ELEMENTS[move(x)['element']]
                              if x < FINISHER_FIRST else 'finisher', clip=False)
                         for i, x in enumerate(para['moves']) if x != 255]
    rep['evolves_from'] = (src_t, O.rec[src_t]['para']['name'] if src_t < species.NUM_ORIGINAL
                           else ctx['names'].get(src_t, str(src_t))) if src_t else None
    rep['original_type'] = ot
    return None, spec, sp, rep


def build_dw1(spec, sp, out_dir, rep, log=print):
    """build_partner with the native option; the tolerance of the retargeted slots rises until it fits."""
    stem = os.path.join(out_dir, spec['name'])
    for tol in (2, 4, 8, 12):
        s2 = dict(spec, tol=tol)
        lines = []
        try:
            data = mmdport.build_partner(None, s2, stem + '.MMD', stem + '.TIM', out_dir, log=lines.append)
        except SystemExit as ex:
            if 'PARTNER_MODEL_BUFFER' not in str(ex):
                raise
            continue
        if tol != 2:
            rep['rules'].append(f'size: everyday slots at tol {tol}')
        rep['mmd_bytes'] = len(data)
        json.dump(s2, open(os.path.join(ctx_spec_dir(), spec['name'] + '.json'), 'w'), indent=1)
        open(stem + '.build.log', 'w').write('\n'.join(lines))
        return data
    rep['hand'].append('does not fit PARTNER_MODEL_BUFFER at tol 12')
    return None


def verify_dw1(path, t, sp, rep, out_dir):
    """Byte-exact reparse, required slots, native slots untouched, contact sheet."""
    O = species.originals()
    nb = mmd.exe().bone_count[t]
    data = open(path, 'rb').read()
    m = mmd.MMD.parse(data, nb)
    ok = m.build() == data
    tab = m.anims.table
    moves = O.rec[t]['para']['moves']
    missing = [s for s in REQUIRED_SLOTS + [0x2E + i for i, x in enumerate(moves) if x != 255]
               if s >= len(tab) or tab[s] is None]
    orig = mmd.MMD.load(O.model_path(t), t)
    same = [s for s, x in enumerate(orig.anims.table) if x is not None and (
        s >= len(tab) or tab[s] is None or m.anims.anims[tab[s]].build() != orig.anims.anims[x].build())]
    rep['verify'] = dict(roundtrip=ok, missing_slots=[f'{s:#04x}' for s in missing],
                         native_slots_changed=[f'{s:#04x}' for s in same])
    if not ok:
        rep['hand'].append('MMD does not reparse byte for byte')
    if missing:
        rep['hand'].append(f'missing slots {rep["verify"]["missing_slots"]}')
    if same:
        rep['hand'].append(f'native slots changed {rep["verify"]["native_slots_changed"]}')
    techs = [0x2E + i for i, x in enumerate(moves) if x != 255]
    slots = [0x00, 0x02, 0x03, 0x08, 0x0A, 0x11, 0x15, 0x1B, 0x21, 0x28, 0x2B, 0x2C, 0x2A] + techs
    sheet = os.path.join(out_dir, sp['name'] + '-sheet.png')
    cmd = [sys.executable, os.path.join(HERE, 'animsheet.py'), path, sheet, '--type', str(t), '--tex-type', str(t),
           '--frames', '8', '--size', '96', '--slots'] + [hex(s) for s in slots if s < len(tab) and tab[s] is not None]
    r = subprocess.run(cmd, capture_output=True, text=True)
    rep['sheet'] = os.path.relpath(sheet, ROOT) if r.returncode == 0 else f'failed: {r.stderr[-200:]}'


# ------------------------------------------------------------------ commands
def load_list(path):
    L = json.load(open(path))
    if 'clip_policy' in L:
        for entry in L['digimon']:
            entry.setdefault('clip_policy', L['clip_policy'])
    L['_path'] = path
    return L


def selected(L, only):
    for i, e in enumerate(L['digimon']):
        if not only or e['name'] in only:
            yield L['first_id'] + i, e


def cmd_donors(a):
    global ROLES
    L = load_list(a.list)
    for typ, e in selected(L, a.only):
        ROLES = bool(e.get('roles'))
        m, meta = load_source(e, log=lambda *x: None)
        idle_rest(m)
        sh = shape_of_model(m)
        spec_map, lev_map = dcb_mappings()
        el = e.get('element', spec_map.get(meta.get('card_spec'), 1))
        lv = 6 if e.get('level') == 'mega' else e.get('level', lev_map.get(meta.get('card_level'), 4))
        print(f'{e["name"]} ({len(m.bones) + 1} bones, {sh.H:.0f} tall, aspect {sh.aspect[0]:.2f}/{sh.aspect[1]:.2f}, '
              f'{ELEMENTS[el]}, level {lv}):')
        O = species.originals()
        rk = donor_scores(sh, el, lv)
        for s, t, d in rk[:a.top] + [x for x in rk[a.top:] if x[1] in (a.with_ or [])]:
            print(f'  {s:.3f} {t:3d} {O.rec[t]["para"]["name"]:14s} fit {d["fit"]} aspect {d["aspect"]} '
                  f'feet {d["feet"]} element {d["element"]} level {d["level"]:.2f} mapped {d["mapped"]}/{len(m.bones)}')
            if a.map:
                print('      ', ' '.join(f'{tb}<-{sb}' for tb, sb in sorted(d['map'].items())))


def cmd_clips(a):
    L = load_list(a.list)
    for typ, e in selected(L, a.only):
        m, meta = load_source(e, log=lambda *x: None)
        idle_rest(m)
        m.H = shape_of_model(m).H
        for name in sorted(m.anims):
            en, hy, hd = energy(m, name)
            print(f'{e["name"]} {name}: {len(en)} ticks, energy peak {max(en):.3f} at {en.index(max(en))}, '
                  f'hips y {min(hy):.2f}..{max(hy):.2f}, travel max {max(hd):.2f}')
            if name in ('anim_01', 'anim_02', 'anim_03'):
                print('   window(90):', attack_window(m, name, 90))


def cmd_run(a):
    L = load_list(a.list)
    out_dir = os.path.join(ROOT, L.get('out', 'build/batch'))
    os.makedirs(out_dir, exist_ok=True)
    existing = {t: s for t, s in species.load_content().items() if t < L['first_id']}
    ctx = dict(free=free_slots(existing), used={}, list=os.path.relpath(a.list, ROOT),
               names={t: x['name'] for t, x in existing.items()})
    reports = {}
    rpath = os.path.join(out_dir, 'report.json')
    if os.path.exists(rpath):
        reports = json.load(open(rpath))
    # every species file first (the Exe registers them in id order, consecutive)
    plans = []
    gone = retired()
    OVERWRITE.update(a.overwrite or [])
    for typ, e in selected(L, None):
        if typ in gone and 'merged_into' not in gone[typ]:
            print(f'== {typ} {e["name"]}: skipped, {gone[typ].get("removed")} ({os.path.relpath(RETIRED_PATH, ROOT)})',
                  flush=True)
            continue
        if typ in gone:
            MERGED[typ] = gone[typ]['merged_into']
            print(f'== {typ} {e["name"]}: its file is species {MERGED[typ]} now ({gone[typ].get("why", "merged")})')
        print(f'== {typ} {e["name"]}', flush=True)
        m, spec, sp, rep = (plan_dw1 if e.get('game') == 'dw1' else plan)(e, typ, out_dir, ctx)
        path = os.path.join(species.CONTENT, f'{typ}-{e["name"].lower()}.json')
        if not a.only or e['name'] in a.only or not existing_file(MERGED.get(typ, typ)):
            write_species(path, sp)                        # (--only: the others keep their built files)
        plans.append((typ, e, m, spec, sp, rep))
        ctx['names'][typ] = e['name']
        ctx['free'][typ] = NEW_TARGETS      # later entries may evolve from this one ("from" in the list)
    mmd._EXE = None
    for typ, e, m, spec, sp, rep in plans:
        if a.only and e['name'] not in a.only:
            continue
        print(f'== build {typ} {e["name"]}: donor {rep["donor"]["name"] if "donor" in rep else "-"}', flush=True)
        if e.get('game') == 'dw1':
            data = build_dw1(spec, sp, out_dir, rep) if not rep['hand'] else None
        else:
            data = build_one(m, spec, sp, out_dir, rep)
        write_species(os.path.join(species.CONTENT, f'{typ}-{e["name"].lower()}.json'), sp)
        if e.get('game') != 'dw1':
            rep['techniques'] = [t for t in rep['techniques'] if sp['para']['moves'][int(t['slot'], 16) - 0x2E] != 255]
        if data is not None and e.get('game') == 'dw1':
            verify_dw1(os.path.join(out_dir, e['name'] + '.MMD'), int(e['type']), sp, rep, out_dir)
        elif data is not None:
            verify(os.path.join(out_dir, e['name'] + '.MMD'), typ, os.path.join(out_dir, e['name'] + '.TIM'), sp,
                   rep, out_dir)
        rep['outcome'] = 'failed' if rep['hand'] else ('rule fix' if rep['rules'] else 'automatic')
        reports[e['name']] = rep
        json.dump(reports, open(rpath, 'w'), indent=1, default=str)        # saved after each Digimon (power cuts)
        print(json.dumps(rep, indent=1, default=str), flush=True)
    cmd_report(a)


def cmd_report(a):
    L = load_list(a.list)
    out_dir = os.path.join(ROOT, L.get('out', 'build/batch'))
    reports = json.load(open(os.path.join(out_dir, 'report.json')))
    print(f'{"id":>3} {"name":15s} {"level":9s} {"element":8s} {"donor":12s} {"from":12s} {"bytes":>6} outcome')
    for typ, e in selected(L, None):
        r = reports.get(e['name'])
        if not r:
            continue
        print(f'{typ:3d} {e["name"]:15s} {LEVELS[r["level"]]:9s} {ELEMENTS[r["element"]]:8s} '
              f'{r["donor"]["name"]:12s} {(r["evolves_from"] or ["", "-"])[1]:12s} {r.get("mmd_bytes", 0):6d} '
              f'{r["outcome"]}' + ('' if not r['rules'] and not r['hand'] else
                                   ': ' + '; '.join(r['rules'] + r['hand'])))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name, f in (('run', cmd_run), ('donors', cmd_donors), ('clips', cmd_clips), ('report', cmd_report)):
        p = sub.add_parser(name)
        p.add_argument('list')
        p.add_argument('--only', nargs='*')
        p.set_defaults(f=f)
        if name == 'run':
            p.add_argument('--overwrite', nargs='*', metavar='FIELD',
                           help='take the import\'s value for these PRESERVED fields of an existing file (or "all")')
        if name == 'donors':
            p.add_argument('--top', type=int, default=5)
            p.add_argument('--map', action='store_true')
            p.add_argument('--with', dest='with_', type=int, nargs='*')
    a = ap.parse_args()
    _venv()
    a.f(a)


if __name__ == '__main__':
    main()
