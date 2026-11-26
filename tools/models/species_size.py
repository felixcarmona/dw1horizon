"""Partner sizes: per-bone proportions and one uniform size, baked after the field overlay.

content/models/imports/sizes.json names, per imported species, an optional
`bones` map (bone -> factor) and a uniform `factor`. A bone factor scales the
bone's whole subtree, like a pose scale would: its vertices and the offsets of
its descendants in every animation (battle and field), so a child that should
keep its size takes the inverse factor. Lowered or raised feet are put back on
the ground in every clip. The uniform factor is then baked with the field
cycles retimed to keep their follow pace (tools/models/resize.py).

The species record follows the model: height, radius, the condition bubble and
the effect points attached to a bone.
"""
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)
import mmd
import sizes as sizes_tools
from tools.models import resize as resize_tools

MANIFEST = os.path.join(ROOT, 'content/models/imports/sizes.json')


def rows():
    import json
    with open(MANIFEST) as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith('_')}


def variant_row(row, release):
    """Row `row` as it applies to source release `release` (its `variants` entry, e.g. another factor
    for another release's model), or the row itself."""
    over = row.get('variants', {}).get(release) if release else None
    return {**row, **over} if over else row


def _translation(a):
    return (6, 7, 8) if a.has_scale else (3, 4, 5)


def _clamp(v, what):
    v = int(round(v))
    if not -32768 <= v <= 32767:
        raise ValueError(f'{what} leaves signed 16-bit storage')
    return v


def cumulative(skeleton, bones):
    """Each bone's scale: the product of its own factor and every ancestor's."""
    out = []
    for b, (_, parent) in enumerate(skeleton):
        k = float(bones.get(b, 1.0))
        out.append(k * (out[parent] if 0 <= parent < b else 1.0))
    return out


def _ground(model, skeleton):
    pts = sizes_tools.posed_points(model, skeleton)
    return max(p[1] for p in pts)


def bake_bones(data, skeleton, bones):
    """Scale each listed bone's subtree (bone -> factor) in mesh and every animation; keep the idle on the ground."""
    nb = len(skeleton)
    model = mmd.MMD.parse(data, nb)
    ground = _ground(model, skeleton)
    cum = cumulative(skeleton, bones)
    tmd = model.tmd
    for b, (o, _) in enumerate(skeleton):
        if o < 0 or cum[b] == 1.0:
            continue
        ob = tmd.objects[o]
        for i in range(ob.vert_start, ob.vert_start + ob.nvert):
            x, y, z, p = tmd.verts[i]
            tmd.verts[i] = (_clamp(x * cum[b], 'vertex'), _clamp(y * cum[b], 'vertex'), _clamp(z * cum[b], 'vertex'), p)
    parent_scale = [cum[parent] if parent >= 0 else 1.0 for _, parent in skeleton]
    for a in model.anims.anims:
        ti = _translation(a)
        for c in range(1, nb):
            if parent_scale[c] != 1.0:
                v = a.pose[c - 1]
                for j in ti:
                    v[j] = _clamp(v[j] * parent_scale[c], 'pose offset')
        for ins in a.instrs:
            if ins['op'] != 'key':
                continue
            for block in ins['bones']:
                c = block['bone']
                if c < nb and parent_scale[c] != 1.0:
                    for ch in ('tx', 'ty', 'tz'):
                        if ch in block['vals']:
                            block['vals'][ch] = _clamp(block['vals'][ch] * parent_scale[c], 'key offset')
    lift = round(ground - _ground(model, skeleton))
    if lift:
        carriers = [c for c in range(1, nb) if skeleton[c][1] == 0]
        for a in model.anims.anims:
            ti = _translation(a)
            for c in carriers:
                a.pose[c - 1][ti[1]] = _clamp(a.pose[c - 1][ti[1]] + lift, 'grounded pose')
    return model.build(), cum, lift


def apply(data, skeleton, sid, row):
    """(model, proof): the bone proportions and uniform factor of manifest row `row` baked into model `data`."""
    nb = len(skeleton)
    mmd.exe().add_type(int(sid), skeleton)
    before = sizes_tools.extent(sizes_tools.posed_points(mmd.MMD.parse(data, nb), skeleton))
    bones = {int(b): float(k) for b, k in row.get('bones', {}).items()}
    cum, lift = [1.0] * nb, 0
    if bones:
        data, cum, lift = bake_bones(data, skeleton, bones)
    factor = float(row['factor'])
    paced = True
    if factor != 1.0:
        try:
            data = resize_tools.resize_with_pace(data, skeleton, int(sid), factor)
        except ValueError as why:
            # an incomplete field cycle, or retimed cycles that no longer fit the partner buffer
            if 'repeating field cycle' not in str(why) and 'storage budget' not in str(why):
                raise
            paced = False
            data = resize_tools.resize(data, nb, factor)
    after = sizes_tools.extent(sizes_tools.posed_points(mmd.MMD.parse(data, nb), skeleton))
    proof = dict(applied=True, factor=factor, bones={str(b): k for b, k in sorted(bones.items())},
                 paced=paced, ground_lift=lift, height_before=round(before[0]), height_after=round(after[0]),
                 point_scale=[round(c * factor, 6) for c in cum])
    return data, proof


def patch_record(s, proof):
    """Scale the record's model size and bone-attached points like the model."""
    s = copy.deepcopy(s)
    k = proof['factor']
    scale = proof['point_scale']
    m = s['model']
    if 'height' in m:
        m['height'] = round(m['height'] * proof['height_after'] / max(1, proof['height_before']))
    if 'radius' in m:
        m['radius'] = round(m['radius'] * k)

    def point(xyz, bone):
        f = scale[bone] if isinstance(bone, int) and 0 <= bone < len(scale) else k
        return [round(c * f) for c in xyz]

    if s.get('condition_bubble'):
        b = s['condition_bubble']
        s['condition_bubble'] = point(b[:3], b[3]) + [b[3]]
    if s.get('effect_origins'):
        out = []
        for e in s['effect_origins']:
            e = list(e)
            if isinstance(e[4], int):
                e[5:8] = point(e[5:8], e[4])
            out.append(e)
        s['effect_origins'] = out
    if s.get('effect_origin_fallback'):
        e = list(s['effect_origin_fallback'])
        if isinstance(e[0], int):
            e[1:4] = point(e[1:4], e[0])
        s['effect_origin_fallback'] = e
    return s
