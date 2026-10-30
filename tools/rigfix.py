#!/usr/bin/env python3
"""Rig fixes for imported models: bone merging, missing animations, poor-donor motion.

Everything here is an automatic rule that runs on the player's own copy of the source game at
build time (the batch import, tools/import_batch.py): no model, pose or animation is edited by
hand and nothing derived from a game is stored; the lists and specs only hold parameters.

1. `fit_bones(model, max_bones)`: a skeleton with more bones than the engine takes (a partner has
   room for 34 including the entity: 33 model bones) is reduced by merging bones. Steps:
   - bones with no mesh (pure joints) are dissolved first: their children move to the nearest kept
     ancestor and every pose is kept exactly (the children's local transforms are recomputed);
   - then, greedily, the bone whose piece moves least relative to another kept bone over the source
     clips (leaf pieces, tail chains, fingers) is merged into it: its mesh is moved into that bone's
     frame at the rest pose and from then on follows it rigidly. The cost is the mean and worst
     displacement of the piece's vertices over a sample of every source animation, in units of the
     model height, so a rigid or near-rigid piece goes first.
   Afterwards every source clip is re-evaluated on the reduced skeleton and the pose error (rms and
   worst vertex displacement per clip, in model heights) is reported; `fit_bones` raises
   `RigError` when the worst error is over `max_error` (the species is then not imported).
   The reduction is deterministic, so a spec only records `{"rigfix": {"max_bones": 33}}`.
2. `roles` / `role_cost`: limb roles (leg, arm, wing, tail, head) added to the donor bone cost (list option
   "roles"); `gait_spec` / `gait`: a generic leg gait for legs the donor map leaves unmapped.
Documented in docs/mods/models.md section 15. Hooks: import_batch.load_source/plan, dw3mmd.prepare,
mmdport.build_partner. Numeric helpers use the Python standard library.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mmd  # noqa: E402
import mmdport  # noqa: E402
import meshfix  # noqa: E402

import numeric as np


class RigError(Exception):
    pass


MAX_MODEL_BONES = 33          # 34 DW1 bones for a partner, bone 0 is the entity
MAX_ERROR = 0.12              # worst vertex displacement allowed, in model heights (a whisker or a tail tip)
MAX_RMS = 0.015               # and the rms of any clip (the whole body)


# ---------------------------------------------------------------- numeric helpers
def _trs(q, t, s):
    r = mmd.quat_matrix(q)
    sx, sy, sz = (float(v) for v in s)
    tx, ty, tz = (float(v) for v in t)
    return np.Array([r[0][0]*sx, r[0][1]*sy, r[0][2]*sz, tx,
                     r[1][0]*sx, r[1][1]*sy, r[1][2]*sz, ty,
                     r[2][0]*sx, r[2][1]*sy, r[2][2]*sz, tz,
                     0., 0., 0., 1.], (4, 4), np.float64)


def _world_all(model, frames):
    """W[f][i] 4x4 of every bone for a list of frames (each [bone](q, t, s))."""
    n = len(model.bones)
    out = np.zeros((len(frames), n, 4, 4))
    for k, fr in enumerate(frames):
        for i in range(n):
            L = _trs(*fr[i])
            p = model.bones[i]['parent']
            out[k, i] = out[k, p] @ L if p >= 0 else L
    return out


def _decompose(A):
    """A = R · diag(s) -> (quaternion, scale)."""
    s = np.linalg.norm(A, axis=0)
    s = np.where(s < 1e-9, 1e-9, s)
    R = A / s[None, :]
    if np.linalg.det(R) < 0:                       # a mirrored matrix: put the flip in one scale
        R[:, 0] *= -1
        s[0] *= -1
    return mmdport.quat_of_matrix(R.tolist()), tuple(float(x) for x in s)


def _height(model, ref):
    W = _world_all(model, [ref])[0]
    ys = []
    for i, b in enumerate(model.bones):
        if b['verts']:
            v = np.array(b['verts'], float)
            ys.append((v @ W[i][:3, :3].T + W[i][:3, 3])[:, 1])
    y = np.concatenate(ys)
    return float(y.max() - y.min()) or 1.0


def _sample_frames(model, per_anim=10, ref=None):
    """A sample of every source animation (first, last and evenly spaced frames)."""
    fr = [ref] if ref is not None else []
    for name in sorted(model.anims):
        F = model.anims[name].frames
        n = len(F)
        idx = sorted(set(round(k * (n - 1) / max(1, per_anim - 1)) for k in range(per_anim)))
        fr += [F[i] for i in idx]
    return fr


# ---------------------------------------------------------------- bone merging
def _motion_error(matrices, points, target, height):
    """RMS/worst carrier error without materializing transformed point tensors.

    Keep the four-term transform, three-term square sum and pairwise mean in
    the same order as einsum -> norm -> divide -> square -> mean.
    """
    points = points.tolist()
    expected = target.flat
    squared, worst = [], 0.0
    for frame in matrices:
        r0, r1, r2 = frame.tolist()[:3]
        for x, y, z, w in points:
            dx = ((((0.0 + r0[0]*x) + r0[1]*y) + r0[2]*z) + r0[3]*w) - next(expected)
            dy = ((((0.0 + r1[0]*x) + r1[1]*y) + r1[2]*z) + r1[3]*w) - next(expected)
            dz = ((((0.0 + r2[0]*x) + r2[1]*y) + r2[2]*z) + r2[3]*w) - next(expected)
            distance = math.sqrt(((0.0 + dx*dx) + dy*dy) + dz*dz) / height
            squared.append(distance ** 2)
            if distance > worst: worst = distance
    mean = np.Array(squared, (len(squared),), np.float64).mean()
    return math.sqrt(mean), worst


def fit_bones(model, max_bones=MAX_MODEL_BONES, ref_anim=None, per_anim=12, max_error=MAX_ERROR, max_rms=MAX_RMS, log=print, all_empty=False):
    """Reduces `model` (mmdport.Model, changed in place) to at most `max_bones` bones; see the module doc.
    Returns a report dict (merged pairs, pose error per clip)."""
    nb0 = len(model.bones)
    if nb0 <= max_bones and not all_empty:
        return dict(merged=[], bones=nb0)
    ref_anim = ref_anim or getattr(model, 'idle', None) or ('anim_00' if 'anim_00' in model.anims else sorted(model.anims)[0])
    ref = model.anims[ref_anim].frames[0]
    H = _height(model, ref)
    sample = _sample_frames(model, per_anim, ref)           # sample[0] is the reference
    W = _world_all(model, sample)                           # (F, nb, 4, 4)
    Wref = W[0]
    parent = [b['parent'] for b in model.bones]
    # points of each original bone, in world space per sampled frame
    pts = {}
    for i, b in enumerate(model.bones):
        if b['verts']:
            v = np.array(b['verts'], float)
            v = np.hstack([v, np.ones((len(v), 1))])
            if len(v) > 24:                                  # a sample of a big piece
                v = v[np.linspace(0, len(v) - 1, 24).astype(int)]
            pts[i] = np.einsum('fij,nj->fni', W[:, i], v)[:, :, :3]       # (F, n, 3)
    kept = list(range(nb0))
    carrier = {i: i for i in range(nb0)}                     # original bone -> kept bone that carries its mesh
    newparent = list(parent)                                  # parent among the kept bones (updated as bones go)
    merged = []

    def kept_parent(i):
        p = newparent[i]
        while p >= 0 and p not in kept_set:
            p = newparent[p]
        return p

    def descendants_of(i):
        out, stack = set(), [i]
        while stack:
            x = stack.pop()
            for c in kept:
                if kept_parent(c) == x and c not in out:
                    out.add(c)
                    stack.append(c)
        return out

    def dissolve(i, into):
        """Bone i leaves the kept set; its group's mesh goes to `into` (or nowhere if it has none)."""
        kept.remove(i)
        kept_set.discard(i)
        for o, c in carrier.items():
            if c == i:
                carrier[o] = into if into is not None else -1
        merged.append((i, into))

    kept_set = set(kept)
    # 1. joints with no mesh and no mesh below them that matters: dissolve for free (not roots)
    for i in list(kept):
        if len(kept) <= max_bones and not all_empty:      # all_empty: every empty joint goes (a lighter skeleton, fewer animation bytes)
            break
        if parent[i] >= 0 and i not in pts and kept_parent(i) >= 0:
            dissolve(i, None)
    # 2. greedy: the cheapest merge of a mesh bone into another kept bone
    while len(kept) > max_bones:
        total = sum(len(p[0]) for p in pts.values()) or 1
        best = None
        for i in kept:
            if kept_parent(i) < 0:
                continue                                      # roots stay
            group = [o for o, c in carrier.items() if c == i and o in pts]
            if not group:
                dissolve(i, None)
                break
            P = np.concatenate([pts[o] for o in group], axis=1)           # (F, n, 3) true positions
            n = P.shape[1]
            Pref = np.hstack([P[0], np.ones((n, 1))])
            bad = descendants_of(i) | {i}
            for j in kept:
                if j in bad:
                    continue
                try:
                    Cj = np.einsum('fab,bc->fac', W[:, j], np.linalg.pinv(Wref[j]))      # carrier motion from the reference
                except np.linalg.LinAlgError:
                    continue
                rms, worst = _motion_error(Cj, Pref, P, H)
                cost = (0.5 * rms + 0.5 * worst) * (1 + 6 * n / total) ** 0.5
                # a neighbour is the natural carrier: slight preference to the parent
                if j == kept_parent(i):
                    cost *= 0.9
                if best is None or cost < best[0]:
                    best = (cost, i, j, rms, worst)
        else:
            if best is None:
                raise RigError('no merge possible')
            _, i, j, rms, worst = best
            for c in kept:                                                  # children of i hang from i's parent
                if newparent[c] == i:
                    newparent[c] = kept_parent(i)
            dissolve(i, j)
            log(f'  bone {i + 1} merged into bone {j + 1}: rms {rms * 100:.2f} %, worst {worst * 100:.2f} % of the height')
    old_bones = model.bones
    old_frames = {n: a.frames for n, a in model.anims.items()}
    # parents among kept bones
    kept_set = set(kept)
    kp = {i: kept_parent(i) for i in kept}
    order = list(kept)                                        # original order is kept (parents first)
    new_index = {o: k for k, o in enumerate(order)}
    # new geometry: merged pieces moved into their carrier's frame at the reference pose
    new_bones = []
    for o in order:
        b = model.bones[o]
        nbn = dict(b)
        nbn['verts'], nbn['norms'], nbn['prims'] = list(b['verts']), list(b['norms']), [dict(p) for p in b['prims']]
        new_bones.append(nbn)
    vmap = {o: (new_index[o], 0) for o in order}
    for o in range(nb0):
        c = carrier[o]
        if c == o or c < 0 or not model.bones[o]['verts']:
            continue
        rel = np.linalg.pinv(Wref[c]) @ Wref[o]                # original bone o's local -> carrier's local at the reference
        Rn = rel[:3, :3]
        nbc = new_bones[new_index[c]]
        v0, n0 = len(nbc['verts']), len(nbc['norms'])
        vmap[o] = (new_index[c], v0)
        src = model.bones[o]
        for v in src['verts']:
            nbc['verts'].append(tuple(float(x) for x in (rel @ np.array([v[0], v[1], v[2], 1.0]))[:3]))
        Rnn = np.linalg.pinv(Rn).T                              # normals: inverse transpose, renormalised
        for nv in src['norms']:
            r = Rnn @ np.array(nv[:3], float)
            L = np.linalg.norm(r) or 1.0
            nbc['norms'].append(tuple(float(x) * 4096 / L if abs(nv[0]) + abs(nv[1]) + abs(nv[2]) > 8 else float(x) for x in r))
        for p in src['prims']:
            p2 = dict(p)
            p2['verts'] = [k + v0 for k in p['verts']]
            if p.get('norms') is not None:
                p2['norms'] = [k + n0 for k in p['norms']]
            nbc['prims'].append(p2)
    for o in order:
        nbn = new_bones[new_index[o]]
        nbn['parent'] = new_index[kp[o]] if kp[o] >= 0 else -1
    # animations: bones whose parent did not change keep their data; the others get the local
    # transform that reproduces their world pose under the new parent
    for name, a in model.anims.items():
        nfr = []
        Wf = _world_all(model, a.frames)
        for k, fr in enumerate(a.frames):
            row = []
            for o in order:
                if kp[o] == parent[o]:
                    row.append(fr[o])
                else:
                    L = np.linalg.inv(Wf[k, kp[o]]) @ Wf[k, o]
                    q, s = _decompose(L[:3, :3])
                    row.append((q, tuple(float(x) for x in L[:3, 3]), s))
            nfr.append(row)
        a.frames = nfr
    model.bones = new_bones
    model._rig_map = vmap
    if getattr(model, 'hub', None) is not None and model.hub in new_index:
        model.hub = new_index[model.hub]
    # re-evaluate every clip on the reduced skeleton
    report = dict(merged=[(i + 1, (j + 1) if j is not None else None) for i, j in merged], bones=len(new_bones), nb0=nb0, clips={})
    report['clips'] = pose_error(old_bones, old_frames, model, H)
    worst = max((w for _, w in report['clips'].values()), default=0.0)
    report['worst'] = worst
    log(f'  {nb0} -> {len(new_bones)} bones; pose error over {len(report["clips"])} clips: worst {worst * 100:.1f} % of the height, '
        f'mean of clip rms {100 * sum(r for r, _ in report["clips"].values()) / max(1, len(report["clips"])):.2f} %')
    rms = max((r for r, _ in report['clips'].values()), default=0.0)
    if worst > max_error or rms > max_rms:
        model.bones = old_bones                              # transactional: the model stays as it was
        for n, a in model.anims.items():
            a.frames = old_frames[n]
        raise RigError(f'bone merge pose error: worst {worst * 100:.1f} % (limit {max_error * 100:.0f} %), rms {rms * 100:.2f} % '
                       f'(limit {max_rms * 100:.1f} %) of the height')
    return report


