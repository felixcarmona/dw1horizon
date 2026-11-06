#!/usr/bin/env python3
"""Create review sheets from native need-state and gym captures with repository raster tools."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.image import Image, ImageDraw, ImageFont


def sheet(out, name, title, subtitle, rows):
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    font=ImageFont.truetype(font_path,14)
    small=ImageFont.truetype(font_path,12)
    big=ImageFont.truetype(font_path,21)
    width,height=348,438
    board=Image.new('RGB',(width*len(rows[0]),100+height*len(rows)),(23,27,34))
    draw=ImageDraw.Draw(board)
    draw.text((14,14),title,font=big,fill='white')
    draw.text((14,48),subtitle,font=font,fill=(200,210,220))
    draw.text((14,71),'Native 320 x 240 captures; exact 3x HUD crops. Labels outside game frames.',font=small,fill=(170,180,190))
    for row,cells in enumerate(rows):
        for col,(path,label,detail) in enumerate(cells):
            x,y=col*width+14,100+row*height
            draw.text((x,y),label,font=font,fill='white')
            draw.text((x,y+23),detail,font=small,fill=(200,210,220))
            frame=Image.open(path).convert('RGB')
            assert frame.size==(320,240),path
            board.paste(frame,(x,y+47))
            board.paste(frame.crop((235,185,310,226)).resize((225,123),Image.Resampling.NEAREST),(x,y+299))
    board.save(out/name)
    print(out/name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime',type=Path)
    parser.add_argument('gym',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    runtime=json.loads((args.runtime/'result.json').read_text())
    gym=json.loads((args.gym/'result.json').read_text())
    assert runtime['ram_bytes']==gym['ram_bytes']==2097152
    assert runtime['half_cycle_ticks']==20
    rows=[]
    for need in ('hunger','toilet','tiredness'):
        rows.append([(args.runtime/f'{need}-{state}-{phase}.png',f'{need.title()} / {label}',detail)
                     for state,phase,label,detail in (
                         ('normal','on','normal','Light blue; grey icon'),
                         ('warning','on','warning normal','1 second at normal brightness'),
                         ('warning','off','warning dim','Bar 35%; icon stays normal'),
                         ('active','off','active','55% whole-icon tint; blue bar'))])
    sheet(args.out,'needs-approved-states-2mb.png','Need reserves drain / normal, warning and active',
          'PCSX-Redux interpreter / 2,097,152 B RAM / 20 native ticks per phase',rows)
    sheet(args.out,'need-reserves-fonts-2mb.png','Need reserves / both fonts and reserve endpoints',
          'FULL = fine; toilet empties when due; energy empties at fatigue 100.',[
          [(args.runtime/f'CLASSIC-60-{state}-{on}.png',f'CLASSIC / {label}',detail)
           for state,on,label,detail in (('normal',True,'normal','Live reserves'),
             ('warning',True,'warning bright','Last hour / last step'),
             ('warning',False,'warning dim','Icon stays bright'),
             ('active',True,'active','55% icon tint; live fill'))],
          [(args.runtime/name,label,detail) for name,label,detail in (
             ('toilet-just-used.png','Toilet / just used','48 units / full reserve'),
             ('toilet-last-reserve.png','Toilet / last reserve','1 unit / minimum one pixel'),
             ('tiredness-rested.png','Energy / rested','Fatigue 0 / full reserve'),
             ('tiredness-exhausted-100.png','Energy / depleted','Fatigue 100 / empty reserve'))]])
    for run in gym['runs'][:2]:
        cells=[]
        for frame in run['frames']:
            care=frame['care']
            cells.append((args.gym/frame['file'],f'{run["prefix"]} / session {frame["session"]} of 5',
                          f'Food {care["foodLevel"]}; toilet {care["poopLevel"]}; fatigue {care["tiredness"]}'))
        sheet(args.out,run['prefix']+'-gym-x5-2mb.png',run['prefix']+' / five native training sessions / 2 MB',
              'Energy and toilet reserves drain with native care costs; no care writes between awards.',[cells[:3],cells[3:]])


if __name__=='__main__':
    main()
