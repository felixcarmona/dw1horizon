"""Carry our edits of an imported model onto the same import made from another release of its source disc.

An imported model is  importer output (the source, S) + our edit (the target, T). When another release of the source
game gives another importer output for the same recipe (S'), the edit is carried part by part:

- a TMD object or an animation slot we did not edit (S == T there) is taken from S': the other release's own data;
- a part we edited where both releases agree (S == S') keeps our edit;
- a part we edited where the releases differ is carried by its geometry (`carry_object`): every vertex we moved is
  found in S' at the same position and moved the same way, every face we changed is found in S' by its corners
  (position and texture coordinates, in order) and replaced by our face on S' indices. Anything that cannot be found
  exactly once stops the carry: nothing is guessed.

carry(S, T, S') with S' == S gives T back byte for byte (the layout is rebuilt in the same order), the check
`selftest` runs. Standard library only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import mmd  # noqa: E402


class CarryError(ValueError):
    pass


def parse(data, nbones):
    return mmd.MMD.parse(data, nbones)


def _obj(m, i):
    o = m.tmd.objects[i]
    return (o, [p.raw for p in o.prims], list(m.tmd.verts[o.vert_start:o.vert_start + o.nvert]),
            list(m.tmd.norms[o.norm_start:o.norm_start + o.nnorm]))


def _same_obj(a, i, b):
    oa, pa, va, na = _obj(a, i)
    ob, pb, vb, nb = _obj(b, i)
    return pa == pb and va == vb and na == nb and oa.scale == ob.scale


def _corners(d, verts):
    return tuple((tuple(verts[k][:3]), uv) for k, uv in zip(d['verts'], d['uv'] or [None] * len(d['verts'])))


def _face_key(p, verts):
    d = p.decode()
    return (d['mode'], d['flag'], d['cba'], d['tsb'], _corners(d, verts))


def carry_object(S, T, U, i, log):
    """Our edit of object i (S -> T) on U's object i -> (prims, verts, norms) for U."""
    oS, pS, vS, nS = _obj(S, i)
    oT, pT, vT, nT = _obj(T, i)
    oU, pU, vU, nU = _obj(U, i)
    if len(pS) != len(pT) or len(vS) != len(vT) or nS != nT or oS.scale != oT.scale:
        raise CarryError(f'object {i}: the edit adds or removes faces, vertices or normals')
    at = {}
    for k, v in enumerate(vU):
        at.setdefault(tuple(v[:3]), []).append(k)

    def u_vertex(k):
        hit = at.get(tuple(vS[k][:3]), [])
        if len(hit) != 1:
            raise CarryError(f'object {i}: vertex {k} {vS[k][:3]} is found {len(hit)} times on the other release')
        return hit[0]

    def u_normal(n):
        hit = [j for j, x in enumerate(nU) if x == nS[n]]
        if not hit:
            raise CarryError(f'object {i}: normal {n} {nS[n]} is not on the other release')
        return hit[0]

    verts = list(vU)
    moved = 0
    for k, (a, b) in enumerate(zip(vS, vT)):
        if a != b:
            verts[u_vertex(k)] = b
            moved += 1
    faces = {}
    for j, p in enumerate(oU.prims):
        faces.setdefault(_face_key(p, vU), []).append(j)
    own = {}
    for j, p in enumerate(oS.prims):
        own.setdefault(_face_key(p, vS), []).append(j)
    prims = list(oU.prims)
    changed = 0
    for j, (a, b) in enumerate(zip(pS, pT)):
        if a == b:
            continue
        key = _face_key(oS.prims[j], vS)
        if len(own[key]) != 1 or len(faces.get(key, [])) != 1:
            raise CarryError(f'object {i}: face {j} is found {len(faces.get(key, []))} times on the other release '
                             f'({len(own[key])} on its own)')
        ds, du, d = oS.prims[j].decode(), oU.prims[faces[key][0]].decode(), oT.prims[j].decode()
        # (corner c of our face is corner c of the other release's: same position and texture coordinates)
        corner = [ds['verts'].index(k) if k in ds['verts'] else None for k in d['verts']]
        d['verts'] = [du['verts'][c] if c is not None else u_vertex(k) for k, c in zip(d['verts'], corner)]
        if len(d['norms']) == len(corner):         # (Gouraud: a normal per corner, it follows its vertex)
            d['norms'] = [du['norms'][c] if c is not None and n == ds['norms'][c] else u_normal(n)
                          for n, c in zip(d['norms'], corner)]
        else:
            d['norms'] = [du['norms'][q] if q < len(ds['norms']) and n == ds['norms'][q] else u_normal(n)
                          for q, n in enumerate(d['norms'])]
        prims[faces[key][0]] = mmd.Prim.encode(d)
        changed += 1
    log(f'  object {i}: our edit carried by geometry ({moved} vertices moved, {changed} faces changed)')
    return prims, verts, list(nU)


