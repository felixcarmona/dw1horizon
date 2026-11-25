"""Bind the Card Battle MagnaAngemon mesh to native Angemon's rig and clips, with the World 2003 arm pieces.

The Card Battle model (the importer output, in its zero-rotation pose: standing, arms down; the `posed` bones, the
wings, folded as in its idle) is placed on Angemon's
rest pose (slot 0) scaled by `scale`: each limb segment turned onto Angemon's (swing, stretched along its length), each
hand and foot turned with its segment, everything else moved as one with the body. The World 2003 model gives the
pieces the Card Battle one lacks (`grafts`): the shoulder shield on the upper arm, in the helmet's purple, and the
bracelet with the blue gem wrapped round the other forearm, gem out. Their texels go into the free room of the Card
Battle texture, their palettes into its free palettes.

Developer-only static mesh authoring. Player builds replay the importer outputs and plain deltas; no NumPy or animation
retargeting is needed by players.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import animsheet
import mmd
import retarget

SPEC = Path('content/imports/specs/MagnaAngemon.json')


def parsed(data, part):
    mmd.exe().add_type(part['type'], part['skeleton'])
    model = mmd.MMD.parse(data, len(part['skeleton']))
    model.type = part['type']
    return model


def world(model, nbones, zero=False, keep=()):
    """World bone matrices of slot 0's first frame; zero: every bone's rotation dropped but those in `keep`."""
    pose = animsheet.slot_frames(model, nbones, 0)[0][0]
    pose[0] = [4096] * 3 + [0] * 6
    if zero:
        for b, v in enumerate(pose):
            if b not in keep:
                v[3:6] = [0, 0, 0]
    return np.array(mmd.bone_matrices(model, pose))


def segment(a, b):
    """The swing of direction a onto b, stretched along a to b's length."""
    ua = a / np.linalg.norm(a)
    return np.array(retarget.swing(a.tolist(), b.tolist())) @ (np.eye(3) + (np.linalg.norm(b) / np.linalg.norm(a) - 1) * np.outer(ua, ua))


def cloud(model, skeleton, b, w):
    return np.array(model.tmd.obj_verts(skeleton[b][0]))[:, :3] @ w[b, :3, :3].T + w[b, :3, 3]


def palette(face):
    return (face['cba'] >> 6) - 488


class Atlas:
    """The free texels (no face's UV polygon, one texel apart) and free palettes of a 4-bit texture."""

    def __init__(self, tim, models):
        self.tim, self.h = tim, len(tim.idx) // 256
        img = Image.new('L', (256, self.h), 0)
        draw, used = ImageDraw.Draw(img), set()
        for model in models:
            for ob in model.tmd.objects:
                for p in ob.prims:
                    d = p.decode()
                    if d.get('uv'):
                        used.add(palette(d))
                        uv = [tuple(u) for u in d['uv']]
                        draw.polygon(uv if len(uv) == 3 else [uv[0], uv[1], uv[3], uv[2]], fill=255, outline=255)
        m = np.array(img) > 0
        self.mask = m | np.roll(m, 1, 0) | np.roll(m, -1, 0) | np.roll(m, 1, 1) | np.roll(m, -1, 1)
        self.palettes = [i for i in range(15) if i not in used]

    def fit(self, w, h):
        """The free w x h spot whose border touches the most used texels (keeps the free room in one piece)."""
        pad = np.pad(self.mask, 1, constant_values=True)
        ii = np.cumsum(np.cumsum(np.pad(self.mask, ((1, 0), (1, 0))).astype(int), 0), 1)
        best = None
        for y in range(self.h - h + 1):
            for x in range(256 - w + 1):
                if ii[y + h, x + w] - ii[y, x + w] - ii[y + h, x] + ii[y, x]:
                    continue
                score = pad[y, x:x + w + 2].sum() + pad[y + h + 1, x:x + w + 2].sum() + \
                    pad[y + 1:y + h + 1, x].sum() + pad[y + 1:y + h + 1, x + w + 1].sum()
                if best is None or score > best[0]:
                    best = (score, (x, y))
        return best and best[1]


def box(rects):
    return [min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)]


def area(r):
    return (r[2] - r[0] + 1) * (r[3] - r[1] + 1)


def clusters(rects):
    """The bounding boxes of the groups of touching face rectangles."""
    rs = [list(r) for r in rects]
    merged = True
    while merged:
        merged = False
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                if a[0] <= b[2] + 1 and b[0] <= a[2] + 1 and a[1] <= b[3] + 1 and b[1] <= a[3] + 1:
                    rs[i] = box([a, b])
                    rs.pop(j)
                    merged = True
                    break
            if merged:
                break
    return rs


