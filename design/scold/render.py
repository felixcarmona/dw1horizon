"""Offline review composites; reads local captures and player-disc artwork only."""
import argparse, hashlib, json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/localize/textures/misc'))
from idx import load
p=argparse.ArgumentParser()
p.add_argument('--captures',type=Path,required=True)
p.add_argument('--atlas',type=Path,default=ROOT/'extracted/ETCDAT/ETCTIM.BIN')
p.add_argument('--out',type=Path,default=ROOT/'build/scold')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
w,h,px,cl,bpp=load(a.atlas,4)
pal=cl[4][13]
# MENU_OPTIONS[5]: UV (0,40), 20x20; palette VRAM (256,509).
native=Image.new('RGBA',(20,20))
for y in range(20):
 for x in range(20):
  v=pal[px(x,40+y)]
  native.putpixel((x,y),((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31,255 if v else 0))
# Retain the complete occupied silhouette, fitted to the existing field footprint.
icon=native.crop(native.getbbox()).resize((11,11),Image.Resampling.NEAREST)
icons=[icon.copy() for _ in range(3)]
d=ImageDraw.Draw(icons[1]);d.rectangle((7,0,10,3),fill='#281818');d.rectangle((8,1,9,2),fill='#f84838')
anger=['.rr...rr.','rrrr.rrrr','..rr.rr..','.........','..rr.rr..','rrrr.rrrr','.rr...rr.']
mark=Image.new('RGBA',(9,7));md=ImageDraw.Draw(mark)
for y,row in enumerate(anger):
 for x,c in enumerate(row):
  if c=='r':md.point((x,y),fill='#d83028')
# A compact accent retains the menu silhouette.
d=ImageDraw.Draw(icons[2]);d.line((7,0,7,2),fill='#f84838');d.line((9,1,10,1),fill='#f84838');d.point((9,3),fill='#f84838')
alt=Image.new('RGBA',(11,11));alt.alpha_composite(mark,(1,2));icons.append(alt)
source=Image.open(a.captures/'hp29.png').convert('RGBA')
clean=Image.open(a.captures/'hp31.png').convert('RGBA')
# Preserve the exact captured single bubble shell, tail, and Square badge.
# Cropped Square from this capture, with a colour mask for its transparent corners.
badge=source.crop((142,61,151,69));mask=Image.new('L',badge.size)
for y in range(badge.height):
 for x in range(badge.width):
  r,g,b,_=badge.getpixel((x,y))
  if max(r,g,b)<110 or (r>g+30 and b>g+25):mask.putpixel((x,y),255)
badge.putalpha(mask)
labels=['Native Scold icon','Scold + red warning dot','Scold + red anger accent','Red anger mark']
fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
f=ImageFont.truetype(fontpath,13);title=ImageFont.truetype(fontpath,20)
sheet=Image.new('RGB',(1120,1358),'#171d26');sd=ImageDraw.Draw(sheet)
sd.text((16,12),'SCOLD — four condition-bubble proposals',font=title,fill='white')
sd.text((16,43),'MOCKUPS ONLY · existing 2 MB captures · 320×240 at 1× · exact nearest-neighbour 4× detail',font=f,fill='#c5d1df')
for x,t in [(16,'Scold alone + Square · 1×'),(348,'Scold with other needs · 1×'),(680,'Same pixels · 4×')]:sd.text((x,72),t,font=f,fill='#a4d9ee')
for i,ic in enumerate(icons,1):
 frame=source.copy()
 # Replace icon only, retaining the native captured bubble and badge.
 ImageDraw.Draw(frame).rectangle((125,55,139,67),fill=(205,205,205))
 frame.alpha_composite(ic,(127,56))
 # Restore the captured shell perimeter after replacing the icon interior.
 for yy in range(14):
  for xx in range(17):
   if xx<3 or xx>13 or yy==0 or yy>=12:frame.putpixel((124+xx,54+yy),source.getpixel((124+xx,54+yy)))
 # Place the same bubble beside the existing single need, preserving native spacing.
 combo=clean.copy()
 tile=frame.crop((124,54,141,68))
 combo.alpha_composite(source.crop((124,54,141,68)),(115,54))
 combo.alpha_composite(tile,(132,54))
 combo.alpha_composite(badge,(150,61))
 frame.convert('RGB').save(a.out/f'{i}-alone-1x.png');combo.convert('RGB').save(a.out/f'{i}-group-1x.png')
 z1=frame.crop((120,50,155,77)).resize((140,108),Image.Resampling.NEAREST)
 z2=combo.crop((111,50,163,77)).resize((208,108),Image.Resampling.NEAREST)
 z1.save(a.out/f'{i}-alone-4x.png');z2.save(a.out/f'{i}-group-4x.png')
 y=104+(i-1)*310
 sd.text((16,y),f'{i}   {labels[i-1]}',font=title,fill='white')
 sheet.paste(frame,(16,y+32));sheet.paste(combo,(348,y+32))
 sheet.paste(z1,(680,y+32));sheet.paste(z2,(840,y+32))
 sd.text((680,y+165),'Single bold pictogram; no text.',font=f,fill='#c5d1df')
 sd.text((680,y+190),'Visible exactly while Scold is available.',font=f,fill='#c5d1df')
 sd.text((680,y+215),'Native shell, spacing, tail and Square.',font=f,fill='#c5d1df')
sheet.save(a.out/'SCOLD-options-1-4.png')
manifest={'kind':'offline mockups, no game change','captures_ram_bytes':2097152,'source_sha256':{n:hashlib.sha256((a.captures/n).read_bytes()).hexdigest() for n in ['hp29.png','hp31.png']},'atlas_sha256':hashlib.sha256(a.atlas.read_bytes()).hexdigest(),'menu_sprite':{'entry':4,'uv':[0,40],'size':[20,20],'palette':13,'occupied_bbox':list(native.getbbox())},'field_icon_size':[11,11],'field_frame_size':[320,240],'zoom':4,'options':labels}
(a.out/'evidence.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(a.out/'SCOLD-options-1-4.png')
