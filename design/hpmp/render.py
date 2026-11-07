#!/usr/bin/env python3
"""Offline mockups only. Inputs are local 2 MB proof sheets and disc textures."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.localize.build import tim_entries

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--variants', action='store_true', help='Render 4a-4e native HUD low-resource variants')
p.add_argument('--proof', type=Path, required=True)
p.add_argument('--eight', type=Path, required=True)
p.add_argument('--atlas', type=Path, default=Path('extracted/ETCDAT/ETCTIM.BIN'))
p.add_argument('--out', type=Path, default=Path('build/hpmp-redesign'))
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
data=json.loads(Path(__file__).with_name('pixels.json').read_text())
palette={k:v for k,v in data.pop('palette').items() if k!='.'}
icons={}
for name,rows in data.items():
    assert len(rows)==11 and all(len(row)==11 for row in rows),name
    im=Image.new('RGBA',(11,11))
    for y,row in enumerate(rows):
        for x,c in enumerate(row):
            if c!='.':im.putpixel((x,y),tuple(bytes.fromhex(palette[c][1:]))+(255,))
    icons[name]=im
# Local derivation of battle HUD icons: entry 0, palette VRAM (256,491).
b=a.atlas.read_bytes();off,_,w,h=tim_entries(b)[0]
clut=off-12-16*32+11*32
pal=struct.unpack_from('<16H',b,clut)
for name,u in [('native-heart',144),('native-orb',155)]:
    im=Image.new('RGBA',(11,11))
    for y in range(11):
        for x in range(11):
            idx=(b[off+(48+y)*(w//2)+(u+x)//2]>>(4*((u+x)&1)))&15
            v=pal[idx]
            im.putpixel((x,y),((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31,255 if v else 0))
    icons[name]=im
if a.variants:
    from design.hpmp.native_variants import make
    icons.update(make(icons['native-heart'], icons['native-orb']))
for name,im in icons.items():im.save(a.out/(name+'.png'))
proof=Image.open(a.proof).convert('RGB')
# Exact 320x240 panel from the existing native proof. No field pixel resampling.
base=proof.crop((352,910,672,1150));assert base.size==(320,240)
base.save(a.out/'field-source.png')
eight=Image.open(a.eight).crop((12,74,492,458)).resize((120,96),Image.Resampling.NEAREST).convert('RGBA')
# Trace the captured 17x14 circle. Native single-bubble tail is kept separately.
insets=[4,3,2,1,1,0,0,0,0,1,1,2,3,4]
mask=Image.new('L',(17,14));md=ImageDraw.Draw(mask)
for y,n in enumerate(insets):md.line((n,y,16-n,y),fill=255)
shell=Image.new('RGBA',(17,14));sd=ImageDraw.Draw(shell)
for y,n in enumerate(insets):
    sd.line((n,y,16-n,y),fill=(205,205,205,255))
    if y>=10:sd.point((16-n,y),fill=(164,164,164,255))
# Preserve native pictogram pixels and their shell interiors from the exact 4x proof.
conditions=[]
for x,y in [(24,36),(41,36),(58,36),(75,36),(24,50),(41,50)]:
    tile=eight.crop((x,y,x+17,y+14));tile.putalpha(mask);conditions.append(tile)
badge=eight.crop((89,59,99,68));badge_mask=Image.new('L',badge.size)
for y in range(badge.height):
    for x in range(badge.width):
        r,g,b,_=badge.getpixel((x,y))
        if max(r,g,b)<110 or (r>g+30 and b>g+25):badge_mask.putpixel((x,y),255)
badge.putalpha(badge_mask)
def bubble(icon):
    im=shell.copy();im.alpha_composite(icon,(3,1));return im

def scene(hp,mp,kind,combined=False):
    im=base.convert('RGBA')
    if kind in ('hp','mp'):
        icon=hp if kind=='hp' else mp
        im.alpha_composite(bubble(icon),(152,44))
        # A single condition retains the native little tail.
        d=ImageDraw.Draw(im);d.line((160,58,160,60),fill=(164,164,164));d.point((159,58),fill=(205,205,205))
        im.alpha_composite(badge,(170,53))
    else:
        tiles=conditions+[bubble(hp),bubble(mp)]
        if combined:tiles=conditions+[bubble(icons['combined'])]
        for i,tile in enumerate(tiles):
            if i<4:x,y=126+17*i,31
            else:x,y=(134 if combined else 126)+17*(i-4),45
            im.alpha_composite(tile,(x,y))
        im.alpha_composite(badge,((185 if combined else 194),54))
    return im.convert('RGB')
options=[('Heart + orb','heart-cross','orb','Bold resource shapes; HP has a small white cross.'),
 ('Droplet + lightning','droplet','bolt','Two different silhouettes; no letters.'),
 ('Bare HP / MP','hp-glyph','mp-glyph','Hand-pixelled 5x7 letters directly on the bubble.'),
 ('Native battle HUD','native-heart','native-orb','The existing 11x11 heart and MP orb, at 1:1.'),
 ('Resource + low bar','hp-bar','mp-bar','Small symbol plus 2/7 fill; example shows about 29%.'),
 ('One shared bubble','heart-cross','orb','Single need: full symbol. Both low: heart + energy spark.')]
ids=[f'{i+1:02}' for i in range(len(options))]
if a.variants:
    ids=['4a','4b','4c','4d','4e']
    options=[
        ('Low fill', '4a-hp', '4a-mp', 'Bottom ~30% coloured; upper area empty and dark.'),
        ('Medical cross', '4b-hp', '4b-mp', 'White medical cross on the native heart; MP nearly empty.'),
        ('Low warning', '4c-hp', '4c-mp', 'Red exclamation mark in a dark corner on both icons.'),
        ('Cracked / dim', '4d-hp', '4d-mp', 'Broken heart silhouette inside; MP orb loses its glow.'),
        ('Medical low gauge', '4e-hp', '4e-mp', 'Depleted heart plus medical cross; depleted MP orb.'),
    ]
fontfile='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(fontfile,13);titlefont=ImageFont.truetype(fontfile,21)
sheet=Image.new('RGB',(1412,114+304*len(options)),'#161c25');d=ImageDraw.Draw(sheet)
d.text((16,12),('HP / MP — native HUD low-resource variants 4a–4e — v0.0.8' if a.variants else 'HP / MP — six native-pixel proposals — v0.0.8'),font=titlefont,fill='white')
d.text((16,43),'Design composites on an existing original 2 MB capture. Three 320x240 panels per option; exact nearest-neighbour 4x detail.',font=font,fill='#c2cedb')
for x,label in [(16,'HP alone + Square · 1x'),(348,'MP alone + Square · 1x'),(680,'All conditions + Square · 1x'),(1012,'Single icons + group · 4x')]:d.text((x,72),label,font=font,fill='#a0d8ed')
for i,(title,h,m,note) in enumerate(options):
    y=102+i*304
    d.text((16,y),f'{ids[i]}   {title}',font=titlefont,fill='white')
    d.text((360,y+5),note,font=font,fill='#c2cedb')
    frames={kind:scene(icons[h],icons[m],kind,i==5 and not a.variants) for kind in ('hp','mp','all')}
    for x,kind in [(16,'hp'),(348,'mp'),(680,'all')]:
        frames[kind].save(a.out/f'{ids[i]}-{kind}-1x.png');sheet.paste(frames[kind],(x,y+34))
    # Each zoom preserves the composite pixels, including the captured shell and badge.
    hpz=frames['hp'].crop((150,42,182,64)).resize((128,88),Image.Resampling.NEAREST)
    mpz=frames['mp'].crop((150,42,182,64)).resize((128,88),Image.Resampling.NEAREST)
    sheet.paste(hpz,(1012,y+34));sheet.paste(mpz,(1156,y+34))
    allz=frames['all'].crop((120,27,208,68)).resize((352,164),Image.Resampling.NEAREST)
    sheet.paste(allz,(1012,y+130));allz.save(a.out/f'{ids[i]}-all-4x.png')
    hpz.save(a.out/f'{ids[i]}-hp-4x.png');mpz.save(a.out/f'{ids[i]}-mp-4x.png')
sheetname='HPMP-04-LOW-sheet.png' if a.variants else 'HPMP-REDESIGN-sheet.png'
sheet.save(a.out/sheetname)
manifest={'proof_sha256':hashlib.sha256(a.proof.read_bytes()).hexdigest(),'eight_sha256':hashlib.sha256(a.eight.read_bytes()).hexdigest(),'atlas_sha256':hashlib.sha256(a.atlas.read_bytes()).hexdigest(),'size':[320,240],'icon':[11,11],'shell':[17,14],'options':len(options),'ids':ids,'kind':'offline design composites, not running game output'}
(a.out/('evidence-04-low.json' if a.variants else 'evidence.json')).write_text(json.dumps(manifest,indent=2)+'\n')
print(a.out/sheetname)
