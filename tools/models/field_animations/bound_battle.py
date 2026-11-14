"""The source game's own battle clips on a model bound offline to a native DW1 rig (content/models/imports/bound-battle.json).

A species whose import is a native rig binding made once by a developer tool (MagnaAngemon: tools/models/rig_angemon.py
binds the World 2003 mesh to Angemon's skeleton, the result stored as a plain delta) carries no source motion: its
battle slots would all be the donor's. The imports step makes the same source mesh with the source game's clips in DW1
battle slots (a `native-battle-source-v1` spec, tools/models/native_mesh.py) next to the base model, as
`<id>.battle.MMD`; this overlay plays the recipe's `slots` from it on the bound rig with native_battle.py's retarget:

- the pieces of each bound bone are found by the binding's order (`binding`: the rig spec; its `map` order, each
  mirrored wing piece right after its source on the spec's `wings.left_donor`); their fitting rotations are measured
  from the vertices (least squares, standard library). `mirror`: {source piece: its twin}: a piece the binding made as
  the reflection of its twin, fitted from the twin's vertices mirrored into its own frame;
- `leads`: {bound bone: the source piece it follows} where the bone carries a piece that only rides along (the
  sash on the hips);
- `keep_events`: slots that keep the bound clip's sound events (same length: the hits' impact sounds), where the
  source clip has none;
- `repairs`: {slot: operations} of tools/models/clip_repair.py run on a slot's retargeted ticks (a rebuilt clip).
- `compact_from`: the resident clips of the slots from this one on (battle and techniques) encoded again exactly
  where that is smaller, for room in the resident buffer (field and care slots stay byte for byte).

Every other slot stays byte for byte; the slots listed are the ones that pass tools/models/battle_qa_native.py on the
final model. The base model and the battle source are pinned by SHA-256. Standard library only.
"""
import hashlib
import json
import math
from pathlib import Path

import animsheet
import mmd
import motionstorage
from tools.models.field_animations import native_battle
from tools.models.field_animations.reviewed import reviewed

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / 'content/models/imports/bound-battle.json'
BASE_MODELS = None          # the imported base models folder (content/models/imports/species.py sets it)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rows():
    return json.loads(MANIFEST.read_text())


def recipe_of(data):
    matches = [(sid, r) for sid, r in rows().items() if r['source_sha256'] == reviewed(digest(data))]
    if len(matches) != 1:
        raise ValueError('Bound battle: no unique reviewed source')
    return matches[0]


def battle_path(base, sid):
    return Path(base) / f'{sid}.battle.MMD'


def binding_spec(recipe):
    data = (ROOT / recipe['binding']['spec']).read_bytes()
    if digest(data) != recipe['binding']['sha256']:
        raise ValueError(f'Bound battle: {recipe["binding"]["spec"]}: SHA-256 mismatch')
    return json.loads(data)


def _solve(a, b):
    """x of a.x = b (a n x n, b n x m), Gaussian elimination with partial pivoting."""
    n = len(a)
    m = [list(map(float, a[i])) + list(map(float, b[i])) for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c and m[r][c]:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [[v / m[i][i] for v in m[i][n:]] for i in range(n)]


def affine(x, y):
    """The 3x3 linear part of the least-squares affine map from points x to points y."""
    X = [list(p) + [1.0] for p in x]
    xtx = [[sum(r[i] * r[j] for r in X) for j in range(4)] for i in range(4)]
    xty = [[sum(r[i] * q[j] for r, q in zip(X, y)) for j in range(3)] for i in range(4)]
    sol = _solve(xtx, xty)                     # 4 x 3: rows of the transposed map, then the translation
    return [[sol[j][i] for j in range(3)] for i in range(3)]


def _eigen(s):
    """(eigenvalues, eigenvectors as columns) of a symmetric 3x3 matrix (cyclic Jacobi)."""
    a = [list(map(float, r)) for r in s]
    v = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
    for _ in range(100):
        off = abs(a[0][1]) + abs(a[0][2]) + abs(a[1][2])
        if off < 1e-15 * (abs(a[0][0]) + abs(a[1][1]) + abs(a[2][2]) + 1e-300):
            break
        for p, q in ((0, 1), (0, 2), (1, 2)):
            if a[p][q] == 0:
                continue
            theta = (a[q][q] - a[p][p]) / (2 * a[p][q])
            t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
            c = 1 / math.sqrt(t * t + 1)
            sn = t * c
            for k in range(3):
                akp, akq = a[k][p], a[k][q]
                a[k][p], a[k][q] = c * akp - sn * akq, sn * akp + c * akq
            for k in range(3):
                apk, aqk = a[p][k], a[q][k]
                a[p][k], a[q][k] = c * apk - sn * aqk, sn * apk + c * aqk
            for k in range(3):
                vkp, vkq = v[k][p], v[k][q]
                v[k][p], v[k][q] = c * vkp - sn * vkq, sn * vkp + c * vkq
    return [a[i][i] for i in range(3)], v


def _cross(a, b):
    return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]


