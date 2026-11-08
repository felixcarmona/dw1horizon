#!/usr/bin/env python3
"""Prove native Scold care bubbles, refusal/clear timing and nine-slot edges on 2 MB.

Only setup stats/bag/positions are fixtures. Refusal, Scold and walking clear run
through the game's ordinary input/state machines. Captures use presented frames.
"""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.dev.playtest.qol import ProofEmu
from tools.dev.playtest.birdramon_recruitment import field_card
from tools.dev.playtest.hpmp_bubbles import setup,settle,open_menu,menu_press
from tools.dev.playtest.hpmp_extremes import observer,place,zoom
from tools.dev.playtest.quick_care import position,place_partner,wait
from tools.langpatch import elf_symbols
from tools.languages import CODES
from tools.localize.build import tim_entries


def state(e):
    ram=e.ram();slots=e.peek('MOD_RING_FROM','9i',ram)
    return {'active':[i for i,v in enumerate(slots) if v!=0x10000],
            'slots':slots,'scold':e.peek('ITEM_SCOLD_FLAG','b',ram),
            'badge':e.peek('MOD_RING_BADGE','i',ram),
            'condition':e.peek('PARTNER_PARA','I',ram),
            'tamer':e.peek('TAMER_STATE','b',ram),'partner':e.peek('PARTNER_STATE','b',ram),
            'menu':e.peek('IS_IN_MENU','i',ram)}


def shot(e,out,name):
    e.run('pause');e.run('shot',str(out/(name+'.png')))
    report=e.run('lua','return WORST.report').strip()
    if report not in ('nil',''):
        bounds=json.loads(report)['bounds']
        if bounds[0]<bounds[2]:e.scold_bounds=bounds
        zoom(out,name,getattr(e,'scold_bounds',[100,40,170,85]))
    e.run('resume')
    return state(e)


def begin(e,out,name):
    raw=out/(name+'.raw')
    e.run('lua',f"WORST.n=0;WORST.records={{}};WORST.vbl={{}};WORST.file=Support.File.open('{raw}','TRUNCATE');WORST.max=100000")
    return raw


def frames(e,count=30):
    """Hold a stable case for presented swaps, independent of host CPU load."""
    target=int(e.run('lua','return WORST.n').strip())+count
    end=time.monotonic()+90
    while int(e.run('lua','return WORST.n').strip())<target:
        assert time.monotonic()<end,'presented-frame hold timed out'
        e.wait(.1)


def finish(e,raw):
    e.run('lua','WORST.max=0;WORST.file:close()')
    records=json.loads(e.run('lua',"return '['..table.concat(WORST.records,',')..']'").strip())
    Path(str(raw)+'.vbl').write_text(e.run('lua',"return table.concat(WORST.vbl,' ')").strip())
    subprocess.run([sys.executable,str(ROOT/'tools/dev/presented_frames.py'),'mp4',str(raw),str(raw.with_suffix('.mp4'))],check=True)
    return records


def closed(e):
    wait(e,'IS_IN_MENU',0,seconds=60)
    wait(e,'TAMER_STATE',0,'b',seconds=60)
    wait(e,'PARTNER_STATE',1,'b',seconds=60)


