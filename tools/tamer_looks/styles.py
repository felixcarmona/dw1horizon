"""The hairstyles. Each is one sculpted volume over the bald skull: a welded shell cut at the hem into a few big
swept chunks (fringe blades, sideburns, nape points), each with an underside so the edge has body; tails and buns
are closed tubes. STYLES keeps them in the order the game numbers them."""
import math

from . import vec as np

from .wig import *

BACKING_FRONT=0.8      # cos of the azimuth where the backing band stops: the fringe keeps its open notches
UNDERSIDE_DEPTH=0.6    # a lock's underside ends inside the head: ending on its surface leaves a slit that shows what is behind
TW=23      # width of one hair piece in layout coordinates

DK=[(U0+46,V0+1),(U0+47,V0+1),(U0+46,V0+12)]
def surf(x,az,sc,x0=-8,flare=0.0):
    """On the scaled skull down to x0; below it the hair hangs straight (flare opens it)."""
    if x>=x0: return ray(dirv(X(x),az),sc)
    p=ray(dirv(X(x0),az),sc); k=1+flare*(x0-x)/40; return np.array([x,YC+(p[1]-YC)*k,p[2]*k])
class Sculpt(Wig):
    shine=()
    def build(s,bounds,clumps,sc=(1.10,1.13,1.15,1.15),phis=(62,36,12),groove=0.05,bulge=0.025,mid=0,x0=-8,flare=0.0,scf=None,double=False,flat=False):
        """bounds: [(az,notch_x)] going round; clumps[i] sits between bounds[i] and bounds[i+1]: (tip_x, sweep, tip_sc[, extra bulge])."""
        fr=lambda az: math.cos(math.radians(az))>0.38
        bounds=[(az,max(x,35) if fr(az) and x>=24 else x) for az,x in bounds]
        n=len(bounds); T=s.add(ray(dirv(90,0),sc[0])); nr=len(phis)+mid+1
        vs=[V0]+[V0+3+int(round(k*8/(nr-1))) for k in range(nr)]+[V0+13]
        def col(az,off,x_end):
            f=(lambda k: scf(k,az)) if scf else (lambda k: 0)
            c=[ray(dirv(ph,az),sc[min(k+1,3)]+f(k)+(off if k>0 else off*0.4)) for k,ph in enumerate(phis)]; xl=c[-1][0]
            for j in range(1,mid+1): c.append(surf(xl+(x_end-xl)*j/(mid+1),az,sc[3]+off,x0,flare*j/(mid+1)))
            c.append(surf(x_end,az,sc[3]+off+f(len(phis)),x0,flare)); return [s.add(p) for p in c]
        np0=len(s.prims)
        under=[]
        N=[col(az,-groove,x) for az,x in bounds]
        for i in range(n):
            a0,xa=bounds[i]; a1,xb=bounds[(i+1)%n]
            if a1<a0: a1+=360
            tipx,sw,tsc=clumps[i][:3]; ex=clumps[i][3] if len(clumps[i])>3 else 0; am=(a0+a1)/2; hw=(a1-a0)/2; xm=(xa+xb)/2-1; F=fr(am); F2=math.cos(math.radians(am))>-0.1
            if F and 15<=tipx<30: tipx=29+(tipx-24)*0.4
            C=col(am,bulge+ex,xm); tp=surf(tipx,am+sw*hw,tsc,x0,flare); tip=s.add(tp); L,R=N[i],N[(i+1)%n]
            ub=U0+(1 if i in s.shine else 0)*TW; uL,uC,uR=ub,ub+11,ub+22
            s.tri(L[0],C[0],T,[(uL,vs[1]),(uC,vs[1]),(uC,vs[0])]); s.tri(C[0],R[0],T,[(uC,vs[1]),(uR,vs[1]),(uC,vs[0])])
            for k in range(nr-1):
                s.quad(L[k],C[k],L[k+1],C[k+1],[(uL,vs[k+1]),(uC,vs[k+1]),(uL,vs[k+2]),(uC,vs[k+2])])
                s.quad(C[k],R[k],C[k+1],R[k+1],[(uC,vs[k+1]),(uR,vs[k+1]),(uC,vs[k+2]),(uR,vs[k+2])])
            vt=V0+10 if F2 else vs[-1]
            s.tri(L[-1],C[-1],tip,[(uL,vs[-2]),(uC,vs[-2]),(uC,vt)]); s.tri(C[-1],R[-1],tip,[(uC,vs[-2]),(uR,vs[-2]),(uC,vt)])
            P=[np.array(s.NV[j],float) for j in (L[-1],R[-1],tip)]; l2,r2,t2=[s.add(p) for p in P]
            inner=s.add(surf(min(tipx+14,xm+2),am+sw*hw*0.5,UNDERSIDE_DEPTH,x0,0))
            cen=(P[0]+P[1]+P[2])/3; out=cen-np.array([cen[0],YC,0]); out/=np.norm(out); ref=tuple(cen+out*6+np.array([4.0,0,0]))
            for a,b in ((l2,t2),(t2,r2)):
                s.tri(a,b,inner,[(U0+2,V0+2)]*3 if F2 else DK); s.prims[-1]['ref']=ref
            under.append((l2,inner,ref,F2))
        for i in range(n):      # between two locks' undersides: without it the notch is a slit into the head
            l2,inner,ref,F2=under[i]
            s.tri(l2,under[i-1][1],inner,[(U0+2,V0+2)]*3 if F2 else DK); s.prims[-1]['ref']=ref
        # backing: a plain band of hair under the hem from the temples back, so the gaps between locks show hair, never what is
        # behind the head (the temples too: in a three-quarter close-up they are the head's outline)
        tops={}
        for i in range(n):
            a0,xa=bounds[i]; a1,xb=bounds[(i+1)%n]
            if a1<a0: a1+=360
            am=(a0+a1)/2; tipx=clumps[i][0]
            if math.cos(math.radians(am))>BACKING_FRONT: continue
            cols=[]
            for az,xt in ((a0,xa),(am,max(xa,xb)),(a1,xb)):
                key=(round(az%360,3),xt)
                if key not in tops: tops[key]=s.add(surf(xt+9,az,1.06,x0,0))
                cols.append((tops[key],s.add(surf(tipx+2,az,1.06,x0,flare*0.9))))
            uvb=[(U0+2,V0+2)]*4
            for c0,c1 in ((cols[0],cols[1]),(cols[1],cols[2])): s.quad(c0[0],c1[0],c0[1],c1[1],uvb)
        for p in s.prims[np0:]:
            if flat: p['uv']=[DK[0] if min(s.NV[v][0] for v in p['verts'])<30 else (U0+2,V0+2)]*len(p['uv'])
            if double and all(s.NV[v][0]<x0+6 or s.NV[v][0]<12 for v in p['verts'][1:]) and 'ref' not in p: p['flag']=2
    def tail(s,pts,radii,sides=6,flat=1.0):
        """A tube of hair along pts (ponytail, bun); the last point is the tip."""
        pts=[np.array(p,float) for p in pts]; n=len(pts)-1; rings=[]
        for i in range(n):
            t=pts[i+1]-pts[max(i-1,0)]; t/=np.norm(t); a=np.cross(t,[0,0,1.0])
            if np.norm(a)<0.2: a=np.cross(t,[0,1.0,0])
            a/=np.norm(a); b=np.cross(t,a)
            rings.append([s.add(pts[i]+(a*math.cos(2*math.pi*j/sides)*flat+b*math.sin(2*math.pi*j/sides))*radii[i]) for j in range(sides)])
        apex=s.add(pts[-1]); v=lambda i: V0+6+int(round(i*7/n)); u=lambda j: U0+(16 if j%2 else 6)
        for i in range(n):
            for j in range(sides):
                k=(j+1)%sides; ref=tuple(pts[i])
                if i<n-1: s.quad(rings[i][j],rings[i][k],rings[i+1][j],rings[i+1][k],[(u(j),v(i)),(u(j+1),v(i)),(u(j),v(i+1)),(u(j+1),v(i+1))])
                else: s.tri(rings[i][j],rings[i][k],apex,[(u(j),v(i)),(u(j+1),v(i)),(U0+11,V0+13)])
                s.prims[-1]['ref']=ref
    def fade(s,hem,sc=1.05,xs=(47,35),lo=50,step=20):
        """Shaved sides and back: a thin dark skin under the top hair."""
        azs=list(range(lo,360-lo+1,step)); r=[[s.add(surf(x,az,sc)) for x in xs]+[s.add(surf(hem(az),az,sc-0.01))] for az in azs]
        for A,B in zip(r,r[1:]):
            for k in range(len(xs)): s.quad(A[k],B[k],A[k+1],B[k+1],[DK[0],DK[1],DK[2],DK[2]])