def pack(atlas, source_tim, faces, half, recolour):
    """Copy the texels and palettes of the graft faces into the atlas -> remap(face dict) (uv, cba in place).
    faces: [(graft index, face)]; half: graft indices copied at half resolution; recolour: {source palette: the ramp
    (target palette, first, last entry) its colours take by brightness rank}."""
    tim, palmap, texmap, pending = atlas.tim, {}, {}, []

    def rect(f):
        uv = np.array(f['uv'])
        return [*uv.min(0), *uv.max(0)]
    for pal in sorted({palette(f) for _, f in faces}):
        if pal not in palmap:
            new = atlas.palettes.pop(0)
            tim.pal[new] = list(source_tim.pal[pal])
            palmap[pal] = new
            if pal in recolour:
                target, first, last = recolour[pal]
                ramp = [tim.pal[target][k] for k in range(first, last + 1)]
                lum = lambda c: sum((c >> s) & 31 for s in (0, 5, 10))  # noqa: E731
                ids = sorted([k for k in range(16) if tim.pal[new][k] & 0x7fff], key=lambda k: -lum(tim.pal[new][k]))
                for r, k in enumerate(ids):
                    tim.pal[new][k] = (tim.pal[new][k] & 0x8000) | \
                        (ramp[round(r * (len(ramp) - 1) / max(len(ids) - 1, 1))] & 0x7fff)
        for k in (1, 2):
            pf = [rect(f) for g, f in faces if palette(f) == pal and (2 if g in half else 1) == k]
            for c in clusters(pf):
                pending.append((pal, k, [r for r in pf if c[0] <= r[0] and r[2] <= c[2] and c[1] <= r[1] and r[3] <= c[3]]))
    while pending:
        pending.sort(key=lambda e: -area(box(e[2])))
        pal, k, group = pending.pop(0)
        r = box(group)
        if (pal, tuple(r)) in texmap:
            continue
        w, h = (r[2] - r[0]) // k + 1, (r[3] - r[1]) // k + 1
        spot = atlas.fit(w, h)
        if spot is None:
            # cut the group in two by face centres, along the axis that leaves the smaller larger half
            if len(group) < 2:
                raise ValueError(f'MagnaAngemon: no texture room for {w}x{h} (palette {pal})')
            best = None
            for axis in (0, 1):
                cs = sorted(group, key=lambda f: f[axis] + f[axis + 2])
                for i in range(1, len(cs)):
                    cost = max(area(box(cs[:i])), area(box(cs[i:])))
                    if best is None or cost < best[0]:
                        best = (cost, cs[:i], cs[i:])
            pending += [(pal, k, best[1]), (pal, k, best[2])]
            continue
        x, y = spot
        atlas.mask[y:y + h, x:x + w] = True
        for j in range(h):
            for i in range(w):
                tim.idx[(y + j) * 256 + x + i] = source_tim.idx[(r[1] + j * k) * 256 + r[0] + i * k]
        texmap[(pal, tuple(r))] = (x, y, k)

    def remap(f):
        pal = palette(f)
        for (p, r), (x, y, k) in texmap.items():
            if p == pal and all(r[0] <= u <= r[2] and r[1] <= v <= r[3] for u, v in f['uv']):
                f['uv'] = [(int(x + (u - r[0]) // k), int(y + (v - r[1]) // k)) for u, v in f['uv']]
                f['cba'] = (488 + palmap[pal]) << 6
                return
        raise KeyError(f['uv'])
    return remap


def bind(mesh, texture, graft_mesh, graft_texture, donor, spec):
    pins = ((mesh, spec['mesh']['sha256']), (texture, spec['mesh']['texture_sha256']),
            (graft_mesh, spec['grafts']['mesh']['sha256']), (graft_texture, spec['grafts']['mesh']['texture_sha256']))
    for data, want in pins:
        if hashlib.sha256(data).hexdigest() != want:
            raise ValueError('MagnaAngemon: unpinned source')
    sk, gk = spec['mesh']['skeleton'], spec['grafts']['mesh']['skeleton']
    s = parsed(mesh, spec['mesh'])
    g = parsed(graft_mesh, spec['grafts']['mesh'])
    n = mmd.MMD.parse(donor, 26)
    n.type = spec['source']['type']
    nk = mmd.exe().skeleton[n.type]
    scale = spec['scale']
    sw, gw, nw = world(s, len(sk), zero=True, keep=spec['posed']), world(g, len(gk)), world(n, 26)
    nw[:, :3, 3] *= scale
    mapping = {int(k): v for k, v in spec['map'].items()}
    children = {int(k): v for k, v in spec['segments'].items()}
    ends = {int(k): v for k, v in spec['ends'].items()}
    # the body moves as one: the least-squares offset of the mapped joints
    shift = np.mean([nw[t, :3, 3] - sw[b, :3, 3] for b, t in mapping.items()], axis=0)
    # the wings and the back cloth turn about their own joints, not Angemon's: the bones they ride move there
    joints = {}
    for sb in spec.get('pivots', []):
        tb = mapping[sb]
        nw[tb, :3, 3] = sw[sb, :3, 3] + shift
    for sb in spec.get('pivots', []):
        tb = mapping[sb]
        parent = nk[tb][1]
        joints[tb] = np.linalg.solve(nw[parent, :3, :3], nw[tb, :3, 3] - nw[parent, :3, 3])

    def turn(sb):
        return segment(sw[children[sb], :3, 3] - sw[sb, :3, 3], nw[mapping[children[sb]], :3, 3] - nw[mapping[sb], :3, 3])
    items = {i: [] for i in range(26)}
    placed = {}
    for sb, tb in mapping.items():
        points = cloud(s, sk, sb, sw)
        if sb in children or sb in ends:
            mat = turn(sb) if sb in children else retarget_rotation(turn(ends[sb]))
            points = (points - sw[sb, :3, 3]) @ mat.T + nw[tb, :3, 3]
        else:
            mat = np.eye(3)
            points = points + shift
        placed[sb] = points
        local = (points - nw[tb, :3, 3]) @ nw[tb, :3, :3]
        obj = sk[sb][0]
        norms = np.array(s.tmd.obj_norms(obj)[:s.tmd.objects[obj].nnorm]).reshape(-1, 4)[:, :3] @ sw[sb, :3, :3].T @ \
            np.linalg.inv(mat) @ nw[tb, :3, :3]
        items[tb].append((s, obj, local, norms, None))

    # the World 2003 arm pieces
    tim, gt = mmd.Tim4(texture), mmd.Tim4(graft_texture)
    atlas = Atlas(tim, [s])
    pieces = []
    for i, piece in enumerate(spec['grafts']['pieces']):
        faces = [p.decode() for p in g.tmd.objects[gk[piece['source']][0]].prims]
        keep = piece.get('palettes')
        faces = [f for f in faces if keep is None or (f.get('uv') and palette(f) in keep)]
        pieces.append((piece, faces))
    recolour = {int(k): v for piece in spec['grafts']['pieces'] for k, v in piece.get('recolour', {}).items()}
    remap = pack(atlas, gt, [(i, f) for i, (_, faces) in enumerate(pieces) for f in faces if f.get('uv')],
                 {i for i, (piece, _) in enumerate(pieces) if piece.get('half')}, recolour)
    for piece, faces in pieces:
        sb, (limb, joint), tb = piece['source'], piece['limb'], piece['bone']
        obj = gk[sb][0]
        vids = sorted({v for f in faces for v in f['verts']})
        nids = sorted({v for f in faces for v in f.get('norms') or []})
        pts = np.array(g.tmd.obj_verts(obj))[vids, :3] @ gw[sb, :3, :3].T + gw[sb, :3, 3]
        child = next(b for b, (_, parent) in enumerate(nk) if parent == tb)
        a, b = gw[joint, :3, 3] - gw[limb, :3, 3], nw[child, :3, 3] - nw[tb, :3, 3]
        mat = segment(a, b)
        pts = (pts - gw[limb, :3, 3]) @ mat.T + nw[tb, :3, 3]
        wrap = piece.get('wrap')
        if wrap:
            # wrap the bracelet snugly round the bound Card Battle forearm, the gem facing away from the body
            base, u = nw[tb, :3, 3], b / np.linalg.norm(b)

            def perp(p):
                return (p - base) - np.outer((p - base) @ u, u)
            arm = sorted({v for p in g.tmd.objects[gk[limb][0]].prims for v in p.decode()['verts']
                          if palette(p.decode()) == wrap['palette']})
            src = (np.array(g.tmd.obj_verts(gk[limb][0]))[arm, :3] @ gw[limb, :3, :3].T + gw[limb, :3, 3] - gw[limb, :3, 3]) @ mat.T + base
            forearm = placed[next(sb_ for sb_, t in mapping.items() if t == tb)]
            ratio = np.median(np.linalg.norm(perp(forearm), axis=1)) / np.median(np.linalg.norm(perp(src), axis=1)) * wrap['fit']
            gem = perp(gem_centre(g, gk, gt, limb, wrap['gem'], gw, mat, base)[None])[0]
            want = np.array([np.sign(base[0]) or -1., 0., 0.])
            want -= (want @ u) * u
            gem, want = gem / np.linalg.norm(gem), want / np.linalg.norm(want)
            ang = np.arctan2(np.cross(gem, want) @ u, gem @ want)
            k = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
            rot = np.eye(3) + np.sin(ang) * k + (1 - np.cos(ang)) * k @ k
            radial = perp(pts)
            pts = base + (pts - base - radial) + (radial * ratio) @ rot.T
            mat = rot @ mat
        local = (pts - nw[tb, :3, 3]) @ nw[tb, :3, :3]
        norms = np.array(g.tmd.obj_norms(obj))[nids, :3] @ gw[sb, :3, :3].T @ np.linalg.inv(mat) @ nw[tb, :3, :3]
        vm, nm = {v: k for k, v in enumerate(vids)}, {v: k for k, v in enumerate(nids)}
        prims = []
        for f in faces:
            f['verts'] = [vm[v] for v in f['verts']]
            if f.get('norms'):
                f['norms'] = [nm[v] for v in f['norms']]
            if f.get('uv'):
                remap(f)
            prims.append(mmd.Prim.encode(f))
        items[tb].append((g, obj, local, norms, prims))

    tmd = mmd.TMD()
    rig = []
    for b, (_, parent) in enumerate(nk):
        if not items[b]:
            rig.append([-1, parent])
            continue
        ob = mmd.TMDObject()
        ob.vert_start, ob.norm_start, ob.scale, ob.prims = len(tmd.verts), len(tmd.norms), 0, []
        nv = nn = 0
        for model, obj, pts, norms, prims in items[b]:
            tmd.verts.extend(tuple([round(v) for v in p] + [0]) for p in pts)
            norms = norms / np.maximum(np.linalg.norm(norms, axis=1)[:, None], 1) * 4096
            tmd.norms.extend(tuple([round(v) for v in p] + [0]) for p in norms)
            for p in model.tmd.objects[obj].prims if prims is None else prims:
                d = p.decode()
                d['verts'] = [v + nv for v in d['verts']]
                if d.get('norms'):
                    d['norms'] = [v + nn for v in d['norms']]
                ob.prims.append(mmd.Prim.encode(d))
            nv += len(pts)
            nn += len(norms)
        ob.nvert, ob.nnorm = nv, nn
        rig.append([len(tmd.objects), parent])
        tmd.objects.append(ob)
    result = copy.deepcopy(n)
    result.tmd = tmd
    for a in result.anims.anims:
        for b, p in enumerate(a.pose, 1):     # the pose starts at bone 1
            p[-3:] = [round(v) for v in joints[b]] if b in joints else [round(v * scale) for v in p[-3:]]
        for ins in a.instrs:
            if ins['op'] == 'key':
                for grp in ins['bones']:
                    for k in grp['vals']:
                        if k in ('tx', 'ty', 'tz'):
                            grp['vals'][k] = round(grp['vals'][k] * scale)
        a.instrs = [i for i in a.instrs if i['op'] != 'tex']
        a.tail = b''
    slots = list(result.anims.table)
    result.anims.table += [None] * max(0, 61 - len(slots))
    for dest, src in enumerate(spec['technique_slots'], 46):
        result.anims.table[dest] = slots[src]
    for dest, src in spec['extra_slots'].items():
        result.anims.table[int(dest)] = slots[src]
    return result.build(), tim.to_bytes(), rig


def retarget_rotation(m):
    """The rotation of a swing-and-stretch (a hand or foot turns with its segment, unstretched)."""
    u, _, vt = np.linalg.svd(m)
    return u @ vt


def gem_centre(g, gk, gt, limb, pal, gw, mat, base):
    """The centre of the forearm's faces of palette `pal` that show the blue gem, bound like the forearm."""
    obj = gk[limb][0]
    verts = np.array(g.tmd.obj_verts(obj))[:, :3] @ gw[limb, :3, :3].T + gw[limb, :3, 3]
    pts = []
    for p in g.tmd.objects[obj].prims:
        f = p.decode()
        if not f.get('uv') or palette(f) != pal:
            continue
        uv = np.array(f['uv'])
        lo, hi = uv.min(0), uv.max(0)
        blue = sum(1 for y in range(lo[1], hi[1] + 1) for x in range(lo[0], hi[0] + 1)
                   if (lambda c: (c >> 10 & 31) > (c & 31) + 6)(gt.pal[pal][gt.idx[y * 256 + x]]))
        if blue > 4:
            pts += list(verts[f['verts']])
    return (np.mean(pts, 0) - gw[limb, :3, 3]) @ mat.T + base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path, help='the folder the importer outputs are in (edit.py sources)')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text())
    read = lambda p: (args.sources / p).read_bytes()  # noqa: E731
    graft = Path(spec['grafts']['mesh']['file'])
    model, texture, rig = bind(read(spec['mesh']['file']), read(spec['mesh']['texture']), read(graft),
                               read(graft.with_suffix('.TIM')), Path(spec['source']['mmd']).read_bytes(), spec)
    args.output.write_bytes(model)
    args.output.with_suffix('.TIM').write_bytes(texture)
    args.output.with_suffix('.rig.json').write_text(json.dumps(rig, indent=2) + '\n')
    print(f'{args.output}: {len(model)} bytes, {len(rig)} native bones')


if __name__ == '__main__':
    main()
