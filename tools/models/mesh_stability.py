"""Budget-neutral final import pass: independently cull the worst bent quads.

No vertex, normal, UV, palette, skeleton or decoded animation changes. Splitting
uses the GPU's original diagonal. Only lossless resident animation compaction
and final-stage unused/duplicate pool entries may pay for the extra primitives;
remaining bent quads are reported, never removed or flattened to meet a budget.
The original pools must remain available to the earlier grounding/rig passes.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import mmd

DEGREES = 3.0
MAX_PACKET_GROWTH = 1024
PINS = Path(__file__).resolve().parents[1] / 'derive/recipes/species-pins.json'


def apply_provider(data, skeleton):
    """Preserve already pinned alternate-release outputs until independently
    verified/repinned. This uses the existing release pins, never species rules.
    The developer apply() entry point remains available to audit those inputs."""
    digest = hashlib.sha1(data).hexdigest()
    pins = json.loads(PINS.read_text())
    for provider, rows in pins.items():
        if provider.startswith('imports@') and any(pair[0] == digest for pair in rows.values()):
            return data, dict(applied=False, source_variant=provider, deferred=True)
    return apply(data, skeleton)


def split_quad(prim):
    """Keep both original GPU triangles, including every per-corner attribute."""
    d = prim.decode()
    if len(d['verts']) != 4:
        raise ValueError('expected quad')
    result = []
    for corners in ((0, 1, 2), (1, 3, 2)):
        p = copy.deepcopy(d)
        p['mode'] &= ~8
        p['olen'] = mmd.OLEN[p['mode']]
        for key in ('verts', 'uv', 'norms', 'colors'):
            if len(d[key]) == 4:
                p[key] = [d[key][k] for k in corners]
        if p['colors']:
            p['colors'][0] = (*p['colors'][0][:3], p['mode'])
        p['uvpad'], p['pad'] = [0], []
        result.append(mmd.Prim.encode(p))
    return result


def _normal(a, b, c):
    u = [b[k]-a[k] for k in range(3)]; v = [c[k]-a[k] for k in range(3)]
    return (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])


def bent_quads(model, degrees=DEGREES):
    rows = []
    for oi, ob in enumerate(model.tmd.objects):
        v = model.tmd.obj_verts(oi)
        for pi, p in enumerate(ob.prims):
            ids = p.decode()['verts']
            if len(ids) != 4:
                continue
            a,b,c,d = [v[i] for i in ids]
            n = _normal(a,b,c); q = _normal(b,d,c)
            l = math.sqrt(sum(x*x for x in n)); r = math.sqrt(sum(x*x for x in q))
            # A repeated corner is commonly a triangle in a quad packet. It
            # has no second surface to flicker and needs a different audit.
            if min(l,r) < 1e-8:
                continue
            cosine = max(-1, min(1, sum(x*y for x,y in zip(n,q))/(l*r)))
            angle = math.degrees(math.acos(cosine))
            if angle > degrees:
                # Smaller half's area times angular disagreement: a large
                # visible surface that can be wrongly culled is fixed first.
                rows.append(dict(object=oi, primitive=pi, degrees=angle,
                                 risk=min(l,r)*(1-cosine)/2))
    return sorted(rows, key=lambda r:(-r['risk'], r['object'], r['primitive']))


def flatten_identical_shading(model):
    """Gouraud with identical corner normals/colors is exactly flat shading.
    Keep all state and the format's required color/normal entries; only the
    redundant representation and GPU interpolation are removed."""
    count = 0
    for oi, ob in enumerate(model.tmd.objects):
        normals = model.tmd.obj_norms(oi)
        for pi, prim in enumerate(ob.prims):
            d = prim.decode()
            if not d['mode'] & 16:
                continue
            if len({tuple(normals[i]) for i in d['norms']}) > 1:
                continue
            if len({tuple(c[:3]) for c in d['colors']}) > 1:
                continue
            d['mode'] &= ~16
            d['olen'] = mmd.OLEN[d['mode']]
            _, _, ncolor, nnormal = mmd.prim_shape(d['mode'], d['flag'])
            d['norms'] = d['norms'][:nnormal]
            d['colors'] = d['colors'][:ncolor]
            if d['colors']:
                d['colors'][0] = (*d['colors'][0][:3], d['mode'])
            d['pad'], d['uvpad'] = [], []
            ob.prims[pi] = mmd.Prim.encode(d)
            count += 1
    return count


def packet_bytes(model):
    return sum((p.olen+1)*4 for ob in model.tmd.objects for p in ob.prims)


def compact_pools(model):
    """Lossless final-only compaction; primitive order and values stay exact."""
    t = model.tmd
    vertices, normals = [], []
    for oi, ob in enumerate(t.objects):
        vv, nn = t.obj_verts(oi), t.obj_norms(oi)
        vm, nm, vlookup, nlookup = {}, {}, {}, {}
        newv, newn, prims = [], [], []
        for prim in ob.prims:
            d = prim.decode()
            for key, pool, mapping, lookup, target in (
                    ('verts', vv, vm, vlookup, newv), ('norms', nn, nm, nlookup, newn)):
                for index in d[key]:
                    value = tuple(pool[index])
                    if value not in lookup:
                        lookup[value] = len(target); target.append(value)
                    mapping[index] = lookup[value]
                d[key] = [mapping[i] for i in d[key]]
            prims.append(mmd.Prim.encode(d))
        ob.vert_start, ob.nvert = len(vertices), len(newv)
        ob.norm_start, ob.nnorm = len(normals), len(newn)
        ob.prims = prims
        vertices.extend(newv); normals.extend(newn)
    t.verts, t.norms = vertices, normals


def apply(data, skeleton, packet_growth=MAX_PACKET_GROWTH):
    """Return unchanged input if no safe repair fits. Resident bytes never grow.
    The sum of all primitives' packet-format sizes is bounded separately.
    This is not a bound on per-frame growth: culling can expose a previously
    absent half. No render buffer is resized; runtime profiling is still needed."""
    import coldsplit
    from tools.models import battle_restore
    nb = len(skeleton)
    original = mmd.MMD.parse(data, nb)
    bent = bent_quads(original)
    if not bent:
        return data, dict(applied=False, split=0, remaining=0)
    resident_before = len(coldsplit.split(data, nb)[0])
    compact, clips = battle_restore.compact(data, nb, 0)
    result = mmd.MMD.parse(compact, nb)
    flattened = flatten_identical_shading(result)
    packet_saved = packet_bytes(original) - packet_bytes(result)
    compact_pools(result)
    compact = result.build()
    resident_compact = len(coldsplit.split(compact, nb)[0])
    allowance = resident_before - resident_compact
    # Pool compaction changes corner indices, never object/primitive indices.
    used, packets, selected = 0, 0, {}
    for row in bent:
        oi, pi = row['object'], row['primitive']
        prim = result.tmd.objects[oi].prims[pi]
        triangles = split_quad(prim)
        cost = sum(len(p.raw) for p in triangles) - len(prim.raw)
        emitted = sum((p.decode()['olen']+1)*4 for p in triangles) - (prim.decode()['olen']+1)*4
        if used+cost <= allowance and packets+emitted-packet_saved <= packet_growth:
            selected[oi,pi] = triangles
            used += cost; packets += emitted
    if not selected:
        return data, dict(applied=False, split=0, remaining=len(bent), resident_before=resident_before,
                          available_bytes=max(0, allowance))
    for oi, ob in enumerate(result.tmd.objects):
        ob.prims = [p for pi, prim in enumerate(ob.prims) for p in selected.get((oi,pi), [prim])]
    output = result.build()
    resident_after = len(coldsplit.split(output, nb)[0])
    if resident_after > resident_before:
        raise ValueError('mesh stability pass grew resident data')
    return output, dict(applied=True, split=len(selected), remaining=len(bent)-len(selected),
                        risk_before=sum(r['risk'] for r in bent),
                        risk_after=sum(r['risk'] for r in bent if (r['object'],r['primitive']) not in selected),
                        resident_before=resident_before, resident_after=resident_after,
                        packet_growth=packets-packet_saved, flat_shading=flattened, compacted_clips=clips)