STYLES={}
def style(f): STYLES[f.__name__]=f; return f
@style
def classic():
    h=Sculpt()
    b=[(-58,31),(-20,33),(12,33),(40,32),(62,28),(88,20),(112,23),(140,16),(166,19),(-168,14),(-142,20),(-114,24),(-90,20)]
    c=[(26,.35,1.17,.02),(23,.3,1.19,.04),(25,-.3,1.18),(26,-.4,1.16,.03),(9,-.2,1.12),(20,.2,1.17,.02),(11,.4,1.21,.03),(5,.3,1.22),(8,-.1,1.24,.04),(4,-.3,1.22),(11,-.4,1.21,.03),(20,-.2,1.17),(9,.2,1.12)]
    h.shine={1,2,5,8,11}; h.build(b,c); return h
def tuft(s,phi,az,w,reach,length,dphi,daz,sc=1.13):
    """A loose lock standing off the volume: base sunk in the shell at (phi,az), pointing along (dphi,daz)."""
    c=ray(dirv(phi,az),sc); n=c-O; n/=np.norm(n); f=ray(dirv(phi+dphi,az+daz),sc)-c; f-=n*(f@n); f/=np.norm(f); sd=np.cross(n,f)
    bl=s.add(c-sd*w-n*4); br=s.add(c+sd*w-n*4); root=s.add(c-f*w*1.3+n*1.5); apex=s.add(c+f*reach+n*length)
    ref=tuple((c-sd*w-n*4+c+sd*w-n*4+c-f*w*1.3+n*1.5+c+f*reach+n*length)/4)
    DK=[(U0+46,V0+1),(U0+47,V0+1),(U0+46,V0+12)]
    s.tri(bl,root,apex,[(U0,V0+8),(U0+11,V0+7),(U0+11,V0+13)]); s.prims[-1]['ref']=ref
    s.tri(root,br,apex,[(U0+11,V0+7),(U0+22,V0+8),(U0+11,V0+13)]); s.prims[-1]['ref']=ref
    b2,a2,r2=[s.add(s.NV[j]) for j in (bl,apex,br)]
    s.tri(b2,a2,r2,DK); s.prims[-1]['ref']=ref
