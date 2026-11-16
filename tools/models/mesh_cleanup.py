"""Reviewed surface and clip repairs after final mesh fitting.

Opaque duplicate packets are removed only when both oriented GPU triangles,
including all corner attributes and material state, are identical. Opposite
faces and translucent layers remain. Layer offsets name reviewed objects/UVs;
they do not flatten arbitrary geometry to satisfy an audit threshold.
"""
import hashlib
import math
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mmd
from tools.models import mesh_stability


MANIFEST = Path(__file__).resolve().parents[2] / 'content/models/imports/mesh-cleanup.json'


def duplicate_surfaces(model):
    removed = 0
    for oi, obj in enumerate(model.tmd.objects):
        vertices, normals = model.tmd.obj_verts(oi), model.tmd.obj_norms(oi)
        seen, keep = set(), []
        for prim in obj.prims:
            d = prim.decode()
            if d['mode'] & 2:  # repeated blending changes the framebuffer
                keep.append(prim)
                continue
            corners = []
            for k, vi in enumerate(d['verts']):
                corners.append((tuple(vertices[vi]),
                    tuple(normals[d['norms'][min(k, len(d['norms'])-1)]]) if d['norms'] else (),
                    tuple(d['uv'][k]) if d['uv'] else (),
                    tuple(d['colors'][min(k, len(d['colors'])-1)][:3]) if d['colors'] else ()))
            triangles = []
            for ids in ((0, 1, 2), (1, 3, 2)) if len(corners) == 4 else ((0, 1, 2),):
                t = tuple(corners[k] for k in ids)
                triangles.append(min(t, t[1:]+t[:1], t[2:]+t[:2]))
            key = (d['mode'], d['flag'], d['cba'], d['tsb'], tuple(sorted(triangles)))
            if key in seen:
                removed += 1
            else:
                seen.add(key)
                keep.append(prim)
        obj.prims = keep
    return removed


def apply(data, bones, sid):
    sid = int(sid)
    reviewed = json.loads(MANIFEST.read_text())
    if str(sid) not in reviewed:
        return data, dict(applied=False)
    end = int.from_bytes(data[4:8], "little")
    if hashlib.sha256(data[8:end]).hexdigest() != reviewed[str(sid)]:
        raise ValueError(f'{sid}: surface repair requires the reviewed final TMD')
    model = mmd.MMD.parse(data, len(bones))
    report = dict(applied=True)
    if sid == 432:
        report['duplicate_packets'] = duplicate_surfaces(model)
    if sid == 323:
        # Crossed tail flame cards: the longitudinal cards of pelvis, tail
        # base and tip all occupied x=0. Keep each card's two windings together.
        for oi, distance in ((13, 4), (14, 8)):
            obj = model.tmd.objects[oi]
            verts = model.tmd.obj_verts(oi)
            if len(verts) != 8 or any(v[0] != 0 for v in verts[:4]):
                raise ValueError('tail flame card no longer matches reviewed mesh')
            for vi in range(4):
                v = list(verts[vi]); v[0] += distance
                model.tmd.verts[obj.vert_start+vi] = tuple(v)
        report['tail_card_offsets'] = [4, 8]
    if sid == 405:
        # Toe detail lay one unit above the sole on both front feet. Inset
        # that existing detail ring, retaining the sole and its ground contact.
        counts = []
        for oi in (6, 9):
            obj = model.tmd.objects[oi]
            count = 0
            for vi, vertex in enumerate(model.tmd.obj_verts(oi)):
                if vertex[1] == 36:
                    v = list(vertex); v[1] -= 4
                    model.tmd.verts[obj.vert_start+vi] = tuple(v); count += 1
            counts.append(count)
        if counts != [8, 8]:
            raise ValueError(f'toe detail no longer matches reviewed mesh: {counts}')
        report['toe_inset'] = 4
    if sid == 326:
        # A triangular armour decal was exactly on the underlying shell.
        # Give only the decal independent corners and an outward four-unit gap.
        obj = model.tmd.objects[5]
        matches = [i for i, p in enumerate(obj.prims)
                   if p.decode()['uv'] == [(182, 81), (182, 95), (191, 88)]]
        if len(matches) != 1:
            raise ValueError('armour decal no longer matches reviewed mesh')
        pi = matches[0]; d = obj.prims[pi].decode()
        vv = model.tmd.obj_verts(5)
        a, b, c = [vv[i] for i in d['verts']]
        n = mesh_stability._normal(a, b, c)
        length = math.sqrt(sum(v*v for v in n))
        delta = [round(4*v/length) for v in n]
        # Rebuild pools since an object's slice may be followed by another's.
        pools = [list(model.tmd.obj_verts(i)) for i in range(len(model.tmd.objects))]
        for k, vi in enumerate(d['verts']):
            vertex = vv[vi]
            d['verts'][k] = len(pools[5])
            pools[5].append(tuple(vertex[j]+delta[j] for j in range(3))+(vertex[3],))
        obj.prims[pi] = mmd.Prim.encode(d)
        model.tmd.verts = []
        for ob, pool in zip(model.tmd.objects, pools):
            ob.vert_start, ob.nvert = len(model.tmd.verts), len(pool)
            model.tmd.verts.extend(pool)
        report['decal_offset'] = delta
    if sid == 407:
        # Run: open the rear hip's yaw by twelve degrees. A constant local
        # offset preserves its swing, acceleration and loop rather than freezing
        # the offending foot. Update all aliases of this program together.
        import animsheet
        index = model.anims.table[4]
        frames, loop, events = animsheet.slot_frames(model, len(bones), 4)
        frames = [[[int(v) for v in bone] for bone in pose] for pose in frames]
        for pose in frames:
            pose[24][4] -= round(12*4096/360)
        model.anims.anims[index] = mmd.encode_anim(frames, len(bones), loop, events, tol=0)
        report['run_hip_yaw'] = -12
        # One mouth quad is a line in local space in every pose: it can never
        # cover a pixel before projection rounding and has no surface to retain.
        model.tmd.objects[2].prims.pop(0)
        report['zero_surface_packets'] = 1
    mesh_stability.compact_pools(model)
    return model.build(), report


def main():
    """Record reviewed final TMD hashes through a repository authoring tool."""
    import argparse
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('command', choices=['review'])
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    rows = {}
    for sid in (323, 326, 405, 407, 432):
        data = (args.folder / f'{sid}.MMD').read_bytes()
        end = int.from_bytes(data[4:8], 'little')
        rows[str(sid)] = hashlib.sha256(data[8:end]).hexdigest()
    MANIFEST.write_text(json.dumps(rows, indent=2)+'\n')
    print(f'{MANIFEST.relative_to(MANIFEST.parents[3])}: {len(rows)} reviewed meshes')


if __name__ == '__main__':
    main()
