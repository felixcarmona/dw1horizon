#!/usr/bin/env python3
"""Compare automatic presentation with the preceding manual renderer in DuckStation.

DS_MAP must match DISC. Uses a private DuckStation tree in this checkout and the
standard DS_DISPLAY/DS_GDB_PORT isolation. Every run stops the emulator it starts.
A fresh private memory card is required; --card is copied before boot.
"""
import argparse
from collections import Counter
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev import duckstation as ds
from tools.langpatch import elf_symbols
from tools.dev.fps.curlingdscheck import BatchGDB

ds.sym = lru_cache(None)(ds.sym)


def read(*names):
    g = BatchGDB()
    try:
        return {n: int.from_bytes(bytes.fromhex(x), 'little') for n, x in zip(
            names, g.batch(['m%x,%x' % (ds.sym(n), {'CURRENT_SCREEN':2,'GAME_STATE':1,'MENU_HIGHLIGHTS':1,'TAMER_STATE':1,'MOD_FONT':1}.get(n.split('+')[0],4)) for n in names]))}
    finally:
        g.close()


def write(name, value, size=4):
    g = BatchGDB()
    try:
        g.write(ds.sym(name), int(value).to_bytes(size, 'little', signed=value < 0))
    finally:
        g.close()


def wait_for(predicate, seconds=90):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(.25)
    raise RuntimeError('timed out waiting for game state')


def key(key):
    ds.focus(ds.window())
    subprocess.run(['xdotool', 'key', key], env=ds.ENV, check=True)


def press(button, frames=8):
    """Count guest refreshes so input remains reliable on a busy host."""
    name = ds.KEYS[button]
    ds.focus(ds.window())
    start = read('Vcount')['Vcount']
    subprocess.run(['xdotool','keydown',name],env=ds.ENV,check=True)
    try:
        end=time.monotonic()+30
        while (read('Vcount')['Vcount']-start)&0xffffffff < frames:
            if time.monotonic()>end: raise RuntimeError('pad press made no refresh progress')
            time.sleep(.005)
    finally:
        subprocess.run(['xdotool','keyup',name],env=ds.ENV,check=True)
    time.sleep(.1)


def continue_game():
    selected = False
    previous = None
    for _ in range(160):
        state=read('CURRENT_MENU','MAIN_MENU_TICKS','MEMORY_CARD_ERROR',
                   'MENU_HIGHLIGHTS','MOD_OPT_BUTTONS','MOD_FPS_TICKS')
        menu=state['CURRENT_MENU']
        marker=(menu,state['MENU_HIGHLIGHTS'])
        if marker!=previous:
            print('continue',state,flush=True);previous=marker
        if selected and menu==0xffffffff and state['MOD_FPS_TICKS']>20:
            return
        if selected and 0<state['MEMORY_CARD_ERROR']<20:
            raise RuntimeError('memory card error '+str(state))
        confirm='CIRCLE' if state['MOD_OPT_BUTTONS'] else 'CROSS'
        if menu==0 and state['MAIN_MENU_TICKS']>3:
            pos=state['MENU_HIGHLIGHTS']
            if pos!=1:
                press('DOWN' if pos==0 else 'UP',2)
            else:
                press(confirm,8);selected=True
        elif selected and menu in (0x14,0x17,0x18):
            press(confirm,8)
        elif not selected:
            press('START',12)
        time.sleep(.5)
    raise RuntimeError('Continue did not reach the world: '+str(state))


def in_control():
    for _ in range(80):
        state=read('IS_SCRIPT_PAUSED','TAMER_STATE','MOD_OPT_BUTTONS')
        if state['IS_SCRIPT_PAUSED']==1 and state['TAMER_STATE']==0:
            return
        press('CIRCLE' if state['MOD_OPT_BUTTONS'] else 'CROSS',4)
        time.sleep(.25)
    raise RuntimeError('no free field control: '+str(state))


def warp(screen):
    in_control()
    g = BatchGDB()
    try:
        for name, value, size in [('TAMER_SUB_STATE',0,1),
                                  ('TARGET_MAP',screen,2),('CURRENT_EXIT',0,1),('TAMER_STATE',5,2)]:
            g.write(ds.sym(name), value.to_bytes(size,'little'))
    finally:
        g.close()
    wait_for(lambda: (read('CURRENT_SCREEN')['CURRENT_SCREEN'] & 65535) == screen)
    in_control()
    time.sleep(2)


