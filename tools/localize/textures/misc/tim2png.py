
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import sys
from tools.image import Image
from idx import load
def c15(v): return (0,0,0,0) if v==0 else ((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3,255)
def render(path,entry=0,clut=0):
    w,h,px,cl,bpp=load(path,entry)
    im=Image.new('RGBA',(w,h)); p=im.load(); pal=cl[4][clut] if cl else None
    for y in range(h):
        for x in range(w): p[x,y]=c15(pal[px(x,y)])
    return im
if __name__=='__main__':
    im=render(sys.argv[1],int(sys.argv[3]) if len(sys.argv)>3 else 0,int(sys.argv[4]) if len(sys.argv)>4 else 0)
    s=int(sys.argv[5]) if len(sys.argv)>5 else 1
    b=Image.new('RGBA',im.size,(40,40,60,255)); b.alpha_composite(im); b.resize((im.width*s,im.height*s),Image.NEAREST).save(sys.argv[2])
