#!/usr/bin/env python3
"""Compare private source meshes with pinned imports and final provider models.

Offline authoring tool; NumPy is required. No disc data is written outside build/.
See docs/mods/mesh-reduction-audit.md for metrics and comparison limitations.
"""
import argparse
from collections import Counter
import copy
import contextlib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import struct
from types import SimpleNamespace
from concurrent.futures import ProcessPoolExecutor

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import numpy as np
import mmd
import mmdport
import meshfix
from tools.models import edit, meshcheck

VIEWS = [('front', 0, 0), ('front-right', math.pi/4, math.pi/6),
         ('right', math.pi/2, 0), ('back-right', 3*math.pi/4, math.pi/6),
         ('back', math.pi, 0), ('left', -math.pi/2, 0)]
WEIGHTS = ((1/3, 1/3, 1/3), (.6, .2, .2), (.2, .6, .2), (.2, .2, .6))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def edges(triangles):
    # Position welding within each rigid part; normals and UV seams aren't holes.
    counts = Counter()
    for tri in triangles:
        keys = [tuple(np.round(v, 4)) for v in tri]
        for a, b in zip(keys, keys[1:]+keys[:1]):
            if a != b:
                counts[tuple(sorted((a, b)))] += 1
    return counts


def geometry(triangles):
    t = np.asarray(triangles, float).reshape(-1, 3, 3)
    areas = np.linalg.norm(np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0]), axis=1)/2
    e = edges(t)
    directed = Counter()
    for tri in t:
        keys = [tuple(np.round(v,4)) for v in tri]
        for a,b in zip(keys,keys[1:]+keys[:1]):
            if a != b:
                directed[(a,b)] += 1
    oriented = all(n == directed[(b,a)] for (a,b),n in directed.items())
    closed = bool(e) and all(n == 2 for n in e.values()) and oriented
    signed = float(np.einsum('ij,ij->i', t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()/6)
    return dict(triangles=len(t), area=float(areas.sum()), degenerate=int((areas < 1e-8).sum()),
                boundary_edges=sum(n == 1 for n in e.values()),
                nonmanifold_edges=sum(n > 2 for n in e.values()),
                closed=closed, volume=abs(signed) if closed else None,
                signed_surface_integral=signed)


def sample(texture, row, uv):
    if uv is None:
        return None
    idx, pal, _ = texture
    u, v = map(lambda x: int(math.floor(x)), uv)
    if row < 0 or row >= len(pal) or not (0 <= v < idx.shape[0] and 0 <= u < idx.shape[1]):
        return -1
    return int(pal[row, idx[v, u]])


def color_distance(a, b):
    return sum(abs(((a >> shift) & 31)-((b >> shift) & 31)) for shift in (0, 5, 10))/93


def barycentric(point, tri):
    a, b, c = tri
    u, v, w = b-a, c-a, point-a
    uu, uv, vv = u@u, u@v, v@v
    det = uu*vv-uv*uv
    if abs(det) < 1e-12:
        return np.array([1., 0, 0])
    beta, gamma = ((w@u)*vv-(w@v)*uv)/det, ((w@v)*uu-(w@u)*uv)/det
    weights = np.maximum([1-beta-gamma, beta, gamma], 0)
    return weights/weights.sum()


def triangle_distances(point,triangles):
    """Vectorized squared point/surface distances, including degenerate edges."""
    if not len(triangles):
        return np.empty(0)
    a,b,c = triangles[:,0],triangles[:,1],triangles[:,2]
    u,v,w = b-a,c-a,point-a
    uu,uv,vv = (u*u).sum(1),(u*v).sum(1),(v*v).sum(1)
    wu,wv = (w*u).sum(1),(w*v).sum(1)
    det = uu*vv-uv*uv
    valid = np.abs(det) > 1e-12
    beta = np.divide(wu*vv-wv*uv,det,out=np.zeros_like(det),where=valid)
    gamma = np.divide(wv*uu-wu*uv,det,out=np.zeros_like(det),where=valid)
    projected = a+beta[:,None]*u+gamma[:,None]*v
    inside = valid & (beta >= 0) & (gamma >= 0) & (beta+gamma <= 1)
    result = np.full(len(a),np.inf)
    result[inside] = ((projected[inside]-point)**2).sum(1)
    for start,end in ((a,b),(b,c),(c,a)):
        edge = end-start
        length = (edge*edge).sum(1)
        fraction = np.clip(np.divide(((point-start)*edge).sum(1),length,
                                     out=np.zeros_like(length),where=length>1e-15),0,1)
        result = np.minimum(result,((start+fraction[:,None]*edge-point)**2).sum(1))
    return result


def compare_parts(before, after, tolerance):
    """Area-weighted source samples, nearest surviving surface in the SAME bone.

    Counts removed triangles separately from displaced surface samples. Open
    surfaces have no enclosed volume: never call their signed integral a volume.
    """
    out = []
    for bone in sorted({t[0] for t in before.tris} | {t[0] for t in after.tris}):
        ai = [i for i,t in enumerate(before.tris) if t[0] == bone]
        bi = [i for i,t in enumerate(after.tris) if t[0] == bone]
        A, B = before.points[ai], after.points[bi]
        ga, gb = geometry(A), geometry(B)
        ea, eb = edges(A), edges(B)
        boundaries = np.asarray([[a,b,b] for (a,b),n in ea.items() if n == 1],float).reshape(-1,3,3)
        new = []
        for (a,b),n in eb.items():
            if n != 1:
                continue
            # A simplified boundary may span several old boundary segments.
            # Test its path, allowing the same quantization tolerance as faces.
            points = [np.asarray(a)*(1-f)+np.asarray(b)*f for f in (0,.25,.5,.75,1)]
            if not len(boundaries) or any(float(triangle_distances(p,boundaries).min()) > tolerance**2 for p in points):
                new.append((a,b))
        lost = bad = clear = black = changed = checked = missing_uv = 0.
        unmatched_triangles,unmatched_area = 0,0.
        max_distance = 0.
        for i, tri in zip(ai, A):
            area = np.linalg.norm(np.cross(tri[1]-tri[0],tri[2]-tri[0]))/2
            if area < 1e-8:
                continue
            t = before.tris[i]
            # An oriented triangle counterpart detects deleted detail even
            # when nearby plates hide it in the coarse surface-distance test.
            same = any(np.any(np.max(np.linalg.norm(B-np.roll(tri,k,axis=0),axis=2),axis=1) <= tolerance)
                       for k in range(3)) if len(B) else False
            if not same:
                unmatched_triangles += 1
                unmatched_area += area
            for weights in WEIGHTS:
                pt = np.asarray(weights) @ tri
                distances = triangle_distances(pt,B)
                dist = math.sqrt(float(distances.min())) if len(distances) else float('inf')
                max_distance = max(max_distance, dist)
                if dist > tolerance:
                    lost += area/len(WEIGHTS)
                    continue
                nearest = np.flatnonzero(distances <= distances.min()+1e-8)
                normal = np.cross(tri[1]-tri[0],tri[2]-tri[0])
                j = max(nearest,key=lambda k:float(np.cross(B[k,1]-B[k,0],B[k,2]-B[k,0])@normal))
                target = after.tris[bi[j]]
                if t[4] is None:
                    continue
                checked += area/len(WEIGHTS)
                if target[4] is None:
                    missing_uv += area/len(WEIGHTS)
                    continue
                wa = np.asarray(weights)
                wb = barycentric(pt,B[j])
                ca = sample(before.tex, t[5], wa @ np.asarray(t[4]))
                cb = sample(after.tex, target[5], wb @ np.asarray(target[4]))
                weight = area/len(WEIGHTS)
                if ca == -1 or cb == -1:
                    bad += weight
                elif ca is not None and cb is not None:
                    clear += weight * (ca != 0 and cb == 0)
                    black += weight * (ca & 0x7fff != 0 and cb != 0 and cb & 0x7fff == 0)
                    changed += weight * (color_distance(ca, cb) > .12)
        out.append(dict(bone=bone, source=ga, target=gb, new_boundary_edges=len(new),
                        new_boundary_length=sum(math.dist(*e) for e in new),
                        area_loss=max(0., ga['area']-gb['area']),
                        triangles_without_counterpart=unmatched_triangles,
                        area_without_counterpart=unmatched_area,
                        volume_loss=max(0.,ga['volume']-gb['volume']) if ga['volume'] is not None and gb['volume'] is not None else None,
                        uncovered_area=lost, uncovered_fraction=lost/max(ga['area'],1e-9),
                        max_sample_distance=max_distance if math.isfinite(max_distance) else None,
                        texture_checked_area=checked, invalid_texture_area=bad,
                        missing_uv_area=missing_uv, opaque_to_clear_area=clear,
                        color_mismatch_area=changed, opaque_to_black_area=black))
    return out


def port_surface(model):
    """Render adapter that retains unquantized pre-reduction geometry and UVs."""
    tris, points = [], []
    W = meshfix.world_matrices(model)
    for b, bone in enumerate(model.bones):
        for pi,p in enumerate(bone['prims']):
            for corners in [(0,1,2)]+([(1,3,2)] if len(p['verts']) == 4 else []):
                vs = [bone['verts'][p['verts'][c]] for c in corners]
                points.append([meshfix._apply(W[b],v) for v in vs])
                uv = [p['uvs'][c] for c in corners] if p['uvs'] is not None else None
                row = p['row'] or 0
                if hasattr(model,'reference_idx') and uv is not None:
                    lookup = bone.get('reference_corners',{})
                    refs = [lookup.get((p['verts'][c],tuple(p['uvs'][c]),row)) for c in corners]
                    if all(r is not None for r in refs) and len({r[1] for r in refs}) == 1:
                        uv,row = [r[0] for r in refs],refs[0][1]
                    else:
                        uv = None  # Geometry remains comparable; texture lineage is unknown.
                tris.append((b,b,pi,(),uv,row,False,p.get('color',(200,200,200))))
    pal = np.asarray(getattr(model,'reference_pals',model.pals),np.uint16)
    rgb = np.stack([(pal&31)<<3, (pal>>5&31)<<3, (pal>>10&31)<<3],-1).astype(np.uint8)
    return SimpleNamespace(tris=tris,points=np.asarray(points,float).reshape(-1,3,3),
                           tex=(np.asarray(getattr(model,'reference_idx',model.idx),np.uint8).reshape(-1,256),pal,rgb))


@contextlib.contextmanager
def original_texture_loader(entry):
    """Retain texture corners BEFORE atlas packing, palette merging or scaling.

    Corner lineage survives lossless quad pairing and bone reordering. This
    temporary instrumentation never changes importer code or its pinned bytes.
    """
    game = entry.get('game','dcb')
    module = importlib.import_module(dict(dcb='dcb2mmd',dw2='dw2mmd',dw3='dw3mmd')[game])
    original = module.load
    def load(*args,**kwargs):
        if game == 'dw2':
            kwargs['maxp'] = 64
        model = original(*args,**kwargs)
        path = module.pak_path(args[0]) if game == 'dcb' else module.model_path(args[0])
        model.reference_source_sha256 = digest(Path(path).read_bytes())
        model.reference_source_name = Path(path).name
        originals = []
        if game == 'dw3':
            raw = module.read_model(args[0])
            pixels = raw.texture[20:]
            hw = struct.unpack('<'+str(len(pixels)//2)+'H',pixels)
            cluts = sorted({tuple(p.material[3:5]) for b in raw.bones for p in b.mesh.prims if p.uvs})
            pals = [list(hw[y*64+x:y*64+x+16]) for x,y in cluts]
            idx = bytearray((pixels[k//2] >> (4*(k%2)))&15 for k in range(256*256))
            for bone in raw.bones:
                row = []
                for p in bone.mesh.prims:
                    if p.uvs:
                        x,y = p.material[0] | p.material[1]<<8,p.material[2]
                        row.append(([(x+u,y+v) for u,v in p.uvs],cluts.index(tuple(p.material[3:5]))))
                    else:
                        row.append((None,0))
                originals.append(row)
        elif game == 'dw2':
            raw = module._dw2().model.load(module.model_path(args[0]))
            from dw2.texture import image_halfwords
            hw = image_halfwords(raw.texture)
            height,width = hw.shape[0],hw.shape[1]*4
            cluts = sorted({p.clut for b in raw.bones for p in b.prims})
            pals = [[int(v) for v in hw[c>>6,(c&63)*16:(c&63)*16+16]] for c in cluts]
            idx = bytearray(256*height)
            for y in range(height):
                for x in range(width):
                    idx[y*256+x] = int(hw[y,x//4] >> (4*(x%4)))&15
            originals = [[(list(p.uvs),cluts.index(p.clut)) for p in b.prims] for b in raw.bones]
        else:
            raw = module._dcb().model.parse_model(Path(module.pak_path(args[0])).read_bytes(),str(args[0]))
            tim = next(t for t in raw.textures if t.bpp == 4)
            ix,iy = tim.image_xy
            height,width = tim.pixels.shape
            idx = bytearray(256*height)
            for y in range(height):
                idx[y*256:y*256+width] = bytes(tim.pixels[y])
            cluts = sorted({raw.vram.resolve_clut(p.clut) for b in raw.bones for p in b.mesh.prims if p.uvs})
            pals = [[int(v) for v in raw.vram.words[y,x:x+16]] for x,y in cluts]
            for bone in raw.bones:
                row = []
                for p in bone.mesh.prims:
                    if p.uvs:
                        px,py = (p.tpage&15)*64,((p.tpage>>4)&1)*256
                        uv = [(u-(ix-px)*4,v-(iy-py)) for u,v in p.uvs]
                        row.append((uv,cluts.index(raw.vram.resolve_clut(p.clut))))
                    else:
                        row.append((None,0))
                originals.append(row)
        model.reference_idx,model.reference_pals = idx,pals
        for bone,rows in zip(model.bones,originals):
            if len(bone['prims']) != len(rows):
                raise ValueError('pre-reduction primitive lineage differs')
            lookup = {}
            for p,(uv,row) in zip(bone['prims'],rows):
                if uv is not None:
                    for i,original_uv in enumerate(uv):
                        lookup[(p['verts'][i],tuple(p['uvs'][i]),p['row'] or 0)] = (tuple(original_uv),row)
            bone['reference_corners'] = lookup
        return model
    module.load = load
    try:
        yield
    finally:
        module.load = original


def final_surface(data, tim, skeleton):
    model = meshcheck.Model(data,skeleton,tim)
    # Use object indices for comparison with importer bones (entity has no mesh).
    return SimpleNamespace(tris=[(t[1],*t[1:]) for t in model.tris],
                           points=model.tri_array(model.world(model.rest())), tex=model.tex), model


def mmd_source(data,tim,skeleton):
    model = meshcheck.Model(data,skeleton,tim)
    bones = []
    for oi,obj in enumerate(model.m.tmd.objects):
        bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,
                    verts=[v[:3] for v in model.m.tmd.obj_verts(oi)],
                    norms=[v[:3] for v in model.m.tmd.obj_norms(oi)[:obj.nnorm]],prims=[])
        for p in obj.prims:
            d = p.decode()
            bone['prims'].append(dict(verts=d['verts'],norms=d['norms'] or None,uvs=d['uv'] or None,
                                     row=(d['cba']>>6)-488 if d['uv'] else 0,semi=bool(p.mode&2)))
        bones.append(bone)
    result = mmdport.Model('native',bones,model.tim.idx,model.tim.pal,{})
    result.reference_source_sha256 = digest(data)
    result.reference_source_name = 'MTGR.MMD'
    return result


def robust_affine(x,y,all_points,tolerance=3):
    """Recover the common proportion transform despite edge-collapse outliers.

    Require a majority consensus of independent corner correspondences. The
    unobserved source points must lie in the fitted affine span. Refused fits
    remain unverified; outliers are measured as changed geometry afterwards.
    """
    pairs = sorted(set(tuple(map(float,a))+tuple(map(float,b)) for a,b in zip(x,y)))
    if len(pairs) < 3:
        return None
    x,y = np.asarray(pairs)[:,:3],np.asarray(pairs)[:,3:]
    design = np.column_stack([x,np.ones(len(x))])
    points = np.column_stack([all_points,np.ones(len(all_points))])
    rng = np.random.default_rng(0)
    candidates = [np.arange(len(x))]+[rng.choice(len(x),min(5,len(x)),replace=False) for _ in range(100)]
    best = None
    for indices in candidates:
        transform,_,rank,_ = np.linalg.lstsq(design[indices],y[indices],rcond=None)
        if rank < 3:
            continue
        residuals = np.linalg.norm(design@transform-y,axis=1)
        inliers = residuals <= tolerance
        count = int(inliers.sum())
        if count >= max(3,math.ceil(.6*len(x))) and (best is None or count > best[0]):
            best = count,inliers
    if best is None:
        return None
    inliers = best[1]
    transform,_,rank,_ = np.linalg.lstsq(design[inliers],y[inliers],rcond=None)
    span_error = np.max(np.abs(points-points@np.linalg.pinv(design[inliers])@design[inliers]))
    residual = float(np.max(np.linalg.norm(design[inliers]@transform-y[inliers],axis=1)))
    if rank < 3 or residual > tolerance or span_error > 1e-5:
        return None
    return transform,residual,float(inliers.mean())


def align_source(source, final,bridge=None):
    """Fit corresponding vertex pools through authored proportions, refusing guesses.

    Four or more corresponding points, equal pool sizes, a nonsingular affine
    fit and a small residual are required. Changed rigs/remeshing are unscored.
    """
    tmd = mmdport.build_tmd(copy.deepcopy(source),log=lambda *a: None)
    mats = final.matrices(final.rest())
    mapped = copy.deepcopy(source)
    fitted, refused = [], []
    source_objects = {bi:oi for oi,bi in enumerate(i for i,b in enumerate(source.bones) if b['verts'])}
    same_rig = mmdport.skeleton(source) == final.bones
    final_points = final.tri_array(final.world(final.rest()))
    def uv_key(uv,row):
        if uv is None:
            return None
        uv = [tuple(int(min(max(c,0),limit)) for c,limit in zip(p,(255,127))) for p in uv]
        return min(tuple(uv[k:]+uv[:k]) for k in range(3))
    target_uv = {}
    for ti,t in enumerate(final.tris):
        key = uv_key(t[4],t[5])
        if key is not None:
            target_uv.setdefault(key,[]).append(ti)
    def fit_uv(bone,preferred):
        groups = {}
        for p in bone['prims']:
            if p['uvs'] is None:
                continue
            for corners in [(0,1,2)]+([(1,3,2)] if len(p['verts']) == 4 else []):
                uv = [tuple(int(min(max(v,0),limit)) for v,limit in zip(p['uvs'][c],(255,127))) for c in corners]
                matches = target_uv.get(uv_key(uv,p['row'] or 0),[])
                local = [ti for ti in matches if final.tris[ti][1] == preferred]
                if same_rig or len(local) == 1:
                    matches = local
                if len(matches) != 1 or len(set(uv)) != 3:
                    continue
                ti, = matches
                t = final.tris[ti]
                group = groups.setdefault(t[1],([],[]))
                for c,u in zip(corners,uv):
                    group[0].append(bone['verts'][p['verts'][c]])
                    group[1].append(final_points[ti][t[4].index(u)])
        for obj,(x,y) in sorted(groups.items(),key=lambda pair:-len(pair[1][0])):
            fitted = robust_affine(x,y,bone['verts'])
            if fitted is not None:
                transform,residual,support = fitted
                return obj,transform,residual,support
        return None
    for oi,bone in enumerate(mapped.bones):
        if oi not in source_objects:
            refused.append(oi); continue
        obj_index = source_objects[oi]
        if same_rig and bridge is not None and obj_index < len(bridge.tmd.objects):
            raw = np.asarray([v[:3] for v in bridge.tmd.obj_verts(obj_index)],float)
            target = np.asarray([v[:3] for v in final.m.tmd.obj_verts(obj_index)],float)
            if raw.shape == target.shape and len(raw) >= 4:
                design = np.column_stack([raw,np.ones(len(raw))])
                transform,_,rank,_ = np.linalg.lstsq(design,target,rcond=None)
                residual = float(np.max(np.linalg.norm(design@transform-target,axis=1)))
                expected = np.asarray(bone.get('importer_vertices',[]),float)
                if rank == 4 and residual <= 3 and len(expected):
                    distances = np.linalg.norm(raw[:,None,:]-expected[None,:,:],axis=2).min(axis=1)
                    # Endpoint collapse retains original source positions.
                    # Verify that fact against the pinned importer pool before
                    # carrying its authored transform onto missing surfaces.
                    if float((distances <= 2.5).mean()) >= .98:
                        bi = next(i for i,(obj,_) in enumerate(final.bones) if obj == obj_index)
                        bone['verts'] = [meshfix._apply(mats[bi],np.r_[v,1]@transform) for v in expected]
                        bone.update(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q)
                        fitted.append(dict(object=oi,target_object=obj_index,residual=residual,
                                           method='pinned importer pool',endpoint_support=float((distances <= 2.5).mean())))
                        continue
        x = np.asarray([v[:3] for v in tmd.obj_verts(obj_index)],float)
        y = np.asarray([v[:3] for v in final.m.tmd.obj_verts(obj_index)],float) if obj_index < len(final.m.tmd.objects) else np.empty((0,3))
        transform = None
        if x.shape == y.shape and len(x) >= 4:
            design = np.column_stack([x,np.ones(len(x))])
            candidate,_,rank,_ = np.linalg.lstsq(design,y,rcond=None)
            residual = float(np.max(np.linalg.norm(design@candidate-y,axis=1)))
            if rank == 4 and abs(np.linalg.det(candidate[:3])) >= .001 and residual <= 3:
                transform = candidate
        if transform is None:
            match = fit_uv(bone,obj_index)
            if match is None:
                refused.append(oi); continue
            obj,transform,residual,support = match
            bone['verts'] = [np.r_[v,1]@transform for v in bone['verts']]
            bone.update(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q)
            fitted.append(dict(object=oi,target_object=obj,residual=residual,corner_support=support,method='UV triangle consensus'))
            continue
        bi = next((i for i,(obj,_) in enumerate(final.bones) if obj == obj_index),None)
        if bi is None:
            refused.append(oi); continue
        # Flatten into final world space; pose differences must not masquerade as holes.
        bone['verts'] = [meshfix._apply(mats[bi], np.r_[v,1]@transform) for v in bone['verts']]
        bone.update(parent=-1, offset=(0,0,0),rest=mmdport.IDENTITY_Q)
        fitted.append(dict(object=oi,target_object=obj_index,residual=residual,method='vertex pool'))
    for oi in refused:
        mapped.bones[oi]['prims'] = []
    mapped.anims = {}
    return mapped, fitted, refused


def matched_target(source,target,fitted):
    """Partition a rebound target object by exact UV triangle lineage."""
    def key(uv,row):
        if uv is None:
            return None
        uv = [tuple(int(min(max(c,0),limit)) for c,limit in zip(p,(255,127))) for p in uv]
        return min(tuple(uv[k:]+uv[:k]) for k in range(3))
    by_object = {}
    source_keys = {}
    for fit in fitted:
        bi = fit['object']
        by_object.setdefault(fit['target_object'],[]).append(bi)
        keys = set()
        for p in source.bones[bi]['prims']:
            if p['uvs'] is not None:
                for c in [(0,1,2)]+([(1,3,2)] if len(p['verts'])==4 else []):
                    keys.add(key([p['uvs'][i] for i in c],p['row'] or 0))
        source_keys[bi] = keys
    tris,points,unassigned = [],[],0
    for t,pt in zip(target.tris,target.points):
        candidates = by_object.get(t[0],[])
        if len(candidates) > 1:
            candidates = [b for b in candidates if key(t[4],t[5]) in source_keys[b]]
        if len(candidates) != 1:
            unassigned += 1
            continue
        tris.append((candidates[0],*t[1:]))
        points.append(pt)
    return SimpleNamespace(tris=tris,points=np.asarray(points,float).reshape(-1,3,3),tex=target.tex),unassigned


def views(before,after,size=192):
    metrics, images = [], []
    for name,yaw,pitch in VIEWS:
        a = meshcheck.render(before,before.points,yaw,pitch,size=size)
        b = meshcheck.render(after,after.points,yaw,pitch,size=size,frame=a[-1])
        union = a[1] | b[1]
        metrics.append(dict(view=name, silhouette=float((a[1]^b[1]).sum())/max(1,int(union.sum())),
                            drawn_difference=float((a[3]^b[3]).sum())/max(1,int(union.sum()))))
        images.append((name,a[0],b[0]))
    return metrics,images


def contact(images,path,title):
    from tools.image import Image,ImageDraw
    size = images[0][1].shape[0]
    canvas = Image.new('RGB',(2*size,len(images)*(size+28)+46),(40,44,52))
    draw = ImageDraw.Draw(canvas)
    draw.text((8,5),title,fill='white')
    draw.text((8,25),'Source (matched)              Shipped (full)',fill='white')
    for k,(name,a,b) in enumerate(images):
        y = 46+k*(size+28)
        draw.text((8,y),name,fill='white')
        canvas.paste(Image.fromarray(a),(0,y+24))
        canvas.paste(Image.fromarray(b),(size,y+24))
    canvas.save(path)


def contact_views(before,after,size=192):
    """Always show the complete shipped model, including unpaired regions.

    Omitting an unassigned final triangle from a review image would make a
    correspondence failure look like an actual missing part. Metrics still use
    matched regions; the image's camera fits the union of both full displays.
    """
    images = []
    for name,yaw,pitch in VIEWS:
        points = meshcheck._rotate(np.concatenate([before.points,after.points]),yaw,pitch).reshape(-1,3)
        lo,hi = points[:,:2].min(0),points[:,:2].max(0)
        scale = (size-8)/max(float((hi-lo).max()),1.)
        frame = scale,size/2-(lo+hi)/2*scale
        a = meshcheck.render(before,before.points,yaw,pitch,size=size,frame=frame)
        b = meshcheck.render(after,after.points,yaw,pitch,size=size,frame=frame)
        images.append((name,a[0],b[0]))
    return images


def provider_output(sid,model,tim,out):
    builder = edit.import_records()[str(sid)].get('builder')
    if builder:
        model,tim = importlib.import_module(builder).build(ROOT/'extracted')
    spec = importlib.util.spec_from_file_location('audit_provider',edit.IMPORTED_MODELS_SCRIPT)
    provider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider)
    base = out/'provider-input'
    base.mkdir(parents=True,exist_ok=True)
    (base/f'{sid}.MMD').write_bytes(model)
    (base/f'{sid}.TIM').write_bytes(tim)
    provider.BASE_MODELS = str(base.resolve())
    _,record = provider.species_file(str(out/'provider'),str(sid),generate=True)
    return Path(record['model']['file']).read_bytes(),Path(record['texture']['file']).read_bytes(),record


def audit_one(job):
    sid,games,out,fingerprint = job
    folder = Path(out)/str(sid)
    folder.mkdir(parents=True,exist_ok=True)
    try:
        result = run_one(sid,Path(games),folder)
    except (Exception,SystemExit) as error:
        detail = str(error).replace(str(ROOT),'.').replace(str(Path(games).resolve()),'<source-games>')
        result = dict(id=sid,error=f'{type(error).__name__}: {detail}')
    result['fingerprint'] = fingerprint
    (folder/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result


def run_one(sid,games,folder):
    import import_batch
    row, = edit.rows(edit.load(edit.MODELS),[str(sid)])
    recipes = edit.load(ROOT/'content/modeldelta/import-batches.json')['recipes']
    source_path = row['mmd']['sources'][0]['path']
    sizes = {r['target']:r['source'] for r in edit.load(edit.SIZES)['files']}
    while source_path in sizes:
        source_path = sizes[source_path]
    recipe = next((r for r in recipes if f'{r["out"]}/{r["entry"]["name"]}.MMD' == source_path),None)
    if recipe is None:
        paths = {180:'veemon',181:'puppetmon',182:'kimeramon-dw2',373:'wargreymon-dcb'}
        location = 'content/models/mega' if sid == 373 else 'content/models/dcb-import'
        spec = edit.load(ROOT/location/(paths[sid]+'.json'))
        entry = dict(name=row['name'],game='dw2' if 'dw2' in spec else 'dcb',model=spec.get('dw2',spec.get('dcb')))
    else:
        entry = recipe['entry']
    args = SimpleNamespace(games_dir=games,from_dir=None)
    # Rebuild/check pinned importer sources, decode plain deltas, then run the
    # same final provider as derive (including field overlays and native rigs).
    model,tim,importer_sources = edit.build(args,row)
    with edit.importing(games):
        shipped,texture,record = provider_output(sid,model,tim,folder)
        # no_drop and meshfix=False bypass destructive mesh reduction only.
        with original_texture_loader(entry):
            source,_ = import_batch.load_source(dict(entry,no_drop=True,meshfix=False),
                                                log=lambda *a:None,card_metadata=False)
    pins = edit.load(ROOT/'tools/derive/recipes/species-pins.json')['imports'][str(sid)]
    if [hashlib.sha1(shipped).hexdigest(),hashlib.sha1(texture).hexdigest()] != pins:
        raise ValueError('final provider pins differ')
    (folder/'shipped.MMD').write_bytes(shipped)
    (folder/'shipped.TIM').write_bytes(texture)
    skeleton = record['model']['skeleton']
    target,final = final_surface(shipped,texture,skeleton)
    if sid == 224:
        native = (ROOT/'extracted/CHDAT/MMD0/MTGR.MMD').read_bytes()
        native_tim = mmd.alltim_entry(Path(mmd.ALLTIM).read_bytes(),12)
        source = mmd_source(native,native_tim,mmd.exe().skeleton[12])
    bridge = None
    if recipe is not None and entry.get('game') in ('dw3','dw2'):
        spec = edit.load(ROOT/recipe['spec'])
        if spec.get('scale') and getattr(source,'scale',None):
            factor = spec['scale']/source.scale
            passes = []
            path = row['mmd']['sources'][0]['path']
            size_rows = {r['target']:r for r in edit.load(edit.SIZES)['files']}
            while path in size_rows:
                size = size_rows[path]
                passes.append(size['scale'])
                path = size['source']
            for bone in source.bones:
                expected = [tuple(round(c*factor) for c in v) for v in bone['verts']]
                for scale in reversed(passes):
                    expected = [tuple(round(c*scale) for c in v) for v in expected]
                bone['importer_vertices'] = expected
            try:
                bridge = mmd.MMD.parse(importer_sources['mmd'][0],len(source.bones)+1)
            except (ValueError,IndexError,struct.error):
                bridge = None
    aligned,fitted,refused = align_source(source,final,bridge)
    baseline = port_surface(aligned)
    subset,unassigned = matched_target(source,target,fitted)
    if not len(baseline.points):
        raise ValueError('no verified source-to-final vertex correspondence')
    diagonal = float(np.linalg.norm(np.ptp(baseline.points.reshape(-1,3),axis=0)))
    tolerance = max(2.5,diagonal*.003)
    parts = compare_parts(baseline,subset,tolerance)
    anatomy = edit.load(ROOT/'content/models/imports/chibi.json').get(str(sid),{}).get('groups',{})
    correspondence = {p['object']:p['target_object'] for p in fitted}
    for part in parts:
        target_obj = correspondence[part['bone']]
        bi = next((i for i,(obj,_) in enumerate(skeleton) if obj == target_obj),None)
        part['region'] = anatomy.get(str(bi),f'object {part["bone"]}')
    original_surface = port_surface(source)
    all_area,matched_area = 0.,0.
    matched_bones = {p['object'] for p in fitted}
    for t,tri in zip(original_surface.tris,original_surface.points):
        value = float(np.linalg.norm(np.cross(tri[1]-tri[0],tri[2]-tri[0]))/2)
        all_area += value
        if t[0] in matched_bones:
            matched_area += value
    coverage = matched_area/max(1e-9,all_area)
    area = sum(p['source']['area'] for p in parts)
    uncovered = sum(p['uncovered_area'] for p in parts)/max(1,area)
    texture_error = sum(p['invalid_texture_area']+p['opaque_to_clear_area']+p['opaque_to_black_area']+p['missing_uv_area'] for p in parts)/max(1,area)
    vm,images = views(baseline,subset)
    worst = max((p['uncovered_fraction'] for p in parts if p['source']['area'] > area*.005),default=0)
    changed_area = sum(p['area_without_counterpart'] for p in parts)/max(1,area)
    color_fraction = sum(p['color_mismatch_area'] for p in parts)/max(1,area)
    score = 100*(uncovered+.35*worst+.25*changed_area+texture_error+.25*color_fraction+max(v['drawn_difference'] for v in vm))
    contact(contact_views(baseline,target),folder/f'{sid}-{row["name"]}.png',f'{sid} {row["name"]} | source area {coverage:.0%}')
    from tools.models.audit_textures import audit as texture_audit
    texture_findings = texture_audit(final.m.tmd,final.tim)
    return dict(id=sid,name=row['name'],score=score,source_sha256=[s['sha256'] for s in row['mmd']['sources']],
                original_source=dict(name=source.reference_source_name,sha256=source.reference_source_sha256),
                shipped_sha256=digest(shipped),texture_sha256=digest(texture),
                tolerance=tolerance,matched_objects=fitted,unmatched_objects=refused,
                unassigned_target_triangles=unassigned,
                source_area_coverage=coverage,status='complete' if coverage > .999 and not unassigned else 'partial',
                coverage_objects=f'{len(fitted)}/{len(source.bones)}',uncovered_fraction=uncovered,
                texture_error_fraction=texture_error,views=vm,parts=parts,
                color_mismatch_fraction=color_fraction,
                texture_findings=texture_findings,contact=f'{sid}/{sid}-{row["name"]}.png')


def input_fingerprint(games):
    """Content hashes, never timestamps: a resumed audit must use identical inputs."""
    h = hashlib.sha256()
    for base in (ROOT/'tools',ROOT/'content',ROOT/'extracted',games):
        for path in sorted(base.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            if base == ROOT/'tools' and path.suffix not in ('.py','.json'):
                continue
            h.update(str(path.relative_to(base)).encode())
            h.update(bytes.fromhex(digest(path.read_bytes())))
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--games',type=Path,default=Path('build/imported-model-edit/source-games'))
    p.add_argument('--out',type=Path,default=Path('build/mesh-audit/all'))
    p.add_argument('--ids',nargs='*',type=int)
    p.add_argument('--jobs',type=int,default=2)
    p.add_argument('--resume',action='store_true',help='reuse this run only; delete output after changing inputs')
    a = p.parse_args()
    ids = a.ids or [r['id'] for r in edit.load(edit.MODELS)['models']]
    a.out.mkdir(parents=True,exist_ok=True)
    fingerprint = input_fingerprint(a.games)
    results,jobs = [],[]
    for sid in ids:
        cached = a.out/str(sid)/'result.json'
        result = edit.load(cached) if a.resume and cached.is_file() else None
        if result and result.get('fingerprint') == fingerprint and 'error' not in result:
            results.append(result)
        else:
            jobs.append((sid,str(a.games),str(a.out),fingerprint))
    with ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for row in pool.map(audit_one,jobs):
            results.append(row)
            print(row['id'],row.get('name',''),row.get('score',row.get('error')),flush=True)
    results.sort(key=lambda r:(-r.get('score',-1),r['id']))
    (a.out/'ranked.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    lines = ['| Rank | Species | Score | Uncovered area | Source area checked | Matched objects | New boundaries |',
             '|---:|---|---:|---:|---:|---|---:|']
    for rank,r in enumerate(results,1):
        if 'error' in r:
            lines.append(f'| {rank} | {r["id"]} | unavailable | {r["error"]} | | | |')
        else:
            boundaries = sum(p['new_boundary_edges'] for p in r['parts'])
            lines.append(f'| {rank} | {r["id"]} {r["name"]} | {r["score"]:.2f} | {r["uncovered_fraction"]:.1%} | {r["source_area_coverage"]:.1%} | {r["coverage_objects"]} | {boundaries} |')
    (a.out/'ranked.md').write_text('\n'.join(lines)+'\n')
    return int(any('error' in r for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
