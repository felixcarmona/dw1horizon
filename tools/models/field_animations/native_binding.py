"""Fit imported rigid mesh pieces to a native DW1 skeleton and its programs.

The recipe identifies every mesh piece anatomically. Joint-to-joint pieces are
swung and stretched once during binding; playback uses the native SRT tracks.
Texture-copy commands are removed because the imported atlas has another layout.
"""
import copy
import math
import hashlib
import json
from pathlib import Path

import animsheet
import mmd
import motionstorage
import numeric as np
import retarget

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / 'content/models/imports/native-bindings.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def spread_offsets(recipe, native):
    """{native bone: translation added to its start pose in every program}: joints moved apart (a wide armored
    body on narrow native hips). The recipe gives them in the world of the native rest pose; they are written in the
    parent's frame. Keys move by speed, so the offset in each program's start pose holds through the whole program."""
    if not recipe.get('spread'):
        return {}
    rig = mmd.exe().skeleton[native.type]
    pose = animsheet.slot_frames(native, len(rig), 0)[0][0]
    pose[0] = [4096]*3 + [0]*6
    world = np.array(mmd.bone_matrices(native, pose))
    out = {}
    for b, offset in recipe['spread'].items():
        parent = world[rig[int(b)][1], :3, :3]
        parent = parent / np.linalg.norm(parent, axis=0)
        out[int(b)] = [round(v) for v in (parent.T @ np.array(offset)).tolist()]
    return out


def _mirror_order(own, other, tolerance):
    """For every point of `own`, the index of the point of `other` that is its mirror across x (twins)."""
    order = []
    for x, y, z in own:
        distance, index = min(((x+a)**2 + (y-b)**2 + (z-c)**2, i) for i, (a, b, c) in enumerate(other))
        if distance > tolerance**2:
            raise ValueError('Native binding: mirrored pieces are not twins')
        order.append(index)
    return order


def mirror_piece(mesh, skeleton, sb, twin, fitted, frame):
    """One side's piece placed as the exact mirror of its twin's fitted piece. A source posed asymmetrically (a
    guard stance) binds each side in a different orientation: the arms and pads then read uneven at rest. The source
    pieces are exact mirrors of each other, so the twin's fitted world shape is reflected across the body's
    middle and stored in this bone's frame (the native rig is mirror symmetric at rest)."""
    original = mesh.tmd.objects[skeleton[sb][0]]
    other = mesh.tmd.objects[skeleton[twin][0]]
    own_points = [v[:3] for v in mesh.tmd.obj_verts(skeleton[sb][0])]
    twin_points = [v[:3] for v in mesh.tmd.obj_verts(skeleton[twin][0])]
    own_normals = [v[:3] for v in mesh.tmd.obj_norms(skeleton[sb][0])[:original.nnorm]]
    twin_normals = [v[:3] for v in mesh.tmd.obj_norms(skeleton[twin][0])[:other.nnorm]]
    points, normals = fitted[twin]
    flip = np.array([-1., 1., 1.])
    points = np.array([points[i].tolist() for i in _mirror_order(own_points, twin_points, 2)]) * flip
    normals = np.array([normals[i].tolist() for i in _mirror_order(own_normals, twin_normals, 80)]) * flip
    local = (points-frame[:3, 3]) @ np.linalg.inv(frame[:3, :3]).T
    return original, local, normals @ frame[:3, :3]


