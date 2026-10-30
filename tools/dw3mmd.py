#!/usr/bin/env python3
"""Digimon World 2003 (PS1, PAL) battle models -> Digimon World MMDs.

DW2003 draws its Digimon like DW1 (rigid one-mesh-per-bone, Y down, 4 bpp texture
with per-face 16-colour palettes) but bigger in every way: ~5x the units, up to 44
bones, ~1000 primitives, 19 palettes in a 256x256 page. The data is read with the
`dw3` package of $DW3_ROOT (docs/dw1-port.md there); the DW1 side
is tools/mmdport.py, shared with tools/dcb2mmd.py. Documented in
docs/mods/models.md, "Importing from Digimon World 2003".

  dw3mmd.py info NAME [--height H]           bones, budgets, palettes, animations of
                                             AAA/DAT/FIGHT/MODEL/NAME.BIN (e.g. M237CHMR)
  dw3mmd.py convert NAME TYPE OUT_DIR [--height H] [--slot anim_NN=SLOT ...]
  dw3mmd.py partner SPEC.json OUT_DIR        a full partner (mmdport.build_partner)
  dw3mmd.py sheet NAME OUT.png [--every 8]   the source animations, rendered here

What the conversion does to fit DW1:
- scale: the whole model (vertices, joints, translations) is scaled to `--height`
  units tall in its first pose (DW1 partners are 150..650);
- palettes: at most 16 CLUT rows; the faces of the palettes over that are moved
  to the palette whose colours at the same pixel indices are closest (the least
  used palettes first), which is exact when the two palettes agree on the indices
  those faces use (`info` prints the error);
- texture: the 256x256 page's CLUTs live in rows 216..248 and its faces use rows up to ~215,
  the DW1 slot is 256x128: the faces below row 127 are moved, island by island, into texels no
  face uses (`repack_page`); when the used texels do not fit, every island is shrunk by a common factor
  (0.9 .. 0.45, nearest texel) until they do;
- triangles: pairs of triangles sharing an edge, with the same palette, both
  normals within --quad-angle degrees and UVs that agree on the shared edge,
  become one quad (36 bytes instead of 2 x 28), as long as the quad is convex;
- normals: a bone's normals within --normal-angle degrees (4) are stored once;
- bones: DW2003 bone i (1-based) -> DW1 bone i, bone 0 = the entity; the rest
  pose is the first frame of the first animation (DW2003 has no other).
Animation timing: the DW2003 export assumes 30 fps (its playback rate was not
measured); `--fps` changes it.

Releases: the recipes (content/imports/specs) are made from the PAL disc. The disc read is $DW3_DISC
(default $DW3_ROOT/disc, the PAL one); its boot file tells the release. Digimon World 3 (USA) keeps
the models in AAA/DAT/MODEL/ and differs in a few of them: tools/dw3release.py patches those into
the PAL files before they are read, so every recipe gives the same Digimon from any release (the
Japanese one has every recipe model as the PAL disc does: no patch, only the checksums).

The bundled player converter uses only the Python standard library.
"""
import argparse
import json
import math
import os
import sys

DW3_ROOT = os.environ.get('DW3_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimonworld2003'))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _dw3():
    sys.path.insert(0, DW3_ROOT)
    import dw3.model, dw3.pose, dw3.texture  # noqa: E401
    import dw3_extra
    dw3_extra.patch()              # rule: the section table's empty slots (Knightmon, Zanbamon, Taomon...) read right
    return dw3


import mmdport  # noqa: E402

MAX_PALETTES = 16


# boot file -> (release, the directory of the battle models)
RELEASES = {'SLES_039.36': ('pal', 'AAA/DAT/FIGHT/MODEL'), 'SLUS_014.36': ('us', 'AAA/DAT/MODEL'),
            'SLPS_034.46': ('jp', 'AAA/DAT/FIGHT/MODEL')}

def disc_dir():
    return os.environ.get('DW3_DISC', os.path.join(DW3_ROOT, 'disc'))