def native_art(data):
    base,bpp,w,h=tim_entries(data)[4]
    assert (bpp,w,h)==(0,256,64)
    clut=base-12-512+13*32
    return bytes(data[clut:clut+32])+b''.join(data[base+y*128:base+y*128+10] for y in range(40,60))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc');p.add_argument('--exe',required=True)
    p.add_argument('--out',type=Path,default=Path('build/scold-proof'))
    p.add_argument('--port',type=int,default=41736);p.add_argument('--display',type=int,default=286)
    p.add_argument('--resume',action='store_true')
    p.add_argument('--clear-ground',action='store_true',help='walk farther south before recording, clear of foreground scenery')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    a.exe=str(Path(a.exe).resolve());a.disc=str(Path(a.disc).resolve())
    e=ProofEmu(a.disc,a.exe,a.port,str(out/'emu'))
    e.env.update(EMU_ARGS='-interpreter -debugger',DISPLAY=f':{a.display}')
    for n,(addr,_,_) in elf_symbols(a.exe+'.elf').items():e.table.setdefault(n,addr)
    display=subprocess.Popen(['Xvfb',f':{a.display}','-screen','0','1024x768x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    result={'exe_sha256':hashlib.sha256(Path(a.exe).read_bytes()).hexdigest(),'cases':{}}
    def interrupted(n,frame):raise SystemExit(128+n)
    signal.signal(signal.SIGTERM,interrupted)
    try:
        card=field_card(ROOT/'tools/dev/saves/corpus/20261027-d2796814.mcd',out/'field.mcd');e.start(str(card))
        base=out/'base.state'
        if a.resume:
            assert json.loads((out/'fixture.json').read_text())['exe_sha256']==result['exe_sha256']
            e.run('load',str(base));e.run('resume')
        else:
            assert e.continue_game()==0;assert e.in_control()
            setup(e,1000,1000);assert e.warp(171);assert e.in_control()
            e.press('DOWN',35);e.press('RIGHT',25);e.press('DOWN',90)
            x,y,z=position(e,'TAMER_ENTITY');place_partner(e,x-350,y,z+200)
            setup(e,1000,1000);e.run('save',str(base))
            (out/'fixture.json').write_text(json.dumps({'exe_sha256':result['exe_sha256']})+'\n')
        if a.clear_ground:
            e.press('DOWN',240);assert e.in_control()
            setup(e,1000,1000);e.run('save',str(base))
            e.run('shot',str(out/'clear-ground-source.png'))
        assert len(e.ram())==0x200000
        assert not json.loads(e.api('/api/v1/execution-flow'))['8mb']
        result['ram_bytes']=0x200000
        assert e.peek('PARTNER_ENTITY','i')==3, 'proof requires native Agumon'
        # Every localized field stack must retain the actual native menu cell/CLUT.
        source=native_art((ROOT/'extracted/ETCDAT/ETCTIM.BIN').read_bytes())
        result['atlases']={}
        for code in CODES:
            path=Path(a.exe).parent.parent/'lang-tex'/code/'ETCDAT/ETCTIM.BIN'
            assert native_art(path.read_bytes())==source,code
            result['atlases'][code]=hashlib.sha256(source).hexdigest()
        observer(e)
        previous=json.loads((out/'resume-checkpoint.json').read_text()) if a.resume and (out/'resume-checkpoint.json').exists() else {}
        if not a.clear_ground and previous.get('cases',{}).get('after-scold') and (out/'pending.state').exists():
            assert previous['exe_sha256']==result['exe_sha256']
            result.update(previous)
            for frame in reversed(previous.get('refusal_frames',[])):
                if frame['quads']:
                    e.scold_bounds=frame['bounds'];break
            for key in ('error','failure_state','passed'):result.pop(key,None)
        else:
            # A 50% HP shortage is optional recovery: no resource bubble or badge.
            # Try ordinary low-discipline feeding until the game's own refusal occurs.
            for attempt in range(12):
                e.run('load',str(base));e.run('resume');setup(e,500,1000)
                e.gs('set','partner.para.discipline=0','partner.para.happiness=50')
                open_menu(e)
                assert e.peek('feedSlots','B')==0
                raw=begin(e,out,'refusal')
                menu_press(e,'CONFIRM')
                until=time.monotonic()+60
                while time.monotonic()<until:
                    got=state(e)
                    if got['scold']==1 and e.peek('feedState','i')==1:break
                    if not got['menu'] and not got['tamer'] and got['partner']==1:break
                    e.wait(.15)
                if e.peek('ITEM_SCOLD_FLAG','b')==1:
                    result['refusal_attempts']=attempt+1
                    assert e.peek('feedSlots','B')==254
                    e.run('shot',str(out/'refused-care-menu.png'))
                    menu_press(e,'CANCEL');closed(e);settle(e)
                    got=shot(e,out,'refused-scold-alone')
                    assert got['active']==[8] and got['badge']==4,got
                    result['cases']['refused-scold-alone']=got
                    frames(e);result['refusal_frames']=finish(e,raw)
                    break
                finish(e,raw)
            else:raise AssertionError('no native refusal after 12 low-discipline feeds')
            e.run('save',str(out/'pending.state'))
            raw=begin(e,out,'scold-use')
            open_menu(e);assert e.peek('feedSlots','B')==254
            menu_press(e,'CONFIRM');closed(e);settle(e)
            got=shot(e,out,'after-scold')
            assert got['scold']!=1 and got['active']==[] and got['badge']==0,got
            result['cases']['after-scold']=got;frames(e)
            result['scold_frames']=finish(e,raw)
        # The existing window expires on movement, rather than a new wall-clock timer.
        e.run('load',str(out/'pending.state'));e.run('resume')
        raw=begin(e,out,'window-expiry');e.wait(.5);e.press('RIGHT',20);closed(e);settle(e)
        got=shot(e,out,'after-window-expiry')
        assert got['scold']==0 and got['active']==[] and got['badge']==0,got
        result['cases']['after-window-expiry']=got;frames(e)
        result['expiry_frames']=finish(e,raw)
        # Keep the naturally produced pending window; add independent care fixtures.
        e.run('load',str(out/'pending.state'));e.run('resume')
        e.run('pause')
        e.gs('set','partner.stats.currentHP=290','partner.stats.currentMP=290',
             'partner.para.condition=4','partner.para.foodLevel=0')
        settle(e);got=shot(e,out,'combined')
        assert got['active']==[0,6,7,8] and got['badge']==4,got
        result['cases']['combined']=got
        raw=begin(e,out,'combined');frames(e,40);result['combined_frames']=finish(e,raw)
        e.run('pause')
        e.gs('set','partner.para.condition=111','partner.para.tiredness=80',
             'partner.para.poopLevel=0','partner.para.poopingTimer=2000',
             'partner.para.happiness=50','partner.para.sicknessTimer=0','partner.para.injuryTimer=0')
        settle(e);assert state(e)['active']==list(range(9)),state(e)
        initial=position(e,'PARTNER_ENTITY')
        for name,target in [('all-nine',(160,90)),('left',(8,90)),('right',(312,90)),
                            ('top',(160,-2)),('top-left',(8,-2)),('top-right',(312,-2))]:
            xyz,projected=place(e,initial,target)
            settle(e);got=shot(e,out,name)
            assert got['active']==list(range(9)) and got['badge']==4,got
            raw=begin(e,out,name);frames(e);records=finish(e,raw)
            assert records and all(r['quads']>=19 for r in records),records[:2]
            bounds=[(min if i<2 else max)(r['bounds'][i] for r in records) for i in range(4)]
            assert bounds[0]>=0 and bounds[1]>=0 and bounds[2]<=320 and bounds[3]<=240,(name,bounds)
            clock_right=e.peek('CLOCK_OFFSET_X','h')+160+50
            overlap=bounds[0]<clock_right and bounds[2]>clock_right-52 and bounds[1]<84 and bounds[3]>16
            assert not overlap,(name,bounds,clock_right)
            zoom(out,name,bounds)
            result['cases'][name]={'state':got,'position':xyz,'projected_head':projected,'bounds':bounds,'clock_overlap':overlap,'frames':records}
            print(name,bounds,flush=True)
        result['passed']=True
    except BaseException as error:
        result['error']=str(error)
        try:
            result['failure_state']=state(e);e.run('shot',str(out/'failure.png'))
            (out/'failure.ram').write_bytes(e.ram())
        except Exception:pass
        raise
    finally:
        if result.get('cases',{}).get('after-scold'):
            (out/'resume-checkpoint.json').write_text(json.dumps(result,indent=2)+'\n')
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        e.stop();display.terminate();display.wait(timeout=10)


if __name__=='__main__':main()
