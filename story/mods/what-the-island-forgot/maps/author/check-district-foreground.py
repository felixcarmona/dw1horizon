#!/usr/bin/env python3
"""Validate built sprites against their RGBA masks and unchanged reference backgrounds."""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / "tools").is_dir())))

from pathlib import Path
import json,sys,hashlib
import numpy as np
from tools.image import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tools'));import dwmap
import argparse
parser=argparse.ArgumentParser(description='Check the exact RGB/alpha, palette and VRAM budgets of screens 358–368.')
parser.add_argument('maps',type=Path)
parser.add_argument('--reference',type=Path,required=True)
parser.add_argument('--report',type=Path)
args=parser.parse_args()
mod=Path(__file__).resolve().parents[2];maproot=args.maps;reference=args.reference;results=[]
def texture_rect(m, sp):
 for raw in m.tims:
  tim=dwmap.TIM(raw)
  if tim.bpp!=8:continue
  x=sp['texX']-(tim.x-384)*2;y=sp['texY']-tim.y
  if 0<=x and x+sp['width']<=tim.w*2 and 0<=y and y+sp['height']<=tim.h:
   return np.frombuffer(tim.pixels,np.uint8).reshape(tim.h,tim.w*2)[y:y+sp['height'],x:x+sp['width']]
 raise AssertionError(('missing sprite TIM',sp))

for mf in sorted((mod/'maps/district-foreground').glob('*.json')):
 d=json.loads(mf.read_text());sid=d['screen'];c=json.loads(next((mod/'screens').glob(f'{sid}-*.json')).read_text());f=c['file'];m=dwmap.MapFile((maproot/(f+'.MAP')).read_bytes());ref=dwmap.MapFile((reference/(f+'.MAP')).read_bytes());t=dwmap.TfsFile((maproot/(f+'.TFS')).read_bytes());rt=dwmap.TfsFile((reference/(f+'.TFS')).read_bytes());w,h,indices=t.image_indices(m);_,_,ri=rt.image_indices(ref);bg=np.array(indices);rbg=np.array(ri);expected=np.zeros((h,w),bool)
 retained=set()
 for i,inst in enumerate(ref.instances):
  if inst['flag']==1:continue
  assert m.instances[i]==inst,(sid,'retained instance changed',i)
  for frame in inst['frames']:
   if frame<0:continue
   retained.add(frame);sp=ref.sprites[frame]
   assert m.sprites[frame]==sp,(sid,'retained definition changed',frame)
   if sp['clut']>=0:continue
   oldpix=texture_rect(ref,sp);newpix=texture_rect(m,sp)
   for k in range(len(t.cluts)):
    a=np.array(rt.cluts[k],np.uint16)[oldpix];b=np.array(t.cluts[k],np.uint16)[newpix]
    assert np.array_equal(a!=0,b!=0),(sid,'retained transparency changed',frame,k)
    assert np.array_equal(a&0x7fff,b&0x7fff),(sid,'retained colours changed',frame,k)
 assert [raw for raw in m.tims if dwmap.TIM(raw).bpp==4]==[raw for raw in ref.tims if dwmap.TIM(raw).bpp==4],(sid,'retained 4-bit textures changed')
 for p in d['pieces']:
  im=Image.open(mod/'art/foreground'/p['png']).convert('RGBA');a=np.array(im);x,y=p['at'];expected[y:y+im.height,x:x+im.width]|=a[:,:,3]>=128
  recipe=p['segmentation'];offset=recipe['source_offset'];native=Image.open(mod/'art'/recipe['source_art']).convert('RGB');crop=np.array(native.crop((x-offset[0],y-offset[1],x-offset[0]+im.width,y-offset[1]+im.height)));assert np.array_equal(a[:,:,:3],crop),(sid,p['png'],'source RGB changed')
 added=[i for i,v in enumerate(m.instances) if v['flag']==0 and (i>=len(ref.instances) or ref.instances[i]['flag']==1)];actual=np.zeros((h,w),bool);words=np.zeros((len(t.cluts),h,w),np.uint16);tims=[dwmap.TIM(raw) for raw in m.tims]
 for i in added:
  inst=m.instances[i];sp=m.sprites[inst['frames'][0]];assert sp['clut']==-1
  if sp['y']:
   face=next((p for p in d['pieces'] if p.get('vertical_face') and p['at'][0]<=inst['x']<p['at'][0]+Image.open(mod/'art/foreground'/p['png']).width and p['at'][1]<=inst['y']<p['at'][1]+Image.open(mod/'art/foreground'/p['png']).height),None)
   assert face and sp['y']<0,(sid,'unexpected raised depth anchor',i)
   basis=dwmap.camera_basis(m);projected=dwmap.project(m,basis,(sp['x'],sp['y'],sp['z']));floor=dwmap.project(m,basis,(sp['x'],0,sp['z']))
   assert abs(projected[1]-(inst['y']+sp['height']/2))<1,(sid,'face band height',i)
   assert abs(floor[1]-face['depth'][1])<1,(sid,'face band floor base',i)
  tw,th=sp['width'],sp['height'];assert sp['texX']%256+tw<256 and sp['texY']%256+th<256,(sid,'UV page-edge shrink',i);page=next(tim for tim in tims if tim.bpp==8 and 0<=sp['texX']-(tim.x-384)*2 and sp['texX']-(tim.x-384)*2+tw<=tim.w*2 and tim.y<=sp['texY'] and sp['texY']+th<=tim.y+tim.h)
  px=np.frombuffer(page.pixels,dtype=np.uint8).reshape(page.h,page.w*2);xx=sp['texX']-(page.x-384)*2;yy=sp['texY']-page.y;px=px[yy:yy+th,xx:xx+tw];x,y=inst['x'],inst['y'];tw=min(tw,w-x);th=min(th,h-y);px=px[:th,:tw]
  for k in range(len(t.cluts)):
   colors=np.array(t.cluts[k],np.uint16)[px];nonzero=colors!=0
   assert np.array_equal(nonzero,np.array(t.cluts[0],np.uint16)[px]!=0),(sid,'time-dependent transparency')
   view=words[k,y:y+th,x:x+tw];view[nonzero]=colors[nonzero]
  actual[y:y+th,x:x+tw]|=nonzero
 assert np.array_equal(actual,expected),(sid,'alpha mismatch',int((actual^expected).sum()))
 hashes=[]
 for k in range(len(t.cluts)):
  palette=np.array(t.cluts[k],np.uint16);rp=np.array(rt.cluts[k],np.uint16);colors=palette[bg]&0x7fff;refcolors=rp[rbg]&0x7fff
  assert np.array_equal(colors,refcolors),(sid,'background RGB changed',k)
  assert np.array_equal(words[k][expected]&0x7fff,colors[expected]),(sid,'foreground RGB mismatch',k)
  hashes.append(hashlib.sha1(colors.astype('<u2').tobytes()).hexdigest())
 row=dict(screen=sid,retained_frames=len(retained),pieces=len(d['pieces']),foreground_pixels=int(expected.sum()),strips=len(added),definitions=len(m.sprites),instances=len(m.instances),map_bytes=len(m.build()),tim_pixel_bytes=sum(len(tim.pixels) for tim in tims),background_rgb555_sha1=hashes,tims=[dict(x=t.x,y=t.y,w=t.w,h=t.h,bpp=t.bpp) for t in tims]);results.append(row);print(row,flush=True)
 assert len(m.sprites)<=180 and len(m.instances)<=188 and len(m.build())<=0x80000
if args.report:args.report.write_text(json.dumps(results,indent=2)+'\n')