def release():
    """(release, models directory) of the disc in disc_dir(), told by its boot file."""
    cnf = open(os.path.join(disc_dir(), 'SYSTEM.CNF'), encoding='latin-1').read()
    boot = cnf.split('cdrom:')[1].lstrip('\\').split(';')[0].strip().upper()
    if boot not in RELEASES:
        raise SystemExit(f'dw3mmd: {disc_dir()} boots {boot}, not a known Digimon World 2003/3 release')
    return RELEASES[boot]


def model_path(name):
    return os.path.join(disc_dir(), release()[1], f'{name}.BIN')


def read_model(name):
    """The parsed model of `name` from the disc in disc_dir(); another release's file is first patched into the
    PAL one the recipes are made from (tools/dw3release.py)."""
    dw3 = _dw3()
    data = open(model_path(name), 'rb').read()
    rel = release()[0]
    if rel != 'pal':
        import dw3release
        data = dw3release.to_pal(rel, name, data)
    return dw3.model.parse_model(data, name)


def _c15_rgb(c):
    return ((c & 31) * 8, (c >> 5 & 31) * 8, (c >> 10 & 31) * 8)


def merge_palettes(prims_by_pal, pals, idx_of_face, maxp, log=print):
    """Moves the faces of the least used palettes onto the closest other palette until
    `maxp` remain. prims_by_pal: {pal: [prim dicts]}; idx_of_face(prim) -> pixel indices
    under the face. Returns {old pal: new pal}."""
    remap = {p: p for p in pals}
    live = sorted(pals, key=lambda p: len(prims_by_pal.get(p, [])))
    while len(set(remap.values())) > maxp:
        src = next(p for p in live if remap[p] == p)
        used = {}
        for pr in prims_by_pal.get(src, []):
            for i in idx_of_face(pr):
                used[i] = used.get(i, 0) + 1
        best, err = None, None
        for dst in pals:
            if remap[dst] != dst or dst == src:
                continue
            e = 0
            for i, n in used.items():
                a, b = pals[src][i], pals[dst][i]
                if (a == 0) != (b == 0):
                    e += n * 3 * 255 ** 2
                else:
                    e += n * sum((x - y) ** 2 for x, y in zip(_c15_rgb(a), _c15_rgb(b)))
            if best is None or e < err:
                best, err = dst, e
        for k, v in remap.items():
            if v == src:
                remap[k] = best
        npx = sum(used.values()) or 1
        log(f'  palette {src} ({len(prims_by_pal.get(src, []))} faces) -> {best}: '
            f'mean colour error {math.sqrt(err / npx / 3):.1f}/255 per texel')
    return remap


def _face_pixels(p):
    """Texel indices (u, v) a primitive covers (its UV bounding triangle(s), sampled)."""
    out = set()
    uvs = p['uvs']
    tris = [(0, 1, 2)] if len(uvs) == 3 else [(0, 1, 2), (1, 3, 2)]
    for t in tris:
        (u0, v0), (u1, v1), (u2, v2) = (uvs[k] for k in t)
        for a in range(0, 11):
            for b in range(0, 11 - a):
                c = 10 - a - b
                out.add((round((a * u0 + b * u1 + c * u2) / 10), round((a * v0 + b * v1 + c * v2) / 10)))
    return out


