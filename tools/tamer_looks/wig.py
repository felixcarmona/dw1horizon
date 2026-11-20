"""Mesh helpers shared by the hairstyles: points on the bald skull, shells, spikes, tubes and the final clean-up."""
import copy
import math

from . import vec as np

import mmd

XC,YC=30.0,-2.0; SK=(44.0,50.0,39.0,40.0)        # the bald skull: up, front, back, side radii
U0,V0,UW,VH=168,114,48,14                         # layout coordinates of the hair pieces; u >= U0+46 marks an underside
HAIRLINE_SINK=0.9
HAIR_ROW=1                                        # the palette row of the hair (the cap's, free once the cap is gone)
HAIR_CBA=(488+HAIR_ROW)<<6
class Wig:
    base=None      # the bald model every style starts from (set by tamer_looks.build)
    def __init__(s):
        s.m=copy.deepcopy(Wig.base)
        tm=s.m.tmd; s.ob=tm.objects[1]; s.NV=[v[:3] for v in tm.obj_verts(1)]; s.base=len(s.NV)
        s.NO=list(tm.norms[s.ob.norm_start:s.ob.norm_start+s.ob.nnorm]); s.prims=[p.decode() for p in s.ob.prims]; s.nold=len(s.prims)
    def add(s,p): s.NV.append(tuple(int(round(c)) for c in p)); return len(s.NV)-1
    def pt(s,phi,az,sc=1.0,lift=0.0):
        f=math.cos(math.radians(phi)); ca,sa=math.cos(math.radians(az)),math.sin(math.radians(az))
        return (XC+(SK[0]*sc+lift)*math.sin(math.radians(phi)), YC-(SK[1] if ca>0 else SK[2])*sc*f*ca, SK[3]*sc*f*sa)
    def atx(s,x,az,sc=1.0):
        xe=max(x,8.0); phi=math.degrees(math.asin(max(-1,min(1,(xe-XC)/(SK[0]*sc))))); p=s.pt(phi,az,sc); return (x,p[1],p[2])
    def quad(s,a,b,c,d,uv): s.prims.append(dict(mode=0x3c,flag=0,olen=12,uv=list(uv),cba=HAIR_CBA,tsb=5,uvpad=[0,0],colors=[],norms=[a,b,c,d],verts=[a,b,c,d],pad=[]))
    def tri(s,a,b,c,uv): s.prims.append(dict(mode=0x34,flag=0,olen=9,uv=list(uv),cba=HAIR_CBA,tsb=5,uvpad=[0],colors=[],norms=[a,b,c],verts=[a,b,c],pad=[]))
    def ucol(s,i): u=U0+(i%8)*6; return u,min(u+6,U0+UW-1)
    def shell(s,N,phis,sc,hem,hemsc,lift=0.0,vs=None):
        """N columns round the head; rings at elevations phis; sc(az,phi) thickness; hem(az,i) height of the loose edge."""
        azs=[-180+360*(i+0.5)/N for i in range(N)]
        bk=lambda a:1+0.06*max(0,-math.cos(math.radians(a)))**6
        rings=[[s.add(s.pt(ph,a,sc(a,ph)*bk(a),lift)) for a in azs] for ph in phis]
        rings.append([s.add(s.atx(hem(a,i),a,hemsc(a,i)*bk(a))) for i,a in enumerate(azs)])
        T=s.add((XC+SK[0]*sc(0,90)+lift,YC+2,0)); K=len(rings); vs=vs or [V0+round(k*(VH-1)/K) for k in range(K+1)]
        for i in range(N):
            j=(i+1)%N; u0,u1=s.ucol(i)
            s.tri(rings[0][i],rings[0][j],T,[(u0,vs[1]),(u1,vs[1]),((u0+u1)//2,vs[0])])
            for k in range(K-1):
                s.quad(rings[k][i],rings[k][j],rings[k+1][i],rings[k+1][j],[(u0,vs[k+1]),(u1,vs[k+1]),(u0,vs[k+2]),(u1,vs[k+2])])
        return rings,azs
    def spike(s,phi,az,width,length,sc=1.0,dphi=0.0,daz=0.0,sides=4,flat=1.0):
        """A lock standing out of the hair: base on the shell round (phi,az), tip `length` further out, bent by dphi/daz."""
        c=np.array(s.pt(phi,az,sc)); o=np.array([XC+10,YC,0]); n=(c-o)/np.norm(c-o)
        up=np.array([1.0,0,0]); t1=np.cross(n,up); 
        if np.norm(t1)<1e-3: t1=np.array([0,0,1.0])
        t1/=np.norm(t1); t2=np.cross(n,t1)
        tipdir=np.array(s.pt(phi+dphi,az+daz,sc))-o; tipdir/=np.norm(tipdir)
        apex=s.add(c+tipdir*length); base=[]
        for k in range(sides):
            a=2*math.pi*k/sides+math.pi/sides; base.append(s.add(c-n*4+t1*math.cos(a)*width*flat+t2*math.sin(a)*width))
        for k in range(sides):
            u0,u1=s.ucol(k); s.tri(base[k],base[(k+1)%sides],apex,[(u0,V0+3),(u1,V0+3),((u0+u1)//2,V0+VH-1)])
    def tube(s,pts,radii,sides=5):
        rs=[]
        for (p,r) in zip(pts,radii):
            p=np.array(p,float); rs.append([s.add(p+np.array([0,math.cos(2*math.pi*k/sides),math.sin(2*math.pi*k/sides)])*r) if r>0 else None for k in range(sides)])
        for a in range(len(pts)-1):
            for k in range(sides):
                u0,u1=s.ucol(k); v0=V0+round(a*(VH-1)/(len(pts)-1)); v1=V0+round((a+1)*(VH-1)/(len(pts)-1)); kk=(k+1)%sides
                if radii[a+1]>0: s.quad(rs[a][k],rs[a][kk],rs[a+1][k],rs[a+1][kk],[(u0,v0),(u1,v0),(u0,v1),(u1,v1)])
                else:
                    if a+1 not in s.__dict__.setdefault('_ap',{}): s._ap[a+1]=s.add(pts[a+1])
                    s.tri(rs[a][k],rs[a][kk],s._ap[a+1],[(u0,v0),(u1,v0),((u0+u1)//2,v1)])
    def model(s):
        """The finished model: hair polygons wound outwards, smooth normals, the covered skull removed."""
        A=np.array(s.NV,float)
        for d in s.prims[s.nold:]:
            ids=d['verts']; P=[A[i] for i in ids]; cen=sum(P)/len(P); a,b,c=P[0],P[1],P[2]
            # outward = away from the piece's own middle when it is a closed lock, else away from the head's axis
            ref=d.get('ref'); o=np.array(ref) if ref is not None else np.array([min(cen[0],XC+8),YC,0.0])
            if np.dot(np.cross(b-a,c-a),cen-o)>0:
                od=[1,0,3,2] if len(ids)==4 else [1,0,2]
                for key in ('verts','norms','uv'): d[key]=[d[key][i] for i in od]
        acc=[np.Vec((0.0,0.0,0.0)) for _ in s.NV]
        for d in s.prims[s.nold:]:
            ids=d['verts']
            for c in ([(0,1,2)]+([(1,3,2)] if len(ids)==4 else [])):
                a,b,cc=[A[ids[k]] for k in c]; gn=-np.cross(b-a,cc-a)
                for k in c: acc[ids[k]]+=gn
        NN=s.NO[:s.base]
        for i in range(s.base,len(s.NV)):
            n=acc[i]; l=np.norm(n); n=n/l if l>0 else np.array([1.0,0,0]); NN.append(tuple(int(round(c*4096)) for c in n)+(0,))
        for d in s.prims: d.pop('ref',None)
        tm=s.m.tmd; ob=s.ob; dv=len(s.NV)-ob.nvert; dn=len(NN)-ob.nnorm
        tm.verts[ob.vert_start:ob.vert_start+ob.nvert]=[v+(0,) for v in s.NV]
        tm.norms[ob.norm_start:ob.norm_start+ob.nnorm]=NN
        ob.nvert=len(s.NV); ob.nnorm=len(NN); skull=list(s.prims[:s.nold])  # the crown is always under hair
        hair=s.prims[s.nold:]
        C=np.array([30.0,-2.0,0.0]); T=[]
        for d in hair:
            v=[np.array(s.NV[i][:3],float) for i in d['verts']]
            T.append((v[0],v[1],v[2]))
            if len(v)==4: T.append((v[1],v[2],v[3])); T.append((v[0],v[1],v[3])); T.append((v[0],v[2],v[3]))
        T=[(a,b-a,c-a,C-a,np.cross(C-a,b-a)) for a,b,c in T]
        def covered(p):
            """Whether the ray from the head's middle to p meets a hair triangle before reaching p."""
            dr=p-C; n=np.norm(dr)
            if n<1e-6: return True
            dr=dr/n
            for a,e1,e2,sv,q in T:
                h=np.cross(dr,e2); det=np.dot(e1,h)
                if abs(det)<=1e-9: continue
                f=1/det; u=f*np.dot(sv,h); w=f*np.dot(q,dr)
                if u>=-.01 and w>=-.01 and u+w<=1.01 and f*np.dot(e2,q)>n-1.0: return True
            return False
        cov={i:covered(np.array(s.NV[i][:3],float)) for d in skull for i in d['verts']}
        keep=[d for d in skull if not all(cov[i] for i in d['verts'])]      # skull polygons wholly under the hair are dropped
        for d in hair: d['flag']=2      # double-faced (the menu's close-up draws the far faces itself: lookHairInside)
        skull=keep
        for i in {i for d in keep for i in d['verts'] if cov.get(i)}:      # the hidden corners of the hairline polygons sink into the head
            q=C+(np.array(s.NV[i][:3],float)-C)*HAIRLINE_SINK; s.NV[i]=tuple(int(round(c)) for c in q)
        tm.verts[ob.vert_start:ob.vert_start+ob.nvert]=[v+(0,) for v in s.NV]
        out=[]
        for d in hair:      # a quad whose corners are not in one plane is dropped whole by the game: triangles only
            if len(d['verts'])==4:
                for od in ((0,1,2),(2,1,3)):
                    out.append(dict(d,uv=[d['uv'][i] for i in od],norms=[d['norms'][i] for i in od],verts=[d['verts'][i] for i in od]))
            else: out.append(d)
        hair=out
        for d in hair: d.update(mode=0x34,olen=9,cba=HAIR_CBA,uvpad=[0])      # textured gouraud triangles in the hair's own palette row
        ob.prims=[mmd.Prim.encode(d) for d in hair+skull]  # hair first: the game draws earlier polygons on top in a depth tie
        for o in tm.objects[2:]: o.vert_start+=dv; o.norm_start+=dn
        return s.m


O=np.array([XC,YC,0.])
def dirv(phi,az):
    p,a=math.radians(phi),math.radians(az); return np.array([math.sin(p),-math.cos(p)*math.cos(a),math.cos(p)*math.sin(a)])
def skull_ray(d,sc=1.0):
    t=1/math.sqrt((d[0]/SK[0])**2+(d[1]/(SK[1] if d[1]<0 else SK[2]))**2+(d[2]/SK[3])**2); return O+d*t*sc
def slerp(d0,d1,l):
    w=math.acos(max(-1,min(1,float(d0@d1))))
    return d0 if w<1e-4 else (math.sin((1-l)*w)*d0+math.sin(l*w)*d1)/math.sin(w)
def X(x): return math.degrees(math.asin(max(-1,min(1,(x-XC)/SK[0]))))
HAIR_THICKNESS=0.55      # how much of a style's nominal lift over the skull is kept
def ray(d,sc):
    """A point over the skull along direction d; sc > 1 lifts the hair off it."""
    return skull_ray(d,1+(sc-1)*HAIR_THICKNESS if sc>1 else sc)
