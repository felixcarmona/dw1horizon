"""The source game's own battle clips on a native binding's donor rig (the recipe's `battle_originals`).

A native binding (native_binding.py) fits the imported mesh pieces to a DW1 donor skeleton and plays the donor's
programs, so every battle slot would be the donor's. This stage takes the source model's own clip of each listed slot
(battle idles 0x21/0x22, movements 0x23/0x24, hits, victory, faint, get up 0x28-0x2C, techniques 0x2E+i) and poses the
donor rig with it, tick by tick:

- every donor bone that carries pieces is turned so that its pieces keep the world orientation the source gives them
  (each piece's own fitting rotation taken out, so a limb points where the source's limb points, at the donor's
  length); a bone carrying several source pieces takes their weighted mean (weights: the pieces' spread about the
  joint), riders (native_binding `riders`) are bones of their own and follow their lead piece;
- the bones above the body that carry nothing turn with the source's body bone, the body joint follows the source's
  body joint (scaled by the ratio of the two hip heights), the root keeps the source's turn and travel;
- every other bone keeps its rest rotation; translations are the bound rig's, scale channels its rest ones;
- the clip is retimed to the length the slot has in the bound model (technique effects are timed to it) as
  tools/models/battle_restore.py retimes: idles repeat whole cycles, movements and one-shot clips are resampled.
  Sounds are the source clip's (texture moves are dropped: the atlas has another layout).

Only the listed slots change; every other slot's program stays byte for byte. Slots whose retargeted clip measured
worse than the donor's (tools/models/battle_qa_native.py) are simply not listed. Standard library only.
"""
import math

import animsheet
import mmd
import motioncyclelayer
from tools.models import battle_restore
from tools.models import clip_repair

IDLES, MOVES = (33, 34), (35, 36)
TECHNIQUES = 0x2E          # slots from here on are the species' techniques
FIELD, BATTLE = range(5), range(33, 37)
MAX_TOL = 5                # compaction tolerance, units of 1/4096 turn: 5 is 0.44 degrees


def _mul(a, b):
    return [[a[i][0]*b[0][j] + a[i][1]*b[1][j] + a[i][2]*b[2][j] for j in range(3)] for i in range(3)]


def _tr(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def _apply(a, v):
    return [a[i][0]*v[0] + a[i][1]*v[1] + a[i][2]*v[2] for i in range(3)]


def polar(m):
    """The rotation of the polar decomposition of a 3x3 matrix (Newton: X <- (X + X^-T) / 2)."""
    x = [list(map(float, r)) for r in m]
    for _ in range(60):
        a, b, c = x
        det = a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0])
        cof = [[b[1]*c[2]-b[2]*c[1], b[2]*c[0]-b[0]*c[2], b[0]*c[1]-b[1]*c[0]],
               [c[1]*a[2]-c[2]*a[1], c[2]*a[0]-c[0]*a[2], c[0]*a[1]-c[1]*a[0]],
               [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]]
        nxt = [[(x[i][j] + cof[i][j]/det)/2 for j in range(3)] for i in range(3)]
        done = max(abs(nxt[i][j]-x[i][j]) for i in range(3) for j in range(3)) < 1e-12
        x = nxt
        if done:
            break
    return x


FLIP = [[-1., 0, 0], [0, 1., 0], [0, 0, 1.]]


def mirrored_fit(twin_fit, twin_bind, own_bind):
    """The fitting rotation of a piece placed as the mirror of its twin's fitted piece (native_binding.mirror_piece):
    its local vertex v is the reflection of the twin's local vertex X.v, so its world shape is
    X.Q_twin.W_twin.X.v, and the rotation from its own source world (W_own.v) is X.Q_twin.W_twin.X.W_own^T. Only when the
    source poses the twins as mirrors of each other (W_twin = X.W_own.X) is it X.Q_twin.X."""
    bind = _mul(_mul(polar(twin_bind), FLIP), _tr(polar(own_bind)))
    return _mul(_mul(FLIP, twin_fit), bind)


def _quat(m):
    """(w, x, y, z) of a rotation matrix."""
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0:
        s = math.sqrt(t + 1) * 2
        return [s/4, (m[2][1]-m[1][2])/s, (m[0][2]-m[2][0])/s, (m[1][0]-m[0][1])/s]
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1 + m[0][0] - m[1][1] - m[2][2]) * 2
        return [(m[2][1]-m[1][2])/s, s/4, (m[0][1]+m[1][0])/s, (m[0][2]+m[2][0])/s]
    if m[1][1] > m[2][2]:
        s = math.sqrt(1 + m[1][1] - m[0][0] - m[2][2]) * 2
        return [(m[0][2]-m[2][0])/s, (m[0][1]+m[1][0])/s, s/4, (m[1][2]+m[2][1])/s]
    s = math.sqrt(1 + m[2][2] - m[0][0] - m[1][1]) * 2
    return [(m[1][0]-m[0][1])/s, (m[0][2]+m[2][0])/s, (m[1][2]+m[2][1])/s, s/4]