def pacing(count=181):
    """Guest refresh intervals between actual display swaps, independent of host speed."""
    g = BatchGDB()
    g.s.settimeout(30)
    address = ds.sym('GsSwapDispBuff')
    samples = []
    try:
        assert g.cmd('Z0,%x,4' % address) == 'OK'
        for _ in range(count):
            stop = g.cmd('c')
            if not stop.startswith(('S', 'T')):
                raise RuntimeError('unexpected debugger stop: '+stop)
            names = ['Vcount', 'MOD_FPS_TICKS', 'MOD_FPS_RENDERS', 'MOD_FPS_MODE_RUN']
            values = [int.from_bytes(bytes.fromhex(v),'little') for v in g.batch(
                ['m%x,4' % ds.sym(n) for n in names])]
            samples.append(dict(zip(names, values)))
    finally:
        g.cmd('z0,%x,4' % address)
        g.close()
    intervals = [(b['Vcount']-a['Vcount']) & 0xffffffff for a,b in zip(samples,samples[1:])]
    if any(d == 0 for d in intervals):
        raise RuntimeError('display breakpoint repeated without a refresh')
    if any(b['MOD_FPS_RENDERS'] != a['MOD_FPS_RENDERS'] + 1 for a,b in zip(samples,samples[1:])):
        raise RuntimeError('missed or repeated display swap')
    return dict(interval_refreshes=dict(sorted(Counter(intervals).items())), samples=samples)


def capture(label, out, baseline, expected, ram):
    if baseline:
        write('MOD_FPS_MODE_RUN', expected)
    time.sleep(5)
    state = read('MOD_CPU_SPINS', 'MOD_FPS_MODE_RUN', 'MOD_COLD_CACHE_TYPE', 'CURRENT_SCREEN', 'GAME_STATE', 'IS_SCRIPT_PAUSED', 'TAMER_STATE')
    assert state['MOD_FPS_MODE_RUN'] == expected, state
    if state['GAME_STATE']==0:
        assert state['IS_SCRIPT_PAUSED']==1 and state['TAMER_STATE']==0, state
    assert (state['MOD_COLD_CACHE_TYPE'] == 0xffffffff) == (ram == 2), state
    result = dict(label=label, ram_mb=ram, state=state, free_running=ds.perf(expected,10), pacing=pacing())
    assert all(row['MOD_FPS_MODE_RUN'] == expected for row in result['pacing']['samples']), result['pacing']
    subprocess.run(['xdotool','mousemove','1000','700'],env=ds.ENV,check=True)
    ds.main(['shot',str(out/(label+'.png'))])
    (out/(label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='pacing'}),flush=True)
    return result


def title_ready():
    for _ in range(100):
        state=read('CURRENT_MENU','MAIN_MENU_TICKS')
        if state['CURRENT_MENU']==0 and state['MAIN_MENU_TICKS']>3:
            return
        press('START',12)
        time.sleep(.25)
    raise RuntimeError('title menu did not open')


def apply_language(build, number, tag):
    data=(build/'lang'/('LANG'+tag+'.BIN')).read_bytes()
    assert data[:4]==b'DWLP'
    count=struct.unpack_from('<I',data,4)[0];offset=8
    g=BatchGDB()
    try:
        for _ in range(count):
            address,size=struct.unpack_from('<II',data,offset);offset+=8
            g.write(address,data[offset:offset+size]);offset+=(size+3)&~3
        g.write(ds.sym('MOD_LANG'),struct.pack('<i',number))
        language=['en','es','pt-br','fr','de','it','ja','ca'][number]
        g.write(elf_symbols(build/'exe/SLUS_010.32.elf')['menu_START'][0],
                (build/('exe-'+language)/'MENU_REL.BIN').read_bytes())
    finally:
        g.close()


