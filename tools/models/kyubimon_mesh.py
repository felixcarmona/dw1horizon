"""Kyubimon-only final surface repair, after the reviewed fan reconstruction.

The proximal cap and the end's inset cap occupied the same attachment ring.
Replace that overlap by a single shared four-corner ring, retaining side UVs
and the flame cards. Tail provenance remains available after rebinding.
"""
import itertools
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mmd
from tools.models import mesh_fan, mesh_stability

# The fan's socket moves this far back from the rear thighs along the tail
# stalk (which grows to reach it), so the full-width fan clears the legs.
SOCKET = (30, -10)
# Extra fan yaw/roll (4096ths) eased over the two clips that swing it into a leg.
CLEAR_SWAY = {8: (200, 500), 52: (500, 100)}


def weld_fan(model):
    obj = model.tmd.objects[9]
    if len(obj.prims) != 224:
        raise ValueError('fan weld requires the reviewed 224-packet fan')
    original = list(model.tmd.obj_verts(9))
    prims = obj.prims
    groups = mesh_fan.packet_groups()
    vertices, packets, provenance = [], [], []
    sources = []
    removed = []
    join_planes = []
    for tail, group in enumerate(groups):
        remap = {}
        if tail < 7:
            proximal = mesh_fan.JOINS[tail][0]
            base_ids = sorted({v for pi in proximal for v in prims[pi].decode()['verts']})
            ring = [v for v in base_ids if original[v][0] > 50]
            join_x = round(sum(original[v][0] for v in ring)/len(ring))
            join_planes.append(join_x)
            start = 84+20*tail
            # Root outer corners are the vertices shared with the long sides.
            end_ids = sorted({v for pi in range(start,start+20) for v in prims[pi].decode()['verts']})
            outer = [end_ids[k] for k in (8,9,12,14)]
            best = min(itertools.permutations(ring), key=lambda r: sum(
                sum((original[a][k]-original[b][k])**2 for k in range(3))
                for a,b in zip(outer,r)))
            remap.update(zip(outer,best))
            # The proximal cap is the only all-distal packet. End inset caps
            # are alternating packets between the root and long side surfaces.
            caps = {pi for pi in proximal if all(original[v][0]>50 for v in prims[pi].decode()['verts'])}
            caps.update(start+k for k in (9,11,13,15))
        else:
            caps = set()
        mapping = {}
        root_id = None
        first = len(packets)
        for pi in group:
            if pi in caps:
                removed.append(pi)
                continue
            d = prims[pi].decode()
            for k, vi in enumerate(d['verts']):
                vi = remap.get(vi,vi)
                if vi not in mapping:
                    value = original[vi]
                    if value[0] < 5:
                        if root_id is None:
                            root_id = len(vertices)
                            vertices.append((0,0,0,0))
                        mapping[vi] = root_id
                    else:
                        mapping[vi] = len(vertices)
                        if tail < 7 and vi in ring:
                            value = (join_x,)+tuple(value[1:])
                        vertices.append(value)
                d['verts'][k] = mapping[vi]
            # A cone apex makes the source's short root edges redundant.
            # Keep exactly the nonzero GPU halves, with their corner data.
            halves = mesh_stability.split_quad(mmd.Prim.encode(d)) if len(d['verts']) == 4 else [mmd.Prim.encode(d)]
            nonzero = [p for p in halves if len(set(p.decode()['verts'])) == 3]
            if not nonzero:
                removed.append(pi)
                continue
            output = nonzero if len(nonzero) != len(halves) else [mmd.Prim.encode(d)]
            packets.extend(output)
            sources.extend([pi]*len(output))
        provenance.append(list(range(first,len(packets))))
    pools = [list(model.tmd.obj_verts(i)) for i in range(len(model.tmd.objects))]
    pools[9] = vertices
    obj.prims = packets
    model.tmd.verts = []
    for ob, pool in zip(model.tmd.objects,pools):
        ob.vert_start, ob.nvert = len(model.tmd.verts),len(pool)
        model.tmd.verts.extend(pool)
    return dict(removed_caps=removed,groups=provenance,join_planes=join_planes,source_packets=sources)


def apply(model, bones):
    from tools.models.mesh_cleanup import translate_bone, transform_piece
    if tuple(bones[15]) != (9,14) or tuple(bones[14]) != (8,1):
        raise ValueError('tail repair requires the reviewed fan/socket binding')
    dx, dz = SOCKET
    translate_bone(model,15,0,dx)
    translate_bone(model,15,2,dz)
    transform_piece(model,8,scale=((84+dx)/84,1,1),shear_zx=dz/84)
    report = dict(tail_socket_extension=[dx,0,dz],tail_fan=mesh_fan.apply(model))
    report['fan_surface'] = weld_fan(model)
    report['sway_slots'] = finish(model,bones)
    report['split_quads'] = split_bends(model,report['fan_surface'])
    mesh_stability.compact_pools(model)
    import coldsplit
    resident = len(coldsplit.split(model.build(),len(bones))[0])
    if resident > 94882:
        raise ValueError(f'Kyubimon repair exceeds its incoming resident size: {resident}')
    report['resident_bytes'] = resident
    return report


def fan_sway(value, center=0, amplitude=200):
    """Periodic smooth fan sway without the donor's inverted tail windup."""
    return center+round(amplitude*math.sin((value-center)*2*math.pi/4096))


def finish(model, bones):
    from tools.models import mesh_pose
    dx, dz = SOCKET
    ob = model.tmd.objects[8]
    for i, v in enumerate(model.tmd.obj_verts(8)):
        if i == 21:
            model.tmd.verts[ob.vert_start+i] = (61+dx,0,-34+dz,0)
        elif v[0] > 50+dx:
            model.tmd.verts[ob.vert_start+i] = (50+dx,)+tuple(v[1:])
    def mapper(slot, tick, poses):
        p = poses[tick]
        values = {(15,a):fan_sway(p[15][3+a],103 if a==1 else 0) for a in range(3)}
        if slot in (8,52):
            weight = mesh_pose.smoothstep(tick/6)*(1-mesh_pose.smoothstep((tick-(len(poses)-7))/6))
            yaw, roll = CLEAR_SWAY[slot]
            values[15,1] += round(yaw*weight)
            values[15,2] += round(roll*weight)
        if slot == 42:
            values[2,1] = fan_sway(p[2][4],886,400)
        return values
    return mesh_pose.edit(model,bones,mapper)


def split_bends(model, fan):
    """Fund independent GPU halves from this model's removed cap packets."""
    selected = {(r['object'],r['primitive']) for r in mesh_stability.bent_quads(model,10)}
    for oi, ob in enumerate(model.tmd.objects):
        output, source, mapping = [], [], {}
        for pi, prim in enumerate(ob.prims):
            first = len(output)
            output.extend(mesh_stability.split_quad(prim) if (oi,pi) in selected else [prim])
            mapping[pi] = list(range(first,len(output)))
            if oi == 9:
                source.extend([fan['source_packets'][pi]]*(len(output)-first))
        ob.prims = output
        if oi == 9:
            fan['groups'] = [[q for p in group for q in mapping[p]] for group in fan['groups']]
            fan['source_packets'] = source
    return len(selected)
