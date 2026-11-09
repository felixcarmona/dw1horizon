#!/usr/bin/env python3
"""Capture the native disliked-habitat mood phase on a 2 MB disc.

Fixture: native Agumon (region 0), screen 92 (Freezeland), positive happiness.
No habitat response is written. --state must belong to this exact disc.
"""
from pathlib import Path
import argparse
import json
import struct
import subprocess
import sys
import itertools
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.food_sickness import emulator
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.field_hud import setcare
from tools.dev import frame_capture as fc


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--state',type=Path)
    p.add_argument('--port',type=int,default=39742)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=emulator(str(Path(a.disc).resolve()),str(Path(a.exe).resolve()),a.port,out)
    display=f':{500+a.port%1000}'
    xv=subprocess.Popen(['Xvfb',display,'-screen','0','1024x768x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);e.env['DISPLAY']=display
    try:
     card=field_card(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd',out/'field.mcd')
     e.start(str(card))
     if a.state:
      e.wait(2);e.run('load',str(a.state.resolve()));e.run('resume')
     else:
      assert e.continue_game()==0
     assert len(e.ram())==2097152
     e.gs('set','gametime_running=0','partner.para.evoTimer=0','partner.para.remainingLifetime=1000','hour=12','minute=0')
     e.poke('MOD_OPT_STORY',struct.pack('<i',0))
     assert e.warp(92);assert e.in_control()
     assert e.peek('PARTNER_ENTITY','i')==3
     setcare(e,condition=0,happiness=50,discipline=80,foodLevel=120,poopLevel=20,tiredness=10,areaEffectTimer=0)
     # Place the partner beside the tamer so both the species and face are visible.
     e.run('pause')
     x,y,z=e.peek('TAMER_POSITION_DATA+0x78','3i')
     pos=e.peek('PARTNER_ENTITY+4','I')
     e.run('poke',hex(pos+0x78),struct.pack('<3i',x+150,y,z+100).hex())
     e.poke('PARTNER_ENTITY+0x10',struct.pack('<3i',(x+150)<<15,y<<15,(z+100)<<15))
     e.run('resume');e.wait(1)
     region=e.peek('RAISE_DATA+103','B');assert region==0
     response=e.peek('MAP_TILE_DATA+0x1bba','b');assert response==2,response
     report={'ram_bytes':2097152,'species':3,'species_name':'Agumon','favored_region':region,'screen':92,'map_response':response,'frames':[]}
     e.run('save',str(out/'field.state'))
     fc.PORT=a.port;fc.BASE=f'http://127.0.0.1:{a.port}';fc.LUA_FILE=str(out/'frames.lua')
     rec=fc.FrameRec();rec.start();rec.ranges([(e.A('PLAYTIME_FRAMES'),2)])
     try:
      for n in range(75):
       rec.step();tick=struct.unpack('<H',rec.read()[0])[0]
       path=out/f'{n:03d}.png';rec.shot(str(path))
       report['frames'].append({'frame':n,'play_ticks':tick,'expected_face':'sad' if tick%10<5 else 'happy'})
     finally:rec.stop()
     # Inspect displayed pixels independently of the sampled RAM phase. GPU buffering
     # delays the presented image at crossings; complete runs must last 15 refreshes.
     raw=subprocess.check_output(['ffmpeg','-loglevel','error','-framerate','60','-i',
         str(out/'%03d.png'),'-vf','crop=11:11:237:193','-f','rawvideo','-pix_fmt','rgb24','-'])
     labels=[]
     for n,row in enumerate(report['frames']):
      data=raw[n*363:(n+1)*363]
      pixels=zip(data[::3],data[1::3],data[2::3])
      pixels=list(pixels)
      sad=any(b>120 and g>120 and r<120 for r,g,b in pixels)
      happy=any(r>180 and g>130 and b<100 for r,g,b in pixels)
      assert sad!=happy,'missing or ambiguous native face'
      row['observed_face']='sad' if sad else 'happy';labels.append(row['observed_face'])
     report['observed_runs']=[{'face':k,'refreshes':len(list(v))} for k,v in itertools.groupby(labels)]
     assert len(report['observed_runs'])>=5,'face did not alternate'
     assert all(r['refreshes']==15 for r in report['observed_runs'][1:-1]),report['observed_runs']
     (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
     e.run('shot',str(out/'final.png'))
     print('PASS: native Agumon in disliked Freezeland on 2 MB; captured 75 consecutive refreshes',flush=True)
    finally:
     e.stop();xv.terminate();xv.wait(timeout=10)


if __name__ == "__main__":
    main()