def _pack_shrunk(prims, fps, src, f, newuvs, page):
    """repack_page's last resort: every UV island scaled by f (nearest texel, one texel of border) and packed
    again from scratch, largest first. Fills `page` and `newuvs`; False when it does not fit."""
    import numeric as np
    import dw2mmd
    items = []
    for grp in dw2mmd._islands(fps, list(range(len(prims)))):
        X0, Y0, M = dw2mmd._union_mask([fps[i] for i in grp])
        h, w = M.shape
        nh, nw = max(1, math.ceil(h * f)), max(1, math.ceil(w * f))
        sy = np.minimum(h - 1, ((np.arange(nh) + 0.5) / f).astype(int))
        sx = np.minimum(w - 1, ((np.arange(nw) + 0.5) / f).astype(int))
        nm = M[np.ix_(sy, sx)]
        nm = np.pad(nm, 1)
        nm = nm | np.roll(nm, 1, 0) | np.roll(nm, -1, 0) | np.roll(nm, 1, 1) | np.roll(nm, -1, 1)
        nm = nm[1:-1, 1:-1]
        gy = np.clip(Y0 + sy, 0, src.shape[0] - 1)
        gx = np.clip(X0 + sx, 0, src.shape[1] - 1)
        img = src[np.ix_(gy, gx)]
        items.append((grp, (X0, Y0, M), nm, img, nh, nw))
    items.sort(key=lambda it: -it[2].sum())
    occ = np.zeros((128, 256), bool)
    for grp, (X0, Y0, M), nm, img, nh, nw in items:
        if nh > 128 or nw > 256:
            return False
        at = dw2mmd._place(occ, nm)
        if at is None:
            return False
        nx, ny = at
        occ[ny:ny + nh, nx:nx + nw] |= nm
        sub = page[ny:ny + nh, nx:nx + nw]
        sub[nm] = img[nm]
        for i in grp:
            newuvs[i] = [(min(nx + nw - 1, max(nx, nx + int((u - X0) * f))), min(ny + nh - 1, max(ny, ny + int((v - Y0) * f))))
                         for u, v in prims[i]['uvs']]
    return True


def repack_page(prims, pix, log=print):
    """Rule: DW1's slot is 256x128 and a DW2003 page 256x256 (its CLUTs live in rows 216-248, the faces
    use rows up to ~215). Faces whose texels all lie in rows 0..127 stay; the others are grouped into UV
    islands (overlapping texels) and each island is copied into texels no face uses (dw2mmd's
    footprint/island/FFT placement); if that fails every island is packed again from scratch, largest
    first. Edits the prims' 'uvs' in place; returns uint8[128, 256]."""
    import numeric as np
    import dw2mmd
    fps = [dw2mmd.footprint(p['uvs']) for p in prims]
    src = np.asarray(pix)[:, :256].astype(np.uint8)
    crossing = [i for i, (x0, y0, m) in enumerate(fps) if y0 + m.shape[0] > 128]
    log(f'  texture: {len(crossing)} of {len(prims)} faces lie below row 127: moved into free texels')

    def pack(items, occ, page, newuvs):
        for faces, (X0, Y0, M) in items:
            at = dw2mmd._place(occ, M)
            if at is None:
                return False
            nx, ny = at
            occ[ny:ny + M.shape[0], nx:nx + M.shape[1]] |= M
            sub = page[ny:ny + M.shape[0], nx:nx + M.shape[1]]
            sub[M] = src[Y0:Y0 + M.shape[0], X0:X0 + M.shape[1]][M]
            for i in faces:
                newuvs[i] = [(u + nx - X0, v + ny - Y0) for u, v in prims[i]['uvs']]
        return True
    items = []
    for grp in dw2mmd._islands(fps, crossing):
        items.append((grp, dw2mmd._union_mask([fps[i] for i in grp])))
    items.sort(key=lambda it: -it[1][2].sum())
    occ = np.zeros((128, 256), bool)
    page = src[:128].copy()
    newuvs = {}
    for i, (x0, y0, m) in enumerate(fps):
        if i not in set(crossing):
            occ[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] |= m
    if not pack(items, occ, page, newuvs):
        log('  texture: free texels too scattered, every island packed again from scratch')
        items = []
        for grp in dw2mmd._islands(fps, list(range(len(prims)))):
            M = dw2mmd._union_mask([fps[i] for i in grp])
            if M[2].shape[0] > 128:
                items += [([i], fps[i]) for i in grp]
            else:
                items.append((grp, M))
        items.sort(key=lambda it: -it[1][2].sum())
        occ = np.zeros((128, 256), bool)
        page = np.zeros((128, 256), np.uint8)
        newuvs = {}
        if not pack(items, occ, page, newuvs):
            # rule: the used texels exceed the slot (or fragment too much): every island shrinks by a common factor
            # (nearest texel, a 1-texel border), 0.9 down to 0.45, the first that packs
            ok = False
            for f in (0.9, 0.8, 0.7, 0.6, 0.5, 0.45):
                page = np.zeros((128, 256), np.uint8)
                newuvs = {}
                if _pack_shrunk(prims, fps, src, f, newuvs, page):
                    log(f'  texture: used texels exceed the 256x128 slot: every island shrunk to x{f}')
                    ok = True
                    break
            if not ok:
                raise SystemExit('texture does not fit the 256x128 slot even repacked')
        crossing = list(range(len(prims)))
    for i in crossing:
        prims[i]['uvs'] = newuvs[i]
    return page


