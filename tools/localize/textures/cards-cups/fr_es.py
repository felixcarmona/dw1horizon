
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import os
from fr_erase import erase_fr
import frfont
LINES=[('¡VENID,',180,56),('TODOS,',173,70),('DIGIMON',176,84),('DE FUEGO!',160,98)]
if os.environ.get('LOCALIZE_LANGUAGE') == 'pt-br':
    LINES=[('VENHAM,',176,56),('TODOS,',173,70),('DIGIMON',176,84),('DE FOGO!',160,98)]
def col(y):  # vertical gradient sampled from the original tagline (whitish top -> yellow bottom)
    t=max(0,min(1,(y-56)/52)); return (248,248,224-int(t*168)) if y>=56 else (248,248,224)
def build():
    w,h,d,pal,o=erase_fr()
    def c(i): v=pal[i]; return None if v==0 else ((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3)
    def red(i): v=c(i); return v and v[0]>v[1]+50
    opaque=[i for i in range(256) if pal[i]!=0]
    rects=[]
    for text,x0,y0 in LINES:
        cov,W=frfont.layout(text)
        for (x,y),a in cov.items():
            X,Y=x0+x,y0+y
            if X>255 or a<0.2: continue
            cur=d[Y*w+X]
            if red(cur): continue          # tagline stays under the red CUP, as in the original
            under=c(cur) or (0,0,0)
            ink=col(Y); v=tuple(under[j]*(1-a)+ink[j]*a for j in range(3))
            d[Y*w+X]=min(opaque,key=lambda i:sum((p-q)**2 for p,q in zip(c(i),v)))
        rects.append((text,[x0,y0,W,13]))
    return w,h,d,pal,o,rects
if __name__=='__main__':
    w,h,d,pal,o,rects=build()
    print(rects)
    open('torneo/FR.es.idx','wb').write(bytes(d))
    if os.environ.get('LOCALIZE_PREVIEWS') != '0':   # (tools/localize/build.py: a build writes no previews: no Pillow)
        from tools.image import Image
        def c(i): v=pal[i]; return (0,0,72) if v==0 else ((v&31)<<3,((v>>5)&31)<<3,((v>>10)&31)<<3)
        im=Image.new('RGB',(w,h)); im.putdata([c(i) for i in d]); im.save('torneo/FR.es.png')
        im2=Image.new('RGB',(w,h)); im2.putdata([c(i) for i in o]); im2.save('torneo/FR.en.png')
        s=Image.new('RGB',(256,260),(0,0,0)); s.paste(im2,(0,0)); s.paste(im,(0,130)); s.resize((768,780),Image.NEAREST).save('study/fr_cmp.png')
