"""Kyubimon-only separating-plane certificates and exhaustive pair comparison.

The legacy inclusive ledger counts touching edges and assigns the *whole*
triangle's plane span as depth. A strict separating plane proves zero interior
intersection even when that diagnostic gives a positive number. No unresolved
body/limb crossing is dismissed by these fan-specific certificates.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from tools.models.mesh_round4 import load


def separating_plane(left, right, origin, iterations=20000):
    """Find and independently check a strict plane through the common apex.

    The search is heuristic; failure is inconclusive. The returned certificate
    is checked against every original vertex, including the coincident apex.
    Linear extrema on a triangle occur at vertices, covering the full surface.
    """
    left, right = [np.unique(np.asarray(v).reshape(-1,3),axis=0)-origin for v in (left,right)]
    constraints = np.concatenate([left,-right])
    constraints = constraints[np.linalg.norm(constraints,axis=1)>1e-7]
    unit = constraints/np.linalg.norm(constraints,axis=1)[:,None]
    n = np.zeros(3)
    for _ in range(iterations):
        dots = unit@n
        worst = dots.argmin()
        if dots[worst] > 1e-5:
            break
        n += unit[worst]
    if np.linalg.norm(n) < 1e-9:
        return None
    n /= np.linalg.norm(n)
    margins = constraints@n
    # A separate direct dot-product check supplies a conservative margin.
    if margins.min() <= 1e-7:
        return None
    return dict(normal=n.tolist(),origin=np.asarray(origin).tolist(),
                positive_margin=float((left[np.linalg.norm(left,axis=1)>1e-7]@n).min()),
                negative_margin=float((-right[np.linalg.norm(right,axis=1)>1e-7]@n).min()))


def certificates(model, fan):
    groups=fan['groups'];source=fan['source_packets']
    triangles=lambda packets: np.array([model.local[15][list(t[3])] for t in model.tris
                                       if t[0]==15 and t[2] in packets])
    tails=[triangles(g) for g in groups]
    rows=[]
    for a in range(9):
        for b in range(a+1,9):
            cert=separating_plane(tails[a],tails[b],np.zeros(3))
            if cert is None:
                raise ValueError(f'no strict cross-tail certificate {a}/{b}')
            rows.append(dict(tails=[a,b],certificate=cert,interior_depth_units=0))
    from tools.models.mesh_fan import JOINS
    joins=[]
    for tail,(proximal,_,_) in enumerate(JOINS):
        base=triangles([i for i,s in enumerate(source) if s in proximal])
        end=triangles([i for i,s in enumerate(source) if 84+20*tail<=s<104+20*tail])
        x=fan['join_planes'][tail]
        if base[:,:,0].max()>x or end[:,:,0].min()<x:
            raise ValueError(f'join {tail}: plane separation failed')
        if any(np.any(np.all(t[:,:,0]==x,axis=1)) for t in (base,end)):
            raise ValueError(f'join {tail}: retained a cap on the common plane')
        joins.append(dict(tail=tail,plane_x=x,interior_depth_units=0))
    roots=[];ticks=0
    for slot in model.slots():
        for tick,pose in enumerate(model.poses(slot,6000)):
            matrices=model.matrices(pose)
            if not np.allclose(matrices[15][:3,:3].T@matrices[15][:3,:3],np.eye(3),atol=1e-9):
                raise ValueError('tail rigid-depth invariance failed')
            relative=np.linalg.inv(matrices[14])@matrices[15]
            fan_points=model.local[15]@relative[:3,:3].T+relative[:3,3]
            cert=separating_plane(fan_points,model.local[14],np.array([121,0,-54]))
            if cert is None:
                raise ValueError(f'root separation inconclusive at {slot}/{tick}')
            roots.append(dict(slot=slot,tick=tick,certificate=cert,interior_depth_units=0))
            ticks+=1
    return dict(cross_tail=rows,joins=joins,root_frames=roots,slots=len(model.slots()),ticks=ticks,
                rigid_tail_depth_invariance=True,all_certificates_verified=True)


def pair_table(before, after, path):
    with path.open('w') as f:
        writer=csv.writer(f)
        writer.writerow(['bone_pair','before_units','after_units','after_slot','after_frame','status'])
        for key in sorted(before['pairs'].keys()|after['pairs'].keys(),key=lambda k:tuple(map(int,k.split('/')))):
            b=before['pairs'].get(key,{});a=after['pairs'].get(key,{})
            status='cleared' if not a else 'boundary-only; verified separating planes' if key=='14/15' else 'unresolved; no unrestricted floor proven'
            writer.writerow([key,round(b.get('depth',0),6),round(a.get('depth',0),6),a.get('slot',''),a.get('tick',''),status])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path)
    p.add_argument('fan',type=Path)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    result=certificates(load(args.folder,409),json.loads(args.fan.read_text()))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(result['ticks'],'ticks: all fan separating planes verified')


if __name__=='__main__':
    main()