def merge_quads(bone, max_angle=8.0):
    """Pairs of triangles -> quads (same palette, near-coplanar, UVs agree on the shared
    edge, convex). Returns the number of quads made."""
    tris = [p for p in bone['prims'] if len(p['verts']) == 3]
    others = [p for p in bone['prims'] if len(p['verts']) != 3]
    V = bone['verts']

    def normal(p):
        a, b, c = (V[k] for k in p['verts'])
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        L = math.sqrt(sum(x * x for x in n)) or 1.0
        return [x / L for x in n]
    used = [False] * len(tris)
    made = []
    cos_max = math.cos(math.radians(max_angle))
    norms = [normal(p) for p in tris]
    for i, p in enumerate(tris):
        if used[i]:
            continue
        for j in range(i + 1, len(tris)):
            q = tris[j]
            if used[j] or q['row'] != p['row'] or (p['uvs'] is None) != (q['uvs'] is None) \
                    or (p['norms'] is None) != (q['norms'] is None) or p.get('semi') != q.get('semi'):
                continue
            if sum(a * b for a, b in zip(norms[i], norms[j])) < cos_max:
                continue
            shared = [k for k in range(3) if p['verts'][k] in q['verts']]
            if len(shared) != 2:
                continue
            # p = (a, b, c) with a the vertex not shared; q's lone vertex d
            ka = next(k for k in range(3) if k not in shared)
            kd = next(k for k in range(3) if q['verts'][k] not in p['verts'])
            ok = True
            for k in shared:
                kq = q['verts'].index(p['verts'][k])
                if p['uvs'] and tuple(p['uvs'][k]) != tuple(q['uvs'][kq]):
                    ok = False
            if not ok:
                continue
            # p in its own winding: a -> b -> c; quad corners (PS1 order) a, b, c, d with
            # triangles (a, b, c) and (b, d, c): b, c the shared edge in p's order
            kb, kc = (ka + 1) % 3, (ka + 2) % 3
            # q must traverse the shared edge the other way: c -> b -> d (same facing)
            qb, qc = q['verts'].index(p['verts'][kb]), q['verts'].index(p['verts'][kc])
            if (qc + 1) % 3 != qb:
                continue
            A, B, C, D = (V[x] for x in (p['verts'][ka], p['verts'][kb], p['verts'][kc], q['verts'][kd]))
            # convex: A and D on opposite sides of BC, B and C on opposite sides of AD
            def side(P, Q, R, n):
                u = [Q[i] - P[i] for i in range(3)]
                v = [R[i] - P[i] for i in range(3)]
                c = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
                return sum(a * b for a, b in zip(c, n))
            n = norms[i]
            if side(B, C, A, n) * side(B, C, D, n) >= 0 or side(A, D, B, n) * side(A, D, C, n) >= 0:
                continue
            # TMD quad corner order: v0 v1 v2 v3 drawn (0,1,2) + (1,3,2): (a, b, c) + (b, d, c)
            order_p = [ka, kb, kc]
            quad = dict(p)
            quad['verts'] = [p['verts'][k] for k in order_p] + [q['verts'][kd]]
            quad['norms'] = ([p['norms'][k] for k in order_p] + [q['norms'][kd]]) if p['norms'] else None
            quad['uvs'] = ([tuple(p['uvs'][k]) for k in order_p] + [tuple(q['uvs'][kd])]) if p['uvs'] else None
            made.append(quad)
            used[i] = used[j] = True
            break
    bone['prims'] = others + made + [p for k, p in enumerate(tris) if not used[k]]
    return len(made)