class _Shim:
    def __init__(self, bones):
        self.bones = bones


def pose_error(old_bones, old_frames, model, H, step=3):
    """{clip: (rms, worst)}: vertex displacement, in model heights, of every source clip on the reduced
    skeleton (`model`) against the original skeleton (`old_bones`, `old_frames` {clip: frames})."""
    out = {}
    so = _Shim(old_bones)
    for name, fr_old in old_frames.items():
        idx = list(range(0, len(fr_old), step))
        if idx[-1] != len(fr_old) - 1:
            idx.append(len(fr_old) - 1)
        Wo = _world_all(so, [fr_old[i] for i in idx])
        Wn = _world_all(model, [model.anims[name].frames[i] for i in idx])
        # every vertex of the original bones against the same vertex in the reduced bones: the new
        # vertex list of a bone is its own vertices then the merged ones, so match by construction
        P0, P1 = [], []
        new_of = getattr(model, '_rig_map', {})
        for o, (nb_, voff) in new_of.items():
            v = np.array(old_bones[o]['verts'], float)
            if not len(v):
                continue
            if len(v) > 40:
                v = v[np.linspace(0, len(v) - 1, 40).astype(int)]
                sel = np.linspace(0, len(old_bones[o]['verts']) - 1, 40).astype(int)
            else:
                sel = np.arange(len(v))
            vh = np.hstack([v, np.ones((len(v), 1))])
            P0.append(np.einsum('fij,nj->fni', Wo[:, o], vh)[:, :, :3])
            vn = np.array([model.bones[nb_]['verts'][voff + k] for k in sel], float)
            vnh = np.hstack([vn, np.ones((len(vn), 1))])
            P1.append(np.einsum('fij,nj->fni', Wn[:, nb_], vnh)[:, :, :3])
        d = np.linalg.norm(np.concatenate(P1, axis=1) - np.concatenate(P0, axis=1), axis=2) / H
        out[name] = (float(np.sqrt((d ** 2).mean())), float(d.max()))
    return out


