
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json,os
PREVIEWS = os.environ.get('LOCALIZE_PREVIEWS') != '0'   # (tools/localize/build.py: a build writes no previews: no Pillow)
if PREVIEWS:
    from tools.image import Image, ImageDraw
from cards_es import build,toimg,NAMES,text_box
from card import load,c15
os.makedirs('cartas',exist_ok=True)
rects=[]; EN={}; ES={}
for k in range(66):
    c,d,r=build(k,NAMES[k])
    if PREVIEWS:
        c0=load(k); en=Image.new('RGB',(150,180)); en.putdata([c15(c0['pal'][i]) for i in c0['data']])
        en.save('cartas/card-%02d.en.png'%k); EN[k]=en
        es=toimg(c,d); es.save('cartas/card-%02d.es.png'%k); ES[k]=es
    open('cartas/card-%02d.es.idx'%k,'wb').write(bytes(d))
    x0,x1=text_box(load(k),k)
    rects.append({"en":"(katakana name, JP art)","es":NAMES[k],"texture":"CARD/CARD.ALL entry %d (150x180 8bpp, VRAM 576,256, CLUT 448,511)"%k,
      "u":r[0],"v":r[1]-1,"w":r[2],"h":11,"en_rect":[x0,163,x1-x0+1,13],
      "drawn_by":"game_menu.c:2178 renderCardImage (whole card as one 150x180 quad)","screen_xy_change":"none"})
# card 00 for English: "Hero"
c,d,r=build(0,'Hero')
if PREVIEWS: toimg(c,d).save('cartas/card-00.en-latin.png')
open('cartas/card-00.en-latin.idx','wb').write(bytes(d))
rects.append({"en":"主人公 (JP)","es":"Hero (English-language variant of card 00)","texture":"CARD/CARD.ALL entry 0","u":r[0],"v":r[1]-1,"w":r[2],"h":11,"en_rect":rects[0]["en_rect"],"drawn_by":"game_menu.c:2178","screen_xy_change":"none"})
json.dump(rects,open('cartas/rects.json','w'),ensure_ascii=False,indent=1)
if PREVIEWS:
    # side by side strips, 3 columns x 22, 3x
    S=3; cw=150*S; ch=16*S
    sheet=Image.new('RGB',(3*cw+4*12, 22*(2*ch+30)+40),(28,28,34)); dr=ImageDraw.Draw(sheet)
    dr.text((12,10),"Cartas: nombre en la franja. Arriba EN (disco US, katakana), debajo ES (nuestro).",fill=(230,230,230))
    for k in range(66):
        col=k//22; row=k%22; x=12+col*(cw+12); y=40+row*(2*ch+30)
        dr.text((x,y),"%02d  %s"%(k,NAMES[k]),fill=(200,200,120))
        sheet.paste(EN[k].crop((0,161,150,177)).resize((cw,ch),Image.NEAREST),(x,y+12))
        sheet.paste(ES[k].crop((0,161,150,177)).resize((cw,ch),Image.NEAREST),(x,y+12+ch+2))
    sheet.save('lado-a-lado-cartas.png')
    # full cards contact sheet: pairs EN|ES, 6 pairs per row
    cs=Image.new('RGB',(6*(300+14)+14,11*(180+18)+14),(28,28,34)); dr=ImageDraw.Draw(cs)
    for k in range(66):
        x=14+(k%6)*(314); y=14+(k//6)*198
        cs.paste(EN[k],(x,y+12)); cs.paste(ES[k],(x+150,y+12)); dr.text((x,y),"%02d EN | ES"%k,fill=(200,200,120))
    cs.save('cartas-en-es.png')