UNIT_SCALE = 0.2128         # DW2003 units -> DW1 units (the median piece ratio of the shape comparison, crossgame.md)


def load(name, height=600.0, fps=30.0, maxp=MAX_PALETTES, quad_angle=8.0, normal_angle=4.0, log=print, scale=None):
    dw3 = _dw3()
    import numeric as np
    from dw3.pose import animation_frames, local_trs, world_matrices
    from dw3.texture import tim_halfwords, indices_4bpp
    m = read_model(name)
    if m.texture is None:
        raise SystemExit(f'{name}: no texture in the file')
    f0 = animation_frames(m.animations[0])[0] if m.animations else 0
    W = world_matrices(m, f0, unit_scale=True)
    ys = [(np.array(b.mesh.vertices, float) @ W[b.index - 1][:3, :3].T + W[b.index - 1][:3, 3])[:, 1]
          for b in m.bones if b.mesh.vertices]
    tall = -min(y.min() for y in ys)
    S = scale if scale else height / tall          # `scale`: DW1 units per DW2003 unit (the Digimon's natural size)
    log(f'{name}: {tall:.0f} units tall in its first pose -> scale {S:.4f} ({height:.0f} units)')
    hw = tim_halfwords(m.texture)
    pix = indices_4bpp(hw)
    cluts = sorted({(p.material[3], p.material[4]) for b in m.bones for p in b.mesh.prims if p.uvs})
    pals = {c: [int(x) for x in hw[c[1], c[0]:c[0] + 16]] for c in cluts}
    bones, by_pal = [], {}
    for b in m.bones:
        prims = []
        for p in b.mesh.prims:
            if p.uvs:
                u0, v0 = p.material[0] | p.material[1] << 8, p.material[2]
                uvs = [(u0 + u, v0 + v) for u, v in p.uvs]
                if max(u for u, _ in uvs) > 255:
                    raise SystemExit(f'{name}: bone {b.index} has UVs outside the 256 columns of the page')
                key = (p.material[3], p.material[4])
            else:
                uvs, key = None, None
            st = p.state if isinstance(p.state, dict) else {}
            pr = dict(verts=list(p.verts), norms=list(p.normals) if p.normals else None, uvs=uvs, row=key,
                      semi=bool(st.get(0xe, 0)), abr=0, color=tuple(p.color[:3]) if p.color else (128, 128, 128))
            prims.append(pr)
            if key is not None:
                by_pal.setdefault(key, []).append(pr)
        t, R, s = local_trs(b, f0)
        bones.append(dict(parent=b.parent - 1, offset=tuple(float(x) * S for x in t),
                          rest=mmdport.quat_of_matrix(R.tolist()),
                          verts=[tuple(float(x) * S for x in v) for v in b.mesh.vertices],
                          norms=[tuple(n) for n in b.mesh.normals], prims=prims))
    # palettes
    remap = merge_palettes(by_pal, pals, lambda pr: [int(pix[v, u]) for u, v in _face_pixels(pr)], maxp, log)
    final = sorted(set(remap.values()))
    row_of = {c: final.index(remap[c]) for c in cluts}
    for b in bones:
        for p in b['prims']:
            p['row'] = row_of[p['row']] if p['row'] is not None else 0
    idx = bytearray(256 * 128)
    allp = [p for b in bones for p in b['prims'] if p['uvs']]
    if any(max(v for _, v in p['uvs']) > 127 for p in allp):      # rule: faces below row 127 are moved up
        page = repack_page(allp, pix, log)
        for y in range(128):
            idx[y * 256:(y + 1) * 256] = bytes(page[y])
    else:
        for y in range(128):
            idx[y * 256:(y + 1) * 256] = bytes(np.asarray(pix[y, :256], np.uint8))
    # triangles -> quads
    if quad_angle > 0:
        n = sum(merge_quads(b, quad_angle) for b in bones)
        log(f'  {n} quads made from pairs of triangles')
    if normal_angle > 0:
        n = sum(merge_normals(b, normal_angle) for b in bones)
        log(f'  {n} normals merged into one within {normal_angle} degrees')
    anims = {}
    def convert_frames(a):
        frames = []
        for f in timeline_frames(a):
            row = []
            for b in m.bones:
                t, R, s = local_trs(b, f)
                row.append((mmdport.quat_of_matrix(R.tolist()), tuple(float(x) * S for x in t),
                            tuple(float(x) for x in s)))
            frames.append(row)
        return frames
    for a in m.animations:
        anims[f'anim_{a.slot:02d}'] = mmdport.Anim(lambda a=a: convert_frames(a), fps, bool(a.loop))
    model = mmdport.Model(name, bones, idx, [pals[c] for c in final], anims)
    model.scale = S
    return model


