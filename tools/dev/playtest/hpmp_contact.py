#!/usr/bin/env python3
"""Arrange native proof captures and exact 4x crops; never alter gameplay pixels."""
from pathlib import Path
import argparse
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.image import Image,ImageDraw,ImageFont


def contact(folder,rows,name,columns=2,zoom=False):
    size=(352,288) if zoom else (320,240)
    pitch=(size[0]+20,size[1]+36)
    im=Image.new('RGB',(columns*pitch[0]+12,((len(rows)+columns-1)//columns)*pitch[1]+52),(20,25,32))
    draw=ImageDraw.Draw(im)
    font=ImageFont.load_default(size=13)
    title=ImageFont.load_default(size=18)
    draw.text((12,9),name.replace('-',' '),font=title,fill='white')
    draw.text((12,32),'Native 320x240 / original 2 MB RAM'+(' / exact nearest-neighbour 4x' if zoom else ''),font=font,fill='#c4cfda')
    for i,(stem,label) in enumerate(rows):
        x=12+i%columns*pitch[0];y=60+i//columns*pitch[1]
        draw.text((x,y),label,font=font,fill='white')
        frame=Image.open(folder/(stem+('-4x' if zoom else '')+'.png')).convert('RGB')
        assert frame.size==size,(stem,frame.size)
        im.paste(frame,(x,y+22))
    path=folder/(name+'.png');im.save(path);print(path)


def implementation_contact(folder,edges):
    """One sheet of unaltered native frames and exact 4x resource/edge crops."""
    import json
    report=json.loads((edges/'result.json').read_text())
    assert report['passed'] and report['ram_bytes']==0x200000
    assert all(c.get('resource_fill') for c in report['cases'].values())
    rows=[(folder,'hp29','HP low + Square'),(folder,'mp29','MP low + Square'),
          (folder,'both-hunger','HP + MP + hunger + Square')]
    rows += [(edges,k,label) for k,label in (
        ('centre','All eight conditions / centre'),('left','All eight / left edge'),
        ('right','All eight / right edge'),('top','All eight / top edge'),
        ('top-left','All eight / top-left'),('top-right','All eight / top-right'))]
    sheet=Image.new('RGB',(1128,1800),(20,25,32));draw=ImageDraw.Draw(sheet)
    font=ImageFont.load_default(size=13);title=ImageFont.load_default(size=19)
    draw.text((12,10),'4a implemented — depleted native HP heart / MP orb — v0.0.8',font=title,fill='white')
    draw.text((12,36),'Original 2 MB / native 320x240 above / exact 4x detail below / all nine atlases share the same art',font=font,fill='#c4cfda')
    for i,(source,stem,label) in enumerate(rows):
        x=12+(i%3)*372;y=70+(i//3)*574
        draw.text((x,y),label,font=font,fill='white')
        frame=Image.open(source/(stem+'.png')).convert('RGB');assert frame.size==(320,240)
        sheet.paste(frame,(x,y+24))
        if source==folder:
            zoom=Image.open(source/(stem+'-4x.png')).convert('RGB');assert zoom.size==(352,288)
        else:
            l,t,r,b=report['cases'][stem]['bounds']
            cx=max(0,min(232,(l+r)//2-44));cy=max(0,min(168,(t+b)//2-36))
            zoom=frame.crop((cx,cy,cx+88,cy+72)).resize((352,288),Image.Resampling.NEAREST)
        sheet.paste(zoom,(x,y+272))
    path=folder/'HPMP-4a-2MB-sheet.png';sheet.save(path);print(path)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('--edges',type=Path);a=p.parse_args()
    if a.edges:
        implementation_contact(a.folder,a.edges);return
    contact(a.folder,[('hp29','HP 29%: bubble + Square'),('hp31','HP 31%: neither'),
       ('mp29','MP 29%: bubble + Square'),('mp31','MP 31%: neither'),
       ('both-hunger','HP + MP below 30% + hunger'),('no-items','Low HP + MP, no items: bubbles only'),
       ('both30','Exactly 30%: neither'),('recovered','Recovery used: HP bubble clears'),
       ('optional-menu','31%: optional recovery still offered'),('urgency-menu','Low MP first; noncritical HP last')],
       'hpmp-native-proof')
    contact(a.folder,[('hp29','HP depleted heart'),('mp29','MP depleted orb (blue)'),
                     ('both-hunger','Three needs + existing Square overlay'),('no-items','Empty bag: no Square badge')],
            'hpmp-native-4x',zoom=True)
    rows=[]
    for code in ('en','es','pt-br','fr','de','it','ja','ca'):
        for font,label in ((0,'new font'),(1,'original font')):
            rows.append((f'{code}-font-{font}-menu',f'{code} / {label}'))
    if all((a.folder/(stem+'.png')).exists() for stem,_ in rows):
        contact(a.folder,rows,'hpmp-eight-languages',columns=4)


if __name__=='__main__':main()
