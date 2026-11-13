"""Fit imported rigid mesh pieces to a native DW1 skeleton and its programs.

The recipe identifies every mesh piece anatomically. Joint-to-joint pieces are
swung and stretched once during binding; playback uses the native SRT tracks.
Texture-copy commands are removed because the imported atlas has another layout.
"""
import copy
import math
import hashlib
import importlib
import importlib.util
import json
import tempfile
from pathlib import Path

import animsheet
import mmd
import motionstorage
import numeric as np
import retarget
from tools.models.field_animations import native_arms, native_battle, native_hands, native_jaws
from tools.models.field_animations.reviewed import reviewed

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / 'content/models/imports/native-bindings.json'
# the folder of the imported base models (`<id>.MMD`, or `<id>-<name>.MMD` as tools/models/edit.py get writes them) that a
# donor which is itself an imported species is read from (`donor_species`); content/models/imports/species.py sets it
BASE_MODELS = None


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


def spin_frame(axis, parent_rotation):
    """(rx, ry) in 1/4096 turn that make the bone's own z axis (the axis rz turns about: M = Rx·Ry·Rz) point along `axis`
    in the world, for a parent whose world rotation is `parent_rotation`, and the bone's world rotation (rz = 0)."""
    a = parent_rotation.T @ (axis / np.linalg.norm(axis))
    ry = math.asin(max(-1.0, min(1.0, a[0])))
    rx = math.atan2(-a[1], a[2])
    k = 4096 / (2 * math.pi)
    rx, ry = round(rx * k), round(ry * k)
    return rx, ry, parent_rotation @ np.array(mmd.rot_matrix(rx, ry, 0))


def add_spin(output, rig, spin):
    """Turn the recipe's spinning pieces in the field programs: each bone of `spin['bones']` (their own bones, after the donor's)
    gets a steady rz in the slots of `spin['quarters']` ({slot: quarter turns per loop body}; 90 degrees is one quarter, the
    facets of a drum repeat every quarter, so every loop closes). The momentum is set once a loop, at its first frame."""
    import animsheet
    model = mmd.MMD.parse(output, len(rig))
    first = len(rig) - len(spin['bones'])
    seen = set()
    for slot, quarters in spin['quarters'].items():
        slot = int(slot)
        index = model.anims.table[slot]
        if index in seen:
            raise ValueError(f'Native binding: slot {slot} shares its program')
        seen.add(index)
        anim = model.anims.anims[index]
        loop = [i for i in anim.instrs if i['op'] == 'loop_end']
        starts = [i for i in anim.instrs if i['op'] == 'key' and i['frame'] == 1 and i['bones']]
        length = loop[0]['frame'] - loop[0]['jump']
        for number, (bone, row) in enumerate(spin['bones'].items()):
            sign = row.get('sign', 1)
            starts[-1]['bones'].append(dict(bone=first + number, div=length, vals=dict(rz=sign * quarters * 1024)))
    return model.build()


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


def donor_model(recipe):
    """The donor's bytes: its extracted file, or (`donor_builder`) the model a builder script (a path from the repository root with `build(out_path)`) writes from the extraction
    (a boss whose own file lacks the care slots a partner plays: its partner copy has them), or (`donor_species`) the
    model of another imported species with its own field programs, read from BASE_MODELS."""
    if recipe.get('donor_species'):
        if BASE_MODELS is None:
            raise ValueError('Native binding: the imported donor needs BASE_MODELS (the imported base models folder)')
        found = sorted(Path(BASE_MODELS).glob(f"{recipe['donor_species']}.MMD")) + sorted(Path(BASE_MODELS).glob(f"{recipe['donor_species']}-*.MMD"))
        if not found:
            raise ValueError(f"Native binding: no model of the donor species {recipe['donor_species']} in {BASE_MODELS}")
        return found[0].read_bytes()
    if recipe.get('donor_builder'):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'donor.MMD'
            spec = importlib.util.spec_from_file_location('donor_builder', ROOT / recipe['donor_builder'])
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            builder.build(str(path))
            return path.read_bytes()
    return (Path(mmd.EXTRACTED) / recipe['model']).read_bytes()


