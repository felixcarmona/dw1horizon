"""Close Cherrymon's mesh: the faces JURE.MMD never had because the game only showed the NPC from the front.

JURE's trunk (object 0) is a shell open at the back: the face, the left flank and the top, nothing behind or on
the right flank behind the arms. Its six branch prongs, four root spikes and the 24 leaf cards of the three canopy layers are one
sided, so from behind (and the canopy from below) they vanish: back faces are culled (libgs' GsTMDfast routines
skip a face whose screen winding is reversed and ignore the TMD double-sided flag).

`close(tmd)` adds, in JURE's own coordinates (before the partner scale):

  - the right flank: the left flank's eight faces mirrored (x -> -x, winding reversed, the same bark UVs), joined
    to the right flank's front edge by one triangle; two of the mirrored corners are existing right-flank vertices;
  - the sides the two back branches lack where they leave the top of the trunk, and the floor of the fork;
  - the back: from the left flank's back edge to the mirrored one through a centre line that bulges out like the
    front does, textured with the bark of the trunk's flanks (texture regions the flanks already use);
  - the other side of the prongs, the root spikes at the foot and the leaf cards: each face again with reversed
    winding and its own flat normal.

Every new face is skinned to the bone of the piece it closes (the trunk, a canopy layer), its texture is the
model's own (the CLUT row and page of the faces next to it), and no new vertex leaves the trunk's hull, so the
radius and height do not change.
"""

FLANK = (59, 61, 26, 25, 27, 28, 40, 41)        # the left flank behind the arms (trunk prims)
PRONGS = range(3, 17)                            # the six prongs' faces (trunk prims)
ROOTS = (27, 28, 40, 41, 42, 43, 44, 45)         # the four root spikes at the trunk's foot (trunk prims)
CANOPY = (1, 2, 3)                               # the leaf layers (objects)
# Mirrored left-flank corners that already exist on the right: the top cap's back corner and the flank's middle,
# and the trunk's front-right foot instead of the mirror of the left one.
MIRROR_EXISTING = {1: 54, 10: 11, 13: 14, 0: 4}
# The back's centre line: the bulge at the arms and the foot (its top is the top cap's back edge 1-54).
CENTRE = {'mid': (0, -42, 140), 'foot': (0, 164, 118)}
# bark of the flanks (texture rows 0-95): the left flank's strip for the upper back, the right one's for the lower
BARK_UPPER = ((148, 4), (163, 4), (147, 46), (164, 46))
BARK_LOWER = ((235, 4), (248, 4), (235, 54), (248, 54))

TRI_G, QUAD_G, TRI_F, QUAD_F = 0x34, 0x3C, 0x24, 0x2C    # textured Gouraud / flat, lit


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(v, n=4096):
    ln = _dot(v, v) ** 0.5 or 1
    return (round(v[0] / ln * n), round(v[1] / ln * n), round(v[2] / ln * n), 0)


def _corners(k):
    """The triangles of a primitive with k corners (a TMD quad is 0 1 2 and 1 3 2)."""
    return [(0, 1, 2)] + ([(1, 3, 2)] if k == 4 else [])


def _reverse(k):
    """The corner order that turns a primitive over and keeps its triangles (a quad keeps its 1-2 diagonal)."""
    return (0, 2, 1) if k == 3 else (0, 2, 1, 3)


def _face_normal(P):
    """The outward normal (not normalised) of a face that is visible from outside: DW1 stores normals opposite to
    cross(v1 - v0, v2 - v0)."""
    n = (0, 0, 0)
    for a, b, c in _corners(len(P)):
        x = _cross(_sub(P[b], P[a]), _sub(P[c], P[a]))
        n = (n[0] - x[0], n[1] - x[1], n[2] - x[2])
    return n


class _Object:
    """One TMD object being extended: its vertices, normals and primitives (indices local to the object)."""

    def __init__(self, tmd, oi):
        import mmd
        self.mmd = mmd
        ob = tmd.objects[oi]
        self.ob = ob
        self.verts = list(tmd.verts[ob.vert_start:ob.vert_start + ob.nvert])
        self.norms = list(tmd.norms[ob.norm_start:ob.norm_start + ob.nnorm])

    def vert(self, p):
        p = tuple(int(round(c)) for c in p[:3]) + (0,)
        if p in self.verts:
            return self.verts.index(p)
        self.verts.append(p)
        return len(self.verts) - 1

    def norm(self, n):
        n = _unit(n)
        if n in self.norms:
            return self.norms.index(n)
        self.norms.append(n)
        return len(self.norms) - 1

    def add(self, mode, vids, uvs, nids, like):
        d = dict(mode=mode, flag=0, uv=list(uvs), cba=like['cba'], tsb=like['tsb'], uvpad=[0, 0][:max(0, len(uvs) - 2)],
                 colors=[], norms=list(nids), verts=list(vids), pad=[])
        self.ob.prims.append(self.mmd.Prim.encode(d))


def _store(tmd, objs):
    """Write the extended objects back: the pools are rebuilt object by object (each object's vertices and normals
    stay one contiguous run, as JURE has them)."""
    verts, norms = [], []
    for oi, ob in enumerate(tmd.objects):
        e = objs.get(oi)
        vs = e.verts if e else tmd.verts[ob.vert_start:ob.vert_start + ob.nvert]
        ns = e.norms if e else tmd.norms[ob.norm_start:ob.norm_start + ob.nnorm]
        ob.vert_start, ob.nvert, ob.norm_start, ob.nnorm = len(verts), len(vs), len(norms), len(ns)
        verts += vs
        norms += ns
    tmd.verts, tmd.norms = verts, norms