# ---------------------------------------------------------------- inspection
def sheet(model, out, anims=None, every=8, size=120, yaw=30.0, typ=250):
    """Contact sheet of a source model's animations through the DW1 renderer (as dw3mmd.py sheet, but for a
    model already loaded and possibly reduced): one row per animation, one frame every `every` ticks."""
    base = mmdport.base_mmd(model, typ, log=lambda *a: None)
    tim = mmd.Tim4(mmdport.build_tim(model.idx, model.pals))
    rows = []
    for k in (anims or list(model.anims)):
        an = model.anims[k]
        imgs = []
        for f in an.frames[::every]:
            pose = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]]
            prev = None
            for (q, t, s) in f:
                e = [round(x) for x in mmd.matrix_euler(mmd.quat_matrix(q), prev)]
                pose.append([round(x * 4096) for x in s] + e + [round(x) for x in t])
            imgs.append(mmd.render(base, tim, pose, size, math.radians(yaw)))
        rows.append(imgs)
    W = max(len(r) for r in rows) * size
    Hh = len(rows) * size
    img = bytearray([30, 30, 30, 255] * (W * Hh))
    for r, imgs in enumerate(rows):
        for c, im in enumerate(imgs):
            for y in range(size):
                o = ((r * size + y) * W + c * size) * 4
                img[o:o + size * 4] = im[y * size * 4:(y + 1) * size * 4]
    mmd.png_write(out, W, Hh, img)


