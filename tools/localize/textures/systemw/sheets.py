
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json
from tools.image import Image, ImageDraw, ImageFont
from tex import *
EN=grid()
raw=open('SYSTEM_W.es.idx','rb').read(); ES=[[raw[y*W+x] for x in range(W)] for y in range(H)]
items=json.load(open('rects.json'))
FONT=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
FONTB=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',26)
PANEL=(41,57,65,255)
def cropg(gr,u,v,w,h,row,bg=PANEL,s=6):
    im=Image.new('RGBA',(w,h)); p=im.load(); P=pal(row)
    for y in range(h):
        for x in range(w): p[x,y]=c15(P[gr[y+v][x+u]])
    b=Image.new('RGBA',(w,h),bg); b.alpha_composite(im)
    return b.resize((w*s,h*s),Image.NEAREST)
def find(es,en=None):
    for it in items:
        if it['es']==es and (en is None or it['en']==en): return it
    raise KeyError(es)
def sheet(name,title,rows,note=None):
    blocks=[]
    for es,en,cap in rows:
        it=find(es,en); r=it['clut_row']
        a=cropg(EN,*it['en_rect'],r); b=cropg(ES,it['u'],it['v'],it['w'],it['h'],r)
        blocks.append((a,b,cap or '%s  →  %s'%(it['en'],it['es']),it))
    colw=max(max(a.width for a,_,_,_ in blocks),180)
    capw=max(ImageDraw.Draw(Image.new('RGB',(1,1))).textlength(c+'   [00x00 → 00x00]',font=FONT) for _,_,c,_ in blocks)
    Wd=int(max(40+colw+40+max(b.width for _,b,_,_ in blocks)+40, 760, capw+70))
    Hh=90+sum(max(a.height,b.height)+70 for a,b,_,_ in blocks)+(60 if note else 0)
    out=Image.new('RGB',(Wd,Hh),(18,20,26)); d=ImageDraw.Draw(out)
    d.text((24,20),title,font=FONTB,fill=(240,240,240))
    d.text((40,62),'inglés (original)',font=FONT,fill=(150,160,170)); d.text((40+colw+40,62),'español (nuevo)',font=FONT,fill=(150,160,170))
    y=100
    for a,b,cap,it in blocks:
        d.text((40,y),cap+'   [%dx%d → %dx%d]'%(it['en_rect'][2],it['en_rect'][3],it['w'],it['h']),font=FONT,fill=(220,200,120))
        y+=32
        out.paste(a,(40,y)); out.paste(b,(40+colw+40,y))
        y+=max(a.height,b.height)+38
    if note: d.text((24,y),note,font=FONT,fill=(170,170,170))
    out.save(name)
sheet('lado-a-lado-estado-digimon.png','Pantalla de estado (Status)',[
 ('PERFIL',None,None),('ESTADO',None,None),('ATRIBUTOS',None,None),
 ('NOMBRE',None,None),('ESPECIE',None,None),('EDAD',None,None),('PESO',None,None),
 ('ESPECIAL',None,None),('TIPO',None,None),('ACTIVO',None,None),
 ('FELICIDAD',None,'HAPPINESS → FELICIDAD (el inglés ya salía cortado)'),('VELOCIDAD',None,None),('INTELECTO',None,'BRAINS → INTELECTO (INTELIGENCIA no cabe: 47 px)'),
 ('RAPIDEZ',None,'alternativa: SPEED → RAPIDEZ (más holgada)')],
 note='VELOCIDAD e INTELECTO acaban justo antes de la barra (x 194).')
sheet('lado-a-lado-tecnicas.png','Técnicas (Tech): cabecera y ficha de técnica',[
 ('POTENCIA',None,None),('MP',None,'MP → MP (igual)'),('ALC.',None,'RANG → ALC. (cabecera)'),('ALCANCE',None,'RANG → ALCANCE (ficha)'),('EFECTO',None,None),('DATOS TÉC.',None,None)])
sheet('lado-a-lado-tiendas.png','Tiendas y listas: cabeceras',[
 ('OBJETO',None,None),('PRECIO',None,None),('CANT.',None,None),('PUNTOS',None,None),('Nº',None,None),('TÍTULO',None,None),('LUGAR',None,None)])