Sculpt.tuft=tuft
@style
def messy():
    h=Sculpt()
    b=[(-62,28),(-36,33),(-10,31),(12,34),(38,31),(62,27),(88,20),(114,24),(140,15),(166,20),(-170,13),(-144,19),(-116,24),(-90,20)]
    c=[(24,.5,1.18,.03),(22,.4,1.21,.05),(18,.1,1.17,.02),(23,-.5,1.22,.06),(25,.3,1.17,.02),(8,-.2,1.12),(17,.5,1.26,.04),
       (9,.4,1.24,.02),(3,.5,1.30,.05),(7,-.2,1.25,.02),(2,-.5,1.31,.06),(10,-.3,1.23,.02),(18,-.5,1.27,.05),(8,.2,1.12)]
    h.shine={1,3,6,10}; h.build(b,c,sc=(1.12,1.16,1.18,1.17))
    for t in [(70,150,10,18,7,-40,25),(60,-30,10,17,6,-30,-30),(50,70,9,16,7,-25,40),(36,120,9,17,7,-20,35),(42,-115,10,18,7,-15,-40),
              (26,178,10,16,8,-25,-20),(56,-165,9,15,7,-20,-35)]: h.tuft(*t)
    return h
def R(phi,az,sc=1.1): return ray(dirv(phi,az),sc)
def nrm(p): v=p-O; return v/np.norm(v)
def V(*a): return np.array(a,float)
@style
def ponytail():
    h=Sculpt()
    b=[(-60,29),(-22,32),(14,33),(42,31),(64,27),(88,21),(114,23),(140,14),(166,12),(-168,12),(-142,14),(-116,23),(-90,21)]
    c=[(24,.5,1.16,.02),(22,.5,1.18,.04),(23,.5,1.17,.02),(25,.2,1.15),(9,-.2,1.11),(19,.3,1.15),(12,.3,1.16),(10,.2,1.16),(9,0,1.16),(10,-.2,1.16),(12,-.3,1.16),(19,-.3,1.15),(9,.2,1.11)]
    h.shine={1,6,8,10}; h.build(b,c,sc=(1.09,1.12,1.13,1.13),groove=0.03)
    h.tail([V(50,30,0),V(60,47,0),V(58,66,0),V(38,79,0),V(14,78,0),V(-10,71,0),V(-30,62,0)],[14,13.5,21,24.5,22,13],flat=0.85)
    return h