# ---------------------------------------------------------------- batch-import hooks
def on_load(m, entry, log=print):
    """Called by import_batch.load_source for a DW2003 model, after the roots are joined: applies the
    rules this module has (the entry may switch them off with "rigfix": false). Sets m.rig (what
    happened and the spec fields to rebuild it) or m.rig_error."""
    m.rig, m.rig_error = None, None
    if entry.get('rigfix') is False:
        return
    spec = {}
    notes = []
    try:
        if len(m.bones) > MAX_MODEL_BONES:
            if entry.get('meshfix') is not False and not (isinstance(entry.get('meshfix'), dict) and entry['meshfix'].get('hidden') is False):
                # rule: effect pieces the idle hides by a zero scale (Kyubimon's nine spread tails: 18 of its 44 bones) go
                # first, so their bones are empty joints that fit_bones dissolves for free instead of being merged
                h = meshfix.drop_hidden(m, log)
                if h:
                    spec['hidden'] = True
                    notes.append(f'{len(h)} effect pieces hidden by a zero scale in the idle animation dropped (bones {h[0][0]}..{h[-1][0]})')
            r = fit_bones(m, MAX_MODEL_BONES, log=log, all_empty=bool(spec.get('hidden')))
            spec['max_bones'] = MAX_MODEL_BONES
            notes.append(f'{r["nb0"]} bones merged down to {r["bones"]} ({len(r["merged"])} merges); pose error over '
                         f'{len(r["clips"])} source clips: worst {r["worst"] * 100:.1f} % of the height, '
                         f'rms of the worst clip {max(x for x, _ in r["clips"].values()) * 100:.2f} %')
    except RigError as e:
        m.rig_error = str(e)
        return
    if spec:
        m.rig = dict(spec=spec, notes=notes)