sheet('lado-a-lado-elementos.png','Ayuda de técnicas: nombres de elemento',[
 ('FUEGO',None,None),('COMBATE',None,None),('AIRE',None,None),('TIERRA',None,None),('HIELO',None,None),('MECA',None,None),('MUGRE',None,None)])

# ---- mocks over the screenshots ----
def mock(src,dst,places,s=3):
    im=Image.open(src).convert('RGBA')
    for it,(ex,ey),(sx,sy) in places:
        u,v,w,h=it['en_rect']
        # erase the English label with the panel colour found just left of it
        bgc=im.getpixel((max(0,160+ex-1),120+ey+h//2))
        ImageDraw.Draw(im).rectangle([160+ex,120+ey,160+ex+w-1,120+ey+h-1],fill=bgc)
    for it,(ex,ey),(sx,sy) in places:
        r=it['clut_row']
        c=Image.new('RGBA',(it['w'],it['h'])); p=c.load(); P=pal(r)
        for y in range(it['h']):
            for x in range(it['w']): p[x,y]=c15(P[ES[it['v']+y][it['u']+x]])
        im.alpha_composite(c,(160+sx,120+sy))
    im.resize((im.width*s,im.height*s),Image.NEAREST).save(dst)
st=[(find('PERFIL'),(-140,-81),(-140,-81)),(find('ESTADO'),(-140,-12),(-140,-12)),(find('ATRIBUTOS'),(-18,-12),(-18,-12)),
    (find('NOMBRE'),(-138,-66),(-143,-66)),(find('ESPECIE'),(-138,-50),(-143,-50)),(find('PESO'),(-67,-34),(-63,-34)),(find('EDAD'),(-133,-34),(-135,-34)),
    (find('ESPECIAL'),(9,-62),(9,-62)),(find('TIPO'),(52,-62),(52,-62)),(find('ACTIVO'),(85,-62),(85,-62)),
    (find('FELICIDAD'),(-126,49),(-125,49)),(find('VELOCIDAD'),(-4,64),(-5,64)),(find('INTELECTO'),(-4,79),(-5,79))]
mock('../common/en_status.png','mock-estado-digimon.png',st)
te=[(find('POTENCIA'),(22,-76),(14,-76)),(find('ALC.'),(98,-76),(98,-76)),(find('EFECTO'),(122,-76),(117,-76)),
    (find('POTENCIA'),(22,-9),(14,-9)),(find('ALC.'),(98,-9),(98,-9)),(find('EFECTO'),(122,-9),(117,-9))]
mock('../common/en_tech.png','mock-tecnicas.png',te)

# synthetic layout of the move-help grid (no screenshot of that screen): boxes as the code draws them
def elem_mock(lang,dst):
    im=Image.new('RGBA',(320,240),(41,57,65,255)); d=ImageDraw.Draw(im)
    for row in range(7):
        for j in range(8):
            x=160+j*18-42; y=120+row*15-7; d.rectangle([x,y,x+11,y+11],fill=(0x4e,0x60,0x6e,255))
    names=[('FIRE','FUEGO'),('BATTLE','COMBATE'),('AIR','AIRE'),('EARTH','TIERRA'),('ICE','HIELO'),('MECH','MECA'),('FILTH','MUGRE')]
    for j,(en,es) in enumerate(names):
        if lang=='en':
            for x0 in (-67,100):
                im.alpha_composite(cropg(EN,j*20,24,20,10,4,bg=(0,0,0,0),s=1),(160+x0,120+j*15-8))
        else:
            it=find(es); c=cropg(ES,it['u'],it['v'],it['w'],it['h'],4,bg=(0,0,0,0),s=1)
            im.alpha_composite(c,(160-45-it['w'],120+j*15-8)); im.alpha_composite(c,(160+100,120+j*15-8))
    im.crop((60,100,300,220)).resize((240*4,120*4),Image.NEAREST).save(dst)
elem_mock('en','mock-elementos-en.png'); elem_mock('es','mock-elementos.png')
print('ok')