def pigtails_cap():
    h=Sculpt()
    b=[(-62,27),(-38,26),(-12,27),(12,26),(38,27),(62,27),(88,21),(114,23),(140,14),(166,12),(-168,12),(-142,14),(-116,23),(-90,21)]
    c=[(22,.2,1.16,.02),(23,-.1,1.17,.03),(22,.1,1.17,.03),(23,.1,1.17,.03),(22,-.2,1.16,.02),(7,-.2,1.11),(19,.3,1.15),(12,.3,1.16),(10,.2,1.16),(10,-.2,1.16),(12,-.3,1.16),(19,-.3,1.15),(7,.2,1.11)]
    h.shine={1,3,7,11}; h.build(b,c[:8]+[(9,0,1.16)]+c[8:],sc=(1.09,1.12,1.13,1.13),groove=0.03); return h
@style
def pigtails():
    h=pigtails_cap()
    for sg in (1,-1):
        r=R(22,sg*108,1.05); n=nrm(r); p1=r+n*8; p2=p1+n*11+V(-6,1,0); p3=p2+V(-16,2,sg*10); p4=p3+V(-18,1,sg*4); p5=p4+V(-14,0,0)
        h.tail([r-n*5,p1,p2,p3,p4,p5,p5+V(-9,0,0)],[16,15,17,19,16,9],flat=0.9)
    return h
@style
def bun():
    h=Sculpt()
    b=[(-58,35),(-20,38),(16,38),(46,36),(66,27),(88,21),(114,23),(140,14),(166,12),(-168,12),(-142,14),(-116,23),(-90,21),(-68,27)]
    c=[(33,.3,1.13),(35,.2,1.14,.02),(34,-.3,1.13),(12,.6,1.14),(19,-.2,1.12),(19,.3,1.14),(12,.3,1.15),(10,.2,1.15),(9,0,1.15),(10,-.2,1.15),(12,-.3,1.15),(19,-.3,1.14),(19,.2,1.12),(12,-.6,1.14)]
    h.shine={1,5,8,11}; h.build(b,c,sc=(1.08,1.10,1.11,1.11),groove=0.025,bulge=0.015)
    r=R(58,180,1.0); n=nrm(r)
    h.tail([r,r+n*7,r+n*18,r+n*30,r+n*41,r+n*47],[12,23,27,25,14],sides=7)
    return h
@style
def buns():
    h=pigtails_cap()
    for sg in (1,-1):
        r=R(50,sg*92,1.0); n=nrm(r)
        h.tail([r,r+n*6,r+n*15,r+n*26,r+n*36,r+n*41],[10,19,22.5,20.5,12],sides=6)
    return h
@style
def long():
    h=Sculpt()
    b=[(-56,29),(-18,33),(18,32),(46,30),(66,-6),(92,-20),(118,-16),(144,-24),(170,-18),(-164,-25),(-138,-17),(-112,-21),(-88,-18),(-64,-6)]
    c=[(23,.5,1.17,.03),(21,.5,1.19,.05),(23,.5,1.18,.03),(-12,.1,1.17),(-22,.2,1.18,.02),(-28,-.2,1.20),(-24,.3,1.21,.02),(-31,.2,1.22),(-27,-.1,1.23,.02),
       (-32,-.2,1.22),(-25,-.3,1.21,.02),(-29,.2,1.20),(-23,-.2,1.18,.02),(-13,-.1,1.17)]
    h.shine={1,4,6,8,10,12}; h.build(b,c,mid=1,x0=6,flare=0.10,double=True)
    return h