def prepare(model, spec, log=print):
    """dw3mmd.prepare: the same reductions from the spec's parameters. (A `"lone"` key, left in specs
    made before 2026-10-13, is ignored: the "one long sequence" of Guilmon and Bastemon was the dw3
    decoder reading the wrong section as the animation table; both files have their slots.)"""
    if spec.get('hidden') and len(model.bones) > spec.get('max_bones', MAX_MODEL_BONES):
        meshfix.drop_hidden(model, lambda *a: None)
    if spec.get('max_bones') and len(model.bones) > spec['max_bones']:
        fit_bones(model, spec['max_bones'], log=lambda *a: None, all_empty=bool(spec.get('hidden')))


def report(m, rep):
    if getattr(m, 'rig', None):
        rep['rules'] += ['rigfix: ' + n for n in m.rig['notes']]
    if getattr(m, 'rig_error', None):
        rep['hand'].append('rigfix: ' + m.rig_error)


# ---------------------------------------------------------------- limb roles for the donor match
def roles(shape):
    """Role of every bone of an import_batch.Shape (height units, ground at 0, Y down, facing -Z): 'leg' (the piece
    is in the lower third, below the hips), 'head' (top 15 %), 'wing' (far to the side and high), 'tail' (behind the
    hips, low or level with them), 'arm' (to the side, between), 'body' (the rest: centred pieces). Cached."""
    r = getattr(shape, '_roles', None)
    if r is not None:
        return r
    n = len(shape.joint)
    hips = shape.joint[1] if n > 1 else (0, -0.5, 0)
    r = ['body'] * n
    for b in range(1, n):
        if not shape.mass[b]:
            continue
        x, y, z = shape.tip[b]
        if y > -0.34 and y > hips[1] + 0.02:
            r[b] = 'leg'
        elif y < -0.85:
            r[b] = 'head'
        elif abs(x) > 0.25 and y < -0.35:
            r[b] = 'wing'
        elif z > 0.12 and y > -0.6:
            r[b] = 'tail'
        elif abs(x) > 0.06:
            r[b] = 'arm'
    shape._roles = r
    return r


