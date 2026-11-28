"""Restore deleted source triangles on an unchanged indexed vertex pool.

Offline authoring only (NumPy and NetworkX required). Keep the fitted vertices, texture and all animations;
lossless quad pairing pays for restored faces before considering edge collapse.
Refuse remapped pools and texture lineage ambiguity rather than guessing.
"""
import copy
import itertools
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools'),str(ROOT)]
from collections import defaultdict
import numpy as np
import mmd
import mmdport
import motionstorage
from tools.models.repair_beelzemon import pair_triangles


def triangles(prims):
    for p in prims:
        for corners in [(0,1,2)]+([(1,3,2)] if len(p['verts']) == 4 else []):
            t = copy.deepcopy(p)
            for field in ('verts','norms','uvs'):
                t[field] = [p[field][c] for c in corners] if p[field] is not None else None
            yield t


def face(d, semi=False):
    """Decoded primitive -> build_tmd face. Unlit faces carry no normals and keep their flat colour; untextured faces
    carry no UVs (build_tmd reads None as either)."""
    p = dict(verts=d['verts'],norms=d['norms'] or None,uvs=d['uv'] or None,semi=semi)
    if p['uvs']:
        p['row'] = (d['cba']>>6)-488
    else:
        p['row'] = None
    if not p['norms'] or not p['uvs']:
        p['color'] = tuple(d['colors'][0][:3])
    return p


def key(p):
    corners = list(zip(p['verts'],map(tuple,p['uvs'] or [()]*len(p['verts']))))
    return min(tuple(corners[k:]+corners[:k]) for k in range(3))


def vertex_key(p):
    v = list(p['verts'])
    return min(tuple(v[k:]+v[:k]) for k in range(3))


def touches(mask, p):
    us, vs = [u for u,_ in p['uvs']], [v for _,v in p['uvs']]
    return bool(mask[min(vs):max(vs)+1, min(us):max(us)+1].any())


def ordered_alignment(x, y):
    """Survivors of a compacted pool keep their order: the increasing source subsequence nearest to y, over a
    scan of uniform scales (the import scale is unknown here)."""
    best = None
    for scale in np.linspace(.5,2,151):
        distance = np.linalg.norm(x[:,None]*scale-y[None],axis=2)
        cost = np.full((len(x)+1,len(y)+1),np.inf)
        cost[:,0] = 0
        for i in range(1,len(x)+1):
            for j in range(1,min(i,len(y))+1):
                cost[i,j] = min(cost[i-1,j],cost[i-1,j-1]+distance[i-1,j-1])
        if best is None or cost[-1,-1] < best[0]:
            i,j,keep = len(x),len(y),[]
            while j:
                if cost[i,j] == cost[i-1,j]:
                    i -= 1
                else:
                    keep.append(i-1)
                    i,j = i-1,j-1
            best = cost[-1,-1],keep[::-1]
    return best[1]


def pool_mapping(x, y, max_residual, max_dropped=3):
    """Source vertex index -> pool index. An unchanged pool maps to itself; a pool the reducer compacted (order
    kept) maps the survivors and appends the dropped ones. Up to max_dropped dropped vertices are searched
    exhaustively, more through ordered_alignment. The kept vertices must fit one affine transform within
    max_residual units, or nothing is mapped."""
    def fitted(keep):
        design = np.column_stack([x[keep],np.ones(len(keep))])
        fit,_,rank,_ = np.linalg.lstsq(design,y,rcond=None)
        return fit, rank == 4 and float(np.max(np.linalg.norm(design@fit-y,axis=1))) <= max_residual
    def mapped(keep, fit):
        mapping, extra = [], len(y)
        for i in range(len(x)):
            if i in keep:
                mapping.append(keep.index(i))
            else:
                mapping.append(extra)
                extra += 1
        return mapping,fit
    dropped = len(x)-len(y)
    if dropped < 0:
        return None,None
    if dropped > max_dropped:
        keep = ordered_alignment(x,y)
        fit,ok = fitted(keep)
        return mapped(keep,fit) if ok else (None,None)
    for drop in itertools.combinations(range(len(x)),dropped):
        keep = [i for i in range(len(x)) if i not in drop]
        fit,ok = fitted(keep)
        if ok:
            return mapped(keep,fit)
    return None,None