@style
def curtains():
    h=Sculpt()
    b=[(0,39),(34,27),(64,20),(90,13),(116,14),(142,9),(168,11),(-168,9),(-142,13),(-116,12),(-90,13),(-64,20),(-34,27)]
    c=[(22,.75,1.21,.05),(12,.4,1.19,.02),(4,.2,1.20,.02),(3,.4,1.22),(0,.3,1.23,.03),(-2,.2,1.24),(-3,0,1.25,.03),(-2,-.2,1.24),(0,-.3,1.23,.03),(3,-.4,1.22),(4,-.2,1.20,.02),(12,-.4,1.19,.02),(22,-.75,1.21,.05)]
    h.shine={0,12,3,6,9}; h.build(b,c,sc=(1.10,1.15,1.17,1.16),groove=0.06)
    return h
@style
def quiff():
    h=Sculpt()
    b=[(-50,35),(-18,37),(16,37),(48,35),(78,40),(108,42),(140,43),(172,42),(-158,43),(-128,42),(-100,42),(-74,40)]
    c=[(34,.3,1.05,.03),(35,.3,1.05,.06),(34,.3,1.05,.03),(39,.2,1.20,.03),(38,.3,1.18),(39,.3,1.18),(38,.2,1.18),(37,0,1.18),(38,-.2,1.18),(39,-.3,1.18),(38,-.3,1.18),(40,-.2,1.20,.03)]
    def scf(k,az):
        f=max(0.0,math.cos(math.radians(az-12)))**1.5; return f*(0.14,0.26,0.17,-0.13)[k]
    h.shine={0,1,2,5,9}; h.build(b,c,sc=(1.16,1.17,1.15,1.13),phis=(68,52,36),groove=0.06,scf=scf)
    for t in [(50,-14,9,15,9,22,150,1.42),(54,18,9,16,10,20,170,1.44),(62,-40,8,13,7,15,-120,1.30),(60,52,8,13,7,15,125,1.30),(74,10,9,14,6,-20,170,1.28)]: h.tuft(*t)
    def hem(az):
        a=az if az<=180 else 360-az
        return 22 if a<110 else 22-(a-110)/70*12
    h.fade(hem); return h
@style
def mullet():
    h=Sculpt()
    b=[(-62,28),(-36,33),(-10,31),(12,34),(38,31),(62,27),(88,21),(112,22),(136,6),(160,2),(-176,5),(-152,1),(-130,7),(-110,22),(-88,21)]
    c=[(24,.5,1.18,.03),(22,.4,1.21,.05),(19,.1,1.17,.02),(23,-.5,1.22,.06),(25,.3,1.17,.02),(9,-.2,1.12),(16,.3,1.22,.04),
       (-10,.3,1.22,.02),(-20,.2,1.25,.04),(-24,0,1.27,.02),(-21,-.2,1.25,.04),(-12,-.3,1.22,.02),(15,-.3,1.22,.04),(9,.2,1.12)]
    h.shine={1,3,8,10}; h.build(b[:13]+b[13:],c[:13]+[(18,-.4,1.2)]+c[13:],sc=(1.12,1.16,1.18,1.17),mid=1,x0=6,flare=0.25,double=True)
    for t in [(68,150,10,17,7,-40,25),(60,-30,10,17,6,-30,-30),(50,70,9,16,7,-25,40),(44,-115,10,17,7,-15,-40)]: h.tuft(*t)
    return h
@style
def buzz():
    h=Sculpt()
    b=[(-56,33),(-20,35),(18,35),(54,33),(76,26),(96,25),(122,18),(150,12),(180,10),(-150,12),(-122,18),(-96,25),(-76,26)]
    c=[(32,0,1.045)]*4+[(15,-.3,1.04),(24,0,1.04),(17,0,1.04),(11,0,1.04),(11,0,1.04),(17,0,1.04),(24,0,1.04),(24,0,1.04),(15,.3,1.04)]
    h.build(b,c,sc=(1.035,1.04,1.045,1.045),groove=0.0,bulge=0.0,flat=True)
    return h
