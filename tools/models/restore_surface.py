"""Restore deleted source triangles on an unchanged indexed vertex pool.

Offline authoring only (NumPy and NetworkX required). Keep the fitted vertices, texture and all animations;
lossless quad pairing pays for restored faces before considering edge collapse.
Refuse remapped pools and texture lineage ambiguity rather than guessing.
"""
import copy
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


def key(p):
    corners = list(zip(p['verts'],map(tuple,p['uvs'])))
    return min(tuple(corners[k:]+corners[:k]) for k in range(3))


def restore(source, data, texture, bones, objects, max_packet_growth=1024):
    model = mmd.MMD.parse(data,bones)
    acting = model.anims.build()
    before_primitives = sum(len(o.prims) for o in model.tmd.objects)
    src = mmdport.build_tmd(source,log=lambda *a:None)
    if len(source.bones) != len(model.tmd.objects) or not all(b['verts'] for b in source.bones):
        raise ValueError('source objects do not retain a direct indexed mapping')
    tim = mmd.Tim4(texture)
    if bytes(source.idx) != bytes(tim.idx):
        raise ValueError('source texture layout differs')
    mesh, restored = [], {}
    for oi,obj in enumerate(model.tmd.objects):
        bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,
                    verts=[v[:3] for v in model.tmd.obj_verts(oi)],
                    norms=[v[:3] for v in model.tmd.obj_norms(oi)[:obj.nnorm]],prims=[])
        for p in obj.prims:
            d = p.decode()
            bone['prims'].append(dict(verts=d['verts'],norms=d['norms'],uvs=d['uv'],
                                      row=(d['cba']>>6)-488,semi=bool(p.mode&2)))
        if oi in objects:
            x = np.array([v[:3] for v in src.obj_verts(oi)],float)
            y = np.array(bone['verts'],float)
            if x.shape != y.shape:
                raise ValueError(f'object {oi}: vertex pool differs')
            design = np.column_stack([x,np.ones(len(x))])
            fit,_,rank,_ = np.linalg.lstsq(design,y,rcond=None)
            if rank < 4 or np.max(np.linalg.norm(design@fit-y,axis=1)) > 3:
                raise ValueError(f'object {oi}: vertex indices no longer correspond')
            current = {key(p):p for p in triangles(bone['prims'])}
            source_prims = []
            for original in src.objects[oi].prims:
                d = original.decode()
                source_prims.append(dict(verts=d['verts'],norms=d['norms'],uvs=d['uv'],
                                         row=(d['cba']>>6)-488,semi=bool(original.mode&2)))
            full = list(triangles(source_prims))
            rows = defaultdict(set)
            for p in full:
                if key(p) in current:
                    rows[p['row']].add(current[key(p)]['row'])
            for p in full:
                if key(p) in current:
                    continue
                if len(rows[p['row']]) != 1:
                    raise ValueError(f'object {oi}: ambiguous palette lineage')
                p = copy.deepcopy(p)
                original_norms = p['norms']
                p['row'] = next(iter(rows[p['row']]))
                p['norms'] = []
                for n in original_norms:
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
    return result,dict(restored_triangles=restored,primitives=primitive_count,packet_growth_bound=packet_growth,storage=storage)


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
                            args.max_packet_growth)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(result)
    args.out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
