#!/usr/bin/env python3
"""Check generated screens 312–322 against their RGBA foregrounds and exact background colors.

Run with the standard-library image API:
    python3 maps/author/check-depth-a2.py SCREENS_DIR [REFERENCE_SCREENS_DIR]
No player-disc pixels are stored by this check.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / "tools").is_dir())))

import sys,json
from pathlib import Path
MOD=Path(__file__).resolve().parents[2]
ROOT=MOD.parents[2]
sys.path.insert(0,str(ROOT/'tools'));import dwmap
from tools.image import Image
screens=Path(sys.argv[1]);total=0
for p in sorted((MOD/'maps/foreground').glob('*.json')):
 d=json.loads(p.read_text())
 if not 312<=d['screen']<=322:continue
 name=p.stem;m=dwmap.MapFile((screens/(name+'.MAP')).read_bytes());t=dwmap.TfsFile((screens/(name+'.TFS')).read_bytes());W,H,bg=t.image_indices(m)
 vram=[bytearray(768) for _ in range(256)];custom=None
 for raw in m.tims:
  tim=dwmap.TIM(raw)
  if tim.bpp!=8:continue
  if tim.clut[1]==484:custom=tim.clut[4]
  left=(tim.x-384)*2;w=tim.w*2
  for y in range(tim.h):vram[tim.y+y][left:left+w]=tim.pixels[y*w:(y+1)*w]
 expected=set()
 for q in d['pieces']:
  im=Image.open(MOD/'art/foreground'/q['png']);art=Image.open(MOD/'art'/(d['art']+'.png')).convert('RGB');x0,y0=q['at'];assert im.convert('RGB').tobytes()==art.crop((x0,y0,x0+im.width,y0+im.height)).tobytes()
  expected.update((x0+x,y0+y) for y in range(im.height) for x in range(im.width) if im.getpixel((x,y))[3]>=128)
 actual=set()
 for inst in m.instances:
  if inst['flag']==1:continue
  for f in inst['frames']:
   if f<0:continue
   s=m.sprites[f]
   # PS1 transparency is a zero color word, not merely index zero. Check
   # the padded pixels' real CLUT too, so a black rectangle cannot pass.
   assert all((custom if s['clut']==16 else pal)[0] == 0 for pal in t.cluts),(name,'opaque transparent padding')
   assert s['texX']%256+s['width']<256 and s['texY']+s['height']<256
   for y in range(s['height']):
    for x in range(s['width']):
     c=vram[s['texY']+y][s['texX']+x]
     if not c:continue
     xx,yy=inst['x']+x,inst['y']+y;assert (xx,yy) in expected,(name,xx,yy)
     for pal in t.cluts:
      out=(custom if s['clut']==16 else pal)[c];src=pal[bg[yy][xx]]
      assert out!=0 and (out&0x7fff)==(src&0x7fff),(name,s['clut'],xx,yy,c,out,src)
     actual.add((xx,yy))
 assert actual==expected,(name,'missing opaque pixels',len(expected-actual))
 if len(sys.argv)>2:assert (screens/(name+'.TFS')).read_bytes()==(Path(sys.argv[2])/(name+'.TFS')).read_bytes()
 assert m.build()==dwmap.MapFile(m.build()).build()
 assert len(m.sprites)<=180 and len(m.instances)<=188
 total+=len(expected)
 print(name,len(d['pieces']),'pieces;',len(expected),'opaque pixels; VRAM, day/night colors, black opacity and round trip PASS')
print('PASS',total,'opaque own-art pixels; RGBA masks, color, opacity, GPU pages and engine table bounds hold.')