def prepare(model, spec=None, log=print):
    """The model edits a batch spec records (import_batch.py, `game: dw3`): `hub_roots` (one body
    root, as DW2's) and `reverse` {new name: animation} (the get-up played backwards is the fall)."""
    spec = spec or {}
    if spec.get('hub_roots'):
        import dw2mmd
        dw2mmd.hub_roots(model, log)
    if spec.get('rigfix'):
        import rigfix
        rigfix.prepare(model, spec['rigfix'], log)         # rule: bones merged (tools/rigfix.py)
    for new, old in (spec.get('reverse') or {}).items():
        a = model.anims[old]
        model.anims[new] = mmdport.Anim(a.frames[::-1], a.fps, False)
    if spec.get('meshfix') is not None:        # tools/meshfix.py: the mesh edits a batch spec records (same parameters, no search)
        import meshfix
        meshfix.apply(model, spec['meshfix'], log=log)


def timeline_frames(anim):
    """Timeline frame of every displayed frame. A segment that holds timeline frame 0
    (frame 0 is a construction pose, an arm straight up) is a pause: it holds the
    previous segment's last frame, or the next segment's first one at the start."""
    out = []
    segs = anim.segments
    for k, seg in enumerate(segs):
        if seg.start == seg.end == 0:
            if out:
                hold = out[-1]
            else:
                nxt = next((x for x in segs[k + 1:] if not (x.start == x.end == 0)), None)
                hold = nxt.start if nxt else 0
            out += [hold] * seg.duration
        elif seg.start == seg.end:
            out += [seg.start] * seg.duration
        else:
            out += list(range(seg.start, seg.end + 1))
    return out


def merge_normals(bone, max_angle):
    """Normals within max_angle degrees of an earlier one are replaced by it (8 bytes each)."""
    c = math.cos(math.radians(max_angle))
    reps, remap = [], []
    for n in bone['norms']:
        L = math.sqrt(sum(x * x for x in n)) or 1.0
        u = [x / L for x in n]
        k = next((i for i, (r, _) in enumerate(reps) if sum(a * b for a, b in zip(u, r)) >= c), None)
        if k is None:
            k = len(reps)
            reps.append((u, n))
        remap.append(k)
    bone['norms'] = [n for _, n in reps]
    for p in bone['prims']:
        if p['norms'] is not None:
            p['norms'] = [remap[k] for k in p['norms']]
    return len(remap) - len(reps)


def stats(m):
    nv = sum(len(set(map(tuple, b['verts']))) for b in m.bones)
    q = sum(1 for b in m.bones for p in b['prims'] if len(p['verts']) == 4)
    t = sum(1 for b in m.bones for p in b['prims'] if len(p['verts']) == 3)
    return nv, q, t


def cmd_info(a):
    m = load(a.name, a.height, quad_angle=a.quad_angle)
    nv, q, t = stats(m)
    print(f'{len(m.bones)} bones (+ the entity), {nv} vertices, {q + t} primitives ({q} quads, {t} triangles), '
          f'{len(m.pals)} palettes, max {max(len(b["verts"]) for b in m.bones)} vertices per bone')
    for k, an in m.anims.items():
        print(f'  {k}: {len(an.frames)} frames ({len(an.frames) * 20 / an.fps:.0f} DW1 ticks){" loop" if an.loop else ""}')


