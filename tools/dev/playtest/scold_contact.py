#!/usr/bin/env python3
"""Arrange unaltered Scold playtest frames and a short labelled evidence video."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.image import Image,ImageDraw,ImageFont


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);a=p.parse_args()
    folder=a.folder.resolve()
    report=json.loads((folder/'result.json').read_text());assert report['passed']
    # Clear-state detail uses the actual pre-clear bubble area, including headroom.
    from tools.dev.playtest.hpmp_extremes import zoom
    prior=next(r['bounds'] for r in reversed(report['refusal_frames']) if r['quads'])
    for name in ('after-scold','after-window-expiry'):zoom(folder,name,prior)
    rows=[('refused-scold-alone','1  Refused item: native Scold bubble + Square'),
          ('after-scold','2  Scold used: bubble + Square gone'),
          ('after-window-expiry','3  Window expired by walking: both gone'),
          ('combined','4  Hunger + HP + MP + Scold'),
          ('all-nine','5  All nine conditions'),('left','6  Left edge'),('right','7  Right edge'),
          ('top-left','8  Top-left corner / clock clearance'),('top-right','9  Top-right corner')]
    sheet=Image.new('RGB',(856,92+len(rows)*420),'#171d26');d=ImageDraw.Draw(sheet)
    title=ImageFont.load_default(size=20);font=ImageFont.load_default(size=13)
    d.text((16,12),'SCOLD - option 1 / live original 2 MB proof',font=title,fill='white')
    d.text((16,43),'Actual built game: 320x240 frames at 1x (left), exact nearest-neighbour 4x detail (right).',font=font,fill='#c5d1df')
    for i,(name,label) in enumerate(rows):
        y=80+i*420;d.text((16,y),label,font=title,fill='white')
        im=Image.open(folder/(name+'.png'));assert im.size==(320,240)
        z=Image.open(folder/(name+'-4x.png'));assert z.size==(480,384)
        sheet.paste(im,(16,y+30));sheet.paste(z,(352,y+30))
    sheet.save(folder/'SCOLD-2MB-proof-sheet.png')
    # Caption bands preserve every game pixel. Presentations keep their vblank timing.
    clips=[]
    video_rows=[('refusal','Item refused : Scold bubble + Square'),
                ('scold-use','Use Scold : bubble and Square clear'),
                ('window-expiry','Walk away : Scold window expires'),
                ('combined','Other conditions + native Scold icon'),
                ('left','Nine conditions: left edge'),('right','Nine conditions: right edge'),
                ('top-left','Nine conditions: top-left / clock'),('top-right','Nine conditions: top-right')]
    for i,(name,label) in enumerate(video_rows):
        caption=folder/f'caption-{i}.png'
        band=Image.new('RGB',(640,40),'#171d26')
        ImageDraw.Draw(band).text((12,10),label,font=ImageFont.load_default(size=18),fill='white')
        band.save(caption)
        out=folder/f'captioned-{i}.mp4';clips.append(out)
        vf='[0:v]pad=640:520:0:40:color=0x171d26[game];[game][1:v]overlay=0:0:shortest=1'
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(folder/(name+'.mp4')),
                        '-loop','1','-i',str(caption),'-filter_complex',vf,'-shortest','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',str(out)],check=True)
    playlist=folder/'video-concat.txt';playlist.write_text(''.join(f"file '{p}'\n" for p in clips))
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(playlist),
                    '-c','copy',str(folder/'SCOLD-2MB-proof.mp4')],check=True)
    print(folder/'SCOLD-2MB-proof-sheet.png');print(folder/'SCOLD-2MB-proof.mp4')


if __name__=='__main__':main()