def role_cost(T, S, tb, sb):
    """Extra bone-match cost when the two bones' limb roles differ (a 'body' piece goes with anything at a small price)."""
    a, b = roles(T)[tb], roles(S)[sb]
    if a == b:
        return 0.0
    if 'body' in (a, b):
        return 0.04
    return 0.16


# ---------------------------------------------------------------- generic gait for legs the donor map leaves out
def gait_spec(shape, bmap):
    """Rule: when the donor's map leaves limbs of the 'leg' role unmapped (a body unlike the donor's: a
    six-legged beetle on a four-legged donor), those legs get a procedural gait in every retargeted slot where the
    body travels: the top bone of each unmapped leg chain swings about the lateral axis in step with the distance
    covered (one cycle per `stride`), diagonal legs in opposition, the next bone along it lagging for a knee.
    Returns the spec dict ({"legs": [[bone, phase, depth]], "stride", "amp"}) or None."""
    r = roles(shape)
    n = len(shape.joint)
    top = [b for b in range(1, n) if r[b] == 'leg' and b not in bmap and shape.mass[b]
           and not (shape.parent[b] > 0 and r[shape.parent[b]] == 'leg' and shape.parent[b] not in bmap)]
    if not top:
        return None
    legs = []
    stride = []
    for b in top:
        x, y, z = shape.joint[b]
        side = 1 if shape.tip[b][0] >= 0 else -1
        front = 1 if shape.tip[b][2] <= shape.joint[1][2] else -1             # -Z is forward
        phase = 0.0 if side * front > 0 else math.pi
        legs.append([b, round(phase, 3), 0])
        chain, c = [], b
        while True:                                                            # the chain below: knees and feet
            kids = [k for k in range(1, n) if shape.parent[k] == c and shape.mass[k] and r[k] == 'leg' and k not in bmap]
            if not kids:
                break
            c = kids[0]
            legs.append([c, round(phase, 3), len(chain) + 1])
            chain.append(c)
        low = max(shape.tip[k][1] for k in [b] + chain)
        stride.append(max(0.1, low - min(0.0, y)) * shape.H)
    return dict(legs=legs, stride=round(1.3 * sum(stride) / len(stride), 1), amp=26)


def gait(smp, spec, skel, min_cycles=0.75):
    """Adds the gait of `gait_spec` to a slot's poses (`smp`: per tick, per bone [sx sy sz rx ry rz tx ty tz] in engine
    units, bone 0 holding the root motion), in place. Slots where the body covers less than `min_cycles` strides
    are left alone. Returns True when it was applied."""
    from retarget import m3mul, m3t, rot_of, world_rots
    if len(smp) < 4:
        return False
    d, dist = 0.0, [0.0]
    for t in range(1, len(smp)):
        a, b = smp[t - 1][0], smp[t][0]
        d += math.hypot(b[6] - a[6], b[8] - a[8])
        dist.append(d)
    stride = float(spec['stride'])
    if d < min_cycles * stride:
        return False
    prev = {}
    for t, pose in enumerate(smp):
        base = [list(v) for v in pose]
        base[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]                    # the entity's own turn is left out of the axis
        W = world_rots(skel, base)
        for b, phase, depth in spec['legs']:
            th = math.radians(spec.get('amp', 26)) * (0.6 if depth else 1.0) * math.sin(2 * math.pi * dist[t] / stride + phase - 0.9 * depth)
            c, s = math.cos(th), math.sin(th)
            Rx = [[1, 0, 0], [0, c, -s], [0, s, c]]
            par = skel[b][1]
            Wp = W[par]
            L = m3mul(m3t(Wp), m3mul(Rx, m3mul(Wp, rot_of(pose[b]))))
            e = mmd.matrix_euler(L, prev.get(b))
            prev[b] = e
            pose[b][3:6] = [round(x) for x in e]
            base[b][3:6] = pose[b][3:6]
            W = world_rots(skel, base)
    return True
