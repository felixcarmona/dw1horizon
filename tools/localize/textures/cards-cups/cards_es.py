
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import sys,json,os
from card import load,c15
import cardfont
NAMES=open('names.txt').read().split('\n')[:66]
NAMES[0]='Protagonista'; NAMES[65]='Machinedramon'
OVERRIDE={0:'Protagonista'}
BOX_OVERRIDE={20:(62,120)}
Y0=165            # glyph row 0 (cap top) -> texture v
CX=90             # ink centre of the name
XMIN,XMAX=32,145  # name may use [XMIN,XMAX] incl. shadow
def lum(c): return c[0]*.3+c[1]*.59+c[2]*.11
def dist(a,b): return sum((p-q)**2 for p,q in zip(a,b))
def text_box(c,k):
    w=c['w'];d=c['data']
    if k in BOX_OVERRIDE: return BOX_OVERRIDE[k]
    from collections import Counter
    bg=Counter(d[y*w+x] for y in range(163,176) for x in range(30,146)).most_common(1)[0][0]
    cols=[x for x in range(30,146) if sum(1 for y in range(164,176) if d[y*w+x]!=bg)>=2]
    runs=[];
    for x in cols:
        if runs and x-runs[-1][1]<=6: runs[-1][1]=x
        else: runs.append([x,x])
    r=max(runs,key=lambda r:r[1]-r[0]); return tuple(r)
def build(k,name,gap=1):
    c=load(k); w=c['w']; d=bytearray(c['data']); pal=[c15(v) for v in c['pal']]
    from collections import Counter
    bg=Counter(d[y*w+x] for y in range(163,176) for x in range(30,146)).most_common(1)[0][0]
    x0,x1=text_box(c,k)
    txt=[d[y*w+x] for y in range(163,176) for x in range(x0,x1+1)]
    tset=[i for i in set(txt) if i!=bg]
    ink=max(tset,key=lambda i:lum(pal[i])); sh=min(tset,key=lambda i:lum(pal[i]))
    # erase: row-wise interpolation between clean pixels left/right of the box
    e0,e1=x0-1,min(x1+1,145)
    for y in range(163,176):
        L=d[y*w+e0-1]; R=d[y*w+e1+1] if e1<145 else d[y*w+e1]
        for x in range(e0,e1+1):
            if L==R: d[y*w+x]=L
            else:
                t=(x-e0+1)/(e1-e0+2); col=tuple(pal[L][j]*(1-t)+pal[R][j]*t for j in range(3))
                d[y*w+x]=min(range(1,256),key=lambda i:dist(pal[i],col))
    if not name: return c,d,None
    m,W=cardfont.mask(name,gap)
    tw=W+2  # with shadow
    left=round(CX-W/2); left=max(XMIN,min(left,XMAX-tw+1))
    rgb={}
    def get(x,y): return rgb.get((x,y),pal[d[y*w+x]])
    def put(x,y,col,a):
        b=get(x,y); rgb[(x,y)]=tuple(b[j]*(1-a)+col[j]*a for j in range(3))
    soft=set();core=set()
    for (gx,gy),a in m.items():
        if a<1: continue
        core.add((gx+1,gy+1))
        for o in ((2,1),(1,2),(2,2),(1,0)): soft.add((gx+o[0],gy+o[1]))
    for p in soft-core:
        if p not in m and Y0+p[1]<=175: put(left+p[0],Y0+p[1],pal[sh],0.5)
    for p in core:
        if p not in m or m[p]<1: put(left+p[0],Y0+p[1],pal[sh],1.0)
    for (gx,gy),a in m.items(): put(left+gx,Y0+gy,pal[ink],0.55 if a<1 else 1.0)
    for (x,y),col in rgb.items():
        assert XMIN<=x<=XMAX and 163<=y<=175,(k,name,x,y)
        cand=[ink,sh,bg]+tset
        best=min(cand,key=lambda i:dist(pal[i],col))
        if dist(pal[best],col)>300: best=min(range(1,256),key=lambda i:dist(pal[i],col))
        d[y*w+x]=best
    return c,d,(left,Y0,tw,10)
def toimg(c,d):
    from tools.image import Image   # (previews only)
    im=Image.new('RGB',(c['w'],c['h'])); im.putdata([c15(c['pal'][i]) for i in d]); return im
if __name__=='__main__':
    import os; os.makedirs('es',exist_ok=True); os.makedirs('idx',exist_ok=True)
    rects=[]
    for k in range(66):
        c,d,r=build(k,NAMES[k])
        if os.environ.get('LOCALIZE_PREVIEWS') != '0': toimg(c,d).save('es/card-%02d.es.png'%k)
        open('idx/card-%02d.es.idx'%k,'wb').write(bytes(d))
        rects.append(dict(card=k,es=NAMES[k],rect=r,box=text_box(c,k)))
    json.dump(rects,open('cards_rects_tmp.json','w'),indent=0)
