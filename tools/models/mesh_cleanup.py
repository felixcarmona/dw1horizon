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


def translate_bone(model, bone, axis, distance):
    """Shift a joint in every program without changing timing or momentum.

    Positive-divisor keys are increments, not absolute positions. Only the
    initial pose and zero-divisor assignments receive the constant offset.
    """
    channel = ('tx', 'ty', 'tz')[axis]
    for anim in model.anims.anims:
        anim.pose[bone-1][(6 if anim.has_scale else 3)+axis] += distance
        for ins in anim.instrs:
            if ins['op'] == 'key':
                for key in ins['bones']:
                    if key['bone'] == bone and key['div'] == 0 and channel in key['vals']:
                        key['vals'][channel] += distance


def transform_piece(model, oi, scale=(1, 1, 1), offset=(0, 0, 0), shear_zx=0):
    """Fit a rigid shell about its attachment, including inverse-scale normals."""
    ob = model.tmd.objects[oi]
    for i, v in enumerate(model.tmd.obj_verts(oi)):
        model.tmd.verts[ob.vert_start+i] = (round(v[0]*scale[0]+offset[0]), round(v[1]*scale[1]+offset[1]),
            round(v[2]*scale[2]+v[0]*shear_zx+offset[2]), v[3])
    if scale[0] == scale[1] == scale[2] and not shear_zx:
        return
    for i, n in enumerate(model.tmd.obj_norms(oi)):
        q = [n[0]/scale[0]-n[2]*shear_zx/(scale[0]*scale[2]), n[1]/scale[1], n[2]/scale[2]]
        length = math.sqrt(sum(x*x for x in q))
        model.tmd.norms[ob.norm_start+i] = tuple(round(x*4096/length) if length else 0 for x in q)+(n[3],)


def rotate_clip_bone(model, slot, bone, degrees):
    """Offset one clip's local rotation, retaining its keys and timing exactly."""
    anim = model.anims.anims[model.anims.table[slot]]
    for axis, angle in enumerate(degrees):
        offset = round(angle*4096/360)
        anim.pose[bone-1][(3 if anim.has_scale else 0)+axis] += offset
        channel = ('rx', 'ry', 'rz')[axis]
        for ins in anim.instrs:
            if ins['op'] == 'key':
                for key in ins['bones']:
                    if key['bone'] == bone and key['div'] == 0 and channel in key['vals']:
                        key['vals'][channel] += offset


def taper_ankle(model, oi):
    """Taper a distal ring and transform its corner normals with the same map."""
    ob = model.tmd.objects[oi]
    vertices = list(model.tmd.obj_verts(oi))
    old_norms = list(model.tmd.obj_norms(oi))
    pools = [list(model.tmd.obj_norms(i)) for i in range(len(model.tmd.objects))]
    normals, lookup = [], {}
    for pi, prim in enumerate(ob.prims):
        d = prim.decode()
        for k, ni in enumerate(d['norms']):
            points = [vertices[v] for v in d['verts']] if len(d['norms']) == 1 else [vertices[d['verts'][k]]]
            x, y, z = [sum(v[j] for v in points)/len(points) for j in range(3)]
            factor = 1-.4*max(0, min(1, (y-50)/40))
            slope = -.01 if 50 < y < 90 else 0
            n = old_norms[ni]
            q = [n[0]/factor, n[1]-slope*(x*n[0]+z*n[2])/factor, n[2]/factor]
            length = math.sqrt(sum(v*v for v in q))
            normal = tuple(round(v*4096/length) if length else 0 for v in q)+(n[3],)
            if normal not in lookup:
                lookup[normal] = len(normals); normals.append(normal)
            d['norms'][k] = lookup[normal]
        ob.prims[pi] = mmd.Prim.encode(d)
    pools[oi] = normals
    model.tmd.norms = []
    for obj, pool in zip(model.tmd.objects, pools):
        obj.norm_start, obj.nnorm = len(model.tmd.norms), len(pool)
        model.tmd.norms.extend(pool)
    for vi, v in enumerate(vertices):
        factor = 1-.4*max(0, min(1, (v[1]-50)/40))
        model.tmd.verts[ob.vert_start+vi] = (round(v[0]*factor), v[1], round(v[2]*factor), v[3])