def bind(data, skeleton, recipe):
    if digest(data) != recipe['source_sha256'] or digest(json.dumps(skeleton).encode()) != recipe['skeleton_sha256']:
        raise ValueError('Native binding: source model or skeleton differs')
    sid, donor_id = recipe['species'], recipe['donor']
    mmd.exe().add_type(sid, skeleton)
    mesh = mmd.MMD.parse(data, len(skeleton))
    mesh.type = sid
    donor_bytes = (Path(mmd.EXTRACTED) / recipe['model']).read_bytes()
    if digest(donor_bytes) != recipe['donor_sha256']:
        raise ValueError('Native binding: donor model differs')
    native = mmd.MMD.parse(donor_bytes, mmd.exe().bone_count[donor_id])
    native.type = donor_id
    native_rig = mmd.exe().skeleton[donor_id]
    source_pose = animsheet.slot_frames(mesh, len(skeleton), recipe.get('bind_slot', 33))[0][0]
    native_pose = animsheet.slot_frames(native, len(native_rig), 0)[0][0]
    source_pose[0] = native_pose[0] = [4096]*3 + [0]*6
    sw = np.array(mmd.bone_matrices(mesh, source_pose))
    if recipe.get('source_yaw'):
        # a source posed turned about the vertical (a side-on stance) is turned to face forward whole before fitting
        c, s = math.cos(math.radians(recipe['source_yaw'])), math.sin(math.radians(recipe['source_yaw']))
        sw = np.array([np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]]) @ m for m in sw])
    nw = np.array(mmd.bone_matrices(native, native_pose))
    nw[:, :3, 3] *= recipe['scale']
    mapping = {int(k): v for k, v in recipe['map'].items()}
    segments = {int(k): v for k, v in recipe['segments'].items()}
    if set(mapping) != {b for b, (obj, _) in enumerate(skeleton) if obj >= 0}:
        raise ValueError('Native binding: every source mesh must be assigned once')
    items = {b: [] for b in range(len(native_rig))}
    fitted = {}
    mirrors = {int(k): v for k, v in recipe.get('mirror', {}).items()}
    for sb, tb in sorted(mapping.items(), key=lambda item: item[0] in mirrors):
        if sb in mirrors:
            items[tb].append(mirror_piece(mesh, skeleton, sb, mirrors[sb], fitted, nw[tb]))
            continue
        obj = skeleton[sb][0]
        original = mesh.tmd.objects[obj]
        points = np.array(mesh.tmd.obj_verts(obj))[:, :3] @ sw[sb, :3, :3].T + sw[sb, :3, 3]
        rule = recipe.get('pieces', {}).get(str(sb), {})
        factor = rule.get('scale', recipe['mesh_scale'])
        transform = np.eye(3) * factor
        direction = rule.get('direction', [sb, segments[sb]] if sb in segments else None)
        if direction:
            start, end = direction
            a = sw[end, :3, 3] - sw[start, :3, 3]
            b = nw[mapping[end], :3, 3] - nw[mapping[start], :3, 3]
            axis = a / np.linalg.norm(a)
            transform = np.array(retarget.swing(a.tolist(), b.tolist())) @ (
                np.eye(3)*factor + (np.linalg.norm(b)/np.linalg.norm(a)-factor)*np.outer(axis, axis))
            if rule.get('membrane'):
                # A bat's web starts in a different rest plane from bird feathers.
                # Roll it about the fitted spar so its trailing edge lies behind it.
                axis = b / np.linalg.norm(b)
                transverse = transform @ np.array(rule['membrane'])
                transverse -= axis*(transverse @ axis)
                trailing = np.array([0., 0., 1.])
                trailing -= axis*(trailing @ axis)
                transform = np.array(retarget.swing(transverse.tolist(), trailing.tolist())) @ transform
        if 'follow' in rule:
            # a rigid end piece (a fist) turns with the fitted segment it hangs from, without its stretch
            start = rule['follow']
            a = sw[segments[start], :3, 3] - sw[start, :3, 3]
            b = nw[mapping[segments[start]], :3, 3] - nw[mapping[start], :3, 3]
            transform = np.array(retarget.swing(a.tolist(), b.tolist())) @ transform
            if 'roll' in rule:
                # turned about that segment too (a glove whose palm the source posed facing forward)
                k = b / np.linalg.norm(b)
                cr, sr = math.cos(math.radians(rule['roll'])), math.sin(math.radians(rule['roll']))
                cross = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
                transform = (np.eye(3)*cr + sr*cross + (1-cr)*np.outer(k, k)) @ transform
        if 'yaw' in rule:
            # a foot posed turned out in the source's stance, turned about the vertical to face forward
            c, s = math.cos(math.radians(rule['yaw'])), math.sin(math.radians(rule['yaw']))
            transform = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]) @ transform
        if 'swing' in rule:
            # a held prop (a staff) turned from its direction in the source world onto the donor's own prop direction
            transform = np.array(retarget.swing(rule['swing']['from'], rule['swing']['to'])) @ transform
        if 'aim' in rule:
            # a piece set whole in a reviewed orientation of the native rest world (shoulder armour moved from the
            # source's swinging upper arm onto the chest): its own y axis along aim y, its x axis turned toward aim x
            source = sw[sb, :3, :3] / np.linalg.norm(sw[sb, :3, :3], axis=0)
            y = np.array(rule['aim']['y'], dtype=float)
            y = y / np.linalg.norm(y)
            x = np.array(rule['aim']['x'], dtype=float)
            x = x - y*(x @ y)
            x = x / np.linalg.norm(x)
            transform = np.column_stack([x, y, np.cross(x, y)]) @ source.T * factor
        anchor = np.array(rule.get('anchor', sw[sb, :3, 3].tolist()))
        destination = nw[rule.get('joint', tb), :3, 3] + np.array(rule.get('offset', [0, 0, 0]))
        points = (points-anchor) @ transform.T + destination
        local = (points-nw[tb, :3, 3]) @ np.linalg.inv(nw[tb, :3, :3]).T
        normals = np.array(mesh.tmd.obj_norms(obj)[:original.nnorm]).reshape(-1, 4)[:, :3]
        normals = normals @ np.linalg.inv(sw[sb, :3, :3]) @ np.linalg.inv(transform) @ nw[tb, :3, :3]
        items[tb].append((original, local, normals))
        fitted[sb] = (points, normals @ np.linalg.inv(nw[tb, :3, :3]))
    tmd, rig = mmd.TMD(), []
    for bone, (_, parent) in enumerate(native_rig):
        if not items[bone]:
            rig.append([-1, parent])
            continue
        obj = mmd.TMDObject()
        obj.vert_start, obj.norm_start = len(tmd.verts), len(tmd.norms)
        obj.scale = 0
        nv = nn = 0
        for original, points, normals in items[bone]:
            tmd.verts.extend(tuple([round(v) for v in p]+[0]) for p in points)
            normals = normals / np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1)*4096
            tmd.norms.extend(tuple([round(v) for v in p]+[0]) for p in normals)
            for prim in original.prims:
                polygon = prim.decode()
                polygon['verts'] = [v+nv for v in polygon['verts']]
                if polygon.get('norms'):
                    polygon['norms'] = [v+nn for v in polygon['norms']]
                obj.prims.append(mmd.Prim.encode(polygon))
            nv += len(points)
            nn += len(normals)
        obj.nvert, obj.nnorm = nv, nn
        rig.append([len(tmd.objects), parent])
        tmd.objects.append(obj)
    result = copy.deepcopy(native)
    result.tmd = tmd
    spread = spread_offsets(recipe, native)
    for animation in result.anims.anims:
        for pose in animation.pose:
            pose[-3:] = [round(v*recipe['scale']) for v in pose[-3:]]
        for bone, offset in spread.items():
            pose = animation.pose[bone - 1]
            pose[-3:] = [v + o for v, o in zip(pose[-3:], offset)]
        for instruction in animation.instrs:
            if instruction['op'] == 'key':
                for group in instruction['bones']:
                    for channel in group['vals']:
                        if channel in ('tx', 'ty', 'tz'):
                            group['vals'][channel] = round(group['vals'][channel]*recipe['scale'])
        animation.instrs = [i for i in animation.instrs if i['op'] != 'tex']
        animation.tail = b''
    slots = list(result.anims.table)
    result.anims.table += [None]*max(0, 61-len(slots))
    for destination, source in enumerate(recipe['technique_slots'], 46):
        if slots[source] is None:
            raise ValueError(f'Native binding: missing technique {source}')
        result.anims.table[destination] = slots[source]
    for destination, source in recipe.get('extra_slots', {}).items():
        result.anims.table[int(destination)] = slots[source]
    output = result.build()
    storage = motionstorage.require(output, len(rig))
    return output, dict(species=sid, source_sha256=digest(data), output_sha256=digest(output),
                        donor=donor_id, generated_skeleton=rig, storage=storage,
                        species_patch=recipe['species_patch'])


def build(data, skeleton):
    recipes = json.loads(MANIFEST.read_text())
    matches = [r for r in recipes.values() if r['source_sha256'] == digest(data)]
    if len(matches) != 1:
        raise ValueError('Native binding: no unique reviewed source')
    return bind(data, skeleton, matches[0])