def bind_pose(mesh, skeleton, recipe):
    """The source pose the pieces are fitted in: a frame of the bind slot, or, where the source only stands in a fighting
    stance, a reviewed pose of its own (`bind_pose`: per bone the local rotation, or rotation and translation, in 4096ths),
    such as the symmetric pose its mesh is modelled in (every rotation zero) with the knees and arms eased."""
    pose = animsheet.slot_frames(mesh, len(skeleton), recipe.get('bind_slot', 33))[0][recipe.get('bind_frame', 0)]
    for b, channels in recipe.get('bind_pose', {}).items():
        start = len(pose[int(b)]) - 6       # after the scale channels, when the pose has them
        pose[int(b)][start:start+len(channels)] = channels
    return pose


def bind(data, skeleton, recipe, placements=None):
    """(model bytes, proof). `placements`, when given, receives {source bone: (anchor, transform, destination)}: how each
    piece was moved, for the authoring step that carries effect points and the condition bubble along with their piece."""
    if digest(data) != recipe['source_sha256'] or digest(json.dumps(skeleton).encode()) != recipe['skeleton_sha256']:
        raise ValueError('Native binding: source model or skeleton differs')
    sid, donor_id = recipe['species'], recipe['donor']
    placements = {} if placements is None else placements
    mmd.exe().add_type(sid, skeleton)
    if recipe.get('donor_species'):
        # an imported donor's skeleton is its species file's, not the executable's
        mmd.exe().add_type(donor_id, json.loads(next((ROOT / 'content/species').glob(f'{donor_id}-*.json')).read_text())['model']['skeleton'])
    mesh = mmd.MMD.parse(data, len(skeleton))
    mesh.type = sid
    donor_bytes = donor_model(recipe)
    if reviewed(digest(donor_bytes)) != recipe['donor_sha256']:
        raise ValueError('Native binding: donor model differs')
    native = mmd.MMD.parse(donor_bytes, mmd.exe().bone_count[donor_id])
    native.type = donor_id
    native_rig = mmd.exe().skeleton[donor_id]
    source_pose = bind_pose(mesh, skeleton, recipe)
    native_pose = animsheet.slot_frames(native, len(native_rig), 0)[0][0]
    source_pose[0] = native_pose[0] = [4096]*3 + [0]*6
    sw = np.array(mmd.bone_matrices(mesh, source_pose))
    if recipe.get('source_yaw'):
        # a source posed turned about the vertical (a side-on stance) is turned to face forward whole before fitting
        c, s = math.cos(math.radians(recipe['source_yaw'])), math.sin(math.radians(recipe['source_yaw']))
        sw = np.array([np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]]) @ m for m in sw])
    nw = np.array(mmd.bone_matrices(native, native_pose))
    nw[:, :3, 3] *= recipe['scale']
    if recipe.get('spread_fit'):
        # pieces are fitted to the donor's joints where `spread` puts them (a body on proportions the donor lacks)
        moved = np.zeros((len(native_rig), 3))
        for b, (_, up) in enumerate(native_rig):
            moved[b] = (moved[up] if b and up >= 0 else 0) + np.array(recipe['spread'].get(str(b), [0, 0, 0]), dtype=float)
        nw[:, :3, 3] += moved
    mapping = {int(k): v for k, v in recipe['map'].items()}
    segments = {int(k): v for k, v in recipe['segments'].items()}
    if set(mapping) != {b for b, (obj, _) in enumerate(skeleton) if obj >= 0}:
        raise ValueError('Native binding: every source mesh must be assigned once')
    spin = recipe.get('spin')
    spun = [int(b) for b in spin['bones']] if spin else []
    extended = list(native_rig) + [(-1, mapping[b]) for b in spun]
    # riders: parts of the body that sit on a donor bone but move on bones of their own (a human torso, head and arms on a
    # mount's back), each a bone hung on a donor bone or on an earlier rider, pivoting where its lead piece sits
    riders = recipe.get('riders', [])
    rider_bone = {r['name']: len(extended)+k for k, r in enumerate(riders)}
    rider_of = {sb: rider_bone[r['name']] for r in riders for sb in r['pieces']}
    extended += [(-1, rider_bone.get(r['parent'], r['parent'])) for r in riders]
    def rider_pivot(index):
        r = riders[index-len(native_rig)-len(spun)]
        rule = recipe.get('pieces', {}).get(str(r['pivot']), {})
        return nw[rule.get('joint', mapping[r['pivot']]), :3, 3] + np.array(rule.get('offset', [0, 0, 0]))
    def rider_anchor(index):
        while index >= len(native_rig):
            index = extended[index][1]
        return index
    items = {b: [] for b in range(len(extended))}
    fitted = {}
    battle_pieces, lows = {}, [-1e9, -1e9]       # the pieces' fitting rotations, for battle_originals (native_battle.py)
    spin_poses = {}
    mirrors = {int(k): v for k, v in recipe.get('mirror', {}).items()}
    for sb, tb in sorted(mapping.items(), key=lambda item: item[0] in mirrors):
        if sb in mirrors:
            items[tb].append(mirror_piece(mesh, skeleton, sb, mirrors[sb], fitted, nw[tb]))
            twin = next(row for row in battle_pieces.get(mapping[mirrors[sb]], []) if row[0] == mirrors[sb])
            flip = [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]
            battle_pieces.setdefault(tb, []).append((sb, native_battle._mul(native_battle._mul(flip, twin[1]), flip), twin[2]))
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
        if 'stretch' in rule:
            # a piece scaled unevenly along the world axes (a boot widened and lengthened, not made taller)
            transform = np.diag(np.array(rule['stretch'], dtype=float)) @ transform
        if 'swing' in rule:
            # a held prop (a staff) turned from its direction in the source world onto the donor's own prop direction
            transform = np.array(retarget.swing(rule['swing']['from'], rule['swing']['to'])) @ transform
            if 'roll' in rule['swing']:
                # and turned about its own length (a flat crystal head shown face-on, not edge-on)
                k = np.array(rule['swing']['to'], dtype=float)
                k = k / np.linalg.norm(k)
                cr, sr = math.cos(math.radians(rule['swing']['roll'])), math.sin(math.radians(rule['swing']['roll']))
                cross = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
                transform = (np.eye(3)*cr + sr*cross + (1-cr)*np.outer(k, k)) @ transform
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
        lows[0] = max(lows[0], float(points[:, 1].max()))
        points = (points-anchor) @ transform.T + destination
        lows[1] = max(lows[1], float(points[:, 1].max()))
        joint = rider_pivot(rider_of[sb]) if sb in rider_of else nw[tb, :3, 3]
        if sb not in spun:
            battle_pieces.setdefault(rider_of.get(sb, tb), []).append(
                (sb, native_battle.polar(transform.tolist()), float(((points-joint)**2).sum())))
        if placements is not None:
            placements[sb] = (anchor, transform, destination)
        normals = np.array(mesh.tmd.obj_norms(obj)[:original.nnorm]).reshape(-1, 4)[:, :3]
        normals = normals @ np.linalg.inv(sw[sb, :3, :3]) @ np.linalg.inv(transform)
        if sb in spun:
            # a drum that turns about its own axis: its own bone below the donor's, at the drum's centre, its z axis along the drum
            axis = transform @ sw[sb, :3, :3] @ np.array(spin['bones'][str(sb)]['axis'], dtype=float)
            centre = points.mean(axis=0)
            rx, ry, frame = spin_frame(axis, nw[tb, :3, :3])
            bone = len(native_rig) + spun.index(sb)
            offset = (centre-nw[tb, :3, 3]) @ nw[tb, :3, :3]
            spin_poses[bone] = [rx, ry, 0] + [round(v) for v in offset]
            items[bone].append((original, (points-centre) @ frame, normals @ frame))
            fitted[sb] = (points, normals)
            continue
        if sb in rider_of:
            anchor_bone = rider_anchor(rider_of[sb])
            items[rider_of[sb]].append((original, (points-rider_pivot(rider_of[sb])) @ np.linalg.inv(nw[anchor_bone, :3, :3]).T,
                                        normals @ nw[anchor_bone, :3, :3]))
            fitted[sb] = (points, normals)
            continue
        items[tb].append((original, (points-nw[tb, :3, 3]) @ np.linalg.inv(nw[tb, :3, :3]).T, normals @ nw[tb, :3, :3]))
        fitted[sb] = (points, normals)
    for r in riders:
        bone = rider_bone[r['name']]
        parent = extended[bone][1]
        origin = rider_pivot(parent) if parent >= len(native_rig) else nw[parent, :3, 3]
        spin_poses[bone] = [0, 0, 0] + [round(v) for v in (rider_pivot(bone)-origin) @ nw[rider_anchor(bone), :3, :3]]
    tmd, rig = mmd.TMD(), []
    for bone, (_, parent) in enumerate(extended):
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
        for bone in sorted(spin_poses):
            animation.pose.append(([4096]*3 if animation.has_scale else []) + spin_poses[bone])
    slots = list(result.anims.table)
    wanted = max([61, 46+len(recipe['technique_slots'])] + [int(k)+1 for k in recipe.get('extra_slots', {})])
    result.anims.table += [None]*max(0, wanted-len(slots))
    for destination, source in enumerate(recipe['technique_slots'], 46):
        if slots[source] is None:
            raise ValueError(f'Native binding: missing technique {source}')
        result.anims.table[destination] = slots[source]
    for destination, source in recipe.get('extra_slots', {}).items():
        result.anims.table[int(destination)] = slots[source]
    output = result.build()
    if recipe.get('battle_originals'):
        rest = animsheet.slot_frames(mmd.MMD.parse(output, len(rig)), len(rig), 0)[0][0]
        yaw = None
        if recipe.get('source_yaw'):
            cy, sy = math.cos(math.radians(recipe['source_yaw'])), math.sin(math.radians(recipe['source_yaw']))
            yaw = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
        battle = native_battle.context(mesh, skeleton, source_pose, yaw, rig, rest, battle_pieces,
                                       {rider_bone[r['name']]: r['pivot'] for r in riders}, mapping, lows)
    if recipe.get('arm_pump'):
        output = native_arms.run_arms(mmd.MMD.parse(output, len(rig)), rig, recipe['arm_pump'])
    if recipe.get('pace'):
        # slots the donor lacks or shares (a condition walk that is the walk) rebuilt from one of its own clips, retimed
        # by pace.py with its speed, slip and floor checks (the rows are pace.json rows)
        from tools.models.field_animations import pace
        rows = {slot: dict(row, original_run=dict(map=recipe['map'], limbs=recipe['limbs'], bind_slot=recipe.get('bind_slot', 33)))
                if row.get('original_run') else row for slot, row in recipe['pace'].items()}
        output = pace.retime(output, rig, 9000+sid, rows, (data, skeleton))[0]
    if recipe.get('hands'):
        # hands that trail the forearm's swing, for a donor whose hand is rigid with it (native_hands.py)
        output = native_hands.run_hands(mmd.MMD.parse(output, len(rig)), rig, recipe['hands'])
    if recipe.get('jaws'):
        # the source's own mouth work replayed on the donor bones that carry the jaw pieces (native_jaws.py)
        output = native_jaws.run_jaws(mmd.MMD.parse(output, len(rig)), rig, recipe['jaws'], mesh, skeleton, source_pose, placements)
    patch, chibi_proof = recipe['species_patch'], None
    if recipe.get('chibi'):
        # the chibi proportions of the species' row (chibi.json), as the last stage: its head, hands and feet grow and its
        # legs shorten on the donor's rig, the floor and the speeds are checked again, the effect points ride along
        from tools.models.field_animations import chibi
        spec = recipe['chibi']
        row = json.loads(chibi.MANIFEST.read_text())[str(spec.get('row', sid))]
        output, report, scales, k, used = chibi.reshape_bound(output, rig, 9000+sid, recipe['map'], row, spec.get('factors'))
        patch = dict(patch, **chibi.species_patch(patch, scales, k))
        chibi_proof = dict(factors=used['factors'], fit=used['fit'], trim=used['trim'], final_scale=report['final_scale'],
                           speeds=report['speeds'], floors=report['floors'])
    gait_proof = None
    if recipe.get('gait'):
        # the legs planted on the floor under the donor's own trunk, wings, tail and arms, written over the final (chibi) shape
        gait = importlib.import_module(f"tools.models.field_animations.{recipe['gait']}")
        output, gait_proof = gait.build(output, rig)
    if spin:
        # drums that turn about their own axis (their bones below the donor's), written last: no step above reshapes them
        output = add_spin(output, rig, spin)
    battle_proof = None
    if recipe.get('battle_originals'):
        # the source game's own battle clips on the donor rig, for the slots that measured sound (native_battle.py)
        output, battle_proof = native_battle.apply(output, battle, recipe['battle_originals']['slots'])
    storage = motionstorage.require(output, len(rig))
    proof = dict(species=sid, source_sha256=digest(data), output_sha256=digest(output),
                 donor=donor_id, generated_skeleton=rig, storage=storage, species_patch=patch)
    if chibi_proof:
        proof['chibi'] = chibi_proof
    if gait_proof:
        proof['gait'] = gait_proof['checks']
    if battle_proof:
        proof['battle_originals'] = battle_proof
    return output, proof


def build(data, skeleton):
    recipes = json.loads(MANIFEST.read_text())
    matches = [r for r in recipes.values() if r['source_sha256'] == digest(data)]
    if len(matches) != 1:
        raise ValueError('Native binding: no unique reviewed source')
    return bind(data, skeleton, matches[0])
