"""The bald tamer: the original model with the cap and the hair under it replaced by a bare skull.

make(m, t) takes the tamer model (mmd.MMD) and its texture (mmd.Tim4) and returns the new pair. The face tile is
repainted without the fringe, the head mesh is rebuilt as a closed skull with ears, and nothing else changes.
"""
import copy
import math

from . import vec as np

import mmd


def make(m, t):
    W=t.w
    idx=bytearray(t.idx)
    def g(x,y): return idx[y*W+x]
    def s(x,y,v): idx[y*W+x]=v
    HAIR={0xf,9,8,6}
    # ---------------- face tile (0..55 x 0..39) and the eye frames
    def facefix(ox,x0,x1):          # ox: where tile x=0 sits; touches tile columns x0..x1-1
        for y in range(0,29):
            for x in range(x0,x1):
                c=g(ox+x,y); n=c
                top = y<=3
                tuft = y>=4 and x<=12 and x+y<=16
                side = (y==4 and x>=21 and x<=33) or (5<=y<=14 and 24<=x<=33) or (15<=y<=28 and 23<=x<=33)
                above_ear = y<=12 and x>=34
                if top or tuft:
                    if c in HAIR or c in (7,0xd,5): n=4
                elif x<=2 and 12<=y<=13:
                    n=4
                elif side:
                    if c in HAIR or c in (7,0xd,5): n=4
                elif above_ear:
                    if c==0xf or c in (9,8): n=4
                elif x>=42 and y>=8:
                    if c in HAIR or c==7: n=4 if y<22+(55-x)//3 else 5
                s(ox+x,y,n)
    facefix(0,0,56)
    for k in range(9): facefix(56+16*k-8,8,24)
    for y in range(20,40):
        for x in range(28,56):
            c=g(x,y)
            if c==0xf and y>=29: s(x,y,5)
            elif c==0xd and x>=30: s(x,y,5)
            elif c==5 and x>=36 and y<22+(55-x)//3: s(x,y,4)
    for x,y in ((38,26),(39,26),(40,26)):
        if g(x,y) in (0xf,9,8): s(x,y,7)
    # soft shadow behind and over the ear so it reads without the hair around it
    ear=[[g(x,y) for x in range(56)] for y in range(40)]
    orig=[[t.idx[y*W+x] for x in range(56)] for y in range(40)]
    for y in range(6,29):
        for x in range(33,56):
            o=orig[y][x]
            if o==0xf:          # was dark hair/outline: outline of the ear if it touches ear skin
                near=[orig[y+dy][x+dx] for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)) if 0<=x+dx<56]
                touches=any(n in (1,2,3,0xd,7) for n in near) and 34<=x<=47 and 7<=y<=27
                if touches and x>=41: s(x,y,0xd)
                elif touches and y<=9: s(x,y,5)
    # ---------------- back of the head (176..199 x 72..87) and the hair under the jaw tile (160..175 x 81..87)
    for y in range(72,88):
        for x in range(176,200):
            s(x,y,4 if y<81 else 5)
    for y in range(81,88):
        for x in range(160,176):
            if g(x,y) in HAIR or g(x,y)==7: s(x,y,0xd)
    # ---------------- new tiles on the space the hat used
    def tone(az,h):
        ph=math.radians(min(h,1)*90); d=lambda a,p:(math.cos(p)*math.cos(math.radians(a)),math.cos(p)*math.sin(math.radians(a)),math.sin(p))
        p,c=d(az,ph),d(38,math.radians(52)); ang=math.degrees(math.acos(max(-1,min(1,sum(i*j for i,j in zip(p,c))))))
        if ang<13: return 1
        if ang<29: return 2
        if ang<58: return 3
        return 4
    BU=[0,28,46,70,95]; BAZ=[0,57,93,121,180]
    def band_az(u):
        for j in range(4):
            if u<=BU[j+1]: return BAZ[j]+(BAZ[j+1]-BAZ[j])*(u-BU[j])/(BU[j+1]-BU[j])
    for y in range(40,56):
        for x in range(0,96): s(x,y,tone(band_az(x),(55-y)/15*0.27))
    for x in range(0,96):                       # the row that meets the face keeps the face's tone
        s(x,55,4); s(x,54,4)
    brow={50:range(13,21),51:range(9,23),52:range(7,22),53:range(6,11)}
    for y,xs in brow.items():
        for x in xs: s(x,y,9 if (y==51 and 11<=x<=20) or (y==52 and 8<=x<=15) else 8)
    s(23,52,7); s(22,52,8); s(5,53,7)
    TX,TY,TRU,TRV=239.5,89,15.0,21.0
    for y in range(88,112):
        for x in range(224,256):
            du=(x+.5-TX)/TRU; dv=(y+.5-TY)/TRV
            r=min(1,math.sqrt(du*du+dv*dv)); az=math.degrees(math.atan2(dv,-du))
            s(x,y,tone(az,0.27+(1-r)*0.73))
    t2=copy.deepcopy(t); t2.idx=bytes(idx)

    # ---------------- mesh
    tm=m.tmd; ob=tm.objects[1]
    V=[v[:3] for v in tm.obj_verts(1)]
    HAT={0,1,4,5,6,7,13,14,15,20,21,22,48,43,46,45,44,42,47}
    keep=[i for i in range(49) if i not in HAT]; remap={o:n for n,o in enumerate(keep)}
    NV=[V[i] for i in keep]
    prims=[]
    for p in ob.prims:
        d=p.decode()
        if d['cba']==0x7a40 or set(d['verts'])&HAT: continue
        d['verts']=[remap[v] for v in d['verts']]; prims.append(d)
    def add(x,y,z):
        NV.append((int(round(x)),int(round(y)),int(round(z)))); return len(NV)-1
    XC,YC,AX,AYF,AYB,AZ=30.0,-2.0,44.0,50.0,39.0,40.0
    def pt(phi,az,rf=1.0):
        f=math.cos(math.radians(phi))*rf; ca,sa=math.cos(math.radians(az)),math.sin(math.radians(az))
        return (XC+AX*math.sin(math.radians(phi)), YC-(AYF if ca>0 else AYB)*f*ca, AZ*f*sa)
    # rings: (phi front, phi back, azimuths of A B C, radial factors of A B C)
    RINGS=[(25,13,(57,93,121),(.93,.975,1.0)),(48,42,(52,91,127),(.985,1,1)),(70,67,(47,90,133),(1,1,1))]
    L0=[remap[27],remap[28],remap[26],remap[12],remap[3]]            # ring0, z<0 side: F A B C K
    R0=[remap[27],remap[38],remap[40],remap[41],remap[3]]
    ringsL=[L0]; ringsR=[R0]
    for pf,pb,azs,rfs in RINGS:
        ph=lambda az: pf+(pb-pf)*(1-math.cos(math.radians(az)))/2
        F=add(*pt(pf,0)); K=add(*pt(pb,180))
        Ls,Rs=[F],[F]
        for az,rf in zip(azs,rfs):
            x,y,z=pt(ph(az),az,rf); Ls.append(add(x,y,-z)); Rs.append(add(x,y,z))
        Ls.append(K); Rs.append(K); ringsL.append(Ls); ringsR.append(Rs)
    T=add(XC+AX,YC+2,0)
    def topuv(ring,j,side):
        r=[0.97,0.66,0.34][ring-1]; az=[0,RINGS[ring-1][2][0],RINGS[ring-1][2][1],RINGS[ring-1][2][2],180][j]
        az=[0,50,90,130,180][j]
        return (int(round(TX-TRU*r*math.cos(math.radians(az)))), int(round(TY+TRV*r*math.sin(math.radians(az)))))
    CBA,TSB=0x7b80,0x5
    def quad(a,b,c,d,uva,uvb,uvc,uvd,flip):
        # corner order a b c d renders as (a,b,c),(b,d,c)
        if flip: a,b,c,d,uva,uvb,uvc,uvd=b,a,d,c,uvb,uva,uvd,uvc
        prims.append(dict(mode=0x3c,flag=0,olen=12,uv=[uva,uvb,uvc,uvd],cba=CBA,tsb=TSB,uvpad=[0,0],colors=[],norms=[a,b,c,d],verts=[a,b,c,d],pad=[]))
    def tri(a,b,c,uva,uvb,uvc,flip):
        if flip: a,b,uva,uvb=b,a,uvb,uva
        prims.append(dict(mode=0x34,flag=0,olen=9,uv=[uva,uvb,uvc],cba=CBA,tsb=TSB,uvpad=[0],colors=[],norms=[a,b,c],verts=[a,b,c],pad=[]))
    for side,rings in ((0,ringsL),(1,ringsR)):
        for k in range(3):
            lo,hi=rings[k],rings[k+1]
            for j in range(4):
                if k==0: uv=[(BU[j],55),(BU[j+1],55),(BU[j],40),(BU[j+1],40)]
                else: uv=[topuv(k,j,side),topuv(k,j+1,side),topuv(k+1,j,side),topuv(k+1,j+1,side)]
                quad(lo[j],lo[j+1],hi[j],hi[j+1],*uv,flip=(side==1))
        for j in range(4):
            tri(rings[3][j],rings[3][j+1],T,topuv(3,j,side),topuv(3,j+1,side),(int(TX),int(TY)),flip=(side==1))
    # ---------------- nape: the skull curves in towards the neck instead of dropping straight
    def setv(i,x,y,z): NV[i]=(x,y,z)
    nb=len(prims)
    K_,N7=1,7
    setv(1,15,32,0); setv(7,-8,13,0)
    SIDE=[(6,5,18,-1),(29,19,20,1)]
    P_=add(3,25,0); B_=add(-3,19,0)
    drop=[]
    for C_,S_,J_,sg in SIDE:
        setv(S_,5,17,sg*26)
        M_=add(18,28,sg*22); N_=add(4,22,sg*18); R_=add(-6,13,sg*13); Q_=add(-2,19,sg*11)
        for k,d in enumerate(prims):
            vs=set(d['verts'])
            if vs=={S_,C_,7,1} or vs=={S_,7,J_}: drop.append(k)
            elif {1,C_}<=vs and len(vs)==4 and k<nb:
                drop.append(k); u1,=[x for x in vs if NV[x][2]==0 and x!=1]; u2,=[x for x in vs-{1,C_,u1}]
                band=(u1,u2)
        f=False
        quad(C_,M_,S_,N_,(176,72),(188,72),(178,80),(189,80),f)
        quad(M_,1,N_,P_,(188,72),(199,72),(189,80),(199,80),f)
        tri(S_,N_,R_,(178,80),(189,80),(184,87),f)
        quad(N_,P_,Q_,B_,(189,80),(199,80),(192,84),(199,84),f)
        tri(N_,Q_,R_,(189,80),(192,84),(184,87),f)
        quad(R_,Q_,7,B_,(184,87),(192,84),(199,87),(199,84),f)
        tri(1,M_,band[0],(95,55),(82,55),(95,40),f); quad(M_,C_,band[0],band[1],(82,55),(70,55),(95,40),(70,40),f)
        tri(S_,R_,J_,(175,80),(167,84),(175,68),f)
        tri(R_,7,J_,(167,84),(160,87),(175,68),f)
    # a short neck under the skull so the head does not sit on the collar like a ball
    NK=[(11,0),(8,11),(-1,15),(-11,12),(-17,0)]
    top=[add(-5,14,0)]+[add(-5,y*1.25,-z*1.3) for y,z in NK[1:4]]+[add(-7,-17,0)]; bot=[add(-26,10,0)]+[add(-26,y*.92,-z*.92) for y,z in NK[1:4]]+[add(-26,-15,0)]
    topR=[top[0]]+[add(-5,y*1.25,z*1.3) for y,z in NK[1:4]]+[top[4]]; botR=[bot[0]]+[add(-26,y*.92,z*.92) for y,z in NK[1:4]]+[bot[4]]
    for tp,bt in ((top,bot),(topR,botR)):
        for j in range(4): quad(tp[j],tp[j+1],bt[j],bt[j+1],(199-5*j,84),(194-5*j,84),(199-5*j,87),(194-5*j,87),False)
    newp=prims[nb:]
    prims[:]=[d for k,d in enumerate(prims) if k not in drop]
    assert len(drop)==6,drop
    # winding: make every new face agree with the model (geometric normal inward), fix by flipping if wrong
    A=np.array(NV,float); cen=np.array([35,-2,0.])
    for d in prims[-32-len(newp):]:
        ids=d['verts']; a,b,c=A[ids[0]],A[ids[1]],A[ids[2]]
        if np.dot(np.cross(b-a,c-a),(a+b+c)/3-(np.array([8,5,0.]) if any(d is q for q in newp) else cen))>0:
            if len(ids)==4:
                for key in ('verts','norms','uv'): x=d[key]; d[key]=[x[1],x[0],x[3],x[2]]
            else:
                for key in ('verts','norms','uv'): x=d[key]; d[key]=[x[1],x[0],x[2]]
    # smooth normals, one per vertex (the model's own convention)
    acc=[np.Vec((0.0,0.0,0.0)) for _ in NV]
    for d in prims:
        ids=d['verts']
        for c in ([(0,1,2)]+([(1,3,2)] if len(ids)==4 else [])):
            a,b,cc=[A[ids[k]] for k in c]; gn=-np.cross(b-a,cc-a)
            for k in c: acc[ids[k]]+=gn
    acc=[n/np.norm(n) for n in acc]
    # vertices on the mirror plane: no sideways lean
    for i,v in enumerate(NV):
        if v[2]==0: acc[i][2]=0; acc[i]/=np.norm(acc[i])
    NN=[tuple(int(round(c*4096)) for c in n)+(0,) for n in acc]
    for d in prims: d['norms']=list(d['verts'])
    dv=len(NV)-ob.nvert; dn=len(NN)-ob.nnorm
    tm.verts[ob.vert_start:ob.vert_start+ob.nvert]=[v+(0,) for v in NV]
    tm.norms[ob.norm_start:ob.norm_start+ob.nnorm]=NN
    ob.nvert=len(NV); ob.nnorm=len(NN); ob.prims=[mmd.Prim.encode(d) for d in prims]
    for o in tm.objects[2:]: o.vert_start+=dv; o.norm_start+=dn
    return m, t2