def restore(source, data, texture, bones, objects, max_packet_growth=1024, max_residual=3):
    model = mmd.MMD.parse(data,bones)
    acting = model.anims.build()
    before_primitives = sum(len(o.prims) for o in model.tmd.objects)
    src = mmdport.build_tmd(source,log=lambda *a:None)
    if len(source.bones) != len(model.tmd.objects) or not all(b['verts'] for b in source.bones):
        raise ValueError('source objects do not retain a direct indexed mapping')
    tim = mmd.Tim4(texture)
    if len(bytes(source.idx)) != len(bytes(tim.idx)):
        raise ValueError('source texture layout differs')
    # A later texture edit (Gallantmon's full-resolution eyes) may reuse texels of deleted faces: those faces stay out.
    edited = (np.frombuffer(bytes(source.idx),np.uint8) != np.frombuffer(bytes(tim.idx),np.uint8)).reshape(-1,256)
    def faces(prims):
        return list(triangles([face(q.decode()) for q in prims]))
    model_rows = defaultdict(set)
    for oi,obj in enumerate(model.tmd.objects):
        kept = {key(t):t for t in faces(src.objects[oi].prims) if t['uvs']}
        for t in faces(obj.prims):
            if t['uvs'] and key(t) in kept:
                # every face kept from the source must still read its own texels, or the layout moved
                if touches(edited,t):
                    raise ValueError('source texture layout differs')
                model_rows[kept[key(t)]['row']].add(t['row'])
    mesh, restored, skipped, removed = [], {}, {}, {}
    for oi,obj in enumerate(model.tmd.objects):
        bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,
                    verts=[v[:3] for v in model.tmd.obj_verts(oi)],
                    norms=[v[:3] for v in model.tmd.obj_norms(oi)[:obj.nnorm]],prims=[])
        for p in obj.prims:
            bone['prims'].append(face(p.decode(),bool(p.mode&2)))
        if oi in objects:
            x = np.array([v[:3] for v in src.obj_verts(oi)],float)
            y = np.array(bone['verts'],float)
            mapping,fit = pool_mapping(x,y,max_residual)
            if mapping is None:
                raise ValueError(f'object {oi}: vertex pool differs (no order-kept affine fit)')
            compacted = len(x) != len(y)
            for i,j in enumerate(mapping):
                if j >= len(bone['verts']):
                    # a vertex the reducer collapsed comes back where the source had it
                    bone['verts'].append(tuple(int(round(c)) for c in np.append(x[i],1)@fit))
            current = {key(p):p for p in triangles(bone['prims'])}
            # a face whose UVs a later edit moved (same oriented corners) is still there
            present = {vertex_key(p) for p in triangles(bone['prims'])}
            source_prims = []
            for original in src.objects[oi].prims:
                p = face(original.decode(),bool(original.mode&2))
                p['verts'] = [mapping[v] for v in p['verts']]
                source_prims.append(p)
            full = list(triangles(source_prims))
            if compacted:
                # the faces the collapse made are replaced by the source's own faces
                ours = {key(p) for p in full} | {vertex_key(p) for p in full}
                kept_faces = [t for t in triangles(bone['prims']) if key(t) in ours or vertex_key(t) in ours]
                removed[oi] = len(list(triangles(bone['prims']))) - len(kept_faces)
                bone['prims'] = kept_faces
            rows = defaultdict(set)
            for p in full:
                if key(p) in current:
                    rows[p['row']].add(current[key(p)]['row'])
            for p in full:
                if key(p) in current or vertex_key(p) in present or len(set(p['verts'])) < 3:
                    continue  # kept, re-textured, or a degenerate face that draws nothing
                if p['uvs'] and touches(edited,p):
                    skipped[oi] = skipped.get(oi,0)+1
                    continue
                if p['row'] is None:
                    pass  # untextured: its flat colour needs no palette
                elif not rows[p['row']]:
                    # no kept face of this object uses the row: the model-wide lineage decides
                    rows[p['row']] = model_rows[p['row']] or {
                        r for r,colors in enumerate(tim.pal) if list(colors) == list(source.pals[p['row']])}
                if p['row'] is not None and len(rows[p['row']]) != 1:
                    raise ValueError(f'object {oi}: ambiguous palette lineage {p["row"]} -> {sorted(rows[p["row"]])}')
                p = copy.deepcopy(p)
                if p['row'] is not None:
                    p['row'] = next(iter(rows[p['row']]))
                original_norms = p['norms']
                p['norms'] = [] if original_norms else None
                for n in original_norms or []:
                    normal = np.asarray(src.obj_norms(oi)[n][:3],float) @ np.linalg.pinv(fit[:3]).T
                    length = float(np.linalg.norm(normal))
                    normal = tuple(int(round(v*4096/max(length,1e-9))) for v in normal)
                    if normal not in bone['norms']:
                        bone['norms'].append(normal)
                    p['norms'].append(bone['norms'].index(normal))
                bone['prims'].append(p)
                restored[oi] = restored.get(oi,0)+1
        pair_triangles(bone,max_angle=.5)
        mesh.append(bone)
    model.tmd = mmdport.build_tmd(mmdport.Model('restored',mesh,tim.idx,tim.pal,{}),log=lambda *a:None)
    result = model.build()
    if model.anims.build() != acting:
        raise ValueError('animation changed')
    if max(o.nvert for o in model.tmd.objects) > 172:
        raise ValueError('object vertex target exceeded')
    primitive_count = sum(len(o.prims) for o in model.tmd.objects)
    packet_growth = max(0,primitive_count-before_primitives)*52
    if packet_growth > max_packet_growth:
        raise ValueError(f'packet growth {packet_growth} exceeds {max_packet_growth}; revise the authoring budget')
    storage = motionstorage.require(result,bones)
    return result,dict(restored_triangles=restored,skipped_edited_texels=skipped,removed_collapse_faces=removed,primitives=primitive_count,packet_growth_bound=packet_growth,storage=storage)


