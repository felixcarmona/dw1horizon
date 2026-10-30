
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json
from idx import load
import gradefont as F
import os
# the disc's files: tools/localize/build.py --extracted (LOCALIZE_EXTRACTED), else the repository's extracted/
GD=os.path.join(os.environ.get('LOCALIZE_EXTRACTED') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'extracted'),'STDDAT','GRADE','')
def c15(v): return None if v==0 else ((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3)
def read(name):
    w,h,px,cl,bpp=load(GD+name+'.TIM'); pal=cl[4][0]
    d=bytearray(px(x,y) for y in range(h) for x in range(w)); return w,h,d,pal
def toimg(w,h,d,pal,bg=(0,0,72)):
    from tools.image import Image   # (previews only)
    im=Image.new('RGB',(w,h)); im.putdata([c15(pal[i]) or bg for i in d]); return im
def stamp(d,w,text,cx,top,gap=2,left=None):
    pts,W=F.layout(text,gap)
    x0=left if left is not None else round(cx-W/2)
    for x,y,i in pts: d[(top+y)*w+x0+x]=i
    return (x0,top-(2 if any(F.G[c][1] for c in text) else 0),W,9+(2 if any(F.G[c][1] for c in text) else 0))
L1='el COLISEO DIGITALMONSTER'; L2='TORNEO ABIERTO'; L3='CATEGORÍA'
if os.environ.get('LOCALIZE_LANGUAGE') == 'pt-br':
    L1='COLISEU DIGITALMONSTER'; L2='TORNEIO ABERTO'; L3='CATEGORIA'
def build(letter):
    name='GRADE'+letter; w,h,d,pal=read(name); en=bytes(d)
    T=0xff
    def col(i): v=pal[i]; return (v&31,(v>>5)&31,(v>>10)&31)
    cp=[(x,y) for y in range(94,119) for x in range(133,158) if d[y*w+x]!=T and len(set(col(d[y*w+x])))>1]
    bx0=min(p[0] for p in cp); bx1=max(p[0] for p in cp)
    art=[(x,y,d[y*w+x]) for y in range(94,119) for x in range(bx0,bx1+1) if d[y*w+x]!=T]
    ax0=min(a[0] for a in art); ax1=max(a[0] for a in art)
    for y in range(64,120):
        for x in range(0,256):
            if y>=64 and d[y*w+x]!=T and not (y<66 and x>=190): d[y*w+x]=T
    rects=[]
    rects.append(dict(en='the DIGITALMONSTER COLISEUM',es=L1,rect=stamp(d,w,L1,131,66),en_rect=[25,66,213,9]))
    rects.append(dict(en='OPEN TOURNAMENT',es=L2,rect=stamp(d,w,L2,122.5,81),en_rect=[57,81,132,9]))
    # line 3: dot, CATEGORÍA, letter art, dot
    _,Wc=F.layout(L3); aw=ax1-ax0+1
    total=4+6+Wc+6+aw+3+4
    x=round(120-total/2)
    stamp(d,w,'·',0,97,left=x); dot1=x
    r=stamp(d,w,L3,0,97,left=x+4+6)
    nx=x+4+6+Wc+6
    for (ax,ay,i) in art: d[ay*w+nx+(ax-ax0)]=i
    stamp(d,w,'·',0,97,left=nx+aw+3)
    rects.append(dict(en='* GRADE %s *'%letter,es='· CATEGORÍA %s ·'%letter,rect=[x,95,total,19],en_rect=[78,96,85,18],
        note='GRADE -> CATEGORÍA drawn at %s; the coloured %s art moved from u=%d to u=%d'%(r,letter,ax0,nx)))
    return w,h,en,d,pal,rects
if __name__=='__main__':
    import os; os.makedirs('torneo',exist_ok=True); allr=[]
    for L in 'DCBA':
        w,h,en,d,pal,rects=build(L)
        if os.environ.get('LOCALIZE_PREVIEWS') != '0':   # (tools/localize/build.py: a build writes no previews: no Pillow)
            toimg(w,h,d,pal).save('torneo/GRADE%s.es.png'%L)
            toimg(w,h,bytearray(en),pal).save('torneo/GRADE%s.en.png'%L)
        open('torneo/GRADE%s.es.idx'%L,'wb').write(bytes(d))
        for r in rects:
            r.update(texture='STDDAT/GRADE/GRADE%s.TIM (256x128 8bpp, VRAM 384,0, CLUT 0,486)'%L,
                drawn_by='std_main.c:3413 STD_renderBracketIntro (whole 255x128 quad at -128,-64)',screen_xy_change='none')
            allr.append(r)
    json.dump(allr,open('torneo/rects_grade.json','w'),ensure_ascii=False,indent=1)