def _matrix(q):
    w, x, y, z = q
    return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
            [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
            [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]


def mean_rotation(rotations, weights):
    """The normalised weighted mean of rotations (quaternions turned to the heaviest one's hemisphere)."""
    if len(rotations) == 1:
        return rotations[0]
    qs = [_quat(r) for r in rotations]
    lead = qs[max(range(len(qs)), key=lambda i: weights[i])]
    acc = [0.0]*4
    for q, w in zip(qs, weights):
        sign = 1 if sum(a*b for a, b in zip(q, lead)) >= 0 else -1
        acc = [a + sign*w*v for a, v in zip(acc, q)]
    n = math.sqrt(sum(a*a for a in acc))
    return _matrix([a/n for a in acc])


def order(skeleton):
    """Bone indices with every parent before its children (a source rig may list a child first)."""
    out, seen = [], set()

    def visit(b):
        if b not in seen:
            seen.add(b)
            if skeleton[b][1] >= 0:
                visit(skeleton[b][1])
            out.append(b)
    for b in range(len(skeleton)):
        visit(b)
    return out


def world(skeleton, pose, yaw=None):
    """(rotation, position) per bone of a pose with the root's turn and travel taken out (y down)."""
    rot, pos = [None]*len(skeleton), [None]*len(skeleton)
    for b in order(skeleton):
        parent, v = skeleton[b][1], pose[b]
        if parent < 0:
            rot[b], pos[b] = [[1., 0, 0], [0, 1., 0], [0, 0, 1.]], [0., 0., 0.]
            continue
        rot[b] = _mul(rot[parent], mmd.rot_matrix(*v[3:6]))
        offset = [x*s/4096 for x, s in zip(v[6:9], pose[parent][0:3])]
        pos[b] = [p + d for p, d in zip(pos[parent], _apply(rot[parent], offset))]
    if yaw is not None:
        rot = [_mul(yaw, r) for r in rot]
        pos = [_apply(yaw, p) for p in pos]
    return rot, pos


def plan(slot, source_ticks, want):
    """(frames, cycles) of the retimed clip: battle_restore's rule for the battle idles and movements; any other slot
    (hits, victory, faint, get up, techniques) is resampled to the slot's length."""
    if slot in IDLES or slot in MOVES:
        return battle_restore.plan(slot, source_ticks, want)
    return want, 1


def scaled_events(events, frames, want):
    """Events of a clip of `frames` frames moved to the same moments of a clip of `want` frames."""
    if want == frames:
        return list(events)
    return [(min(want - 2, round(k * (want - 1) / (frames - 1))), kind, c) for k, kind, c in events]


def source_clip(source, nb, slot, want):
    """(samples, events, loop sample, cycles) of the source's clip of `slot` for a final clip of `want` frames."""
    frames, loop, events = animsheet.slot_frames(source, nb, slot)
    events = [e for e in events if not e[1].startswith('tex')]
    count, tile = plan(slot, len(frames), want)
    if loop not in (None, 0):
        raise ValueError(f'slot {slot}: a source clip that loops from tick {loop} is not supported')
    if count != len(frames):
        frames, events = battle_restore.retimed(frames, events, count - 1, tile)
    frames = [[[int(v) for v in bone] for bone in pose] for pose in frames]
    return frames, events, loop, tile


def retarget(frames, ctx):
    """Donor-rig samples for source poses `frames` (see the module's header)."""
    rig, rest, pieces = ctx['rig'], ctx['rest'], ctx['pieces']
    nb = len(rig)
    rest_local = [mmd.rot_matrix(*rest[b][3:6]) for b in range(nb)]
    lifted, hips, top, k = ctx['lifted'], ctx['hips'], ctx['top'], ctx['k']
    bind_rot, bind_pos = ctx['bind_rot'], ctx['bind_pos']
    out = []
    prev = [list(rest[b][3:6]) for b in range(nb)]
    for pose in frames:
        rot, pos = world(ctx['skeleton'], pose, ctx['yaw'])
        body = _mul(rot[hips[0]], _tr(bind_rot[hips[0]]))
        R = [None]*nb
        sample = [None]*nb
        for b in order(rig):
            parent = rig[b][1]
            if parent < 0:
                R[b] = [[1., 0, 0], [0, 1., 0], [0, 0, 1.]]
                continue
            if b in pieces:
                R[b] = mean_rotation([_mul(rot[s], c) for s, c, _ in pieces[b]], [w for _, _, w in pieces[b]])
            elif b in lifted:
                R[b] = _mul(body, ctx['rest_rot'][b])
            else:
                R[b] = _mul(R[parent], rest_local[b])
            local = _mul(_tr(R[parent]), R[b])
            e = mmd.matrix_euler(local, prev=prev[b])
            prev[b] = e
            sample[b] = list(rest[b][0:3]) + [int(round(v)) for v in e] + list(rest[b][6:9])
        # the body joint follows the source's body joint: the top bone's translation puts it there
        P = [None]*nb
        for b in order(rig):
            parent = rig[b][1]
            P[b] = [0., 0., 0.] if parent < 0 else [p + d for p, d in zip(P[parent], _apply(R[parent], sample[b][6:9]))]
        want = [r + k*(s - sb) for r, s, sb in zip(ctx['rest_pos'][hips[1]], pos[hips[0]], bind_pos[hips[0]])]
        shift = [w - p for w, p in zip(want, P[hips[1]])]
        t = [v + d for v, d in zip(sample[top][6:9], _apply(_tr(R[rig[top][1]]), shift))]
        sample[top][6:9] = [int(round(v)) for v in t]
        root = pose[0]
        sample[0] = list(rest[0][0:3]) + [int(v) for v in root[3:6]] + [int(round(v)) for v in root[6:9]]
        out.append(sample)
    return out


def apply(output, ctx, slots, keep_events=(), repairs=None, ticks=None):
    """`output` (the bound model) with each slot of `slots` playing the source's clip on the donor rig
    -> (bytes, proof). `keep_events`: slots that keep the bound clip's sound events (at its ticks: the clip keeps the
    slot's length), for a source whose clip of that slot has none. `repairs`: {slot (text): operations} of
    tools/models/clip_repair.py run on a slot's retargeted ticks (a rebuilt clip: the original repaired where it breaks
    on the donor rig). `ticks`: {slot (text): frames} gives a one-shot slot (hit, victory, faint, get up, technique)
    another length than the donor's, for a source clip that the donor's length would resample too far (slow motion or
    a rush); the donor's events of that slot move with the clip (scaled to the new length)."""
    rig = ctx['rig']
    nb = len(rig)
    model = mmd.MMD.parse(output, nb)
    source, ns = ctx['source'], len(ctx['skeleton'])
    proof = {}
    for slot in sorted(slots):
        if model.anims.table[slot] is None or source.anims.table[slot] is None:
            raise ValueError(f'battle originals: slot {slot} is missing')
        donor, _, donor_events = animsheet.slot_frames(model, nb, slot)
        want = len(donor)
        if ticks and str(slot) in ticks:
            if slot in IDLES or slot in MOVES:
                raise ValueError(f'battle originals: slot {slot} keeps battle_restore\'s length rule')
            want = int(ticks[str(slot)])
            donor_events = scaled_events(donor_events, len(donor), want)
        frames, events, loop, tile = source_clip(source, ns, slot, want)
        if slot >= TECHNIQUES or slot in keep_events:
            events = donor_events       # the species' voice and the swing sounds at the donor's ticks (scaled with the clip)
        else:                           # the common effects and the species' own voice; not the partner's care voice
            events = [e for e in events if e[1] == 'sound' and e[2]['bank'] in (1, 4)]
        samples = retarget(frames, ctx)
        if repairs and str(slot) in repairs:
            samples = clip_repair.apply_ops(samples, [p for _, p in rig], repairs[str(slot)])
        anim = mmd.encode_anim(samples, nb, 0 if loop == 0 else None, events, tol=ctx.get('tol', 1), repeats=tile > 1)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(anim)
        proof[slot] = dict(frames=len(samples), donor_frames=want, cycles=tile)
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build(), proof


def compact(output, nb, spec):
    """Room in the resident buffer for the restored clips (the recipe's `battle_originals.compact`): every resident
    clip encoded again exactly where that is smaller (battle_restore.compact, tolerance 0), then, with `tol` (at most
    MAX_TOL), the clips that are neither field (0-4) nor battle (0x21-0x24) slots re-encoded within that many units;
    identical streams shared and unread stream tails dropped. -> (bytes, {slot: [old, new bytes]})"""
    tol = int(spec.get('tol', 0))
    if not 0 <= tol <= MAX_TOL:
        raise ValueError(f'battle originals: compaction tolerance {tol} is over {MAX_TOL}')
    output, report = battle_restore.compact(output, nb, 0)
    if tol:
        model = mmd.MMD.parse(output, nb)
        loose = set(range(len(model.anims.table))) - set(FIELD) - set(BATTLE)
        output, more = battle_restore.compact(output, nb, tol, loose)
        report.update(more)
    model = mmd.MMD.parse(output, nb)
    for animation in model.anims.anims:
        animation.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build(), {str(k): list(v) for k, v in sorted(report.items())}


def context(mesh, skeleton, source_pose, yaw, rig, rest, pieces, leads, mapping, lows, fixed=()):
    """The retargeting context of a binding: the source model and its bind pose, the generated rig and its rest pose
    (slot 0's first tick of the bound model before any pass), {donor or rider bone: [(source bone, fitting rotation,
    weight)]}, {rider bone: its pivot piece}, the source-to-donor bone map and `lows`, the lowest vertex (y down) of the
    source in its bind pose and of the fitted pieces: the body joint travels by the ratio of the two hip heights over
    them. `fixed`: source pieces the recipe set whole in a reviewed orientation on another bone (a piece rule's `aim`,
    shoulder armour moved from a swinging upper arm onto the chest); they ride their bone and never lead it."""
    bind_rot, bind_pos = world(skeleton, source_pose, yaw)
    rest = [list(v) for v in rest]
    rest[0] = [4096]*3 + [0]*6
    rest_rot, rest_pos = world([(o, p) for o, p in rig], rest)
    # each piece's constant: R_T(t) = Ws(S, t) . Wbind(S)^T . Q^T . R_T(rest)
    table = {}
    for t, rows in pieces.items():
        # the bone follows its lead piece: the rider's pivot, else the pieces at the top of the group (a piece whose
        # parent is on the same bone rides along rigidly; sibling tops are averaged)
        group = {s for s, _, _ in rows}
        tops = [leads[t]] if t in leads else lead_tops(group, skeleton, fixed)
        table[t] = [(s, _mul(_mul(_tr(bind_rot[s]), _tr(q)), rest_rot[t]), w) for s, q, w in rows if s in tops]
    depth = lambda b, sk: 0 if sk[b][1] < 0 else 1 + depth(sk[b][1], sk)
    hips_source = min(mapping, key=lambda s: (depth(s, skeleton), s))
    hips_target = next(t for t, rows in pieces.items() if any(s == hips_source for s, _, _ in rows))
    k = (lows[1] - rest_pos[hips_target][1]) / (lows[0] - bind_pos[hips_source][1])
    top = hips_target
    while rig[top][1] > 0:
        top = rig[top][1]
    # bones above the body that carry nothing and lead to pieces turn with the source's body
    carried = set(pieces)
    lifted = set()
    for b in range(1, len(rig)):
        chain, a = [], b
        while a > 0:
            chain.append(a)
            a = rig[a][1]
        if b not in carried and not any(c in carried for c in chain[1:]) and any(
                d in carried for d in range(len(rig)) if b in _ancestors(rig, d)):
            lifted.add(b)
    return dict(source=mesh, skeleton=skeleton, yaw=yaw, rig=rig, rest=rest, rest_rot=rest_rot, rest_pos=rest_pos,
                pieces=table, bind_rot=bind_rot, bind_pos=bind_pos, hips=(hips_source, hips_target), top=top,
                lifted=lifted, k=k)


def fixed_pieces(recipe):
    """The source pieces a binding recipe sets whole in a reviewed orientation (a piece rule's `aim`), and their
    mirrors (`mirror`: a piece placed as the reflection of its twin), and the pieces `battle_originals.ride` lists: a
    piece that shares a donor bone with a larger one but moves on its own in the source (a small spinning quad inside a
    body) rides that bone and does not pull its turn."""
    aimed = {int(k) for k, rule in recipe.get('pieces', {}).items() if 'aim' in rule}
    ride = {int(b) for b in recipe.get('battle_originals', {}).get('ride', [])}
    return aimed | {int(k) for k, twin in recipe.get('mirror', {}).items() if int(twin) in aimed} | ride


def lead_tops(group, skeleton, fixed=()):
    """The pieces a bone carrying the source pieces `group` follows: those at the top of the group (a piece whose
    parent is on the same bone rides along rigidly), not counting the `fixed` ones unless nothing else is left."""
    tops = [s for s in group if skeleton[s][1] not in group]
    return [s for s in tops if s not in fixed] or tops


def _ancestors(rig, b):
    out = set()
    while rig[b][1] >= 0:
        b = rig[b][1]
        out.add(b)
    return out
