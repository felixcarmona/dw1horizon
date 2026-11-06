#!/usr/bin/env python3
"""Capture B5a on original 2 MB: NEW/CLASSIC, light/dark, 30/60 FPS.

Ordinary and warning stills use live care fixtures. Two motion clips let native
care ticks consume food/toilet timers; handlePostBattleTiredness supplies the
native +5 fatigue event during recording. No gameplay rule is changed.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.food_sickness import emulator
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.training_evolution import call
from tools.dev.game_state import PARTNER_PARA_FIELDS


def care(e):
    ram=e.ram();at=e.A('PARTNER_PARA')&0x1fffff;result={}
    for field,fmt in PARTNER_PARA_FIELDS:
        result[field]=struct.unpack_from('<'+fmt,ram,at)[0];at+=struct.calcsize('<'+fmt)
    return result


def setcare(e,**values):
    e.run('pause')
    try:
        e.gs('set',*(f'partner.para.{k}={v}' for k,v in values.items()))
    finally:
        e.run('resume')


def invoke(e,name,*args):
    result=call(e,name,*args);e.run('resume');return result


def shot_after_swaps(e,path):
    e.run('lua',f'''
      HUD_SWAP={{n=0,done=false}}
      HUD_SWAP.bp=PCSX.addBreakpoint({e.A('GsSortClear')},'Exec',4,'hud-swap',function()
        HUD_SWAP.n=HUD_SWAP.n+1
        if HUD_SWAP.n==6 then
          HUD_SWAP.done=true;HUD_SWAP.bp:remove();PCSX.pauseEmulator()
        end
      end)
      PCSX.resumeEmulator()
    ''')
    for _ in range(200):
        if e.run('lua','return HUD_SWAP.done').strip()=='true':break
        e.wait(.1)
    else:raise AssertionError('no GPU swaps')
    e.run('shot',str(path))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--disc',required=True);p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=41964)
    p.add_argument('--stills-only',action='store_true')
    p.add_argument('--motion-only',action='store_true',help='reuse field.state and matrix results from this build')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    e=emulator(str(Path(a.disc).resolve()),str(Path(a.exe).resolve()),a.port,out)
    report=json.loads((out/'result.json').read_text()) if a.motion_only else {'matrix':[],'motion':[]}
    report['motion']=[];xvfb=None
    if not os.environ.get('DISPLAY'):
        xvfb=subprocess.Popen(['Xvfb',':293','-screen','0','1024x768x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        e.env['DISPLAY']=':293';time.sleep(.5)
    try:
        card=field_card(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd',out/'field.mcd')
        e.start(str(card))
        if a.motion_only:
            e.wait(2);e.run('load',str(out/'field.state'));e.run('resume')
        else:
            assert e.continue_game()==0
        report['ram_bytes']=len(e.ram());assert report['ram_bytes']==2097152
        e.gs('set','gametime_running=0','partner.para.evoTimer=0','partner.para.remainingLifetime=1000')
        e.poke('MOD_OPT_STORY',struct.pack('<i',0));e.poke('MOD_OPT_BARS',struct.pack('<i',1))
        t=e.peek('RAISE_DATA+96','h') # Agumon row 3, 28 bytes/row, poopTimer at +12.
        assert t>0;report['toilet_baseline']=t
        scenes=[] if a.motion_only else [('light',92,12),('dark',0,23)]
        for floor,screen,hour in scenes:
            e.gs('set',f'hour={hour}','minute=0')
            assert e.warp(screen);assert e.in_control()
            for font,f in [('NEW',0),('CLASSIC',2)]:
                invoke(e,'modSetFont',f)
                for fps in (30,60):
                    invoke(e,'modSetFrameRate',fps)
                    e.gs('set','gametime_running=1')
                    setcare(e,condition=0,happiness=52,discipline=32,foodLevel=79,
                            poopLevel=round(2*t*.4),tiredness=68,areaEffectTimer=0)
                    e.wait(.7)
                    stem=f'{floor}-{font}-{fps}'
                    e.run('shot',str(out/f'{stem}-ordinary.png'))
                    setcare(e,condition=12,starvationTimer=54,poopingTimer=2000,tiredness=80)
                    e.wait(.7);e.run('shot',str(out/f'{stem}-needs.png'))
                    report['matrix'].append(dict(scene=stem,screen=screen,font=e.peek('MOD_FONT','b'),
                        fps_mode=e.peek('MOD_FPS_MODE_RUN','i'),care=care(e)))
                    print('CAPTURE',stem,flush=True)
            # OFF comparison and common field suppression paths on each floor.
            e.poke('MOD_OPT_BARS',struct.pack('<i',0));e.wait(.5)
            e.run('shot',str(out/f'{floor}-OFF-original.png'))
            e.poke('MOD_OPT_BARS',struct.pack('<i',1))
        # Native transitions, including toilet's different reset conventions.
        setcare(e,condition=8,poopLevel=0,poopingTimer=2000)
        invoke(e,'handleToilet');assert care(e)['poopLevel']==2*t
        setcare(e,condition=8,poopLevel=0,poopingTimer=2000)
        invoke(e,'handlePortaPotty');assert care(e)['poopLevel']==t
        setcare(e,tiredness=70);invoke(e,'reduceTiredness',30);assert care(e)['tiredness']==40
        report['native_resets']={'toilet':2*t,'portable_potty':t,'rest_tiredness':40}
        e.run('save',str(out/'field.state'))
        if not a.stills_only:
            for floor,screen,hour,font,f,fps in [('light',92,12,'NEW',0,30),('dark',0,23,'CLASSIC',2,60)]:
                e.gs('set','gametime_running=0',f'hour={hour}','minute=0')
                assert e.warp(screen);invoke(e,'modSetFont',f);invoke(e,'modSetFrameRate',fps)
                setcare(e,condition=0,foodLevel=25,starvationTimer=0,poopLevel=2,poopingTimer=2000,
                        tiredness=46,subTiredness=0,areaEffectTimer=0,energyLevel=40,
                        happiness=52,discipline=80,evoTimer=0,remainingLifetime=1000,
                        sleepyHour=1,wakeupHour=9,tirednessSleepTimer=-10000)
                e.wait(.4);before=care(e)
                stem=f'motion-{floor}-{font}-{fps}'
                e.gs('set','gametime_running=1')
                recording=subprocess.Popen([sys.executable,str(ROOT/'tools/dev/emulator.py'),'record',str(out/f'{stem}.mp4'),'25','30'],env=e.env,stdout=(out/f'{stem}.log').open('w'),stderr=subprocess.STDOUT)
                e.wait(4)
                invoke(e,'handlePostBattleTiredness')
                event=care(e)
                assert event['tiredness']==before['tiredness']+5,(before,event)
                recording.wait(timeout=90)
                assert recording.returncode==0
                e.gs('set','gametime_running=0');after=care(e)
                assert after['condition']&4 and after['condition']&8,after
                assert after['starvationTimer']<180,after
                e.run('shot',str(out/f'{stem}-end.png'))
                report['motion'].append(dict(scene=stem,before=before,post_battle_event=event,after=after))
                print('MOTION',stem,json.dumps(after),flush=True)
        # Existing tick-owned slide still suppresses the taller HUD.
        e.gs('set','gametime_running=0');e.wait(.6)
        assert e.peek('STATUS_UI_OFFSET_X','h')==240
        e.run('shot',str(out/'field-suppressed.png'))
        e.gs('set','gametime_running=1');e.wait(.6)
        assert e.peek('STATUS_UI_OFFSET_X','h')==75
        report['slide']={'hidden':240,'shown':75}
        # A real wild battle, then deterministic ON/OFF renders from one checkpoint.
        e.gs('set','gametime_running=1','hour=12','minute=0','partner.stats.off=10')
        setcare(e,condition=0,foodLevel=180,poopLevel=2*t,tiredness=0)
        assert e.warp(0);assert e.in_control()
        e.gs('approach','0','120')
        for _ in range(40):
            if e.peek('GAME_STATE','b')==1:break
            e.press('CONFIRM',8);e.wait(.5)
        else:raise AssertionError('wild battle did not begin')
        e.wait(2);e.run('pause');e.run('save',str(out/'battle.state'))
        for enabled in (0,1):
            e.run('load',str(out/'battle.state'))
            e.poke('MOD_OPT_BARS',struct.pack('<i',enabled))
            shot_after_swaps(e,out/f'battle-bars-{enabled}.png')
        from PIL import Image, ImageChops
        assert ImageChops.difference(Image.open(out/'battle-bars-0.png'),Image.open(out/'battle-bars-1.png')).getbbox() is None
        report['battle']={'on_off_pixels_identical':True,'swaps_after_checkpoint':6}
        print('BATTLE: ON/OFF frames identical',flush=True)
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: 2 MB, eight font/floor/rate combinations, native resets and live care transitions',flush=True)
    finally:
        if report:
            (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        e.stop()
        if xvfb:xvfb.terminate()


if __name__=='__main__':main()