def carry(s, t, u, nbones, log=lambda *a: None):
    """The bytes of our edit (s -> t) carried onto u (all three MMD files of one species) -> (bytes, report)."""
    S, T, U = parse(s, nbones), parse(t, nbones), parse(u, nbones)
    n = len(T.tmd.objects)
    if len(S.tmd.objects) != n or len(U.tmd.objects) != n:
        raise CarryError('the object counts differ')
    report = dict(objects_other=[], objects_ours=[], objects_carried=[], slots_other=[], slots_ours=[])
    out = mmd.MMD()
    out.tmd = mmd.TMD()
    out.tmd.id, out.tmd.flags = T.tmd.id, T.tmd.flags
    for i in range(n):
        if _same_obj(S, i, T):                         # not edited: the other release's object
            src_obj = U.tmd.objects[i]
            prims, (_, _, verts, norms) = list(src_obj.prims), _obj(U, i)
            if not _same_obj(S, i, U):
                report['objects_other'].append(i)
        elif _same_obj(S, i, U):                       # edited, the releases agree: our object
            src_obj = T.tmd.objects[i]
            prims, (_, _, verts, norms) = list(src_obj.prims), _obj(T, i)
            report['objects_ours'].append(i)
        else:
            src_obj = U.tmd.objects[i]
            prims, verts, norms = carry_object(S, T, U, i, log)
            report['objects_carried'].append(i)
        ob = mmd.TMDObject()
        ob.prims = prims
        ob.vert_start, ob.nvert = len(out.tmd.verts), len(verts)
        ob.norm_start, ob.nnorm = len(out.tmd.norms), len(norms)
        ob.scale = src_obj.scale
        out.tmd.verts += verts
        out.tmd.norms += norms
        out.tmd.objects.append(ob)
    # animations: T's table and order; each animation from U when we did not edit it
    sect = mmd.AnimSection()
    sect.table = list(T.anims.table)
    sect.anims = []

    def slot(m, k):
        a = m.anims.table[k] if k < len(m.anims.table) else None
        return None if a is None else m.anims.anims[a].build()

    users = {}
    for k, a in enumerate(T.anims.table):
        if a is not None:
            users.setdefault(a, []).append(k)
    for a, anim in enumerate(T.anims.anims):
        slots = users.get(a, [])
        mine = anim.build()
        # the source slot this animation is (our edit may have pointed more slots at it): the first of its own
        # slots where the source has it, else any source slot that has it
        same = [k for k in slots if slot(S, k) == mine] or \
               [k for k in range(len(S.anims.table)) if slot(S, k) == mine]
        if not slots:
            sect.anims.append(anim)                       # (an unreferenced stream T keeps)
        elif same:
            k = same[0]
            if slot(U, k) is None:
                raise CarryError(f'slot {k}: an animation of ours that the other release does not have')
            sect.anims.append(U.anims.anims[U.anims.table[k]])
            if slot(U, k) != slot(S, k):
                report['slots_other'] += slots
        else:
            differ = [k for k in slots if slot(S, k) != slot(U, k)]
            if differ:
                raise CarryError(f'slots {differ}: we edited them and the releases differ there')
            sect.anims.append(anim)
            report['slots_ours'] += slots
    out.anims = sect
    data = out.build()
    return data, report


def selftest(s, t, nbones):
    """carry(S, T, S) must be T."""
    got, _ = carry(s, t, s, nbones)
    if got != t:
        raise CarryError('carrying onto the same source does not give the target back')