def _turned_over(obj, prim):
    """The primitive again, facing the other way, with one flat normal (the reverse of the face's own)."""
    d = prim.decode()
    k = len(d['verts'])
    order = _reverse(k)
    P = [obj.verts[d['verts'][i]] for i in order]
    obj.add(TRI_F if k == 3 else QUAD_F, [d['verts'][i] for i in order], [d['uv'][i] for i in order],
            [obj.norm(_face_normal(P))], d)


def close(tmd):
    """Add the missing faces to JURE's TMD (in place). Returns the number of primitives added."""
    for ob in tmd.objects:
        assert ob.nvert == ob.nnorm and all(max(p.decode()['verts']) < ob.nvert and
                                            max(p.decode()['norms']) < ob.nnorm for p in ob.prims), \
            'JURE.MMD: an object uses vertices or normals outside its own run'
    before = sum(len(ob.prims) for ob in tmd.objects)
    trunk = _Object(tmd, 0)
    prims = list(tmd.objects[0].prims)
    V = trunk.verts
    like = prims[59].decode()                     # bark: CLUT row 0, the model's texture page

    # 1. the right flank: the left one mirrored
    mirror = dict(MIRROR_EXISTING)
    new_faces = []                                # (vertex ids, uvs) of the Gouraud faces still to normal
    for pi in FLANK:
        d = prims[pi].decode()
        k = len(d['verts'])
        ids = []
        for v in d['verts']:
            if v not in mirror:
                x, y, z, _ = V[v]
                mirror[v] = trunk.vert((-x, y, z))
            ids.append(mirror[v])
        order = _reverse(k)
        new_faces.append(([ids[i] for i in order], [d['uv'][i] for i in order]))
    # the triangle between the right flank's front edge (4-14, prim 39) and the mirrored flank (33')
    new_faces.append(([4, 14, mirror[33]], [(176, 71), (191, 37), (177, 38)]))
    # where the two back branches leave the top of the trunk: the right one's outside, the left one's inside, as
    # triangles turned away from the middle of the fork (58 60 61 64), and the fork's floor between them, facing up
    # (the neck bark of prims 53 and 54)
    fork = [sum(V[i][j] for i in (58, 60, 61, 64)) / 4 for j in range(3)]
    for ids, uvs in (([11, 54, 56], [(231, 71), (208, 71), (225, 40)]), ([54, 55, 56], [(208, 71), (215, 40), (225, 40)]),
                     ([1, 58, 53], [(208, 71), (231, 69), (212, 40)]), ([58, 57, 53], [(231, 69), (227, 40), (212, 40)])):
        new_faces.append((ids, uvs, ('from', fork)))
    new_faces.append(([60, 61, 58, 64], [(212, 40), (227, 40), (212, 66), (227, 66)], ('dir', (0, -1, 0))))

    # 2. the back: left back edge 3-7-1, mirrored edge 3'-7'-54 (the top cap's back edge 1-54 kept whole: no
    # T-junction), through the centre line
    mid, foot = trunk.vert(CENTRE['mid']), trunk.vert(CENTRE['foot'])
    l_top, l_mid, l_foot = 1, 7, 3
    r_top, r_mid, r_foot = mirror[1], mirror[7], mirror[3]
    u0, u1, u2, u3 = BARK_UPPER
    w0, w1, w2, w3 = BARK_LOWER
    um = ((u2[0] + u3[0]) // 2, u2[1])           # the centre line's middle, on the strip's lower edge
    new_faces += [([l_top, r_top, mid], [u0, u1, um]),
                  ([l_top, mid, l_mid], [u0, um, u2]),
                  ([r_top, r_mid, mid], [u1, u3, um]),
                  ([l_mid, mid, l_foot, foot], [w0, w1, w2, w3]),
                  ([mid, r_mid, foot, r_foot], [w1, w0, w3, w2])]

    # outward winding (away from the trunk's axis x = 0, z = -20 unless the face says otherwise) and smooth normals
    # over the new faces
    acc = {}
    oriented = []
    for face in new_faces:
        ids, uvs = face[0], face[1]
        P = [V[i] for i in ids]
        c = [sum(p[j] for p in P) / len(P) for j in range(3)]
        how = face[2] if len(face) > 2 else None
        if how is None:
            out = (c[0], 0, c[2] + 20)
        elif how[0] == 'from':
            out = tuple(c[j] - how[1][j] for j in range(3))
        else:
            out = how[1]
        if _dot(_face_normal(P), out) < 0:
            o = _reverse(len(ids))
            ids, uvs = [ids[i] for i in o], [uvs[i] for i in o]
            P = [V[i] for i in ids]
        n = _face_normal(P)
        ln = _dot(n, n) ** 0.5 or 1
        for i in ids:
            a = acc.setdefault(i, [0.0, 0.0, 0.0])
            for j in range(3):
                a[j] += n[j] / ln
        oriented.append((ids, uvs))
    for ids, uvs in oriented:
        trunk.add(TRI_G if len(ids) == 3 else QUAD_G, ids, uvs, [trunk.norm(acc[i]) for i in ids], like)

    # 3. the other side of the prongs and of the root spikes (the left flank's two mirrored ones too)
    flank_new = {pi: len(prims) + k for k, pi in enumerate(FLANK)}
    added = list(trunk.ob.prims)
    for pi in PRONGS:
        _turned_over(trunk, prims[pi])
    for pi in ROOTS:
        _turned_over(trunk, prims[pi])
        if pi in flank_new:
            _turned_over(trunk, added[flank_new[pi]])

    # 4. the leaf cards' other side
    objs = {0: trunk}
    for oi in CANOPY:
        layer = _Object(tmd, oi)
        for p in list(tmd.objects[oi].prims):
            _turned_over(layer, p)
        objs[oi] = layer
    _store(tmd, objs)
    return sum(len(ob.prims) for ob in tmd.objects) - before