def _unit(a):
    n = math.sqrt(sum(x * x for x in a))
    return [x / n for x in a]


def rotation(m):
    """The nearest rotation to a 3x3 matrix, also for a flat piece's map (rank 2) or a reflection: U.V^T of its
    singular value decomposition with the smallest singular direction set so that the result turns (det +1)."""
    ata = [[sum(m[k][i] * m[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    values, vecs = _eigen(ata)
    order = sorted(range(3), key=lambda i: -values[i])
    v1, v2 = ([vecs[k][i] for k in range(3)] for i in order[:2])
    v1 = _unit(v1)
    v2 = _unit([b - sum(x * y for x, y in zip(v1, v2)) * a for a, b in zip(v1, v2)])
    v3 = _cross(v1, v2)
    u1 = _unit([sum(m[i][k] * v1[k] for k in range(3)) for i in range(3)])
    u2 = [sum(m[i][k] * v2[k] for k in range(3)) for i in range(3)]
    u2 = _unit([b - sum(x * y for x, y in zip(u1, u2)) * a for a, b in zip(u1, u2)])
    u3 = _cross(u1, u2)
    return [[u1[i] * v1[j] + u2[i] * v2[j] + u3[i] * v3[j] for j in range(3)] for i in range(3)]


def _inv3(m):
    a, b, c = m
    det = a[0]*(b[1]*c[2]-b[2]*c[1]) - a[1]*(b[0]*c[2]-b[2]*c[0]) + a[2]*(b[0]*c[1]-b[1]*c[0])
    cof = [[b[1]*c[2]-b[2]*c[1], c[1]*a[2]-c[2]*a[1], a[1]*b[2]-a[2]*b[1]],
           [b[2]*c[0]-b[0]*c[2], c[2]*a[0]-c[0]*a[2], a[2]*b[0]-a[0]*b[2]],
           [b[0]*c[1]-b[1]*c[0], c[0]*a[1]-c[1]*a[0], a[0]*b[1]-a[1]*b[0]]]
    return [[v / det for v in row] for row in cof]


def _world(matrix, points):
    return [[sum(matrix[i][j] * p[j] for j in range(3)) + matrix[i][3] for i in range(3)] for p in points]


def _local(matrix, points):
    inv = _inv3([row[:3] for row in matrix[:3]])
    return [[sum(inv[i][j] * (p[j] - matrix[j][3]) for j in range(3)) for i in range(3)] for p in points]


def source_model(data, spec):
    """The battle source parsed on the binding's source rig (registered under the source spec's type)."""
    kind = json.loads((ROOT / spec['mesh']['spec']).read_text())['type']
    mmd.exe().add_type(kind, [list(b) for b in spec['mesh']['skeleton']])
    model = mmd.MMD.parse(data, len(spec['mesh']['skeleton']))
    model.type = kind
    return model


def verts(model, obj):
    return [list(v[:3]) for v in model.tmd.obj_verts(obj)]


def binding(recipe, spec, source, final, rig):
    """(blocks {source piece: (bound bone, first vertex, count)}, fits {source piece: (fitting rotation, weight,
    final local vertices, source local vertices)}, leads {bound bone: [source pieces it follows]}, the source-to-bound
    map, the source's bind pose)."""
    skeleton = [list(b) for b in spec['mesh']['skeleton']]
    mapping = {int(k): v for k, v in spec['map'].items()}
    twin_of = {int(k): int(v) for k, v in recipe.get('mirror', {}).items()}
    mirrored = {v: k for k, v in twin_of.items()}
    used, blocks = {}, {}

    def place(sb, tb):
        n = source.tmd.objects[skeleton[sb][0]].nvert
        start = used.get(tb, 0)
        blocks[sb] = (tb, start, n)
        used[tb] = start + n
    for sb, tb in mapping.items():
        place(sb, tb)
        if sb in mirrored:
            place(mirrored[sb], spec['wings']['left_donor'])
    for tb, n in used.items():
        total = final.tmd.objects[rig[tb][0]].nvert
        if total != n and not (tb in map(int, recipe.get('extra_vertices', [])) and total > n):
            raise ValueError(f'Bound battle: bone {tb}: the pieces do not account for its {total} vertices ({n})')
    bind = animsheet.slot_frames(source, len(skeleton), 0)[0][0]
    bind[0] = [4096] * 3 + [0] * 6
    world = mmd.bone_matrices(source, bind)
    fits = {}
    for sb, (tb, start, n) in blocks.items():
        if sb in twin_of:
            twin = twin_of[sb]
            points = [[-p[0], p[1], p[2]] for p in _world(world[twin], verts(source, skeleton[twin][0]))]
            x = _local(world[sb], points)
        else:
            x = verts(source, skeleton[sb][0])
        y = verts(final, rig[tb][0])[start:start + n]
        mean = [sum(p[i] for p in y) / len(y) for i in range(3)]
        weight = sum((p[i] - mean[i]) ** 2 for p in y for i in range(3)) + 1.0
        fits[sb] = (rotation(affine(x, y)), weight, y, x)
    groups = {}
    for sb, (tb, _, _) in blocks.items():
        groups.setdefault(tb, set()).add(sb)
    pivots = {int(k): v for k, v in recipe.get('leads', {}).items()}
    leads = {tb: [pivots[tb]] if tb in pivots else native_battle.lead_tops(group, skeleton)
             for tb, group in groups.items()}
    full = {**mapping, **{sb: blocks[sb][0] for sb in twin_of}}
    return blocks, fits, leads, full, skeleton, bind


def context(recipe, spec, source, final, rig):
    """native_battle.context of the bound model `final` (parsed, rig `rig`) and the battle source."""
    blocks, fits, leads, full, skeleton, bind = binding(recipe, spec, source, final, rig)
    rest = animsheet.slot_frames(final, len(rig), 0)[0][0]
    rest_rot, _ = native_battle.world([(o, p) for o, p in rig], [[4096] * 3 + [0] * 6] + [list(v) for v in rest[1:]])
    bind_rot, _ = native_battle.world(skeleton, bind)
    pieces = {}
    for sb, (tb, _, _) in blocks.items():
        q, w, _, _ = fits[sb]
        world = native_battle._mul(native_battle._mul(rest_rot[tb], q), native_battle._tr(bind_rot[sb]))
        pieces.setdefault(tb, []).append((sb, world, w))
    # the lowest vertex (y down: the largest y) of the source in its bind pose and of the bound model at rest
    sw = mmd.bone_matrices(source, bind)
    low_source = max(p[1] for sb in spec['map'] for p in _world(sw[int(sb)], verts(source, skeleton[int(sb)][0])))
    fw = mmd.bone_matrices(final, [[4096] * 3 + [0] * 6] + [list(v) for v in rest[1:]])
    low_final = max(p[1] for b, (o, _) in enumerate(rig) if o >= 0 for p in _world(fw[b], verts(final, o)))
    return native_battle.context(source, skeleton, bind, None, [list(b) for b in rig], rest, pieces,
                                 {int(k): v for k, v in recipe.get('leads', {}).items()}, full, (low_source, low_final))


def build(data, skeleton):
    sid, recipe = recipe_of(data)
    if BASE_MODELS is None:
        raise ValueError('Bound battle: the battle source needs BASE_MODELS (the imported base models folder)')
    battle = battle_path(BASE_MODELS, sid).read_bytes()
    if digest(battle) != recipe['battle_source']['sha256']:
        raise ValueError(f'Bound battle: {sid}: battle source SHA-256 mismatch')
    spec = binding_spec(recipe)
    rig = [list(b) for b in skeleton]
    mmd.exe().add_type(int(sid), rig)
    final = mmd.MMD.parse(data, len(rig))
    final.type = int(sid)
    source = source_model(battle, spec)
    ctx = context(recipe, spec, source, final, rig)
    output, proof = native_battle.apply(data, ctx, recipe['slots'], recipe.get('keep_events', ()), recipe.get('repairs'),
                                       recipe.get('ticks'))
    compacted = None
    if 'compact_from' in recipe:
        output, compacted = compact(output, len(rig), recipe['compact_from'])
    storage = motionstorage.require(output, len(rig))
    out = dict(species=int(sid), source_sha256=digest(data), battle_source_sha256=digest(battle),
               output_sha256=digest(output), storage=storage, battle_originals=proof)
    if compacted is not None:
        out['battle_compact'] = compacted
    return output, out


def compact(output, nb, first):
    """Room in the resident buffer: the resident clips of the slots from `first` on (battle and techniques, never a
    field or care slot) encoded again exactly where that is smaller (battle_restore.compact, tolerance 0: the same
    ticks) -> (bytes, {slot: [old, new bytes]})."""
    from tools.models import battle_restore
    if first < native_battle.IDLES[0]:
        raise ValueError(f'Bound battle: compaction from slot {first} would touch field or care slots')
    model = mmd.MMD.parse(output, nb)
    output, report = battle_restore.compact(output, nb, 0, set(range(first, len(model.anims.table))))
    return output, {str(k): list(v) for k, v in sorted(report.items())}
