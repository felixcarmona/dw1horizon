
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
from idx import load
import os
# the disc's files: tools/localize/build.py --extracted (LOCALIZE_EXTRACTED), else the repository's extracted/
GD=os.path.join(os.environ.get('LOCALIZE_EXTRACTED') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'extracted'),'STDDAT','GRADE','')
def erase_fr():
    w,h,px,cl,bpp=load(GD+'FR.TIM'); pal=cl[4][0]
    def c(i): v=pal[i]; return ((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3)
    T=0
    d=bytearray(px(x,y) for y in range(h) for x in range(w)); o=bytes(d)
    def red(i): r,g,b=c(i); return r>g+50
    mask=set()
    for y in range(54,112):
        x0=(178 if y<69 else 175) if y<96 else 136
        for x in range(x0,256):
            if pal[o[y*w+x]]!=0: d[y*w+x]=T
        xa=163 if y<69 else (140 if y<96 else 136)
        for x in range(xa,178):
            i=o[y*w+x]; r,g,b=c(i)
            if pal[i]!=0 and not red(i) and (r-g)<14 and r+g>(200 if y<69 else 300): mask.add((x,y))
    # dilate by 1 (AA), not into red CUP
    m2=set(mask)
    for (x,y) in mask:
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                p=(x+dx,y+dy)
                if 54<=p[1]<=110 and p[0]<178 and not red(o[p[1]*w+p[0]]): m2.add(p)
    mask=m2
    val={}  # known values: rgb or None (transparent)
    for y in range(50,115):
        for x in range(130,200):
            if (x,y) in mask: continue
            i=d[y*w+x]; val[(x,y)]=None if pal[i]==0 else c(i)
    todo=set(mask)
    while todo:
        nxt={}
        for (x,y) in todo:
            nb=[val[(x+dx,y+dy)] for dx in (-1,0,1) for dy in (-1,0,1) if (x+dx,y+dy) in val and (dx or dy)]
            if len(nb)>=3:
                cols=[v for v in nb if v]; 
                nxt[(x,y)]=None if len(cols)*2<len(nb) else tuple(sum(v[j] for v in cols)/len(cols) for j in range(3))
        if not nxt:  # isolated
            for p in todo: nxt[p]=None
        for p,v in nxt.items(): val[p]=v; todo.discard(p)
    opaque=[i for i in range(256) if pal[i]!=0]
    for (x,y) in mask:
        v=val[(x,y)]
        d[y*w+x]=T if v is None else min(opaque,key=lambda i:sum((a-b)**2 for a,b in zip(c(i),v)))
    for _ in range(3):
        for y in range(54,111):
            for x in range(140,180):
                if pal[d[y*w+x]]==0 or red(d[y*w+x]): continue
                n=sum(1 for dx in (-1,0,1) for dy in (-1,0,1) if (dx or dy) and pal[d[(y+dy)*w+x+dx]]!=0)
                if n<4: d[y*w+x]=T
    return w,h,d,pal,o
if __name__=='__main__':
    from tools.image import Image
    w,h,d,pal,o=erase_fr()
    def c(i): v=pal[i]; return (0,0,72) if v==0 else ((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3)
    im=Image.new('RGB',(w,h)); im.putdata([c(i) for i in d]); im.crop((90,40,256,115)).resize((166*5,75*5),Image.NEAREST).save('study/fr_erase.png')
