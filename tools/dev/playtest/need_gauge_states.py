#!/usr/bin/env python3
"""Capture normal, both blinking halves, active and satisfied need gauges on 2 MB.

Run with the project's Pillow-enabled Python. Only care fixtures and the existing
clock rule are changed in RAM; the blink phases advance through native play ticks.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.training_evolution import call,await_value
from tools.dev.playtest.training_care_hud import care
from tools.langpatch import elf_symbols

NEEDS=('hunger','toilet','tiredness')
VALUES={'hunger':('foodLevel',120,30,0,4),'toilet':('poopLevel',24,3,0,8),
        'tiredness':('tiredness',40,76,80,2)}


def phase(e,on):
    address=e.A('PLAYTIME_FRAMES')&0x1fffff
    # A new tick prevents a repeated phase from capturing the previous fixture.
    target=3 if on else 23
    e.run('lua',f'''local start=PCSX.getMemPtr()[{address}]+256*PCSX.getMemPtr()[{address+1}]
      NA={{done=false}}
      NA.l=PCSX.Events.createEventListener('GPU::Vsync',function()
        local m=PCSX.getMemPtr();local n=m[{address}]+256*m[{address+1}]
        if n~=start and n%40=={target} then NA.tick=n;NA.done=true;NA.l:remove();PCSX.pauseEmulator() end
      end)
      PCSX.resumeEmulator()''')
    end=time.monotonic()+20
    while time.monotonic()<end:
        if e.run('lua','return NA.done').strip()=='true':
            return int(e.run('lua','return NA.tick').strip())
        time.sleep(.05)
    raise AssertionError('native blink phase did not advance')


def warp(e,screen):
    # Explicit POST-backed pause/resume also works after a phase listener paused.
    e.run('pause')
    e.poke('TAMER_SUB_STATE',b'\0')
    e.poke('TARGET_MAP',struct.pack('<h',screen))
    e.poke('CURRENT_EXIT',b'\0')
    e.poke('TAMER_STATE',b'\5')
    e.run('resume')
    for _ in range(30):
        e.wait(1)
        ram=e.ram()
        if e.peek('CURRENT_SCREEN','h',ram)==screen and e.peek('TAMER_STATE','b',ram)==0:
            # Control can return before the native map fade has finished.
            e.wait(2)
            return
    raise AssertionError(f'warp to {screen} did not finish')


def fixture(e,need=None,state='normal',all_needs=False):
    e.run('pause')
    fields=dict(condition=0,foodLevel=120,poopLevel=24,tiredness=40,
                starvationTimer=120,poopingTimer=1200,energyLevel=100,
                happiness=52,discipline=80,sleepyHour=23,sleepyMinute=0,
                virusBar=0,age=1,evoTimer=0,remainingLifetime=1000)
    for name in NEEDS if all_needs else (() if need is None else (need,)):
        field,normal,warning,active,bit=VALUES[name]
        fields[field]=dict(normal=normal,warning=warning,active=active)[state]
        if state=='active':fields['condition']|=bit
    # A zero day-length rule freezes game time while leaving the field HUD visible.
    # PLAYTIME_FRAMES continues at 20 real ticks/s, including during gym training.
    e.poke('MOD_CLOCK',struct.pack('<h',0))
    e.poke('MOD_OPT_BARS',struct.pack('<i',1))
    e.gs('set','gametime_running=1','hour=12','minute=0',
         *[f'partner.para.{k}={v}' for k,v in fields.items()])
    e.poke('CURRENT_FRAME',struct.pack('<H',14400))
    e.poke('LAST_HANDLED_FRAME',struct.pack('<H',14400))
    return fields


def check_image(file,name,state,on):
    im=Image.open(file).convert('RGB');assert im.size==(320,240)
    y=185+NEEDS.index(name)*14
    top=im.getpixel((274,y))
    pixels=[im.getpixel((x,y+6)) for x in range(289,307)]
    # Count blue fill independently of its brightness; dim fills stay present.
    count=sum(b>r+15 and b>g+5 for r,g,b in pixels)
    normal=dict(hunger=12,toilet=9,tiredness=11)
    warning=dict(hunger=3,toilet=1,tiredness=4)
    want=dict(hunger=0,toilet=0,tiredness=4)[name] if state=='active' else normal[name] if state=='normal' else warning[name]
    special={'tiredness-exhausted-100.png':0,'tiredness-rested.png':18,
             'tiredness-last-energy.png':1,'toilet-just-used.png':18,
             'toilet-last-reserve.png':1}
    want=special.get(file.name,want)
    assert count==want,(file,count,want,pixels)
    if state=='active':
        assert top[0]>top[1]+25 and top[1]>top[2],(file,top)
    else:
        assert top[0]==top[1]==top[2],(file,top)
    dim=state=='warning' and not on
    assert top[0]>150,(file,top)
    # Both rows, outline and grey remainder must dim as well as the fill.
    scale=45/128 if dim else 1
    for yoff,base in ((6,(160,208,248)),(7,(120,184,248))):
        observed=im.getpixel((289,y+yoff))
        expected=base if want else (112,112,112) if yoff==6 else (88,88,88)
        assert all(abs(c-scale*b)<10 for c,b in zip(observed,expected)),(file,observed,expected,scale)
    outline=im.getpixel((288,y+5))
    assert all(abs(c-scale*b)<10 for c,b in zip(outline,(16,24,32))),(file,outline)
    if want<18:
        remainder=im.getpixel((306,y+6))
        assert all(abs(c-scale*112)<10 for c in remainder),(file,remainder)
    return {'fill_pixels':count,'housing_top_rgb':top,'dim':dim}


def capture(e,out,rows,name,state,on,label=None):
    tick=phase(e,on)
    file=out/(label or f'{name}-{state}-{("on" if on else "off")}.png')
    e.run('shot',str(file))
    gauges=NEEDS if name=='all' else (name,)
    pixels={n:check_image(file,n,state,on) for n in gauges}
    raw=care(e)
    for n in gauges:
        field,normal,warning,active,bit=VALUES[n]
        expected=dict(normal=normal,warning=warning,active=active)[state]
        special={'tiredness-exhausted-100.png':100,'tiredness-rested.png':0,
                 'tiredness-last-energy.png':99,'toilet-just-used.png':48,
                 'toilet-last-reserve.png':1}
        expected=special.get(label,expected)
        assert raw[field]==expected,(file,n,raw,expected)
    row=dict(file=file.name,need=name,state=state,on=on,play_tick=tick,
             current_frame=e.peek('CURRENT_FRAME','H'),game_time_running=e.peek('IS_GAMETIME_RUNNING','b'),
             font=e.peek('MOD_FONT','b'),fps_mode=e.peek('MOD_FPS_MODE_RUN','i'),care=raw,pixels=pixels)
    rows.append(row);print(json.dumps(row),flush=True)
    return tick


def compare_pixels(out):
    """Compare active tint, unchanged warning icons and dimmed bar pixels."""
    errors={}
    for index,need in enumerate(NEEDS):
        y=185+index*14
        normal=Image.open(out/f'{need}-normal-on.png').convert('RGB')
        active=Image.open(out/f'{need}-active-off.png').convert('RGB')
        bright=Image.open(out/f'{need}-warning-on.png').convert('RGB')
        dim=Image.open(out/f'{need}-warning-off.png').convert('RGB')
        tint_error=dim_error=icon_error=0
        for dy in range(13):
            for dx in range(34):
                point=(274+dx,y+dy)
                if dx<13:
                    rgb=normal.getpixel(point)
                    # Captures have already undergone native RGB15 expansion.
                    lum=sum(c*w for c,w in zip(rgb,(.299,.587,.114)))/255
                    expected=[.45*c+.55*lum*t for c,t in zip(rgb,(235,90,80))]
                    tint_error=max(tint_error,max(abs(a-b) for a,b in zip(active.getpixel(point),expected)))
                if dx<13:
                    icon_error=max(icon_error,max(abs(a-b) for a,b in zip(dim.getpixel(point),bright.getpixel(point))))
                if 14<=dx<34 and 5<=dy<9:
                    expected=[c*45/128 for c in bright.getpixel(point)]
                    dim_error=max(dim_error,max(abs(a-b) for a,b in zip(dim.getpixel(point),expected)))
        assert tint_error<12,(need,tint_error)
        assert dim_error<10,(need,dim_error)
        assert icon_error==0,(need,icon_error)
        errors[need]=dict(whole_icon_tint_max_error=tint_error,bar_dim_max_error=dim_error,warning_icon_max_error=icon_error)
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True);p.add_argument('--card',required=True)
    p.add_argument('--out',default='build/need-alerts/runtime');p.add_argument('--port',type=int,default=41968)
    p.add_argument('--boot-state',type=Path,help='field checkpoint from this exact disc only')
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    display=next(n for n in range(190,230) if not Path(f'/tmp/.X11-unix/X{n}').exists())
    log=(out/'xvfb.log').open('w')
    xvfb=subprocess.Popen(['Xvfb',f':{display}','-screen','0','1024x768x24','-nolisten','tcp'],stdout=log,stderr=log)
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'))
    e.env.update(EMU_ARGS='-interpreter -debugger',DISPLAY=f':{display}')
    for name,(address,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(name,address)
    try:
        time.sleep(1);e.start(a.card)
        if a.boot_state:
            e.run('load',str(a.boot_state.resolve()));e.run('resume')
        else:
            assert e.continue_game()==0;e.wait(5)
        assert len(e.ram())==2097152 and e.in_control()
        assert e.peek('PARTNER_ENTITY','i')==3,'supply an Agumon card'
        warp(e,112)
        call(e,'modSetFont',0);e.poke('MOD_FPS_MODE_RUN',struct.pack('<i',1))
        e.poke('MOD_OPT_STORY',struct.pack('<i',0))
        e.run('save',str(out/'field-native-clock.state'))
        fixture(e);phase(e,True);e.run('save',str(out/'field.state'))
        rows=[]
        for name in NEEDS:
            fixture(e,name,'normal');capture(e,out,rows,name,'normal',True)
            fixture(e,name,'warning')
            capture(e,out,rows,name,'warning',True);capture(e,out,rows,name,'warning',False)
            fixture(e,name,'active')
            capture(e,out,rows,name,'active',True);capture(e,out,rows,name,'active',False)
            fixture(e,name,'normal');capture(e,out,rows,name,'normal',True,f'{name}-satisfied.png')
        fixture(e,'tiredness','active');e.gs('set','partner.para.tiredness=100')
        capture(e,out,rows,'tiredness','active',False,'tiredness-exhausted-100.png')
        for name,field,value,state,label in (
            ('toilet','poopLevel',48,'normal','toilet-just-used.png'),
            ('toilet','poopLevel',1,'warning','toilet-last-reserve.png'),
            ('tiredness','tiredness',0,'normal','tiredness-rested.png'),
            ('tiredness','tiredness',99,'active','tiredness-last-energy.png')):
            fixture(e,name,state);e.gs('set',f'partner.para.{field}={value}')
            capture(e,out,rows,name,state,True,label)
        # Six uninterrupted native half-cycles with frozen care timers establish cadence.
        fixture(e,state='warning',all_needs=True)
        ticks=[]
        for k in range(6):ticks.append(capture(e,out,rows,'all','warning',k%2==0,f'cadence-{k}.png'))
        assert all((b-a)%1200==20 for a,b in zip(ticks,ticks[1:])),ticks
        assert all(r['current_frame']==14400 for r in rows), 'care clock advanced during fixtures'
        call(e,'modSetFont',2);e.poke('MOD_FPS_MODE_RUN',struct.pack('<i',2))
        for state,on in [('normal',True),('warning',True),('warning',False),('active',True)]:
            fixture(e,state=state,all_needs=True)
            capture(e,out,rows,'all',state,on,f'CLASSIC-60-{state}-{on}.png')
        # Night floor checks use the same glyph-free geometry in both fonts.
        fixture(e)
        e.gs('set','hour=23','minute=0','partner.para.sleepyHour=6')
        warp(e,0)
        for font in (0,2):
            call(e,'modSetFont',font)
            for state,on in [('normal',True),('warning',True),('warning',False),('active',True)]:
                fixture(e,state=state,all_needs=True)
                e.gs('set','hour=23','minute=0','partner.para.sleepyHour=6')
                e.poke('CURRENT_FRAME',struct.pack('<H',27600))
                e.poke('LAST_HANDLED_FRAME',struct.pack('<H',27600))
                capture(e,out,rows,'all',state,on,f'dark-font{font}-{state}-{on}.png')
        warp(e,112)
        # Exercise the same warning clock through the gym callback with game time paused.
        fixture(e,state='warning',all_needs=True)
        e.poke('TRN_LOADING_COMPLETE',b'\0');call(e,'loadTrainingLibrary',112)
        e.run('resume');await_value(e,'TRN_LOADING_COMPLETE','b',lambda n:n==0)
        e.run('pause');e.gs('set','gametime_running=0')
        call(e,'writePStat',246,0);call(e,'TRN_setupHpTraining',112)
        e.run('resume');await_value(e,'TRAINING_STATE','b',lambda n:n==2);e.run('pause')
        capture(e,out,rows,'all','warning',True,'gym-warning-on.png')
        capture(e,out,rows,'all','warning',False,'gym-warning-off.png')
        assert rows[-1]['game_time_running']==0
        (out/'result.json').write_text(json.dumps(dict(ram_bytes=2097152,half_cycle_ticks=20,pixel_comparison=compare_pixels(out),rows=rows),indent=2)+'\n')
        print('PASS: normal/blink-on/blink-off/active/satisfied, three needs, native one-second phases, CLASSIC/60 and paused gym',flush=True)
    finally:
        e.stop();xvfb.terminate();xvfb.wait(timeout=10);log.close()


if __name__=='__main__':main()
