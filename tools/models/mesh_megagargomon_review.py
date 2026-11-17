"""Exhaustive MegaGargomon-only PSX-rule render measurements.

C rasterization is a local accelerator of psx_blend's orthographic evidence,
not a runtime/GTE emulator. validate() requires exact reference parity.
"""
import ctypes
import hashlib
import json
import math
from pathlib import Path
import subprocess
import numpy as np
from tools.models import meshcheck as MC, psx_blend


class Renderer:
    def __init__(self, model, library):
        self.model = model
        lib = ctypes.CDLL(str(library.resolve()))
        self.raster = lib.raster
        self.raster.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
        self.commands = np.zeros((len(model.tris),26), np.float64)
        groups = {}
        for k, tri in enumerate(model.tris):
            groups.setdefault(tri[:3], []).append(k)
            d = model.m.tmd.objects[tri[1]].prims[tri[2]].decode()
            row = self.commands[k]
            row[6:12] = np.asarray(tri[4] or [(0,0)]*3).reshape(-1)
            colors = d['colors']
            if len(colors) > 1:
                row[12:21] = np.array([colors[d['verts'].index(v)][:3] for v in tri[3]]).reshape(-1)
            else:
                row[12:21] = list(colors[0][:3] if colors else (0,0,0))*3
            row[21:] = [tri[5],tri[4] is not None,len(colors)>1,bool(d['mode']&2),((d['tsb'] or 0)>>5)&3]
        self.groups = list(groups.values())
        self.first = np.array([g[0] for g in self.groups])
        self.second = np.array([g[-1] for g in self.groups])
        self.quad = self.first != self.second
        self.texture = np.ascontiguousarray(model.tex[0],np.uint8)
        self.palette = np.ascontiguousarray(model.tex[1],np.uint16)

    def render(self, pose, yaw, size=96, frame=None, phase=0):
        xyz = self.model.tri_array(self.model.world(pose))
        points = MC._rotate(xyz,yaw,math.pi/6)
        if frame is None:
            low,high = points[...,:2].reshape(-1,2).min(0),points[...,:2].reshape(-1,2).max(0)
            scale=(size-24)/max(high-low)
            frame=scale,size/2-(low+high)/2*scale
        scale,offset=frame
        xy=points[...,:2]*scale+offset
        first=xy[self.first]
        u,v=first[:,1]-first[:,0],first[:,2]-first[:,0]
        visible=u[:,0]*v[:,1]-u[:,1]*v[:,0]>1e-9
        sums=points[self.first,:,2].sum(1)+np.where(self.quad,points[self.second,1,2],0)
        bins=np.floor((sums/(3+self.quad)+phase)/4).astype(int)
        order=np.lexsort((-np.arange(len(bins)),-bins))
        indices=[k for i in order if visible[i] for k in self.groups[i]]
        commands=self.commands.copy()
        commands[:,:6]=xy.reshape(-1,6)
        commands=np.ascontiguousarray(commands[indices])
        output=np.empty((size,size,3),np.uint8)
        self.raster(len(commands),commands.ctypes.data,size,self.texture.ctypes.data,
                    self.texture.shape[1],self.texture.shape[0],self.palette.ctypes.data,output.ctypes.data)
        return (output.astype(np.uint16)*255//31).astype(np.uint8),frame


def compile_renderer(out):
    out.mkdir(parents=True,exist_ok=True)
    library=out/'megagargomon-raster.so'
    subprocess.run(['cc','-O2','-shared','-fPIC','-ffp-contract=off',str(Path(__file__).with_name('megagargomon_raster.c')),
                    '-lm','-o',str(library)],check=True)
    return library


def validate(renderer, cases):
    checks=[]
    for slot,tick in cases:
        pose=renderer.model.poses(slot,6000)[tick]
        for view in range(8):
            yaw=view*math.pi/4
            for phase in (0,2):
                ref,frame=psx_blend.render(renderer.model,yaw,math.pi/6,size=96,pose=pose,depth_offset=phase)
                got,_=renderer.render(pose,yaw,frame=frame,phase=phase)
                different=int(np.any(ref!=got,axis=2).sum())
                if different:
                    raise ValueError(f'render reference mismatch {slot}/{tick}/{view}/{phase}: {different} pixels')
                checks.append([slot,tick,view,phase])
    return dict(reference='psx_blend.render',exact_pixel_matches=checks)


def sweep(before, after, out, validate_cases):
    library=compile_renderer(out)
    ra,rb=[Renderer(m,library) for m in (before,after)]
    checks=[validate(r,validate_cases) for r in (ra,rb)]
    (out/'renderer-parity.json').write_text(json.dumps(checks,indent=2)+'\n')
    tasks = {}; frames = []
    for slot in before.slots():
        aa, bb = before.poses(slot,6000), after.poses(slot,6000)
        assert len(aa) == len(bb)
        for tick, (a,b) in enumerate(zip(aa,bb)):
            key = hashlib.sha256(np.asarray([a,b],dtype='<i4').tobytes()).hexdigest()
            tasks.setdefault(key, (key,a,b))
            frames.append((slot,tick,key))
    import multiprocessing
    cache = {}
    with multiprocessing.Pool(4, initializer=_init_worker,
            initargs=(before,after,library)) as pool:
        for i, (key, views) in enumerate(pool.imap_unordered(_render_worker,tasks.values(),chunksize=8)):
            cache[key] = views
            if i % 50 == 0:
                print('rendered unique poses',i+1,'/',len(tasks),flush=True)
    rows = [dict(slot=slot,tick=tick,views=cache[key]) for slot,tick,key in frames]
    report=dict(size=96,azimuths=8,elevation_degrees=30,bin_phases=[0,2],ticks=len(rows),
                unique_pose_pairs=len(cache),rows=rows,reference_parity=True,
                model_sha256={name:hashlib.sha256(m.m.build()).hexdigest()
                              for name,m in (('before',before),('after',after))})
    (out/'all-frames.json').write_text(json.dumps(report,separators=(',',':'))+'\n')
    return report


def _init_worker(before, after, library):
    global _renderers
    _renderers = [Renderer(m,library) for m in (before,after)]


def _render_worker(task):
    key, a, b = task
    ra, rb = _renderers
    views = []
    for view in range(8):
        yaw=view*math.pi/4
        x,frame=ra.render(a,yaw)
        y,_=rb.render(b,yaw,frame=frame)
        xp,_=ra.render(a,yaw,frame=frame,phase=2)
        yp,_=rb.render(b,yaw,frame=frame,phase=2)
        views.append([int(np.any(x!=y,axis=2).sum()),int(np.any(x!=xp,axis=2).sum()),int(np.any(y!=yp,axis=2).sum()),
                      hashlib.sha256(x.tobytes()).hexdigest(),hashlib.sha256(y.tobytes()).hexdigest()])
    return key, views




def deformation_floor(model, entry):
    """Certify a depth lower bound under independent vertex perturbations.

    For det(u,v,w), each difference vector changes by at most 2 sqrt(3) e
    when each endpoint coordinate changes by e. Multilinearity and Hadamard's
    inequality bound the seven error terms. Five strict orientation signs
    certify an edge through a triangle interior. This includes rotation and
    reshaping whose world-coordinate displacement stays in the stated cube;
    it does not prove a floor under larger edits or topology changes.
    """
    from tools.models.mesh_round4 import pair_at
    triangles = pair_at(model, entry['bones'],entry['slot'],entry['tick'])
    candidates=[]
    for swap, (aa,bb) in enumerate((triangles,triangles[::-1])):
        for i,a in enumerate(aa):
            for j,b in enumerate(bb):
                if (a.min(0)>b.max(0)).any() or (b.min(0)>a.max(0)).any():
                    continue
                for edge in range(3):
                    e=a[[edge,(edge+1)%3]]
                    vectors=[(b[1]-b[0],b[2]-b[0],point-b[0]) for point in e]
                    vectors += [(e[1]-e[0],b[k]-e[0],b[(k+1)%3]-e[0]) for k in range(3)]
                    vectors=np.asarray(vectors)
                    det=np.einsum('ij,ij->i',vectors[:,0],np.cross(vectors[:,1],vectors[:,2]))
                    if not(det[0]*det[1]<0 and (np.all(det[2:]>0) or np.all(det[2:]<0))):
                        continue
                    norms=np.linalg.norm(vectors,axis=2)
                    low,high=0.,128.
                    for _ in range(35):
                        middle=(low+high)/2
                        err=_det_error(norms,middle)
                        if np.all(np.abs(det)>err+1e-7):low=middle
                        else:high=middle
                    candidates.append((low,swap,i,j,edge))
    if not candidates:
        return dict(proven=False,reason='no strict edge/interior witness at this inclusive detector maximum')
    radius,swap,i,j,edge=max(candidates)
    aa,bb=triangles if swap==0 else triangles[::-1]
    result=dict(proven=True,vertex_coordinate_radius=radius/2,
                edge_triangle=aa[i].tolist(),face_triangle=bb[j].tolist(),edge=edge)
    result['depth_lower_bound']=verify_deformation_floor(result)
    return result


def _det_error(norms, radius):
    e=2*math.sqrt(3)*radius
    a,b,c=norms.T
    return e*(a*b+a*c+b*c)+e*e*(a+b+c)+e**3


def verify_deformation_floor(record):
    a,b=np.array(record['edge_triangle']),np.array(record['face_triangle'])
    edge=record['edge'];e=a[[edge,(edge+1)%3]]
    vectors=[(b[1]-b[0],b[2]-b[0],point-b[0]) for point in e]
    vectors += [(e[1]-e[0],b[k]-e[0],b[(k+1)%3]-e[0]) for k in range(3)]
    vectors=np.asarray(vectors)
    det=np.linalg.det(vectors)
    error=_det_error(np.linalg.norm(vectors,axis=2),record['vertex_coordinate_radius'])
    if not (det[0]*det[1]<0 and (np.all(det[2:]>0) or np.all(det[2:]<0)) and np.all(np.abs(det)>error+1e-7)):
        raise ValueError('deformation certificate failed')
    displacement=2*math.sqrt(3)*record['vertex_coordinate_radius']
    normal_bound=(np.linalg.norm(b[1]-b[0])+displacement)*(np.linalg.norm(b[2]-b[0])+displacement)
    return float(np.min((np.abs(det)-error)[:2])/normal_bound)


def floor_report(model, ledger, out):
    records = {}
    for pair, entry in ledger['pairs'].items():
        proof = deformation_floor(model,entry)
        records[pair] = dict(entry=entry,certificate=proof)
        print('floor',pair,proof.get('depth_lower_bound'),flush=True)
    result = dict(scope='independent per-vertex world-coordinate perturbations within each recorded radius; excludes larger edits and topology changes',
                  unrestricted_floor_proven=False,pairs=records)
    out.mkdir(parents=True,exist_ok=True)
    (out/'pair-floors.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def preservation(before, after):
    import mmd
    import motionstorage
    from tools.models.mesh_stability import packet_bytes, _normal
    assert before.bones == after.bones
    assert before.m.anims.table == after.m.anims.table
    assert before.tim.to_bytes() == after.tim.to_bytes()
    ticks=0
    for slot in before.slots():
        a,info=mmd.simulate(before.m.anims.anims[before.m.anims.table[slot]],27,slot=slot)
        b,got=mmd.simulate(after.m.anims.anims[after.m.anims.table[slot]],27,slot=slot)
        assert info == got and len(a) == len(b)
        expected=np.asarray(a)
        expected[:,[20,21],:3]=4096
        assert np.array_equal(expected,np.asarray(b)),slot
        ticks+=len(a)
    def triangles(model, geometry=True):
        out=[]
        for t in model.tris:
            bone,oi,pi,ids,uv,_,_,_=t
            if oi in (19,20):continue
            d=model.m.tmd.objects[oi].prims[pi].decode()
            corners=[]
            for k,vi in enumerate(ids):
                source_corner=d['verts'].index(vi)
                normal=d['norms'][min(source_corner,len(d['norms'])-1)] if d['norms'] else None
                color=d['colors'][min(source_corner,len(d['colors'])-1)][:3] if d['colors'] else None
                position=tuple(model.m.tmd.obj_verts(oi)[vi]) if geometry and oi not in (1,3,8) else None
                norm=tuple(model.m.tmd.obj_norms(oi)[normal]) if normal is not None and geometry and oi not in (1,3,8) else None
                corners.append((position,norm,tuple(uv[k]) if uv else None,tuple(color) if color else None))
            out.append((bone,oi,d['mode']&~8,d['flag'],d['cba'],d['tsb'],tuple(corners)))
        return out
    assert triangles(before) == triangles(after)
    def zero(model):
        return sum(not any(_normal(*[model.m.tmd.obj_verts(t[1])[v] for v in t[3]]))
                   for t in model.tris if t[1] not in (19,20))
    storage=[motionstorage.require(m.m.build(),27) for m in (before,after)]
    assert storage[1]['resident_bytes'] <= storage[0]['resident_bytes']
    return dict(slots=len(before.slots()),ticks=ticks,visible_decoded_poses_exact=True,
                root_travel_timing_events_loops_aliases_exact=True,foot_trajectories_exact=True,
                pose_exception='scales of empty fin objects 19/20 become implicit unit scales',
                source_gpu_triangles_and_corner_attributes_preserved=True,
                changed_geometry_objects=[1,3,8],removed_invisible_objects=[19,20],
                zero_area_visible_triangles=[zero(m) for m in (before,after)],
                storage_before_after=storage,packet_format_bytes=[packet_bytes(m.m) for m in (before,after)])


if __name__ == '__main__':
    import argparse
    from tools.models.mesh_round4 import load
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('before',type=Path)
    p.add_argument('after',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--floor-ledger',type=Path)
    a=p.parse_args()
    if a.floor_ledger:
        floor_report(load(a.after,335),json.loads(a.floor_ledger.read_text()),a.out)
    else:
        sweep(load(a.before,335),load(a.after,335),a.out,
              [(0,0),(2,22),(4,13),(9,15),(21,11),(48,30)])