def main():
    import argparse
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from tools.models import edit
    import import_batch
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('species',type=int)
    parser.add_argument('--games',type=Path,required=True)
    parser.add_argument('--from',dest='from_dir',type=Path)
    parser.add_argument('--objects',type=int,nargs='+',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--max-packet-growth',type=int,default=1024,
                        help='bytes of draw packets the restored faces may add (52 per primitive; default 1024)')
    parser.add_argument('--max-residual',type=float,default=3,
                        help='game units a kept vertex may sit off the fitted source pool (default 3; rounding after a size pass)')
    args = parser.parse_args()
    row, = edit.rows(edit.load(edit.MODELS),[str(args.species)])
    # The importer recipe is the one behind the delta source (through any size recipe): species renamed
    # after import (Armormon -> Assaultmon) keep the source game's name there.
    source_path = row['mmd']['sources'][0]['path']
    sizes = {r['target']:r['source'] for r in edit.load(edit.SIZES)['files']}
    while source_path in sizes:
        source_path = sizes[source_path]
    recipe = next(r for r in edit.load(edit.BASE/'import-batches.json')['recipes']
                  if f'{r["out"]}/{r["entry"]["name"]}.MMD' == source_path)
    data,tim,_ = edit.build(SimpleNamespace(games_dir=args.games,from_dir=args.from_dir),row)
    with edit.importing(args.games):
        source,_ = import_batch.load_source(dict(recipe['entry'],no_drop=True,meshfix=False,rigfix=False),
                                           log=lambda *a:None,card_metadata=False)
    record = edit.load(next((edit.ROOT/'content/species').glob(f'{args.species}-*.json')))
    result,report = restore(source,data,tim,len(record['model']['skeleton']),args.objects,
                            args.max_packet_growth,args.max_residual)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(result)
    args.out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