def capture_options(build,out):
    rows=[]
    for number,(language,tag) in enumerate(zip(
            ['en','es','pt-br','fr','de','it','ja','ca'],
            ['EN','ES','PT','FR','DE','IT','JA','CA'])):
        apply_language(build,number,tag)
        symbols=elf_symbols(build/'exe/SLUS_010.32.elf')
        for font,value in [('NEW',0),('CLASSIC',2),('ORIGINAL',1)]:
            # Seed the font and reset its glyph ring exactly as modSetFont does.
            # Title captures do not need the setter's script-page reload.
            g=BatchGDB()
            try:
                g.write(symbols['MOD_FONT'][0],bytes([value]))
                g.write(symbols['GLYPH_DRAWING_AREA_INDEX'][0],struct.pack('<i',0))
                g.write(symbols['GLYPH_CARRY_Y'][0],struct.pack('<h',-1))
                if 'KERN_PREV_Y' in symbols:
                    g.write(symbols['KERN_PREV_Y'][0],struct.pack('<h',-1))
            finally:
                g.close()
            write('TARGET_MENU',0)
            wait_for(lambda: read('CURRENT_MENU')['CURRENT_MENU']==0)
            write('TARGET_MENU',4)
            wait_for(lambda: read('CURRENT_MENU')['CURRENT_MENU']==4)
            wait_for(lambda: read('MAIN_MENU_TICKS')['MAIN_MENU_TICKS']>3)
            time.sleep(.5)
            assert read('MOD_FONT')['MOD_FONT']==value
            filename=language+'-'+font+'.png'
            subprocess.run(['xdotool','mousemove','1000','700'],env=ds.ENV,check=True)
            ds.main(['shot',str(out/filename)])
            rows.append(dict(language=language,font=font,file=filename,
                             state=read('CURRENT_MENU','MOD_LANG','MOD_FPS_MODE_RUN','MOD_FONT')))
            print('OPTIONS',language,font,flush=True)
    (out/'options.json').write_text(json.dumps(rows,indent=2)+'\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('disc', type=Path)
    p.add_argument('--card', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--oc', type=int, choices=(100,250), required=True)
    p.add_argument('--ram', type=int, choices=(2,8), required=True)
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--runtime', action='store_true')
    p.add_argument('--options-only', action='store_true')
    a = p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(a.card, Path(ds.BIN)/'memcards/fps-auto.mcd')
    ds.setini('MemoryCards','Card1Path','fps-auto.mcd')
    ds.setini('Console','Enable8MBRAM','true' if a.ram==8 else 'false')
    ds.setini('Hotkeys','ToggleOverclocking','Keyboard/O')
    ds.setini('Hotkeys','FrameStep','Keyboard/F12')
    for name in ('Error','Warning','Info','Quick'):
        ds.setini('Display','OSD'+name+'Duration','0.1')
    ds.setini('Display','AnimateOSDMessages','false')
    results=[]
    try:
        ds.main(['start',str(a.disc),'--oc',str(a.oc)])
        wait_for(lambda: read('MOD_CPU_SPINS')['MOD_CPU_SPINS'] > 0)
        time.sleep(3)
        boot=read('MOD_CPU_SPINS','MOD_FPS_MODE_RUN')
        (a.out/'boot.json').write_text(json.dumps(boot,indent=2)+'\n')
        if not a.baseline:
            assert boot['MOD_FPS_MODE_RUN'] == (2 if a.oc==250 else 0), boot
        if a.options_only:
            title_ready()
            capture_options(a.disc.with_suffix(''),a.out)
            return
        continue_game()
        time.sleep(5)
        expected=2 if a.oc==250 else 0
        write('MOD_FONT',0,1)
        write('MOD_BATTLE_FAST',0,1)
        warp(218)
        results.append(capture('light',a.out,a.baseline,expected,a.ram))
        if a.runtime:
            if a.oc!=250: raise RuntimeError('runtime toggle run must start at 250%')
            for label,mode in [('runtime-100',0),('runtime-250',2)]:
                before=read('Vcount')['Vcount']
                key('o')
                try:
                    wait_for(lambda: read('MOD_FPS_MODE_RUN')['MOD_FPS_MODE_RUN']==mode,120)
                except RuntimeError:
                    print('transition timeout',read('MOD_CPU_SPINS','MOD_FPS_MODE_RUN','Vcount'),flush=True)
                    raise
                elapsed=(read('Vcount')['Vcount']-before)&0xffffffff
                assert elapsed<=360, (label,elapsed)
                result=capture(label,a.out,False,mode,a.ram)
                result['transition_refreshes']=elapsed
                (a.out/(label+'.json')).write_text(json.dumps(result,indent=2)+'\n')
                results.append(result)
        warp(69)
        results.append(capture('heavy',a.out,a.baseline,expected,a.ram))
        warp(0)
        ds.main(['approach','0','150']);time.sleep(1)
        for _ in range(12):
            press('CROSS',8);time.sleep(1)
            if read('GAME_STATE')['GAME_STATE'] & 255 == 1: break
        wait_for(lambda: read('GAME_STATE')['GAME_STATE'] & 255 == 1)
        time.sleep(5)
        results.append(capture('battle',a.out,a.baseline,expected,a.ram))
        (a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    finally:
        ds.main(['stop'])


if __name__ == '__main__':
    main()