def offset_layer(model, oi, primitives, delta):
    """Give a complete decal independent corners, keeping its base shell fixed."""
    pools = [list(model.tmd.obj_verts(i)) for i in range(len(model.tmd.objects))]
    mapping = {}
    ob = model.tmd.objects[oi]
    for pi in primitives:
        d = ob.prims[pi].decode()
        for k, vi in enumerate(d['verts']):
            if vi not in mapping:
                v = pools[oi][vi]
                mapping[vi] = len(pools[oi])
                pools[oi].append(tuple(v[j]+delta[j] for j in range(3))+(v[3],))
            d['verts'][k] = mapping[vi]
        ob.prims[pi] = mmd.Prim.encode(d)
    model.tmd.verts = []
    for obj, pool in zip(model.tmd.objects, pools):
        obj.vert_start, obj.nvert = len(model.tmd.verts), len(pool)
        model.tmd.verts.extend(pool)


def fit_toe_lip(model, oi):
    """Pull only the rear lip into the boot, keeping the tip and sole height.

    The last 50 local Z units compress by 24%, moving the rearmost corner 12
    units. Normals receive the inverse of this piecewise affine deformation.
    The incoming final pools are compact, with object-local normal indices.
    """
    obj = model.tmd.objects[oi]
    vertices = list(model.tmd.obj_verts(oi))
    old = list(model.tmd.obj_norms(oi))
    pools = [list(model.tmd.obj_norms(i))[:ob.nnorm] for i, ob in enumerate(model.tmd.objects)]
    normals, lookup = [], {}
    for pi, prim in enumerate(obj.prims):
        d = prim.decode()
        for k, ni in enumerate(d['norms']):
            points = [vertices[v] for v in d['verts']] if len(d['norms']) == 1 else [vertices[d['verts'][k]]]
            z = sum(v[2] for v in points)/len(points)
            n = old[ni]
            q = [n[0], n[1], n[2]/(.76 if z > -40 else 1)]
            length = math.sqrt(sum(v*v for v in q))
            normal = tuple(round(v*4096/length) if length else 0 for v in q)+(n[3],)
            if normal not in lookup:
                lookup[normal] = len(normals)
                normals.append(normal)
            d['norms'][k] = lookup[normal]
        obj.prims[pi] = mmd.Prim.encode(d)
    pools[oi] = normals
    model.tmd.norms = []
    for ob, pool in zip(model.tmd.objects, pools):
        ob.norm_start, ob.nnorm = len(model.tmd.norms), len(pool)
        model.tmd.norms.extend(pool)
    for vi, v in enumerate(vertices):
        z = round(-40+(v[2]+40)*.76) if v[2] > -40 else v[2]
        model.tmd.verts[obj.vert_start+vi] = (v[0], v[1], z, v[3])


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
    if sid == 295:
        # Two quads end in a collinear second half. Keep their complete first
        # GPU triangle and discard only the zero-area half, including its bogus
        # fourth-corner contribution to AVSZ4 sorting depth.
        count = 0
        for oi, ob in enumerate(model.tmd.objects):
            vertices = model.tmd.obj_verts(oi)
            for pi, prim in enumerate(ob.prims):
                ids = prim.decode()['verts']
                if len(ids) != 4:
                    continue
                a, b, c, d = [vertices[i] for i in ids]
                first = mesh_stability._normal(a, b, c)
                second = mesh_stability._normal(b, d, c)
                if any(first) and not any(second):
                    ob.prims[pi] = mesh_stability.split_quad(prim)[0]
                    count += 1
        if count != 2:
            raise ValueError('zero-area quad halves no longer match reviewed mesh')
        report['zero_area_halves'] = count
    if sid == 409:
        # The rebound fan started inside the rear thighs. Move the whole fan
        # together and lengthen its existing root stalk to retain the socket.
        if tuple(bones[15]) != (9, 14) or tuple(bones[14]) != (8, 1):
            raise ValueError('tail repair requires the reviewed fan/socket binding')
        translate_bone(model, 15, 0, 60)
        translate_bone(model, 15, 2, -20)
        transform_piece(model, 8, scale=(144/84, 1, 1), shear_zx=-20/84)
        report['tail_socket_extension'] = [60, 0, -20]
    if sid == 406:
        # Both cannon caps cut through the housings. Advance their rear lip
        # eight local units; their separate animation and material stay intact.
        for oi in (2, 9):
            transform_piece(model, oi, offset=(0, 0, -8))
        report['cannon_cap_offset'] = -8
    if sid == 335:
        # Oversized rigid shoulder shells engulfed the elbow during its swing.
        # Fit the shell about the shoulder mount; keep the arm and muzzle rig.
        for oi in (12, 22):
            transform_piece(model, oi, scale=(.7, .7, .7))
        # The two calf shells crossed one another in the idle and run poses.
        for oi in (3, 8):
            transform_piece(model, oi, scale=(.9, 1, .9))
        report['shoulder_fit'] = .7
        report['calf_radial_fit'] = .9
    if sid == 336:
        # The wide shoulder plates swept through both forearms and the calves.
        # Narrow each plate toward its unchanged inner mounting edge.
        for oi in (8, 22):
            transform_piece(model, oi, scale=(.6, 1, 1))
        report['shoulder_width_fit'] = .6
        # Slot 43 drives the left forearm through its shoulder plate. Correct
        # the clip's elbow pose instead of rotating both plates in every clip,
        # which introduces plate-to-plate contact in the battle idle.
        if [s for s, index in enumerate(model.anims.table)
                if index == model.anims.table[43]] != [43]:
            raise ValueError('forearm repair requires the reviewed independent slot 43')
        rotate_clip_bone(model, 43, 3, (-10, 10, -5))
        report['slot_43_forearm_rotation_degrees'] = [-10, 10, -5]
    if sid == 461:
        # Animated face masks were exactly on the base head. Keep the masks
        # (including currently transparent texels) on one independent front layer.
        offset_layer(model, 1, range(6), (0, 0, -6))
        # The broadened calf flare pierced the separate toe armour. Taper only
        # its distal ring into the boot, keeping the knee and ankle locations.
        for oi in (15, 19):
            taper_ankle(model, oi)
        # The toe armour's rear lip swept back through the calf and boot.
        # Retract that lip without shortening the toe or moving either joint.
        for oi in (17, 21):
            fit_toe_lip(model, oi)
        report['face_layer_offset'] = -6
        report['ankle_radial_fit'] = .6
        report['toe_rear_lip_fit'] = .76
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
    """Record reviewed TMD hashes or scope heap headroom from a QA audit."""
    import argparse
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('command', choices=['review', 'review-headroom'])
    parser.add_argument('folder', type=Path)
    parser.add_argument('--ids', nargs='+', type=int)
    parser.add_argument('--include', nargs='*', type=int, default=[])
    args = parser.parse_args()
    if args.command == 'review-headroom':
        audit = json.loads(args.folder.read_text())
        imports = set(json.loads(mesh_stability.PINS.read_text())['imports'])
        ids = {int(sid) for sid, row in audit['rows'].items() if sid in imports
               and row.get('envelope_verdict', row['verdict']) == 'fail'}
        ids.update(args.include)
        if any(str(sid) not in imports for sid in ids):
            raise ValueError('headroom review includes an unregistered import')
        record = dict(audit_sha256=hashlib.sha256(args.folder.read_bytes()).hexdigest(), ids=sorted(ids))
        mesh_stability.HEADROOM.write_text(json.dumps(record, indent=2)+'\n')
        print(f'{len(ids)} reviewed headroom candidates')
        return
    rows = json.loads(MANIFEST.read_text())
    for sid in args.ids or (295, 323, 326, 335, 336, 405, 406, 407, 409, 432, 461):
        data = (args.folder / f'{sid}.MMD').read_bytes()
        end = int.from_bytes(data[4:8], 'little')
        rows[str(sid)] = hashlib.sha256(data[8:end]).hexdigest()
    MANIFEST.write_text(json.dumps(dict(sorted(rows.items(), key=lambda kv: int(kv[0]))), indent=2)+'\n')
    print(f'{MANIFEST.relative_to(MANIFEST.parents[3])}: {len(rows)} reviewed meshes')


if __name__ == '__main__':
    main()
