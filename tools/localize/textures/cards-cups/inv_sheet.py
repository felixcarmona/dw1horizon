
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
from tools.image import Image, ImageDraw, ImageFont
from inventory import INV,ORDER
from idx import load
import os
# the disc's files: tools/localize/build.py --extracted (LOCALIZE_EXTRACTED), else the repository's extracted/
GD=os.path.join(os.environ.get('LOCALIZE_EXTRACTED') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'extracted'),'STDDAT','GRADE','')
F=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',14)
Fs=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
COL={'T':(255,220,0),'L':(255,60,200),'A':(0,220,255)}
S=2; cw=256*S+20; ch=128*S+40
sheet=Image.new('RGB',(3*cw+20,((len(ORDER)+2)//3)*ch+60),(20,20,28)); dr=ImageDraw.Draw(sheet)
dr.text((14,10),'Carteles de torneo (STDDAT/GRADE): amarillo = línea en inglés a redibujar · magenta = logo japonés (arte) · cian = letra/número latino de arte (se queda)',font=Fs,fill=(230,230,230))
for n,k in enumerate(ORDER):
    w,h,px,cl,bpp=load(GD+k+'.TIM'); pal=cl[4][0]
    im=Image.new('RGB',(w,h)); im.putdata([(0,0,72) if pal[px(x,y)]==0 else ((pal[px(x,y)]&31)<<3,((pal[px(x,y)]>>5)&31)<<3,((pal[px(x,y)]>>10)&31)<<3) for y in range(h) for x in range(w)])
    im=im.resize((w*S,h*S),Image.NEAREST); d=ImageDraw.Draw(im)
    for i,(kind,(x,y,ww,hh),en,es) in enumerate(INV[k],1):
        d.rectangle([x*S,y*S,(x+ww)*S-1,(y+hh)*S-1],outline=COL[kind],width=2)
        tx,ty=x*S+2,y*S+2
        d.rectangle([tx,ty,tx+16,ty+16],fill=COL[kind]); d.text((tx+4,ty),str(i),font=F,fill=(0,0,0))
    X=10+(n%3)*cw; Y=40+(n//3)*ch
    dr.text((X,Y),k+'.TIM',font=F,fill=(255,255,255)); sheet.paste(im,(X,Y+20))
sheet.save('inventario-carteles-torneo.png')
