
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from idx import load
# the disc's files: tools/localize/build.py --extracted (LOCALIZE_EXTRACTED), else the repository's extracted/
EXT=os.environ.get('LOCALIZE_EXTRACTED') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'extracted')
T=os.path.join(EXT,'ETCDAT','SYSTEM_W.TIM')
W,H,_px,CL,_=load(T)
def grid():
    return [[_px(x,y) for x in range(W)] for y in range(H)]
def c15(v,bg=None):
    if v==0: return bg if bg else (0,0,0,0)
    return ((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3,255)
def pal(row): return CL[4][row]
def crop(g,u,v,w,h,row,bg=(40,40,60,255),s=1):
    from tools.image import Image   # (previews only)
    im=Image.new('RGBA',(w,h)); p=im.load(); P=pal(row)
    for y in range(h):
        for x in range(w):
            p[x,y]=c15(P[g[v+y][u+x]],bg)
    if s>1: im=im.resize((w*s,h*s),Image.NEAREST)
    return im