def cmd_convert(a):
    m = load(a.name, a.height, a.fps, quad_angle=a.quad_angle)
    slots = {}
    for spec in a.slot or []:
        nm, _, s = spec.partition('=')
        slots[nm] = [int(x, 0) for x in s.split(',')]
    if not slots:
        slots = {k: [i] for i, k in enumerate(m.anims)}
    os.makedirs(a.out_dir, exist_ok=True)
    stem = os.path.join(a.out_dir, a.name)
    mmdport.convert(m, a.type, stem + '.MMD', stem + '.TIM', slots, stem + '.gltf', a.tol)
    json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))


def cmd_partner(a):
    spec = json.load(open(a.spec))
    m = load(spec['dw3'], spec.get('height', 600.0), spec.get('fps', 30.0), quad_angle=spec.get('quad_angle', 8.0),
             normal_angle=spec.get('normal_angle', 4.0), scale=spec.get('scale'))
    prepare(m, spec)
    os.makedirs(a.out_dir, exist_ok=True)
    stem = os.path.join(a.out_dir, spec.get('name', m.name))
    mmdport.build_partner(m, spec, stem + '.MMD', stem + '.TIM', a.out_dir)
    json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))


def cmd_sheet(a):
    """The source animations through the converted model (mmd.py's renderer)."""
    import mmd
    m = load(a.name, a.height)
    typ = 250
    base = mmdport.base_mmd(m, typ)
    tim = mmd.Tim4(mmdport.build_tim(m.idx, m.pals))
    sk = mmdport.skeleton(m)
    rows = []
    for k, an in m.anims.items():
        imgs = []
        for f in an.frames[::a.every]:
            pose = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]]
            prev = None
            for (q, t, s) in f:
                e = [round(x) for x in mmd.matrix_euler(mmd.quat_matrix(q), prev)]
                pose.append([round(x * 4096) for x in s] + e + [round(x) for x in t])
            imgs.append(mmd.render(base, tim, pose, a.size, math.radians(a.yaw)))
        rows.append(imgs)
    W = max(len(r) for r in rows) * a.size
    H = len(rows) * a.size
    out = bytearray([30, 30, 30, 255] * (W * H))
    for r, imgs in enumerate(rows):
        for c, im in enumerate(imgs):
            for y in range(a.size):
                o = ((r * a.size + y) * W + c * a.size) * 4
                out[o:o + a.size * 4] = im[y * a.size * 4:(y + 1) * a.size * 4]
    mmd.png_write(a.out, W, H, out)
    print(f'{a.out}: rows {list(m.anims)}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('info'); p.add_argument('name'); p.add_argument('--height', type=float, default=600.0)
    p.add_argument('--quad-angle', type=float, default=8.0); p.set_defaults(f=cmd_info)
    p = sub.add_parser('convert'); p.add_argument('name'); p.add_argument('type', type=lambda s: int(s, 0))
    p.add_argument('out_dir'); p.add_argument('--height', type=float, default=600.0)
    p.add_argument('--fps', type=float, default=30.0); p.add_argument('--tol', type=int, default=1)
    p.add_argument('--quad-angle', type=float, default=8.0)
    p.add_argument('--slot', action='append', help='anim_NN=SLOT[,SLOT]'); p.set_defaults(f=cmd_convert)
    p = sub.add_parser('partner'); p.add_argument('spec'); p.add_argument('out_dir'); p.set_defaults(f=cmd_partner)
    p = sub.add_parser('sheet'); p.add_argument('name'); p.add_argument('out')
    p.add_argument('--height', type=float, default=600.0); p.add_argument('--every', type=int, default=8)
    p.add_argument('--size', type=int, default=120); p.add_argument('--yaw', type=float, default=30.0)
    p.set_defaults(f=cmd_sheet)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
