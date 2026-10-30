
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
from tools.image import Image
from pixfont import text_mask,stamp
def render(font,words,ink=(230,230,230),sh=(70,70,70),bg=(60,60,70),s=8,gap=1):
    rows=[]
    for wd in words:
        m=text_mask(font,wd,gap); H=len(m)+1; W=len(m[0])+1
        im=Image.new('RGB',(W,H),bg); p=im.load()
        stamp(lambda x,y,i: p.__setitem__((x,y),ink if i==15 else sh), m,0,0,15,shadow=1)
        rows.append(im)
    W=max(r.width for r in rows)+2; H=sum(r.height+2 for r in rows)
    out=Image.new('RGB',(W,H),bg); y=0
    for r in rows: out.paste(r,(1,y+1)); y+=r.height+2
    return out.resize((out.width*s,out.height*s),Image.NEAREST)
if __name__=='__main__':
    import sys; from pixfont import LABEL6
    render(LABEL6,sys.argv[2:]).save(sys.argv[1])
